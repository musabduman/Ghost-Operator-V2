import subprocess, re

def get_vram_usage():
    try:
        # nvidia-smi komutunu çalıştır ve CSV formatında çıkış al
        result = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.total,memory.used', '--format=csv,noheader,nounits'], universal_newlines=True)
        # Çıktı: "4096, 1024" gibi
        total_str, used_str = result.strip().split(',')
        total = int(total_str.strip())
        used = int(used_str.strip())
        percent = (used / total) * 100 if total else 0
        print(f"VRAM Kullanımı: {used} MB / {total} MB ({percent:.2f}%)")
    except Exception as e:
        print(f"VRAM bilgisi alınamadı: {e}")

if __name__ == "__main__":
    get_vram_usage()
