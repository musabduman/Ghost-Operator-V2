import os
import json
from pathlib import Path

def get_folder_size(folder_path):
    total_size = 0
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            if file_count >= 100000:
                return None
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
                file_count += 1
            except (OSError, PermissionError):
                pass
    return total_size

def main():
    base_path = Path("C:/")
    folder_sizes = []
    
    for item in base_path.iterdir():
        if item.is_dir():
            folder_name = item.name
            try:
                size_bytes = get_folder_size(str(item))
                if size_bytes is None:
                    folder_sizes.append({"folder": folder_name, "size_gb": 0, "note": "limit_exceeded"})
                else:
                    size_gb = size_bytes / (1024 ** 3)
                    folder_sizes.append({"folder": folder_name, "size_gb": round(size_gb, 2)})
            except (OSError, PermissionError):
                pass
    
    folder_sizes.sort(key=lambda x: x["size_gb"], reverse=True)
    top_5 = folder_sizes[:5]
    print(json.dumps(top_5, ensure_ascii=False))

if __name__ == "__main__":
    main()