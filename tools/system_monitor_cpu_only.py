import subprocess, sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def ensure_packages():
    try:
        import GPUtil
    except ImportError:
        install('GPUtil')

ensure_packages()

import GPUtil

def get_cpu_temp_wmic():
    try:
        # Using wmic to query temperature in tenths of Kelvin
        output = subprocess.check_output(['wmic', 'path', 'Win32_TemperatureProbe', 'get', 'CurrentTemperature'], universal_newlines=True)
        lines = output.strip().splitlines()
        for line in lines:
            line = line.strip()
            if line.isdigit():
                temp_kelvin = int(line) / 10.0
                temp_celsius = temp_kelvin - 273.15
                return round(temp_celsius, 1)
    except Exception:
        pass
    # Alternative query via MSAcpi_ThermalZoneTemperature
    try:
        output = subprocess.check_output(['wmic', 'path', 'MSAcpi_ThermalZoneTemperature', 'get', 'CurrentTemperature'], universal_newlines=True)
        lines = output.strip().splitlines()
        for line in lines:
            line = line.strip()
            if line.isdigit():
                temp_kelvin = int(line) / 10.0
                temp_celsius = temp_kelvin - 273.15
                return round(temp_celsius, 1)
    except Exception:
        pass
    return None

def report():
    gpus = GPUtil.getGPUs()
    if not gpus:
        print('GPU bulunamadı.')
        return
    gpu = gpus[0]
    used_mb = gpu.memoryUsed
    total_mb = gpu.memoryTotal
    usage_percent = (used_mb / total_mb) * 100 if total_mb else 0
    cpu_temp = get_cpu_temp_wmic()
    cpu_temp_str = f"{cpu_temp}" if cpu_temp is not None else "Bilinmiyor"
    result = f"VRAM Kullanım: {used_mb}/{total_mb} MB ({usage_percent:.1f}%), CPU Sıcaklığı: {cpu_temp_str}C"
    print(result)
    return result

if __name__ == "__main__":
    report()
