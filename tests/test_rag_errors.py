"""
tests/test_rag_errors.py — RAG hata yakalama, otomatik başlatma ve state hijyeni testleri.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from core.ollama_health import (
    format_embedding_error,
    ensure_ollama,
    is_ollama_alive,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
)
from hafıza.rag_hafıza import Bellek
from hafıza.proje_kod_bellek import ProjeKodBellek


# ── 1. format_embedding_error Testleri ────────────────────────────────────────

def test_format_connection_error():
    err = requests.exceptions.ConnectionError("Connection refused by host")
    formatted = format_embedding_error(err)
    assert "Ollama embedding servisine ulaşılamadı" in formatted
    assert OLLAMA_BASE_URL in formatted
    assert "\n" not in formatted  # Tek satırlık olmalı


def test_format_404_model_not_found():
    response_mock = MagicMock()
    response_mock.status_code = 404
    err = requests.exceptions.HTTPError("404 Client Error: Not Found", response=response_mock)
    formatted = format_embedding_error(err)
    assert EMBEDDING_MODEL in formatted
    assert "bulunamadı" in formatted
    assert "\n" not in formatted


def test_format_timeout():
    err = requests.exceptions.Timeout("Request timed out after 120s")
    formatted = format_embedding_error(err)
    assert "zaman aşımına uğradı" in formatted
    assert "\n" not in formatted


def test_format_generic_exception():
    err = RuntimeError("Bilinmeyen bir iç hata oluştu" + "x" * 200)
    formatted = format_embedding_error(err)
    assert len(formatted) <= 125
    assert formatted.endswith("...")
    assert "\n" not in formatted


# ── 2. ensure_ollama Testleri ────────────────────────────────────────────────

def test_ensure_ollama_when_already_alive():
    with patch("core.ollama_health.is_ollama_alive", return_value=True):
        err = ensure_ollama()
        assert err is None


def test_ensure_ollama_when_offline_and_boot_fails():
    with patch("core.ollama_health.is_ollama_alive", return_value=False), \
         patch("core.ollama_health._try_boot_ollama", return_value=False):
        err = ensure_ollama()
        assert err is not None
        assert "erişilemez" in err


def test_ensure_ollama_when_offline_and_boot_succeeds():
    with patch("core.ollama_health.is_ollama_alive", return_value=False), \
         patch("core.ollama_health._try_boot_ollama", return_value=True):
        err = ensure_ollama()
        assert err is None


# ── 3. Bellek.sorgula State Hijyeni ve son_hata Testleri ──────────────────────

def test_bellek_sorgula_captures_error(tmp_path):
    with patch("core.config.DB_DIR", str(tmp_path)):
        b = Bellek(collection_name="test_err_col")
        with patch.object(b, "_get_embedding", side_effect=requests.exceptions.ConnectionError("Connection failed")):
            results = b.sorgula("test sorusu")
            assert results == []
            assert b.son_hata is not None
            assert "Ollama embedding servisine ulaşılamadı" in b.son_hata


def test_bellek_sorgula_success_clears_error(tmp_path):
    with patch("core.config.DB_DIR", str(tmp_path)):
        b = Bellek(collection_name="test_succ_col")
        b.son_hata = "Eski bir hata"
        with patch.object(b, "_get_embedding", return_value=[0.1] * 128), \
             patch.object(b.collection, "query", return_value={"documents": [["hatırlanan metin"]]}):
            results = b.sorgula("test sorusu")
            assert results == ["hatırlanan metin"]
            assert b.son_hata is None


# ── 4. command_handler._enrich_with_memory Testleri ──────────────────────────

def test_command_handler_enriches_with_clean_error():
    from handler.command_handler import CommandHandler
    mock_app = MagicMock()
    mock_app._expanded = True

    with patch("core.config.USE_DOCKER_CORE", False):
        ch = CommandHandler(mock_app)
        ch.bellek = MagicMock()
        ch.bellek.son_hata = "Ollama embedding servisine ulaşılamadı (localhost:11434 bağlantı reddedildi)."
        ch.bellek.sorgula.return_value = []

        enriched = ch._enrich_with_memory("dosya.py içeriğini oku")
        assert "[SİSTEM UYARISI (Vektör Hafıza):" in enriched
        assert "Ollama embedding servisine ulaşılamadı" in enriched
        assert "Traceback" not in enriched  # Raw traceback çöplüğü olmamalı
        assert "Kullanıcı Komutu: dosya.py içeriğini oku" in enriched


# ── 5. ProjeKodBellek.baglam_metni_uret Hata Uyarısı Testi ───────────────────

def test_proje_kod_bellek_baglam_returns_warning_on_error(tmp_path):
    with patch("core.config.DB_DIR", str(tmp_path)):
        pkb = ProjeKodBellek(collection_name="test_pkb_err")
        with patch.object(pkb, "_get_embedding", side_effect=requests.exceptions.HTTPError(
            "404 Client Error", response=MagicMock(status_code=404)
        )):
            context = pkb.baglam_metni_uret("fonksiyonu bul", proje_adi="test_proje")
            assert "[PROJE HAFIZASI UYARISI:" in context
            assert "bulunamadı" in context
            assert "Traceback" not in context
