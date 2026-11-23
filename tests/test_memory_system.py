"""
tests/test_memory_system.py — Yeni Özet Hafızası, RAG Alaka Eşiği ve Dinamik L2 Bellek Testleri.
"""

from unittest.mock import MagicMock, patch
import pytest

from core.tool_registry import tool_registry
from hafıza.episodic_db import EpisodicDB
from hafıza.rag_hafıza import Bellek
from hafıza.project_memory import ProjectMemoryL2
from handler.command_handler import CommandHandler
from ai.llm import ChatLLM


# ── 1. gorev_bitti Tool Şeması Testi ─────────────────────────────────────────

def test_gorev_bitti_has_ozet_and_hafiza_notu():
    info = tool_registry.get_tool_info("gorev_bitti")
    assert info is not None
    schema = info["schema"]
    props = schema["function"]["parameters"]["properties"]
    assert "ozet" in props
    assert "hafiza_notu" in props
    required = schema["function"]["parameters"]["required"]
    assert "ozet" in required


# ── 2. Bellek.sorgula Mesafe Eşiği (Alaka Düzeyi) Testi ─────────────────────

def test_rag_sorgula_filters_by_max_distance(tmp_path):
    with patch("core.config.DB_DIR", str(tmp_path)):
        b = Bellek(collection_name="test_distance_col")
        
        # 3 döküman simüle edelim: mesafeler 0.2 (alakalı), 0.4 (alakalı), 0.8 (alakasız)
        fake_results = {
            "documents": [["alakali_1", "alakali_2", "alakasiz_3"]],
            "distances": [[0.20, 0.40, 0.85]],
        }
        with patch.object(b, "_get_embedding", return_value=[0.1] * 128), \
             patch.object(b.collection, "query", return_value=fake_results):
            
            # max_distance=0.45 varsayılanı ile alakasız olan elenmeli
            results = b.sorgula("test sorusu", limit=3, max_distance=0.45)
            assert "alakali_1" in results
            assert "alakali_2" in results
            assert "alakasiz_3" not in results
            assert len(results) == 2


def test_rag_sorgula_returns_empty_when_all_above_threshold(tmp_path):
    with patch("core.config.DB_DIR", str(tmp_path)):
        b = Bellek(collection_name="test_distance_col_2")
        fake_results = {
            "documents": [["cok_uzak_metin"]],
            "distances": [[0.75]],
        }
        with patch.object(b, "_get_embedding", return_value=[0.1] * 128), \
             patch.object(b.collection, "query", return_value=fake_results):
            
            results = b.sorgula("alakasiz soru", max_distance=0.45)
            assert results == []


# ── 3. Dinamik ProjectMemoryL2 Testi ─────────────────────────────────────────

def test_chat_llm_dynamic_l2_memory(tmp_path):
    # Geçici bir .ghost/project_memory.json oluştur
    proj_dir = tmp_path / "test_proj"
    proj_dir.mkdir()
    l2 = ProjectMemoryL2(str(proj_dir))
    l2.add_item("architecture", "FastAPI + React Vite Mimarisi")
    l2.add_item("constraints", "Port 8001 kullanılacak")

    mock_db = MagicMock()
    mock_db.son_aktif_projeyi_getir.return_value = {
        "proje_adi": "TestProj",
        "aktif_dizin": str(proj_dir),
    }

    with patch("hafıza.episodic_db.EpisodicDB", return_value=mock_db):
        llm = ChatLLM(model="qwen3.5:4b")
        dynamic_prompt = llm.guncel_sistem_promptu()
        assert "FastAPI + React Vite Mimarisi" in dynamic_prompt
        assert "Port 8001 kullanılacak" in dynamic_prompt


# ── 4. EpisodicDB gorev_ozeti_kaydet Testi ───────────────────────────────────

def test_episodic_db_gorev_ozetleri(tmp_path):
    with patch("core.config.DB_DIR", str(tmp_path)):
        db = EpisodicDB()
        ozet_id = db.gorev_ozeti_kaydet(
            ozet="İşlem tamamlandı patron",
            hafiza_notu="auth.py dosyasında JWT token süresi 3600 olarak ayarlandı.",
            proje_adi="TestProje",
        )
        assert ozet_id is not None

        kayitlar = db.son_gorev_ozetlerini_getir(limit=5, proje_adi="TestProje")
        assert len(kayitlar) == 1
        assert kayitlar[0]["ozet"] == "İşlem tamamlandı patron"
        assert "JWT token süresi" in kayitlar[0]["hafiza_notu"]
        assert kayitlar[0]["is_embedded"] == 0

        # embedded olarak işaretle
        db.gorev_ozetini_embedded_isaretle(ozet_id)
        kayitlar_sonrasi = db.son_gorev_ozetlerini_getir(limit=5, proje_adi="TestProje")
        assert kayitlar_sonrasi[0]["is_embedded"] == 1


# ── 5. command_handler.gorevi_sonlandir Pipeline Testi ───────────────────────

def test_command_handler_task_end_pipeline():
    mock_app = MagicMock()
    with patch("core.config.USE_DOCKER_CORE", False):
        ch = CommandHandler(mock_app)
        ch.episodic_db = MagicMock()
        ch.episodic_db.son_aktif_projeyi_getir.return_value = {"proje_adi": "OtoProje"}
        ch.episodic_db.gorev_ozeti_kaydet.return_value = 42

        ch.bellek = MagicMock()

        # gorevi_sonlandir'ı iki argümanla çağır
        ch.gorevi_sonlandir(
            nihai_cevap="Patron, Spotify hatasını çözdüm.",
            hafiza_notu="SpotifyManager sınıfına refresh_token akışı eklendi."
        )

        # 1. SQL'e kaydedildi mi?
        ch.episodic_db.gorev_ozeti_kaydet.assert_called_once_with(
            ozet="Patron, Spotify hatasını çözdüm.",
            hafiza_notu="SpotifyManager sınıfına refresh_token akışı eklendi.",
            proje_adi="OtoProje"
        )
        # 2. RAG'a embed edildi mi? (hafiza_notu tercih edilmeli)
        ch.bellek.bellege_yaz.assert_called_once()
        args, kwargs = ch.bellek.bellege_yaz.call_args
        assert "SpotifyManager sınıfına refresh_token akışı eklendi." in args[0]
        assert kwargs["metadata"]["proje_adi"] == "OtoProje"
        # 3. is_embedded işaretlendi mi?
        ch.episodic_db.gorev_ozetini_embedded_isaretle.assert_called_once_with(42)
