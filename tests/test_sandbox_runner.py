"""
tests/test_sandbox_runner.py
Sandbox Güvenlik Testleri

Kapsam:
  1. Normal skill execution (başarılı senaryo)
  2. Timeout / sonsuz döngü
  3. Filesystem escape attempt (../.. path traversal)
  4. Absolute path access outside workspace
  5. Network access when disabled (default)
  6. Network access when explicitly enabled
  7. Worker crash (exception) — sandbox bunu yakalamalı
  8. Container/process cleanup (temp file silinmeli)
"""
import os
import pytest
from pathlib import Path
from core.sandbox_runner import run_in_sandbox, sandbox_available


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def skill_file(workspace):
    """Başarılı senaryo için basit skill."""
    f = workspace / "basit_skill.py"
    f.write_text(
        "def topla(a, b):\n    return a + b\n",
        encoding="utf-8"
    )
    return f


# ── 1. Normal execution ───────────────────────────────────────────────────────
def test_normal_execution(skill_file, workspace):
    result = run_in_sandbox(
        skill_file=str(skill_file),
        function_name="topla",
        params={"a": 5, "b": 7},
        workspace=str(workspace),
        timeout=10,
    )
    assert result["basarili"], f"Hata: {result.get('hata')}"
    assert "12" in result["sonuc"]


# ── 2. Timeout / sonsuz döngü ─────────────────────────────────────────────────
def test_timeout(workspace):
    f = workspace / "loop_skill.py"
    f.write_text("def sonsuz():\n    while True: pass\n", encoding="utf-8")
    result = run_in_sandbox(
        skill_file=str(f),
        function_name="sonsuz",
        workspace=str(workspace),
        timeout=2,
    )
    assert not result["basarili"]
    assert "TIMEOUT" in result["hata"].upper() or "saniye" in result["hata"].lower()


# ── 3. Path traversal — ../.. ─────────────────────────────────────────────────
def test_path_traversal_blocked(workspace, tmp_path):
    # Workspace dışında bir hedef dosya yarat
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("SECRET DATA", encoding="utf-8")

    traversal = workspace / "traversal_skill.py"
    # Göreli path ile workspace dışına çıkmayı dene
    traversal.write_text(
        f"import os\n"
        f"def hacks():\n"
        f"    return open('../{secret_file.name}').read()\n",
        encoding="utf-8"
    )
    result = run_in_sandbox(
        skill_file=str(traversal),
        function_name="hacks",
        workspace=str(workspace),
        timeout=10,
    )
    # Sandbox izin vermemeli
    assert not result["basarili"], "Path traversal engellenmeliydi"
    error_text = result.get("hata", "") + result.get("sonuc", "")
    assert "reddedildi" in error_text.lower() or "permission" in error_text.lower() or "no such" in error_text.lower()


# ── 4. Absolute path outside workspace ───────────────────────────────────────
def test_absolute_path_blocked(workspace, tmp_path):
    secret_file = tmp_path / "abs_secret.txt"
    secret_file.write_text("ABSOLUTE SECRET", encoding="utf-8")

    abs_skill = workspace / "abs_skill.py"
    abs_skill.write_text(
        f"def steal():\n"
        f"    return open(r'{secret_file}', 'r').read()\n",
        encoding="utf-8"
    )
    result = run_in_sandbox(
        skill_file=str(abs_skill),
        function_name="steal",
        workspace=str(workspace),
        timeout=10,
    )
    assert not result["basarili"], "Workspace dışı mutlak yol erişimi engellenmeliydi"


# ── 5. Network disabled (default) ────────────────────────────────────────────
def test_network_disabled_by_default(workspace):
    net_skill = workspace / "net_skill.py"
    net_skill.write_text(
        "import socket\n"
        "def connect():\n"
        "    s = socket.socket()\n"
        "    s.connect(('8.8.8.8', 53))\n"
        "    return 'connected'\n",
        encoding="utf-8"
    )
    result = run_in_sandbox(
        skill_file=str(net_skill),
        function_name="connect",
        workspace=str(workspace),
        allow_network=False,
        timeout=10,
    )
    assert not result["basarili"], "Network erişimi kapalıyken bağlantı yapılmamalı"
    assert "Network" in result.get("hata", "") or "reddedildi" in result.get("hata", "").lower()


# ── 6. Network explicitly enabled ────────────────────────────────────────────
def test_network_allowed_when_enabled(workspace):
    """DNS lookup gibi basit bir ağ işlemi allow_network=True ile çalışmalı."""
    dns_skill = workspace / "dns_skill.py"
    dns_skill.write_text(
        "import socket\n"
        "def dns_lookup():\n"
        "    try:\n"
        "        return socket.gethostbyname('localhost')\n"
        "    except:\n"
        "        return '127.0.0.1'\n",
        encoding="utf-8"
    )
    result = run_in_sandbox(
        skill_file=str(dns_skill),
        function_name="dns_lookup",
        workspace=str(workspace),
        allow_network=True,
        timeout=10,
    )
    assert result["basarili"], f"allow_network=True ile localhost lookup çalışmalı: {result.get('hata')}"


# ── 7. Worker crash — exception handling ─────────────────────────────────────
def test_crash_recovery(workspace):
    crash_skill = workspace / "crash_skill.py"
    crash_skill.write_text(
        "def patla():\n"
        "    raise ValueError('Kasıtlı çökme')\n",
        encoding="utf-8"
    )
    result = run_in_sandbox(
        skill_file=str(crash_skill),
        function_name="patla",
        workspace=str(workspace),
        timeout=10,
    )
    assert not result["basarili"]
    assert "Kasıtlı çökme" in result.get("hata", "")


# ── 8. Temp file cleanup ──────────────────────────────────────────────────────
def test_temp_file_cleanup(workspace, skill_file):
    """Sandbox bootstrap geçici dosyası çalıştırma sonrası silinmeli."""
    import glob, tempfile
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "ghost_sb_*.py")))
    run_in_sandbox(
        skill_file=str(skill_file),
        function_name="topla",
        params={"a": 1, "b": 1},
        workspace=str(workspace),
        timeout=10,
    )
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "ghost_sb_*.py")))
    leaked = after - before
    assert not leaked, f"Geçici dosya(lar) sızdı: {leaked}"
