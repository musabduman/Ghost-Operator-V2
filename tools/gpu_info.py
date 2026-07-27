import subprocess, csv, os

def get_gpu_info():
    try:
        # Run WMIC command
        result = subprocess.check_output(['wmic', 'path', 'win32_VideoController', 'get', 'Name,AdapterRAM,DriverVersion', '/format:csv'], shell=True, universal_newlines=True)
    except Exception as e:
        print(f'Error: {e}')
        return
    # Split lines and ignore empty ones
    lines = [line for line in result.splitlines() if line.strip()]
    if len(lines) < 2:
        return
    # The first line is header, second line contains data
    reader = csv.DictReader(lines)
    for row in reader:
        name = row.get('Name') or row.get('Name')
        ram_bytes = row.get('AdapterRAM')
        driver = row.get('DriverVersion')
        # Convert RAM to MB
        try:
            ram_mb = round(int(ram_bytes) / (1024**2)) if ram_bytes and ram_bytes.isdigit() else 'Unknown'
        except:
            ram_mb = 'Unknown'
        print(f'GPU Name: {name}')
        print(f'VRAM (MB): {ram_mb}')
        print(f'Driver Version: {driver}')
        break

if __name__ == "__main__":
    get_gpu_info()
