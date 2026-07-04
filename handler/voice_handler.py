"""
handlers/voice_handler.py — Vosk ile offline VAD tabanlı ses tanıma.
Cümle bitince otomatik durur, süre sınırı yok.
"""
import threading
import queue
import json
import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from ui.compact_ui import set_voice_level

MODEL_YOLU = "model"  


class VoiceHandler:

    SAMPLE_RATE = 16000
    BLOCK_SIZE  = 8000

    def __init__(self, app):
        self.app   = app
        self._model = None  
        self.is_listening = False  # ---> YENİ: Çifte mikrofon açılışını engelleyen güvenlik kilidi

    def _get_model(self):
        if self._model is None:
            try:
                self._model = Model(MODEL_YOLU)
            except Exception as e:
                self.app.log(f"SİSTEM HATA (Vosk model): {e}", "red")
                return None
        return self._model

    def start_listening(self):
        """Mikrofonu arka planda dinlemeye başlar."""
        # Eğer asistan zaten dinliyorsa, donanımın çökmemesi için işlemi iptal et
        if self.is_listening:
            return 
            
        self.is_listening = True
        self.app.voice_mode = True
        
        if hasattr(self.app, 'entry') and self.app.entry.winfo_exists():
            self.app.entry.configure(placeholder_text="🎙️ Ghost Dinliyor... (Konuş)")
            
        self.app.update()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        model = self._get_model()
        if model is None:
            self._reset_placeholder()
            self.is_listening = False
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

                    # KENDİ SESİNİ DUYMAMASI İÇİN KULAKLARI KAPAT
                    if getattr(self.app, "is_speaking", False):
                        continue

                    # ORB TİTREŞİM (SES SEVİYESİ) KONTROLÜ
                    if not getattr(self.app, "_expanded", True):
                        audio_np = np.frombuffer(data, dtype=np.int16)
                        if len(audio_np) > 0:
                            rms = np.sqrt(np.mean(np.square(audio_np.astype(np.float32))))
                            rms_normalized = min(1.0, (rms / 32768.0) * 5.0)
                            set_voice_level(self.app, rms_normalized)

                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        text = result.get("text", "").strip()
                        if text:
                            break  
                    else:
                        partial = json.loads(rec.PartialResult())
                        partial_text = partial.get("partial", "").strip()
                        if partial_text:
                            def update_partial(t=partial_text):
                                if hasattr(self.app, 'entry') and self.app.entry.winfo_exists():
                                    self.app.entry.delete(0, "end")
                                    self.app.entry.insert(0, t)
                            self.app.after(0, update_partial)

            if not getattr(self.app, "_expanded", True):
                set_voice_level(self.app, 0.0)

            if text:
                self.app.log(f"Sen (Sesli): {text}")
                
                def update_final(t=text):
                    if hasattr(self.app, 'entry') and self.app.entry.winfo_exists():
                        self.app.entry.delete(0, "end")
                        self.app.entry.insert(0, t)
                self.app.after(0, update_final)
                
                # Sesi aldı, beyne gönderiyor
                self.app.after(100, lambda t=text: self.app.command_handler.handle(event=None, voice_text=t))
            else:
                self.app.log("SİSTEM: Ses anlaşılamadı, biraz daha yaklaş Patron.", "red")
                
                # ---> YENİ EKLENEN: SAĞIRLIK ÇÖZÜMÜ <---
                # Eğer ses boğuk geldiyse ve asistan komutu anlayamadıysa, 
                # kompakt modda olduğumuz sürece pes etmeden dinlemeyi yeniden başlatır.
                if not getattr(self.app, "_expanded", True):
                    self.app.after(500, self.start_listening)

        except Exception as e:
            self.app.log(f"SİSTEM HATA (Ses): {e}", "red")
        finally:
            self.is_listening = False  # Döngü tamamen bittiğinde kilidi kaldır
            self._reset_placeholder()

    def _reset_placeholder(self):
        def reset_ui():
            if hasattr(self.app, 'entry') and self.app.entry.winfo_exists():
                self.app.entry.configure(placeholder_text="Patrondan komut bekliyor...")
        self.app.after(0, reset_ui)