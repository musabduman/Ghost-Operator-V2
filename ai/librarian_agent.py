import re
import time
import json
import threading
import requests
from hafıza.episodic_db import EpisodicDB
from hafıza.rag_hafıza import Bellek

class LibrarianAgent:
    def __init__(self, model="gpt-oss:20b"):
        self.model = model
        self.api_url = "http://localhost:11434/api/chat"
        self.episodic_db = EpisodicDB()
        self.bellek = Bellek()
        self._running = False
        self._thread = None
        
        # Kütüphanecinin veri süzme ve CRUD karar kuralları
        self.prompt = """
        Sen Ghost Operator asistanının arka planda çalışan Kütüphanecisisin (Librarian). 
        Görevin, kullanıcının yaptığı konuşmaları ve aldığı sistem/araç hata loglarını analiz edip kalıcı hafızayı yönetmektir.
        
        Sana analiz etmen için yeni sohbet mesajları ve araç günlükleri verilecek. Bunlara bakarak:
        1. Hatırlanması gereken kalıcı kullanıcı tercihlerini veya teknik bilgileri/hataları tespit et.
        2. Bu bilgiyi 3. şahıs diliyle ("Kullanıcı X'i tercih ediyor", "Spotify API x hatası verdi") özetle.
        3. EĞER yeni tespit ettiğin bilgi, geçmişten hatırlanabilecek bir bilgiyle çelişiyorsa (örn: eskiden mavi rengi seviyordu ama yeni mesajda kırmızı dedi), bunu bir 'update' işlemi olarak işaretle.
        
        Yanıtını SADECE geçerli bir JSON array olarak döndür. Başka hiçbir açıklama, markdown bloğu (```json gibi) veya giriş/gelişme metni yazma. Sadece saf JSON.
        
        JSON Format Şeması:
        [
          {"action": "save", "fact": "Kaydedilecek kalıcı bilgi özeti"},
          {"action": "update", "old_fact_query": "Eski bilgiyi bulmak için vektör DB sorgusu", "new_fact": "Yeni kalıcı bilgi özeti"}
        ]
        
        Eğer kaydedilecek hiçbir bilgi yoksa sadece boş bir liste döndür: []
        
        Örnek girdi:
        [Sohbet]
        Kullanıcı: "En sevdiğim rengi kırmızı olarak hafızana kaydet."
        Ghost: "Kaydettim."
        [Araç Logları]
        -
        
        Örnek çıktı:
        [
          {"action": "save", "fact": "Kullanıcının en sevdiği renk kırmızıdır."}
        ]
        
        Örnek girdi 2:
        [Sohbet]
        Kullanıcı: "Artık mavi rengi daha çok seviyorum, kırmızıyı unut."
        Ghost: "Güncelledim."
        [Araç Logları]
        -
        
        Örnek çıktı 2:
        [
          {"action": "update", "old_fact_query": "Kullanıcının en sevdiği renk", "new_fact": "Kullanıcının en sevdiği renk mavidir."}
        ]
        
        Şimdi analiz et:
        """

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[SİSTEM - KÜTÜPHANECİ]: Arka plan izleme döngüsü başlatıldı.")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._analiz_et()
            except Exception as e:
                print(f"[SİSTEM HATA - KÜTÜPHANECİ]: Döngü hatası: {e}")
            
            # Ana thread'i kilitlemeden 30 saniye uyut (durma sinyalini hızlı yakalamak için 1 saniyelik adımlarla)
            for _ in range(30):
                if not self._running:
                    break
                time.sleep(1)

    def _analiz_et(self):
        mesajlar = self.episodic_db.analiz_edilmemis_mesajlari_getir()
        loglar = self.episodic_db.analiz_edilmemis_arac_loglarini_getir()
        
        if not mesajlar and not loglar:
            return

        print(f"[SİSTEM - KÜTÜPHANECİ]: {len(mesajlar)} yeni mesaj ve {len(loglar)} yeni araç logu analiz ediliyor...")
        
        # Modele sunulacak girdiyi oluştur
        girdi_metni = "[Sohbet]\n"
        for m in mesajlar:
            sender = "Kullanıcı" if m["role"] == "user" else "Ghost"
            girdi_metni += f"{sender}: {m['content']}\n"
            
        girdi_metni += "\n[Araç Logları]\n"
        if loglar:
            for l in loglar:
                durum = "Başarılı" if l["success"] == 1 else "Hata Aldı"
                girdi_metni += f"- {l['tool_name']} aracı çalıştırıldı. Durum: {durum}. Çıktı: {l['result'][:200]}\n"
        else:
            girdi_metni += "-\n"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": girdi_metni}
            ],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=90)
            response.raise_for_status()
            raw_content = response.json()["message"]["content"].strip()
            
            # Markdown kod bloklarını temizle (```json ... ```)
            raw_content = re.sub(r"^```[\w]*\n?", "", raw_content)
            raw_content = re.sub(r"\n?```$", "", raw_content).strip()
            
            if not raw_content or raw_content == "[]":
                self._isaretle(mesajlar, loglar)
                return
                
            try:
                islemler = json.loads(raw_content)
                for islem in islemler:
                    action = islem.get("action")
                    if action == "save":
                        fact = islem.get("fact")
                        if fact:
                            # Aynı bilginin mükerrer kaydedilmesini engelle
                            if self.bellek.benzerini_bul(fact) is None:
                                self.bellek.bellege_yaz(fact)
                                print(f"[KÜTÜPHANECİ]: Yeni bilgi RAG belleğine eklendi -> {fact}")
                    elif action == "update":
                        old_query = islem.get("old_fact_query")
                        new_fact = islem.get("new_fact")
                        if old_query and new_fact:
                            # Vektör DB'de eski bilgiyi arat
                            eski_kayitlar = self.bellek.sorgula(old_query, limit=1)
                            if eski_kayitlar:
                                eski_kayit = eski_kayitlar[0]
                                self.bellek.bellekten_sil(eski_kayit)
                                print(f"[KÜTÜPHANECİ]: Eski çelişkili bilgi silindi -> {eski_kayit}")
                            
                            # Yeni bilgiyi yaz
                            self.bellek.bellege_yaz(new_fact)
                            print(f"[KÜTÜPHANECİ]: Güncel bilgi RAG belleğine eklendi -> {new_fact}")
            except Exception as parse_error:
                print(f"[KÜTÜPHANECİ HATA]: JSON parse hatası. Ham yanıt: {raw_content} | Hata: {parse_error}")
                
        except Exception as api_error:
            print(f"[KÜTÜPHANECİ HATA]: API hatası: {api_error}")
            
        # İşlenen satırları işaretle
        self._isaretle(mesajlar, loglar)

    def _isaretle(self, mesajlar, loglar):
        if mesajlar:
            m_ids = [m["id"] for m in mesajlar]
            self.episodic_db.mesajlari_analiz_edildi_olarak_isaretle(m_ids)
        if loglar:
            l_ids = [l["id"] for l in loglar]
            self.episodic_db.arac_loglarini_analiz_edildi_olarak_isaretle(l_ids)
