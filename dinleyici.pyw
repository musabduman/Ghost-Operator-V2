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

son_tetiklenme=0

def ghost_uyandir():
    global son_tetiklenme
    su_an = time.time()
    
    # KALKAN 0: SOĞUMA SÜRESİ
    if su_an - son_tetiklenme < 5:
        return
        
    kilit_yolu = "ghost_mesgul.lock"
    
    # --- DURUM A: SİSTEM UYKUDAYSA (KİLİT YOKSA) ---
    if not os.path.exists(kilit_yolu):
        try:
            # ATOMİK KİLİT: 'x' modu dosyayı yaratır. Eğer dosya zaten varsa ANINDA hata verir (FileExistsError)
            # Bu sayede 3 dinleyici aynı anda buraya gelse bile, sadece ilk gelen kilidi koyar.
            with open(kilit_yolu, "x") as f:
                f.write("mesgul")
        except FileExistsError:
            # Demek ki başka bir dinleyici bizden 1 milisaniye önce kilidi koymuş. İşlemi iptal et!
            return
        
        print("\n[🔥] GHOST UYANDI! Arayüz tetikleniyor...")
        son_tetiklenme = su_an
        
        mevcut_dizin = os.path.dirname(os.path.abspath(__file__))
        ui_yolu = os.path.join(mevcut_dizin, "ui.py")
        
        # UI'yi başlat
        subprocess.Popen([sys.executable, ui_yolu])
        
        print("Nöbetçi 3 saniye sağır moduna geçiyor...")
        time.sleep(3) 
        with q.mutex:
            q.queue.clear()
        return

    # --- DURUM B: SİSTEM ZATEN AÇIKSA (KİLİT VARSA) ---
    else:
        print("\n[!] Ghost zaten aktif. Arayüze UYANMA SİNYALİ gönderiliyor...")
        son_tetiklenme = su_an 
        
        with open("uyandir_sinyali.txt", "w") as f:
            f.write("uyan")

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load("sistem_baslangic.mp3") 
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            pass
            
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