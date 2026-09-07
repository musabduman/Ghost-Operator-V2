import subprocess
import time
import os
import signal
import sys
import webview
from urllib.request import urlopen
from urllib.error import URLError

def wait_for_server(url, timeout=30):
    print(f"[{url}] Sunucusunun hazır olması bekleniyor...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            urlopen(url)
            print(f"[{url}] Sunucu hazır!")
            return True
        except URLError:
            time.sleep(0.5)
    return False

def main():
    print("Ghost Operator başlatılıyor...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. FastAPI Backend'i başlat
    server_process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=base_dir,
        stdout=subprocess.DEVNULL, # Eğer terminalde görmek istersen None yapabilirsin
        stderr=None
    )
    print("Backend sunucusu başlatıldı (Port 8000).")
    
    # 2. Vite Frontend'i başlat
    frontend_dir = os.path.join(base_dir, "frontend")
    vite_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=None
    )
    print("Frontend dev sunucusu başlatıldı (Port 5173).")
    
    frontend_url = "http://localhost:5173"
    backend_url = "http://127.0.0.1:8000/openapi.json"
    
    try:
        # Sunucuların ayağa kalkmasını bekle
        backend_ready = wait_for_server(backend_url)
        frontend_ready = wait_for_server(frontend_url)
        
        if backend_ready and frontend_ready:
            print("Ghost arayüzü yükleniyor...")
            # Masaüstü penceresini aç
            webview.create_window('Ghost Operator', frontend_url, width=1280, height=800, background_color='#111111')
            webview.start()
        else:
            print("HATA: Sunuculardan biri zaman aşımına uğradı.")
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu.")
    finally:
        print("Kapatılıyor... Alt işlemler sonlandırılıyor.")
        # Alt süreçleri temizle
        try:
            server_process.terminate()
            vite_process.terminate()
            # Windows için force kill gerekebilir
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(server_process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(vite_process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            pass
        print("Ghost Operator tamamen kapatıldı.")

if __name__ == '__main__':
    main()
