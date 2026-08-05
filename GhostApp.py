import multiprocessing
import threading
import sys
import os

# Pyinstaller modülü import sorunlarını önlemek için:
import local_bridge.main
import main

def start_bridge():
    import uvicorn
    # Log_level="critical" konsol kirliliğini önler
    uvicorn.run(local_bridge.main.app, host="0.0.0.0", port=8000, log_level="critical")

if __name__ == '__main__':
    # Windows'ta multiprocessing ve PyInstaller için gerekli
    multiprocessing.freeze_support()
    
    # Local Bridge'i (Uvicorn) arka plan processi olarak başlat
    bridge_proc = multiprocessing.Process(target=start_bridge, daemon=True)
    bridge_proc.start()
    
    # Ana arayüzü başlat
    app = main.GhostOperatorUI()
    app.mainloop()
