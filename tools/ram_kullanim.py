import subprocess
import sys

def install_psutil():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])

try:
    import psutil
except ImportError:
    install_psutil()
    import psutil

def get_ram_usage():
    memory_info = psutil.virtual_memory()
    total_ram = memory_info.total
    used_ram = memory_info.used
    usage_percent = (used_ram / total_ram) * 100
    print(f"Kullanılan RAM: {usage_percent:.2f}%")

if __name__ == "__main__":
    get_ram_usage()