import subprocess

def get_gpu_report():
    try:
        # Query total, used memory and temperature
        result = subprocess.check_output(
            ['nvidia-smi',
             '--query-gpu=memory.total,memory.used,temperature.gpu',
             '--format=csv,noheader,nounits'],
            universal_newlines=True
        )
        # Expected format: "6141, 5822, 68"
        total_str, used_str, temp_str = [x.strip() for x in result.strip().split(',')]
        total = int(total_str)
        used = int(used_str)
        temp = int(temp_str)
        percent = (used / total) * 100 if total else 0
        print(f"VRAM Kullanımı: {used} MB / {total} MB ({percent:.2f}%)")
        print(f"GPU Sıcaklığı: {temp} °C")
    except Exception as e:
        print(f"GPU raporu alınamadı: {e}")

if __name__ == "__main__":
    get_gpu_report()
