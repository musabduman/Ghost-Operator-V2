import queue
import sys
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import json
import subprocess
import os
import time

# İndirdiğin model klasörünün yolu
MODEL_YOLU = "model"

if not os.path.exists(MODEL_YOLU):
    print("HATA: 'model' klasörü bulunamadı! Lütfen Vosk modelini indirip buraya çıkartın.")
    sys.exit(1)

model = Model(MODEL_YOLU)
q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def ghost_uyandir():
    print("\n[!] GHOST UYANIYOR! Arayüz tetikleniyor...")
    mevcut_dizin = os.path.dirname(os.path.abspath(__file__))
    ui_yolu = os.path.join(mevcut_dizin, "ui.py")
    
    # ui.py'yi çalıştır
    subprocess.Popen([sys.executable, ui_yolu])
    
    # Uyandıktan sonra üst üste 10 kere açılmaması için nöbetçiyi biraz uyutuyoruz
    print("Nöbetçi 10 saniye dinleniyor...")
    time.sleep(10) 

def ana_dongu():
    print(">>> Ghost Nöbetçisi Devrede... (VRAM: 0, İnternet: Yok)")
    print(">>> Dinleniyor...")
    
    with sd.RawInputStream(samplerate=16000, blocksize=8000, device=None, dtype='int16',
                            channels=1, callback=callback):
        rec = KaldiRecognizer(model, 16000)
        
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                sonuc = json.loads(rec.Result())
                metin = sonuc.get("text", "")
                
                if metin:
                    print(f"Duyulan: {metin}") # Test için ne duyduğunu ekrana yazdırıyoruz
                    
                    # MÜHENDİSLİK HİLESİ: 
                    # Türkçe model İngilizce "Ghost" kelimesini tam anlamayabilir. 
                    # Okunuşu olan "gost", "dost" veya "boş" gibi kelimeleri duyarsa da tetiklensin.
                    tetikleyiciler = ["ghost", "gost", "dost", "bos", "boss"]
                    
                    if any(kelime in metin for kelime in tetikleyiciler):
                        ghost_uyandir()

if __name__ == "__main__":
    ana_dongu()