import os
import sqlite3
import re
from core.config import DB_DIR

db_path = os.path.join(DB_DIR, "ghost_memory.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Update SQLite Schema
for table in ["sohbet_gecmisi", "arac_gunlukleri"]:
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN proje_adi TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            print(f"Table {table} error: {e}")

conn.commit()
conn.close()
print("Updated SQLite schema for memory scopes.")

# 2. Patch hafıza/episodic_db.py
with open("hafıza/episodic_db.py", "r", encoding="utf-8") as f:
    code = f.read()

# Update create_tables to include the new columns
old_create_sohbet = """                CREATE TABLE IF NOT EXISTS sohbet_gecmisi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp INTEGER,
                    role TEXT,
                    content TEXT,
                    is_analyzed INTEGER DEFAULT 0
                )"""
new_create_sohbet = """                CREATE TABLE IF NOT EXISTS sohbet_gecmisi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp INTEGER,
                    role TEXT,
                    content TEXT,
                    is_analyzed INTEGER DEFAULT 0,
                    proje_adi TEXT
                )"""
code = code.replace(old_create_sohbet, new_create_sohbet)

old_create_arac = """                CREATE TABLE IF NOT EXISTS arac_gunlukleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp INTEGER,
                    tool_name TEXT,
                    arguments TEXT,
                    result TEXT,
                    success INTEGER,
                    is_analyzed INTEGER DEFAULT 0
                )"""
new_create_arac = """                CREATE TABLE IF NOT EXISTS arac_gunlukleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp INTEGER,
                    tool_name TEXT,
                    arguments TEXT,
                    result TEXT,
                    success INTEGER,
                    is_analyzed INTEGER DEFAULT 0,
                    proje_adi TEXT
                )"""
code = code.replace(old_create_arac, new_create_arac)

# Also add migration inside _create_tables
migration_code = """
            # Add columns if missing
            try:
                cursor.execute("ALTER TABLE sohbet_gecmisi ADD COLUMN proje_adi TEXT")
                cursor.execute("ALTER TABLE arac_gunlukleri ADD COLUMN proje_adi TEXT")
            except:
                pass
"""
target_migration = """            # 3. Proje Durum (Working State) Tablosu"""
if migration_code not in code:
    code = code.replace(target_migration, migration_code + "\\n" + target_migration)

# Update mesaj_kaydet
old_mesaj_kaydet = """    def mesaj_kaydet(self, session_id: str, role: str, content: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sohbet_gecmisi (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                (session_id, int(time.time()), role, content)
            )
            conn.commit()"""
new_mesaj_kaydet = """    def mesaj_kaydet(self, session_id: str, role: str, content: str):
        son_proje = self.son_aktif_projeyi_getir()
        proje_adi = son_proje["proje_adi"] if son_proje else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sohbet_gecmisi (session_id, timestamp, role, content, proje_adi) VALUES (?, ?, ?, ?, ?)",
                (session_id, int(time.time()), role, content, proje_adi)
            )
            conn.commit()"""
code = code.replace(old_mesaj_kaydet, new_mesaj_kaydet)

# Update arac_log_kaydet
old_arac_log_kaydet = """    def arac_log_kaydet(self, session_id: str, tool_name: str, arguments: dict, result: str, success: bool):
        arguments_json = json.dumps(arguments, ensure_ascii=False)
        success_int = 1 if success else 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO arac_gunlukleri (session_id, timestamp, tool_name, arguments, result, success) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, int(time.time()), tool_name, arguments_json, result, success_int)
            )
            conn.commit()"""
new_arac_log_kaydet = """    def arac_log_kaydet(self, session_id: str, tool_name: str, arguments: dict, result: str, success: bool):
        arguments_json = json.dumps(arguments, ensure_ascii=False)
        success_int = 1 if success else 0
        son_proje = self.son_aktif_projeyi_getir()
        proje_adi = son_proje["proje_adi"] if son_proje else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO arac_gunlukleri (session_id, timestamp, tool_name, arguments, result, success, proje_adi) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, int(time.time()), tool_name, arguments_json, result, success_int, proje_adi)
            )
            conn.commit()"""
code = code.replace(old_arac_log_kaydet, new_arac_log_kaydet)

with open("hafıza/episodic_db.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Patched hafıza/episodic_db.py")

# 3. Patch hafıza/rag_hafıza.py
with open("hafıza/rag_hafıza.py", "r", encoding="utf-8") as f:
    code = f.read()

old_sorgula = """    def sorgula(self, soru, limit=3):
        try:
            embedding = self._get_embedding(soru)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit
            )
            if results["documents"] and results["documents"][0]:
                return results["documents"][0] 
            return []"""
new_sorgula = """    def sorgula(self, soru, limit=3, proje_adi=None):
        try:
            embedding = self._get_embedding(soru)
            where = {"proje_adi": proje_adi} if proje_adi else None
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit,
                where=where
            )
            if results["documents"] and results["documents"][0]:
                return results["documents"][0] 
            return []"""
code = code.replace(old_sorgula, new_sorgula)
with open("hafıza/rag_hafıza.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Patched hafıza/rag_hafıza.py")

# 4. Patch handler/command_handler.py to pass active project to sorgula
with open("handler/command_handler.py", "r", encoding="utf-8") as f:
    code = f.read()

old_enrich = """    def _enrich_with_memory(self, user_input: str) -> str:
        # Eğer sistem mesajıysa belleğe sormaya gerek yok
        if "GİZLİ SİSTEM BİLGİSİ" in user_input:
            return user_input
            
        memories = self.bellek.sorgula(soru=user_input, limit=2)"""
new_enrich = """    def _enrich_with_memory(self, user_input: str) -> str:
        # Eğer sistem mesajıysa belleğe sormaya gerek yok
        if "GİZLİ SİSTEM BİLGİSİ" in user_input:
            return user_input
            
        son_proje = self.episodic_db.son_aktif_projeyi_getir()
        proje_adi = son_proje["proje_adi"] if son_proje else None
        
        memories = self.bellek.sorgula(soru=user_input, limit=2, proje_adi=proje_adi)"""
if "son_aktif_projeyi_getir" not in code.split("_enrich_with_memory")[1][:500]:
    code = code.replace(old_enrich, new_enrich)
with open("handler/command_handler.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Patched handler/command_handler.py")

# 5. Patch ai/librarian_agent.py to pass project_id to bellege_yaz
with open("ai/librarian_agent.py", "r", encoding="utf-8") as f:
    code = f.read()

old_process = """    def _process_batch(self, mesajlar, loglar):
        print(f"[SİSTEM - KÜTÜPHANECİ]: {len(mesajlar)} yeni mesaj ve {len(loglar)} yeni araç logu analiz ediliyor...")"""
new_process = """    def _process_batch(self, mesajlar, loglar):
        from collections import defaultdict
        grouped = defaultdict(lambda: {'mesajlar': [], 'loglar': []})
        for m in mesajlar:
            grouped[m.get('proje_adi', None)]['mesajlar'].append(m)
        for l in loglar:
            grouped[l.get('proje_adi', None)]['loglar'].append(l)
            
        if len(grouped) > 1:
            # Process project by project
            for p_adi, p_data in grouped.items():
                if p_data['mesajlar'] or p_data['loglar']:
                    self._process_project_batch(p_data['mesajlar'], p_data['loglar'], p_adi)
            return
            
        # Single project fallback
        proje_adi = list(grouped.keys())[0] if grouped else None
        self._process_project_batch(mesajlar, loglar, proje_adi)

    def _process_project_batch(self, mesajlar, loglar, proje_adi):
        print(f"[SİSTEM - KÜTÜPHANECİ]: {len(mesajlar)} yeni mesaj ve {len(loglar)} yeni araç logu ({proje_adi}) analiz ediliyor...")"""
code = code.replace(old_process, new_process)

# Update the metadata in _process_project_batch (formerly _process_batch)
# Find the places where metadata is built:
# metadata = {"created_at": time.time(), "confidence": confidence, "confirmation_count": 1}
old_metadata = """                                metadata = {"created_at": time.time(), "confidence": confidence, "confirmation_count": 1}"""
new_metadata = """                                metadata = {"created_at": time.time(), "confidence": confidence, "confirmation_count": 1}
                                if proje_adi:
                                    metadata["proje_adi"] = proje_adi"""
code = code.replace(old_metadata, new_metadata)

with open("ai/librarian_agent.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Patched ai/librarian_agent.py")
