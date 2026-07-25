import shutil, os

def gb(bytes_val):
    return round(bytes_val / (1024**3), 2)

# Get the system drive (assume C:)
usage = shutil.disk_usage('C:\\')
print(f"Toplam GB: {gb(usage.total)}")
print(f"Kullanılan GB: {gb(usage.used)}")
print(f"Boş GB: {gb(usage.free)}")
