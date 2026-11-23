"""
tests/test_tool_naming.py
Bridge ve Core arasındaki araç isim uyumluluğunu doğrulayan testler.
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from local_bridge.main import app
from core.config import GHOST_TOKEN
from core.tool_registry import (
    TOOL_EKRAN_GORUNTUSU,
    TOOL_WHATSAPP_EKRANI_OKU,
    TOOL_WHATSAPP_MESAJ_GONDER,
    TOOL_BROWSER_SEARCH,
    TOOL_KODU_CALISTIR,
    TOOL_UYGULAMA_AC,
    BRIDGE_TOOLS,
)

client = TestClient(app)
client.headers.update({"X-Ghost-Token": GHOST_TOKEN})


def test_bridge_tool_names_constants():
    """Tüm köprü araçlarının kanonik isimleri registry ile uyumlu olmalı."""
    assert TOOL_EKRAN_GORUNTUSU == "ekran_goruntusu"
    assert TOOL_WHATSAPP_EKRANI_OKU == "whatsapp_ekrani_oku"
    assert TOOL_WHATSAPP_MESAJ_GONDER == "whatsapp_mesaj_gonder"
    assert TOOL_BROWSER_SEARCH == "browser_search"
    assert TOOL_KODU_CALISTIR == "kodu_calistir"
    assert TOOL_UYGULAMA_AC == "uygulama_ac"


def test_command_handler_does_not_use_stale_tool_names():
    """command_handler.py içinde eski/hatalı bridge araç isimleri bulunmamalı."""
    from pathlib import Path
    handler_code = Path("handler/command_handler.py").read_text(encoding="utf-8")
    
    assert "ekran_goruntusu_al" not in handler_code, (
        "command_handler.py içinde eski 'ekran_goruntusu_al' ismi tespit edildi! "
        "'ekran_goruntusu' kullanılmalı."
    )
    assert '"tool_adi": "whatsapp_ekrani_yorumla"' not in handler_code, (
        "command_handler.py içinde bridge'e 'whatsapp_ekrani_yorumla' gönderiliyor! "
        "'whatsapp_ekrani_oku' kullanılmalı."
    )


def test_bridge_recognizes_canonical_tools(monkeypatch):
    """Local bridge kanonik araçların hiçbirine 404 (bilinmeyen araç) dönmemeli."""
    # İzin kontrolünü True yap ve dış servisleri mock'la
    monkeypatch.setattr("local_bridge.main.check_permission", lambda tool: True)
    monkeypatch.setattr("local_bridge.main.minimax_vision_analiz", lambda *args, **kw: (True, "", "ok"))
    monkeypatch.setattr("local_bridge.main.whatsapp_mesaj_gonder", lambda *args, **kw: "ok")
    monkeypatch.setattr("local_bridge.main.whatsapp_ekrani_yorumla", lambda *args, **kw: "ok")
    monkeypatch.setattr("local_bridge.main.browser_google_search", lambda *args, **kw: "ok")
    monkeypatch.setattr("local_bridge.main.kodu_calistir", lambda *args, **kw: {"basarili": True})
    
    # PIL ekran görüntüsünü mock'la
    mock_img = MagicMock()
    mock_img.save = MagicMock()
    monkeypatch.setattr("PIL.ImageGrab.grab", lambda **kw: mock_img)

    for tool_name in BRIDGE_TOOLS:
        params = {}
        if tool_name == "uygulama_ac":
            params = {"yol": "non_existent_app"}
        response = client.post("/execute", json={"tool_adi": tool_name, "parametreler": params})
        # 404 = Bilinmeyen masaüstü aracı. Kanonik hiçbir araç 404 almamalı.
        assert response.status_code != 404, (
            f"Kanonik araç '{tool_name}' Local Bridge tarafından tanınmadı (404 aldı)!"
        )
