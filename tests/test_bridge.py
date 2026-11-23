import os
import json
import pytest
from fastapi.testclient import TestClient

# Local Bridge API'sini içe aktar
from local_bridge.main import app, check_permission, base_dir
from core.config import GHOST_TOKEN

client = TestClient(app)
client.headers.update({"X-Ghost-Token": GHOST_TOKEN})

def test_check_permission_default():
    # Fail-closed: permissions.json yoksa veya araç listede yoksa False dönmeli
    assert check_permission("herhangi_bir_arac") == False

def test_execute_tool_unauthorized(tmp_path, monkeypatch):
    # Geçici bir permissions.json oluşturup, belirli bir aracı yasaklayalım
    temp_perm_file = tmp_path / "permissions.json"
    temp_perm_file.write_text(json.dumps({"gizli_arac": False}))
    
    # check_permission fonksiyonunun okuduğu dosya yolunu mock'la (değiştir)
    monkeypatch.setattr("local_bridge.main.os.path.join", lambda *args: str(temp_perm_file))
    
    # API'ye istek at
    response = client.post("/execute", json={"tool_adi": "gizli_arac", "parametreler": {}})
    
    assert response.status_code == 200
    data = response.json()
    assert data["basarili"] == False
    assert "GÜVENLİK ENGELİ" in data["mesaj"]

def test_execute_tool_authorized_but_unknown(monkeypatch):
    # İzni olan ama sistemde tanımlı olmayan bir araç (404 vermeli)
    monkeypatch.setattr("local_bridge.main.check_permission", lambda tool: True)
    response = client.post("/execute", json={"tool_adi": "olmayan_arac", "parametreler": {}})
    assert response.status_code == 404
    assert "Bilinmeyen masaüstü aracı" in response.json()["detail"]

def test_verify_token_hmac():
    # Geçersiz token ile 403 alınmalı
    bad_client = TestClient(app)
    bad_client.headers.update({"X-Ghost-Token": "hatali_token_12345"})
    res = bad_client.post("/execute", json={"tool_adi": "ekran_goruntusu", "parametreler": {}})
    assert res.status_code == 403
