import os
import sqlite3
import re
from core.config import DB_DIR

db_path = os.path.join(DB_DIR, "ghost_memory.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Update SQLite Schema
columns = [
    ("pending_action", "TEXT"),
    ("son_hata", "TEXT"),
    ("mevcut_context", "TEXT")
]

for col_name, col_type in columns:
    try:
        cursor.execute(f"ALTER TABLE proje_durumu ADD COLUMN {col_name} {col_type}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            print(f"Column {col_name} error: {e}")

conn.commit()
conn.close()
print("Updated SQLite schema.")

# 2. Patch hafıza/episodic_db.py
with open("hafıza/episodic_db.py", "r", encoding="utf-8") as f:
    code = f.read()

# Update CREATE TABLE
old_create = """                CREATE TABLE IF NOT EXISTS proje_durumu (
                    proje_adi TEXT PRIMARY KEY,
                    aktif_dizin TEXT,
                    son_dokunulan_dosyalar TEXT,
                    son_gorev_ozeti TEXT,
                    guncelleme_zamani INTEGER
                )"""
new_create = """                CREATE TABLE IF NOT EXISTS proje_durumu (
                    proje_adi TEXT PRIMARY KEY,
                    aktif_dizin TEXT,
                    son_dokunulan_dosyalar TEXT,
                    son_gorev_ozeti TEXT,
                    guncelleme_zamani INTEGER,
                    pending_action TEXT,
                    son_hata TEXT,
                    mevcut_context TEXT
                )"""
code = code.replace(old_create, new_create)

# Check and update durum_guncelle definition
old_def = "def durum_guncelle(self, proje_adi: str, aktif_dizin: str = None,\n                        dokunulan_dosya: str = None, gorev_ozeti: str = None,\n                        max_dosya_gecmisi: int = 15):"
new_def = "def durum_guncelle(self, proje_adi: str, aktif_dizin: str = None,\n                        dokunulan_dosya: str = None, gorev_ozeti: str = None,\n                        pending_action: str = None, son_hata: str = None,\n                        mevcut_context: str = None, max_dosya_gecmisi: int = 15):"
if old_def in code:
    code = code.replace(old_def, new_def)
else:
    print("Could not find durum_guncelle def!")

# Update durum_guncelle body
old_body = """        if gorev_ozeti is None:
            gorev_ozeti = mevcut["son_gorev_ozeti"] if mevcut else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(\"\"\"
                INSERT INTO proje_durumu (proje_adi, aktif_dizin, son_dokunulan_dosyalar, son_gorev_ozeti, guncelleme_zamani)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(proje_adi) DO UPDATE SET
                    aktif_dizin = excluded.aktif_dizin,
                    son_dokunulan_dosyalar = excluded.son_dokunulan_dosyalar,
                    son_gorev_ozeti = excluded.son_gorev_ozeti,
                    guncelleme_zamani = excluded.guncelleme_zamani
            \"\"\", (proje_adi, aktif_dizin, json.dumps(dosya_listesi, ensure_ascii=False), gorev_ozeti, int(time.time())))
            conn.commit()"""

new_body = """        if gorev_ozeti is None:
            gorev_ozeti = mevcut["son_gorev_ozeti"] if mevcut else None
        
        # New fields fallback to existing if not provided
        if pending_action is None:
            pending_action = mevcut.get("pending_action") if mevcut else None
        if son_hata is None:
            son_hata = mevcut.get("son_hata") if mevcut else None
        if mevcut_context is None:
            mevcut_context = mevcut.get("mevcut_context") if mevcut else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(\"\"\"
                INSERT INTO proje_durumu (proje_adi, aktif_dizin, son_dokunulan_dosyalar, son_gorev_ozeti, guncelleme_zamani, pending_action, son_hata, mevcut_context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proje_adi) DO UPDATE SET
                    aktif_dizin = excluded.aktif_dizin,
                    son_dokunulan_dosyalar = excluded.son_dokunulan_dosyalar,
                    son_gorev_ozeti = excluded.son_gorev_ozeti,
                    guncelleme_zamani = excluded.guncelleme_zamani,
                    pending_action = excluded.pending_action,
                    son_hata = excluded.son_hata,
                    mevcut_context = excluded.mevcut_context
            \"\"\", (proje_adi, aktif_dizin, json.dumps(dosya_listesi, ensure_ascii=False), gorev_ozeti, int(time.time()), pending_action, son_hata, mevcut_context))
            conn.commit()"""
if old_body in code:
    code = code.replace(old_body, new_body)
else:
    print("Could not find durum_guncelle body!")

# Add migration to _create_tables so it doesn't fail on old dbs without the python script
old_create_tables_end = """            # 6. Bildirimler Tablosu"""
migration_code = """
            # Add columns if missing
            try:
                cursor.execute("ALTER TABLE proje_durumu ADD COLUMN pending_action TEXT")
                cursor.execute("ALTER TABLE proje_durumu ADD COLUMN son_hata TEXT")
                cursor.execute("ALTER TABLE proje_durumu ADD COLUMN mevcut_context TEXT")
            except:
                pass

            # 6. Bildirimler Tablosu"""
code = code.replace(old_create_tables_end, migration_code)

with open("hafıza/episodic_db.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Patched hafıza/episodic_db.py")

# 3. Patch core/tool_registry.py
with open("core/tool_registry.py", "a", encoding="utf-8") as f:
    f.write('''
ghost_tool(
    name="calisma_durumu_guncelle",
    description="Aktif projedeki çalışma durumunu (bağlam ve bekleyen işlemler) günceller. Görevler arası geçişte veya uzun bir işlemin ortasında güncel state'i kaydetmek için kullan.",
    params={
        "mevcut_context": ("string", "Şu an tam olarak ne yapılıyor? (örn: 'Auth modülü yazılıyor')"),
        "pending_action": ("string", "Sırada bekleyen işlem ne? (örn: 'Testler çalıştırılacak')")
    },
)(None)
''')
print("Patched core/tool_registry.py")
