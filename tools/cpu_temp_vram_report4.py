import subprocess, sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def ensure_packages():
    try:
        import GPUtil
    except ImportError:
        install('GPUtil')
    try:
        import psutil
    except ImportError:
        install('psutil')

ensure_packages()

import GPUtil
import psutil

def get_cpu_temp():
    # Try psutil
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for entries in temps.values():
                if entries:
                    return round(entries[0].current, 1)
    except Exception:
        pass
    # Try WMIC MSAcpi_ThermalZoneTemperature
    try:
        out = subprocess.check_output(['wmic', 'path', 'MSAcpi_ThermalZoneTemperature', 'get', 'CurrentTemperature'], universal_newlines=True)
        for line in out.splitlines():
            line=line.strip()
            if line.isdigit():
                return round(int(line)/10.0 - 273.15, 1)
    except Exception:
        pass
    # Try WMIC Win32_TemperatureProbe
    try:
        out = subprocess.check_output(['wmic', 'path', 'Win32_TemperatureProbe', 'get', 'CurrentTemperature'], universal_newlines=True)
        for line in out.splitlines():
            line=line.strip()
            if line.isdigit():
                return round(int(line)/10.0 - 273.15, 1)
    except Exception:
        pass
    return None

def report():
    gpus = GPUtil.getGPUs()
    if not gpus:
        print('GPU bulunamadı.')
        return
    gpu = gpus[0]
    used = gpu.memoryUsed
    total = gpu.memoryTotal
    usage = (used/total)*100 if total else 0
    cpu_temp = get_cpu_temp()
    if cpu_temp is None:
        cpu_str = 'CPU sıcaklığı alınamadı'
    else:
        cpu_str = f"{cpu_temp}C"
    print(f"VRAM Kullanım: {used}/{total} MB ({usage:.1f}%), CPU Sıcaklığı: {cpu_str}")

if __name__ == '__main__':
    report()
