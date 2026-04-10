import queue
import sys
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import json
import subprocess
import os
import time
import pygame

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

ui_process = None 

def ghost_uyandir():
    global ui_process # Dışarıdaki değişkeni kullanacağımızı belirtiyoruz
    # KALKAN 1: Eğer arayüz zaten açıksa (poll() None dönüyorsa çalışıyordur), yenisini açma!
    print("\n Ghost zaten aktif. Arayüze Uyanma Sinyali göderiliyor...")
    if ui_process is not None and ui_process.poll() is None:
        # Uyku halindeki sarkmaları engellemek için sadece kuyruğu boşaltıp geri dönüyoruz
        with open("uyandir_sinyal.txt","w")as f:
            f.write("uyan")
            
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load("sistem_baslangic.mp3")
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        
        except Exception as e:
            print(f"Ses çalma hatsı: {e}")
        
        with q.mutex:
            q.queue.clear()
        return

    print("\n[🔥] GHOST UYANDI! Arayüz tetikleniyor...")
    mevcut_dizin = os.path.dirname(os.path.abspath(__file__))
    ui_yolu = os.path.join(mevcut_dizin, "ui.py")
    
    # ui.py'yi çalıştır ve süreci ui_process değişkenine kaydet
    ui_process = subprocess.Popen([sys.executable, ui_yolu])
    
    # 10 saniye çok uzun, 3 saniye sağır modu yeterlidir.   
    print("Nöbetçi 3 saniye sağır moduna geçiyor...")
    time.sleep(3) 
    
    # KALKAN 2: Sağır modundayken kuyrukta biriken tüm sesleri sil (Yankı ve tekrarı önler)
    with q.mutex:
        q.queue.clear()
        
    print("Nöbetçi tekrar dinliyor...")

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