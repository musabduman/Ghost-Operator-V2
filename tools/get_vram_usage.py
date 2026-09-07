import subprocess
import re

def get_gpu_vram_and_temps():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        if not output:
            print("Error: No NVIDIA GPU detected or nvidia-smi returned no output.")
            return
        
        match = re.match(r'(\d+),\s*(\d+)', output)
        if match:
            used_mb = int(match.group(1))
            total_mb = int(match.group(2))
            percent = (used_mb / total_mb) * 100 if total_mb > 0 else 0
            print(f"VRAM Used: {used_mb} MB / {total_mb} MB ({percent:.1f}%)")
        else:
            print("Error: Unable to parse nvidia-smi output.")
    except subprocess.CalledProcessError:
        print("Error: nvidia-smi command failed. Ensure NVIDIA drivers are installed.")
    except FileNotFoundError:
        print("Error: nvidia-smi not found. This system may not have an NVIDIA GPU.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_gpu_vram_and_temps()