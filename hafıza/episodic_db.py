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

            # 3. Proje Durum (Working State) Tablosu
            # Kısa-vadeli buffer (sohbet_gecmisi) ile uzun-vadeli RAG (Bellek) arasında
            # üçüncü bir katman: "şu an hangi projedeyim, en son ne yaptım" bilgisini tutar.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proje_durumu (
                    proje_adi TEXT PRIMARY KEY,
                    aktif_dizin TEXT,
                    son_dokunulan_dosyalar TEXT,
                    son_gorev_ozeti TEXT,
                    guncelleme_zamani INTEGER
                )
            """)

            # 4. Proje Yol Haritası
            # Bir kök dizinin hangi proje adına karşılık geldiğini tutar.
            # Sabit klasör-adı sezgisi yerine: bilinmeyen bir kök dizinle ilk
            # karşılaşıldığında kullanıcıya sorulur, cevap buraya kaydedilir,
            # bir daha hiç sorulmaz. Farklı kullanıcıların farklı klasör
            # yapılarında da çalışsın diye (ürünleşirse) tasarlandı.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proje_yol_haritasi (
                    kok_dizin TEXT PRIMARY KEY,
                    proje_adi TEXT,
                    olusturma_zamani INTEGER
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

    # ── Proje Durum (Working State) ──────────────────────────────────────
    def durum_guncelle(self, proje_adi: str, aktif_dizin: str = None,
                        dokunulan_dosya: str = None, gorev_ozeti: str = None,
                        max_dosya_gecmisi: int = 15):
        """
        Bir proje için durum satırını günceller (yoksa oluşturur).
        dokunulan_dosya verilirse, son_dokunulan_dosyalar listesine eklenir
        (en yeni başta, liste max_dosya_gecmisi ile sınırlı tutulur).
        """
        mevcut = self.durum_getir(proje_adi)

        if aktif_dizin is None:
            aktif_dizin = mevcut["aktif_dizin"] if mevcut else None

        dosya_listesi = json.loads(mevcut["son_dokunulan_dosyalar"]) if mevcut and mevcut["son_dokunulan_dosyalar"] else []
        if dokunulan_dosya:
            if dokunulan_dosya in dosya_listesi:
                dosya_listesi.remove(dokunulan_dosya)
            dosya_listesi.insert(0, dokunulan_dosya)
            dosya_listesi = dosya_listesi[:max_dosya_gecmisi]

        if gorev_ozeti is None:
            gorev_ozeti = mevcut["son_gorev_ozeti"] if mevcut else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO proje_durumu (proje_adi, aktif_dizin, son_dokunulan_dosyalar, son_gorev_ozeti, guncelleme_zamani)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(proje_adi) DO UPDATE SET
                    aktif_dizin = excluded.aktif_dizin,
                    son_dokunulan_dosyalar = excluded.son_dokunulan_dosyalar,
                    son_gorev_ozeti = excluded.son_gorev_ozeti,
                    guncelleme_zamani = excluded.guncelleme_zamani
            """, (proje_adi, aktif_dizin, json.dumps(dosya_listesi, ensure_ascii=False), gorev_ozeti, int(time.time())))
            conn.commit()

    def durum_getir(self, proje_adi: str):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM proje_durumu WHERE proje_adi = ?", (proje_adi,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def son_aktif_projeyi_getir(self):
        """En son güncellenen (geçici/bilinmeyen olmayan) proje durumunu döndürür."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM proje_durumu
                WHERE proje_adi NOT LIKE '\\_bilinmiyor::%' ESCAPE '\\'
                ORDER BY guncelleme_zamani DESC LIMIT 1
            """)
            row = cursor.fetchone()
            return dict(row) if row else None

    def proje_durumu_sil(self, proje_adi: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM proje_durumu WHERE proje_adi = ?", (proje_adi,))
            conn.commit()

    def tum_projeleri_listele(self):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT proje_adi, aktif_dizin, guncelleme_zamani FROM proje_durumu
                WHERE proje_adi NOT LIKE '\\_bilinmiyor::%' ESCAPE '\\'
                ORDER BY guncelleme_zamani DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    # ── Proje Yol Haritası (kök dizin -> proje adı) ──────────────────────
    def proje_adi_ayarla(self, kok_dizin: str, proje_adi: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO proje_yol_haritasi (kok_dizin, proje_adi, olusturma_zamani)
                VALUES (?, ?, ?)
                ON CONFLICT(kok_dizin) DO UPDATE SET proje_adi = excluded.proje_adi
            """, (kok_dizin, proje_adi, int(time.time())))
            conn.commit()

    def proje_adi_bul(self, yol: str):
        """
        Verilen tam yol için, kayıtlı kök dizinler arasında en uzun eşleşen
        (en spesifik) kaydı bulur. Bulamazsa None döner — bu durumda
        CommandHandler kullanıcıya sorması gerektiğini anlar.
        """
        if not yol:
            return None
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT kok_dizin, proje_adi FROM proje_yol_haritasi")
            adaylar = [dict(row) for row in cursor.fetchall()]

        yol_norm = yol.replace("\\", "/").lower()
        en_iyi = None
        for aday in adaylar:
            kok_norm = aday["kok_dizin"].replace("\\", "/").lower()
            if yol_norm.startswith(kok_norm):
                if en_iyi is None or len(kok_norm) > len(en_iyi["kok_dizin"]):
                    en_iyi = aday
        return en_iyi["proje_adi"] if en_iyi else None  