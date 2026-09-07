import subprocess, sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def ensure_packages():
    try:
        import GPUtil
    except ImportError:
        install('GPUtil')
    try:
        import wmi
    except ImportError:
        install('wmi')
    try:
        import psutil
    except ImportError:
        install('psutil')

ensure_packages()

import GPUtil
import wmi
import psutil

def get_cpu_temp_wmi():
    # Try WMI class MSAcpi_ThermalZoneTemperature
    try:
        w = wmi.WMI(namespace="root\wmi")
        temps = w.MSAcpi_ThermalZoneTemperature()
        if temps:
            # Value is in tenths of Kelvin
            temp_kelvin = temps[0].CurrentTemperature / 10.0
            temp_celsius = temp_kelvin - 273.15
            return round(temp_celsius, 1)
    except Exception:
        pass
    # Fallback to wmic command
    try:
        output = subprocess.check_output(['wmic', 'path', 'Win32_TemperatureProbe', 'get', 'CurrentTemperature'], universal_newlines=True)
        lines = output.strip().splitlines()
        for line in lines:
            line = line.strip()
            if line.isdigit():
                # Value is in tenths of Kelvin
                temp_kelvin = int(line) / 10.0
                temp_celsius = temp_kelvin - 273.15
                return round(temp_celsius, 1)
    except Exception:
        pass
    # psutil fallback (may not work on Windows)
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for entries in temps.values():
                if entries:
                    return round(entries[0].current, 1)
    except Exception:
        pass
    return None

def get_gpu_vram_and_cpu_temp():
    gpus = GPUtil.getGPUs()
    if not gpus:
        return "GPU bulunamadı."
    gpu = gpus[0]
    total_mb = gpu.memoryTotal
    used_mb = gpu.memoryUsed
    usage_percent = (used_mb / total_mb) * 100 if total_mb else 0
    cpu_temp = get_cpu_temp_wmi()
    cpu_temp_str = f"{cpu_temp}" if cpu_temp is not None else "Bilinmiyor"
    result = f"VRAM Kullanım: {used_mb}/{total_mb} MB ({usage_percent:.1f}%), CPU Sıcaklığı: {cpu_temp_str}C"
    print(result)
    return result

if __name__ == "__main__":
    get_gpu_vram_and_cpu_temp()
