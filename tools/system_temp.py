import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    import psutil
except ImportError:
    install("psutil")
    import psutil

try:
    import GPUtil
except ImportError:
    install("GPUtil")
    import GPUtil

def get_system_temps():
    cpu_temp = psutil.sensors_temperatures().get('coretemp', [])
    if cpu_temp:
        cpu_temp = cpu_temp[0].current
    else:
        cpu_temp = None

    gpus = GPUtil.getGPUs()
    if gpus:
        gpu_temp = gpus[0].temperature
    else:
        gpu_temp = None

    return f"CPU: {cpu_temp}C, GPU: {gpu_temp}C"