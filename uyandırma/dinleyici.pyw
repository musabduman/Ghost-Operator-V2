import queue
import sys
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import json
import subprocess
import os
import time
import pygame

# --- DİNAMİK YOL (PATH) MANTIĞI ---
# 1. Bu dosyanın çalıştığı alt klasörü bul (uyandırma klasörü)
dinleyici_klasoru = os.path.dirname(os.path.abspath(__file__))

# 2. Bir üst klasöre çık (Asıl projenin olduğu ana dizin)
ana_dizin = os.path.dirname(dinleyici_klasoru)

# 3. Tüm dosya yollarını ana dizine göre sabitle
MODEL_YOLU = os.path.join(ana_dizin, "model")
kilit_yolu = os.path.join(ana_dizin, "ghost_mesgul.lock")
sinyal_yolu = os.path.join(ana_dizin, "uyandir_sinyali.txt")
ses_yolu = os.path.join(ana_dizin, "sistem_baslangic.mp3")
ui_yolu = os.path.join(ana_dizin, "main.py")
# -----------------------------------

if not os.path.exists(MODEL_YOLU):
    print(f"HATA: Model klasörü bulunamadı! Aranan yer: {MODEL_YOLU}")
    sys.exit(1)

model = Model(MODEL_YOLU)
q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

son_tetiklenme = 0

def ghost_uyandir():
    global son_tetiklenme
    su_an = time.time()
    
    # KALKAN 0: SOĞUMA SÜRESİ
    if su_an - son_tetiklenme < 5:
        return
        
    # --- DURUM A: SİSTEM UYKUDAYSA (KİLİT YOKSA) ---
    if not os.path.exists(kilit_yolu):
        try:
            # ATOMİK KİLİT
            with open(kilit_yolu, "x") as f:
                f.write("mesgul")
        except FileExistsError:
            return
        
        print("\n[🔥] GHOST UYANDI! Arayüz tetikleniyor...")
        son_tetiklenme = su_an
        
        # UI'yi başlat (Artık doğru klasördeki main.py'yi bulacak)
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
        
        # 1. Önce sesi çal (Mikrofon açılmadan önce)
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(ses_yolu) 
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            pass
            
        with q.mutex:
            q.queue.clear()
            
        # 2. Ses bittikten sonra sinyal dosyasını ana dizine gönder
        with open(sinyal_yolu, "w") as f:
            f.write("uyan")
                    
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
                    print(f"Duyulan: {metin}")
                    tetikleyiciler = ["ghost", "gost", "dost", "bos", "boss"]
                    
                    if any(kelime in metin for kelime in tetikleyiciler):
                        ghost_uyandir()
    
if __name__ == "__main__":
    ana_dongu()