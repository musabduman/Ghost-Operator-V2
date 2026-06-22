"""
handlers/voice_handler.py — Vosk ile offline VAD tabanlı ses tanıma.
Cümle bitince otomatik durur, süre sınırı yok.
"""
import threading
import queue
import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer

MODEL_YOLU = "model"  # wake-word'deki ile aynı klasör


class VoiceHandler:

    SAMPLE_RATE = 16000
    BLOCK_SIZE  = 8000

    def __init__(self, app):
        self.app   = app
        self._model = None  # lazy load

    def _get_model(self):
        """Modeli ilk kullanımda yükle."""
        if self._model is None:
            try:
                self._model = Model(MODEL_YOLU)
            except Exception as e:
                self.app.log(f"SİSTEM HATA (Vosk model): {e}", "red")
                return None
        return self._model

    def start_listening(self):
        """Mikrofonu arka planda dinlemeye başlar."""
        self.app.entry.configure(placeholder_text="🎙️ Ghost Dinliyor... (Konuş)")
        self.app.update()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        model = self._get_model()
        if model is None:
            self._reset_placeholder()
            return

        q = queue.Queue()
        rec = KaldiRecognizer(model, self.SAMPLE_RATE)
        text = ""

        def callback(indata, frames, time, status):
            q.put(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=self.SAMPLE_RATE,
                blocksize=self.BLOCK_SIZE,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                self.app.log("🎙️ Dinleniyor...", "green")

                while True:
                    data = q.get()

                    if rec.AcceptWaveform(data):
                        # Final sonuç — cümle bitti
                        result = json.loads(rec.Result())
                        text = result.get("text", "").strip()
                        if text:
                            break  # cümle alındı, döngüden çık
                    else:
                        # Partial sonuç — kullanıcı hâlâ konuşuyor
                        partial = json.loads(rec.PartialResult())
                        partial_text = partial.get("partial", "").strip()
                        if partial_text:
                            # Entry'de canlı göster
                            self.app.after(0, lambda t=partial_text: (
                                self.app.entry.delete(0, "end"),
                                self.app.entry.insert(0, t)
                            ))

            if text:
                self.app.log(f"Sen (Sesli): {text}")
                self.app.after(0, lambda: self.app.entry.delete(0, "end"))
                self.app.after(0, lambda: self.app.entry.insert(0, text))
                self.app.after(100, lambda: self.app.command_handler.handle(None))
            else:
                self.app.log("SİSTEM: Ses anlaşılamadı, biraz daha yaklaş Patron.", "red")

        except Exception as e:
            self.app.log(f"SİSTEM HATA (Ses): {e}", "red")
        finally:
            self._reset_placeholder()

    def _reset_placeholder(self):
        self.app.after(0, lambda: self.app.entry.configure(
            placeholder_text="Patrondan komut bekliyor..."
        ))