import webview
import time
import socket
from urllib.request import urlopen
from urllib.error import URLError

def wait_for_server(url, timeout=15):
    """Wait for the Vite dev server to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            urlopen(url)
            return True
        except URLError:
            time.sleep(0.5)
    return False

if __name__ == '__main__':
    url = "http://localhost:5173"
    print(f"Ghost UI'nin hazır olması bekleniyor: {url} ...")
    
    # Sunucunun ayağa kalkmasını bekle
    is_ready = wait_for_server(url)
    
    if is_ready:
        print("Ghost UI hazır! Uygulama penceresi açılıyor...")
        # Pencereyi oluştur ve yerel sunucu adresini ver
        webview.create_window('Ghost Operator', url, width=1280, height=800, background_color='#111111')
        webview.start()
    else:
        print("HATA: Frontend sunucusu başlatılamadı veya bulunamadı.")
        print("Lütfen 'frontend' dizininde 'npm run dev' komutunun çalıştığından emin olun.")
