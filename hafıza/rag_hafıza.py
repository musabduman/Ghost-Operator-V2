import chromadb
import ollama
import os
import hashlib

class Bellek:
    def __init__(self, collection_name="bellek"):
        # HATA DÜZELTİLDİ: "Masaüstü" yerine "Desktop" kullanıldı.
        db_path = os.path.join(os.path.expanduser("~"), "Desktop", "Ghost_Memory", "VektorDB")
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def bellege_yaz(self, metin):
        # Güvenlik Önlemi: Boş metin geldiyse sistemi yorma, işlemi iptal et
        if not metin or not metin.strip():
            return 
            
        try:
            embedding = ollama.embeddings(model="nomic-embed-text", prompt=metin)["embedding"]
            metin_hash = hashlib.md5(metin.encode("utf-8")).hexdigest()
            
            # HATA DÜZELTİLDİ: add yerine upsert kullanıldı (Aynı not gelirse çökmeyi engeller)
            self.collection.upsert(
                documents=[metin],
                embeddings=[embedding],
                ids=[metin_hash]
            )
        except Exception as e:
            # İşlem başarısız olursa arka planda neyin patladığını terminale yazdır
            print(f"[SİSTEM UYARISI] Belleğe yazma başarısız: {e}")

    def sorgula(self, soru, limit=3):
        try:
            embedding = ollama.embeddings(model="nomic-embed-text", prompt=soru)["embedding"]
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit
            )
            # Eğer sonuç boş dönmezse listeyi ver, boşsa boş liste dön
            if results["documents"] and results["documents"][0]:
                return results["documents"][0] 
            return []
        
        except Exception as e:
            print(f"[SİSTEM UYARISI] Bellek sorgusu başarısız: {e}")
            return []