# @ghost_tool
import subprocess

def main():
    try:
        out = subprocess.check_output([
            'nvidia-smi',
            '--query-gpu=memory.total,memory.used,temperature.gpu',
            '--format=csv,noheader,nounits'],
            universal_newlines=True)
        total_str, used_str, temp_str = [s.strip() for s in out.strip().split(',')]
        total = int(total_str)
        used = int(used_str)
        temp = int(temp_str)
        percent = round(used / total * 100, 2) if total else 0
        print(f'VRAM Used: {used} MB / {total} MB ({percent}%) | Temp: {temp}°C')
    except FileNotFoundError:
        print('Error: nvidia-smi not found. Cannot retrieve temperature.')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    main()