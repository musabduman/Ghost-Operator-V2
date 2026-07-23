import sqlite3
import os
import time
import json

class EpisodicDB:
    def __init__(self):
        # Vektör DB ile aynı klasörde olması için ~/Desktop/Ghost_Memory dizinini kullanıyoruz
        db_dir = os.path.join(os.path.expanduser("~"), "Desktop", "Ghost_Memory")
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, "ghost_memory.db")
        self._create_tables()

    def _get_connection(self):
        # check_same_thread=False ile arka planda Kütüphaneci thread'inin güvenle yazıp okumasını sağlıyoruz
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _create_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Sohbet Geçmişi Tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sohbet_gecmisi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp INTEGER,
                    role TEXT,
                    content TEXT,
                    is_analyzed INTEGER DEFAULT 0
                )
            """)
            
            # 2. Araç (Tool) Günlükleri Tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS arac_gunlukleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp INTEGER,
                    tool_name TEXT,
                    arguments TEXT,
                    result TEXT,
                    success INTEGER,
                    is_analyzed INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def mesaj_kaydet(self, session_id: str, role: str, content: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sohbet_gecmisi (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                (session_id, int(time.time()), role, content)
            )
            conn.commit()

    def arac_log_kaydet(self, session_id: str, tool_name: str, arguments: dict, result: str, success: bool):
        arguments_json = json.dumps(arguments, ensure_ascii=False)
        success_int = 1 if success else 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO arac_gunlukleri (session_id, timestamp, tool_name, arguments, result, success) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, int(time.time()), tool_name, arguments_json, result, success_int)
            )
            conn.commit()

    def analiz_edilmemis_mesajlari_getir(self):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sohbet_gecmisi WHERE is_analyzed = 0 ORDER BY id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def analiz_edilmemis_arac_loglarini_getir(self):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM arac_gunlukleri WHERE is_analyzed = 0 ORDER BY id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def mesajlari_analiz_edildi_olarak_isaretle(self, ids: list):
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE sohbet_gecmisi SET is_analyzed = 1 WHERE id IN ({placeholders})",
                ids
            )
            conn.commit()

    def arac_loglarini_analiz_edildi_olarak_isaretle(self, ids: list):
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE arac_gunlukleri SET is_analyzed = 1 WHERE id IN ({placeholders})",
                ids
            )
            conn.commit()
