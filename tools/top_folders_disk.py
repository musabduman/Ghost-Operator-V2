import os
import json

def main():
    base_path = "C:\\"
    folder_sizes = []
    
    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path):
            total_size = 0
            try:
                for entry in os.listdir(item_path):
                    entry_path = os.path.join(item_path, entry)
                    if os.path.isfile(entry_path):
                        try:
                            total_size += os.path.getsize(entry_path)
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass
            size_gb = total_size / (1024 ** 3)
            folder_sizes.append({
                "klasor": item,
                "boyut_gb": round(size_gb, 2)
            })
    
    folder_sizes.sort(key=lambda x: x["boyut_gb"], reverse=True)
    top_5 = folder_sizes[:5]
    print(json.dumps(top_5, ensure_ascii=False))

if __name__ == "__main__":
    main()