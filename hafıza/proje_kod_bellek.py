from core.config import GHOST_TOKEN
import ast
import os
import requests
import chromadb
from hafıza.symbol_graph import get_symbol_graph, SymbolGraph


class ProjeKodBellek:
    """
    Genel hafızadan (Bellek/rag_hafıza.py) AYRI bir Chroma koleksiyonu.
    Kullanıcı tercihleri/gerçekler yerine, projenin kendi kod tabanındaki
    fonksiyon/class imzalarını ve docstring'lerini semantik aranabilir
    hale getirir. Kodlama ajanına (QwenWorker/coder_node) "bu talimatla
    ilgili proje içinde zaten ne var" sorusunun cevabını verir.
    """

    def __init__(self, collection_name="proje_kod"):
        from core.config import DB_DIR, GHOST_TOKEN
        db_path = os.path.join(DB_DIR, "VektorDB")
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.api_url = "http://localhost:11434/api/embeddings"
        # B) Yapısal bellek (SQLite call/import/inheritance graph)
        self.graph: SymbolGraph = get_symbol_graph()

    def _get_embedding(self, metin):
        payload = {"model": "qwen3-embedding:0.6b", "prompt": metin}
        response = requests.post(self.api_url, json=payload, headers={"X-Ghost-Token": GHOST_TOKEN}, timeout=120)
        response.raise_for_status()
        return response.json()["embedding"]

    # ── İndeksleme ────────────────────────────────────────────────────
    def dosyayi_indexle(self, dosya_yolu: str, proje_adi: str):
        """
        Tek bir .py dosyasını AST ile tarar, üst seviye fonksiyon/class
        imzalarını + docstring'lerini çıkarıp embed eder. dosya_yaz tool'u
        her başarılı yazmadan sonra bunu çağırmalı (aşağıda coder_node
        entegrasyonu var) — böylece proje hafızası kendiliğinden güncel kalır.

        Ayrıca yapısal sembol grafiğini de günceller (stale-index korumalı).
        """
        # B) Yapısal grafik güncelleme (hash kontrollü, sadece değişen yeniden parse edilir)
        try:
            self.graph.index_file(dosya_yolu, proje_adi)
        except Exception as e:
            print(f"[SYMBOL GRAPH UYARISI] {dosya_yolu} grafik indeksleme hatası: {e}")

        try:
            with open(dosya_yolu, "r", encoding="utf-8") as f:
                kaynak = f.read()
            agac = ast.parse(kaynak)
        except Exception as e:
            print(f"[PROJE BELLEK UYARISI] {dosya_yolu} parse edilemedi: {e}")
            return

        # Dosya değişmiş olabilir — önce bu dosyaya ait eski sembolleri temizle
        self._dosya_sembollerini_sil(dosya_yolu)

        for node in ast.walk(agac):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self._sembol_kaydet(node, dosya_yolu, proje_adi)

    def _sembol_kaydet(self, node, dosya_yolu, proje_adi):
        imza = self._imza_cikar(node)
        docstring = ast.get_docstring(node) or ""
        ozet = f"{imza}\n{docstring}".strip()

        sembol_id = f"{dosya_yolu}::{node.name}::{node.lineno}"
        metadata = {
            "proje_adi": proje_adi,
            "dosya_yolu": dosya_yolu,
            "sembol_adi": node.name,
            "tip": type(node).__name__,
            "satir": node.lineno,
            "imza": imza,
        }
        try:
            embedding = self._get_embedding(ozet)
            self.collection.upsert(
                documents=[ozet],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[sembol_id],
            )
        except Exception as e:
            print(f"[PROJE BELLEK UYARISI] {node.name} embed edilemedi: {e}")

    def _imza_cikar(self, node):
        if isinstance(node, ast.ClassDef):
            temeller = [self._ifade_str(b) for b in node.bases]
            return f"class {node.name}({', '.join(temeller)})" if temeller else f"class {node.name}"
        args = [a.arg for a in node.args.args]
        on_ek = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{on_ek} {node.name}({', '.join(args)})"

    def _ifade_str(self, node):
        try:
            return ast.unparse(node)
        except Exception:
            return getattr(node, "id", "?")

    def _dosya_sembollerini_sil(self, dosya_yolu):
        try:
            mevcut = self.collection.get(where={"dosya_yolu": dosya_yolu})
            if mevcut and mevcut.get("ids"):
                self.collection.delete(ids=mevcut["ids"])
        except Exception:
            pass

    def baglam_metni_uret(
        self,
        sorgu: str,
        proje_adi: str = None,
        limit: int = 5,
        esik: float = 0.8,
        graph_depth: int = 2,
        graph_max_nodes: int = 20,
    ) -> str:
        """
        İki katmanlı bağlam:
          A) Semantic (ChromaDB) — doğal dil ile en alakalı sembolleri bulur
          B) Structural (SymbolGraph) — bulunan sembollerden derinlikli çağrı/bağımlılık grafiği çekilir

        esik'in üzerindeki (alakasız) sonuçları eler. graph_depth ve graph_max_nodes
        config üzerinden değiştirilebilir (varsayılan: 2 / 20).
        """
        # Config üzerinden override için
        from core import config as _cfg
        graph_depth = getattr(_cfg, "GRAPH_MAX_DEPTH", graph_depth)
        graph_max_nodes = getattr(_cfg, "GRAPH_MAX_NODES", graph_max_nodes)

        # A) Semantic arama
        sonuclar = self.sembol_ara(sorgu, proje_adi=proje_adi, limit=limit)
        alakalilar = [s for s in sonuclar if s["distance"] <= esik]

        metin_parts = []

        if alakalilar:
            metin = "[PROJEDE MEVCUT İLGİLİ SEMBOLLER — bunları tekrar icat etme, gerekiyorsa çağır/kullan]\n"
            for s in alakalilar:
                m = s["metadata"]
                metin += f"- {m['imza']}  ({os.path.basename(m['dosya_yolu'])}:{m['satir']})\n"
            metin_parts.append(metin)

            # B) Bulunan sembol isimlerinden yapısal graph bağlamı çek
            sembol_isimleri = [s["metadata"]["sembol_adi"] for s in alakalilar]
            try:
                graph_text = self.graph.format_context_text(
                    sembol_isimleri,
                    project=proje_adi,
                    max_depth=graph_depth,
                    max_nodes=graph_max_nodes,
                )
                if graph_text:
                    metin_parts.append(graph_text)
            except Exception as e:
                print(f"[SYMBOL GRAPH UYARISI] Bağlam çekme hatası: {e}")

        return "\n".join(metin_parts)

    # ── Arama ─────────────────────────────────────────────────────────
    def sembol_ara(self, sorgu: str, proje_adi: str = None, limit: int = 5):
        """
        Doğal dil talimatına göre en alakalı fonksiyon/class'ları bulur.
        coder_node bunu, worker'a 'MEVCUT KOD' ile birlikte ek bağlam olarak
        vermek için çağırır.
        """
        try:
            embedding = self._get_embedding(sorgu)
            where = {"proje_adi": proje_adi} if proje_adi else None
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            bulunanlar = []
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    bulunanlar.append({
                        "ozet": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                    })
            return bulunanlar
        except Exception as e:
            print(f"[PROJE BELLEK UYARISI] Sembol arama başarısız: {e}")
            return []

    def projeyi_tara(self, kok_dizin: str, proje_adi: str):
        """Bir proje klasörünü baştan sona tarar (ilk kurulum / manuel yenileme için)."""
        # B) Yapısal grafik toplu indeksleme (stale-index korumalı)
        try:
            self.graph.index_project(kok_dizin, proje_adi)
        except Exception as e:
            print(f"[SYMBOL GRAPH UYARISI] Toplu grafik indeksleme hatası: {e}")

        for kok, dizinler, dosyalar in os.walk(kok_dizin):
            dizinler[:] = [d for d in dizinler if d not in (".git", "__pycache__", "venv", ".venv", "node_modules")]
            for dosya in dosyalar:
                if dosya.endswith(".py"):
                    self.dosyayi_indexle(os.path.join(kok, dosya), proje_adi)
        print(f"[PROJE BELLEK]: '{proje_adi}' projesi tarandı ve indekslendi.")