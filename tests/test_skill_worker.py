import pytest
import time
import requests
import multiprocessing
import os
import uvicorn
from core.skill_worker import app

def run_worker():
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="error")

@pytest.fixture(scope="module")
def skill_worker_process():
    p = multiprocessing.Process(target=run_worker, daemon=True)
    p.start()
    time.sleep(2) # Sunucunun başlaması için bekle
    yield p
    p.terminate()
    p.join()

def test_skill_worker_success(skill_worker_process, tmp_path):
    # Basit bir başarılı script
    script_path = tmp_path / "basit.py"
    script_path.write_text("def topla(a, b):\n    return a + b\n")
    
    payload = {
        "dosya": str(script_path),
        "fonksiyon": "topla",
        "parametreler": {"a": 3, "b": 4}
    }
    
    res = requests.post("http://127.0.0.1:8002/execute", json=payload)
    assert res.status_code == 200
    assert res.json()["basarili"] == True
    assert res.json()["sonuc"] == "7"

def test_skill_worker_crash(skill_worker_process, tmp_path):
    # Hata fırlatan script
    script_path = tmp_path / "crasher.py"
    script_path.write_text("def patla():\n    raise ValueError('Bum')\n")
    
    payload = {
        "dosya": str(script_path),
        "fonksiyon": "patla"
    }
    
    res = requests.post("http://127.0.0.1:8002/execute", json=payload)
    assert res.status_code == 200
    assert res.json()["basarili"] == False
    assert "Bum" in res.json()["hata"]

def test_skill_worker_timeout_watchdog(skill_worker_process, tmp_path):
    # Sonsuz döngü simülasyonu
    script_path = tmp_path / "loop.py"
    script_path.write_text("import time\ndef sonsuz():\n    time.sleep(3)\n")
    
    payload = {
        "dosya": str(script_path),
        "fonksiyon": "sonsuz"
    }
    
    # Watchdog'u simüle et: 1 saniye timeout
    try:
        requests.post("http://127.0.0.1:8002/execute", json=payload, timeout=1)
        pytest.fail("Timeout fırlatılmalıydı")
    except requests.exceptions.Timeout:
        assert True
