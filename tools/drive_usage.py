import os, json, shutil

def get_drives():
    drives = []
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        path = f'{letter}:\\'
        if os.path.isdir(path):
            drives.append(path)
    return drives

def drive_usage():
    drives = get_drives()
    usage_list = []
    for d in drives:
        total, used, free = shutil.disk_usage(d)
        usage_list.append({
            'drive': d,
            'used_gb': round(used / (1024**3), 2),
            'total_gb': round(total / (1024**3), 2)
        })
    if not usage_list:
        print(json.dumps({"drives":0,"largest":None}, ensure_ascii=False))
        return
    largest = max(usage_list, key=lambda x: x['used_gb'])
    result = {
        "drives": len(usage_list),
        "largest": {
            "drive": largest['drive'],
            "used_gb": largest['used_gb']
        }
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    drive_usage()
