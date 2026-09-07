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

def get_cpu_temp_ps():
    # Try PowerShell command for MSAcpi_ThermalZoneTemperature
    try:
        cmd = ['powershell', '-Command', "Get-WmiObject -Namespace root\wmi -Class MSAcpi_ThermalZoneTemperature | Select-Object -ExpandProperty CurrentTemperature"]
        out = subprocess.check_output(cmd, universal_newlines=True).strip()
        if out and out.isdigit():
            temp_kelvin = int(out) / 10.0
            return round(temp_kelvin - 273.15, 1)
    except Exception:
        pass
    # Try generic Win32_TemperatureProbe via PowerShell
    try:
        cmd = ['powershell', '-Command', "Get-WmiObject -Class Win32_TemperatureProbe | Select-Object -ExpandProperty CurrentTemperature"]
        out = subprocess.check_output(cmd, universal_newlines=True).strip()
        if out and out.isdigit():
            temp_kelvin = int(out) / 10.0
            return round(temp_kelvin - 273.15, 1)
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
    cpu_temp = get_cpu_temp_ps()
    if cpu_temp is None:
        cpu_str = 'Alınamadı'
    else:
        cpu_str = f"{cpu_temp}C"
    print(f"VRAM Kullanım: {used}/{total} MB ({usage:.1f}%), CPU Sıcaklığı: {cpu_str}")

if __name__ == '__main__':
    report()
