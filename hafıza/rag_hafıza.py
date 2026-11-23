from core.config import GHOST_TOKEN
from core.ollama_health import (
    ensure_ollama,
    format_embedding_error,
    OLLAMA_BASE_URL,
    EMBEDDING_MODEL,
)
import chromadb
import requests
import os
import hashlib
import logging

logger = logging.getLogger("ghost.rag_hafiza")


class Bellek:
    """ChromaDB destekli vektör hafıza.

    Ollama embedding servisi erişilemez durumdaysa önce otomatik başlatmayı
    dener; başarısızsa hataları LangGraph'a aktarılabilecek temiz mesajlara
    çevirir (State Hijyeni — ham traceback veya HTML çöplüğü dışarı sızmaz).
    """

    def __init__(self, collection_name="bellek"):
        from core.config import DB_DIR, GHOST_TOKEN
        db_path = os.path.join(DB_DIR, "VektorDB")
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

        self.api_url = f"{OLLAMA_BASE_URL}/api/embeddings"

        # Son hata — LangGraph veya command_handler tarafından okunabilir
        self.son_hata: str | None = None

    # ── Embedding ────────────────────────────────────────────────────────

    def _get_embedding(self, metin):
        """Ollama'dan embedding vektörü alır.

        Servis kapalıysa otomatik başlatmayı dener.  Başarısızsa
        ``format_embedding_error`` ile temiz hata üretir ve fırlatır.
        """
        # Önce Ollama erişilebilir mi kontrol et / otomatik başlat
        health_err = ensure_ollama()
        if health_err:
            raise ConnectionError(health_err)

        payload = {
            "model": EMBEDDING_MODEL,
            "prompt": metin
        }
        # Ana model meşgulken hata vermemesi için 120 saniye sabır!
        response = requests.post(
            self.api_url,
            json=payload,
            headers={"X-Ghost-Token": GHOST_TOKEN},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    # ── Yazma ────────────────────────────────────────────────────────────

    def bellege_yaz(self, metin, metadata=None):
        if not metin or not metin.strip():
            return

        try:
            embedding = self._get_embedding(metin)
            metin_hash = hashlib.md5(metin.encode("utf-8")).hexdigest()

            kwargs = {
                "documents": [metin],
                "embeddings": [embedding],
                "ids": [metin_hash]
            }
            if metadata is not None:
                kwargs["metadatas"] = [metadata]

            self.collection.upsert(**kwargs)
            self.son_hata = None
        except Exception as e:
            self.son_hata = format_embedding_error(e)
            logger.warning(f"[RAG] Belleğe yazma başarısız: {self.son_hata}")

    # ── Sorgulama ────────────────────────────────────────────────────────

    def sorgula(self, soru, limit=3, proje_adi=None, max_distance=0.45):
        """Vektör belleğini sorgular.

        Args:
            soru: Aranacak doğal dil sorusu.
            limit: Maksimum sonuç sayısı.
            proje_adi: Filtrelenecek proje adı (opsiyonel).
            max_distance: Maksimum mesafe eşiği (varsayılan: 0.45). Eşiğin üstündeki
                alakasız kayıtlar elenir (Context Pollution koruması).

        Returns:
            list[str] — bulunan ve eşiği geçen alakalı dokümanlar (boş liste olabilir).

        Hata durumunda ``self.son_hata`` doldurulur; çağıran taraf bu
        değeri okuyarak LangGraph'a temiz uyarı geçebilir.
        """
        try:
            embedding = self._get_embedding(soru)
            where = {"proje_adi": proje_adi} if proje_adi else None
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit,
                where=where,
                include=["documents", "distances"]
            )
            self.son_hata = None
            if not results["documents"] or not results["documents"][0]:
                return []

            docs = results["documents"][0]
            distances = results.get("distances", [[]])[0] if results.get("distances") else []

            alakali_dokumanlar = []
            for i, doc in enumerate(docs):
                dist = distances[i] if i < len(distances) else 0.0
                if max_distance is None or dist <= max_distance:
                    alakali_dokumanlar.append(doc)

            return alakali_dokumanlar

        except Exception as e:
            self.son_hata = format_embedding_error(e)
            logger.warning(f"[RAG] Bellek sorgusu başarısız: {self.son_hata}")
            return []

    def sorgula_metadata_ile(self, soru, limit=3):
        try:
            embedding = self._get_embedding(soru)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit,
                include=["documents", "metadatas", "distances"]
            )
            kayitlar = []
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    kayitlar.append({
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {},
                        "distance": results["distances"][0][i] if results.get("distances") and results["distances"][0] else 0.0,
                        "id": results["ids"][0][i]
                    })
            return kayitlar
        except Exception as e:
            self.son_hata = format_embedding_error(e)
            logger.warning(f"[RAG] Metadata ile bellek sorgusu başarısız: {self.son_hata}")
            return []

    def benzerini_bul(self, metin, esik=0.15):
        """Yazmadan önce aynı/çok benzer bir kaydın olup olmadığını kontrol
        eder. Chroma'nın döndürdüğü mesafeye (distance) bakar — küçük mesafe
        büyük benzerlik demektir. Koleksiyon boşsa veya hiçbir kayıt eşiğin
        altında değilse None döner.
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
            self.son_hata = None
            if not results["documents"] or not results["documents"][0]:
                return None
            en_yakin_mesafe = results["distances"][0][0]
            if en_yakin_mesafe <= esik:
                return results["documents"][0][0]
            return None
        except Exception as e:
            self.son_hata = format_embedding_error(e)
            logger.warning(f"[RAG] Benzerlik kontrolü başarısız: {self.son_hata}")
            return None

    def benzerini_bul_metadata_ile(self, metin, esik=0.15, proje_adi=None):
        """Benzer kaydı arar ve bulursa metadata'sını da döndürür."""
        if self.collection.count() == 0:
            return None
        try:
            embedding = self._get_embedding(metin)
            where = {"proje_adi": proje_adi} if proje_adi else None
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=1,
                include=["documents", "metadatas", "distances"],
                where=where
            )
            self.son_hata = None
            if not results["documents"] or not results["documents"][0]:
                return None
            en_yakin_mesafe = results["distances"][0][0]
            if en_yakin_mesafe <= esik:
                return {
                    "document": results["documents"][0][0],
                    "metadata": results["metadatas"][0][0] if results.get("metadatas") and results["metadatas"][0] else {},
                    "distance": en_yakin_mesafe,
                    "id": results["ids"][0][0]
                }
            return None
        except Exception as e:
            self.son_hata = format_embedding_error(e)
            logger.warning(f"[RAG] Metadata'lı benzerlik kontrolü başarısız: {self.son_hata}")
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

    def bellek_budamasi_yap(self):
        """Zaman bazlı decay uygular ve confidence < 0.3 olan eski bilgileri siler."""
        import time
        try:
            results = self.collection.get(include=["metadatas", "documents"])
            if not results["ids"]:
                return "Bellek boş, budama yapılmadı."

            silinecekler = []
            guncellenecek_idler = []
            guncellenecek_metadatalar = []

            su_an = time.time()
            gun_saniye = 24 * 3600
            
            for i, d_id in enumerate(results["ids"]):
                meta = results["metadatas"][i]
                if not meta:
                    continue
                
                created_at = meta.get("created_at", su_an)
                gecen_gun = (su_an - created_at) / gun_saniye
                
                if gecen_gun < 1:
                    continue
                
                conf = float(meta.get("confidence", 1.0))
                count = int(meta.get("confirmation_count", 1))
                
                decay_miktari = (gecen_gun * 0.01) / count
                yeni_conf = conf - decay_miktari
                
                if yeni_conf < 0.3:
                    silinecekler.append(d_id)
                else:
                    # Update edilecek
                    if yeni_conf != conf:
                        meta["confidence"] = round(yeni_conf, 3)
                        guncellenecek_idler.append(d_id)
                        guncellenecek_metadatalar.append(meta)
            
            silinen_sayisi = len(silinecekler)
            guncellenen_sayisi = len(guncellenecek_idler)
            
            if silinecekler:
                self.collection.delete(ids=silinecekler)
            
            if guncellenecek_idler:
                self.collection.update(
                    ids=guncellenecek_idler,
                    metadatas=guncellenecek_metadatalar
                )
                
            msg = f"Budama tamamlandı. Silinen (Pruning): {silinen_sayisi}, Puanı Düşürülen (Decay): {guncellenen_sayisi}."
            print(f"[SİSTEM - HAFIZA]: {msg}")
            return msg
        except Exception as e:
            hata = f"[SİSTEM UYARISI] Bellek budama başarısız: {e}"
            print(hata)
            return hata