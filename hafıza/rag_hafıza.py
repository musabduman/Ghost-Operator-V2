import chromadb
import requests
import os
import hashlib

class Bellek:
    def __init__(self, collection_name="bellek"):
        db_path = os.path.join(os.path.expanduser("~"), "Desktop", "Ghost_Memory", "VektorDB")
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=self.collection_name)
        
        self.api_url = "http://localhost:11434/api/embeddings"

    def _get_embedding(self, metin):
        # YENİ MODEL BURADA DEVREYE GİRİYOR
        payload = {
            "model": "qwen3-embedding:0.6b", 
            "prompt": metin
        }
        # Ana model meşgulken hata vermemesi için 120 saniye sabır!
        response = requests.post(self.api_url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["embedding"]

    def bellege_yaz(self, metin):
        if not metin or not metin.strip():
            return 
            
        try:
            embedding = self._get_embedding(metin)
            metin_hash = hashlib.md5(metin.encode("utf-8")).hexdigest()
            
            self.collection.upsert(
                documents=[metin],
                embeddings=[embedding],
                ids=[metin_hash]
            )
        except Exception as e:
            print(f"[SİSTEM UYARISI] Belleğe yazma başarısız: {e}")

    def sorgula(self, soru, limit=3):
        try:
            embedding = self._get_embedding(soru)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit
            )
            if results["documents"] and results["documents"][0]:
                return results["documents"][0] 
            return []
        
        except Exception as e:
            print(f"[SİSTEM UYARISI] Bellek sorgusu başarısız: {e}")
            return []

    def benzerini_bul(self, metin, esik=0.15):
        """Yazmadan önce aynı/çok benzer bir kaydın olup olmadığını kontrol
        eder. Chroma'nın döndürdüğü mesafeye (distance) bakar — küçük mesafe
        büyük benzerlik demektir. Koleksiyon boşsa veya hiçbir kayıt eşiğin
        altında değilse None döner.

        esik: varsayılan 0.15 kaba bir başlangıç değeri — Chroma'nın hangi
        mesafe metriğini (L2/cosine) kullandığına göre gerçek "benzer"
        sınırı değişir. İlk birkaç gerçek yazımdan sonra konsoldaki mesafe
        değerlerini gözlemleyip bu sayıyı ayarlaman gerekecek.
        """
        if self.collection.count() == 0:
            return None
        try:
            embedding = self._get_embedding(metin)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=1,
                include=["documents", "distances"],
            )
            if not results["documents"] or not results["documents"][0]:
                return None
            en_yakin_mesafe = results["distances"][0][0]
            if en_yakin_mesafe <= esik:
                return results["documents"][0][0]
            return None
        except Exception as e:
            print(f"[SİSTEM UYARISI] Benzerlik kontrolü başarısız: {e}")
            return None

    def bellekten_sil(self, metin):
        if not metin or not metin.strip():
            return
        try:
            metin_hash = hashlib.md5(metin.encode("utf-8")).hexdigest()
            self.collection.delete(ids=[metin_hash])
            print(f"[SİSTEM - HAFIZA]: Vektör başarıyla silindi: {metin}")
        except Exception as e:
            print(f"[SİSTEM UYARISI] Bellekten silme başarısız: {e}")