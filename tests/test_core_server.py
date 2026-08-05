import pytest
from fastapi.testclient import TestClient

# Core Server API'sini içe aktar
from core_server import app, headless_ghost

client = TestClient(app)

def test_core_server_history():
    # Başlangıçta mesaj geçmişi boş veya default sistem mesajı olmalı
    response = client.get("/history")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)

def test_core_server_busy_state():
    # Ghost meşgulken yeni chat isteği atılırsa reddedilmeli
    headless_ghost.is_busy = True
    
    response = client.post("/chat", json={"message": "Merhaba"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "busy"
    
    # Test bittiğinde durumu düzelt
    headless_ghost.is_busy = False
