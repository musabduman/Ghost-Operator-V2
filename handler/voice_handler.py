"""
handlers/voice_handler.py — Mikrofon dinleme ve STT işlemleri.
"""
import threading
import sounddevice as sd
import scipy.io.wavfile as wav
import speech_recognition as sr

class VoiceHandler:

    SAMPLE_RATE = 16000
    DURATION    = 5  # saniye

    def __init__(self, app):
        self.app = app

    def start_listening(self):
        """Mikrofonu arka planda dinlemeye başlar."""
        self.app.entry.configure(placeholder_text="🎙️ Ghost Dinliyor... (Konuş)")
        self.app.update()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        audio_path = "komut.wav"
        try:
            data = sd.rec(
                int(self.DURATION * self.SAMPLE_RATE),
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype="int16",
            )
            sd.wait()
            wav.write(audio_path, self.SAMPLE_RATE, data)

            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as src:
                audio = recognizer.record(src)
            text = recognizer.recognize_google(audio, language="tr-TR")

            self.app.log(f"\nSen (Sesli): {text}")
            self.app.after(0, lambda: self.app.entry.delete(0, "end"))
            self.app.after(0, lambda: self.app.entry.insert(0, text))
            self.app.after(100, lambda: self.app.command_handler.handle(None))

        except sr.UnknownValueError:
            self.app.log("SİSTEM: Ses anlaşılamadı, biraz daha yaklaş Patron.", "red")
        except sr.RequestError:
            self.app.log("SİSTEM HATA: STT servisine ulaşılamıyor.", "red")
        except Exception as e:
            self.app.log(f"SİSTEM HATA (Ses): {e}", "red")
        finally:
            self.app.after(0, lambda: self.app.entry.configure(
                placeholder_text="Patrondan komut bekliyor..."
            ))