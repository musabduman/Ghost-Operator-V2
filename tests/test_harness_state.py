import os
import json
import pytest
from pathlib import Path
from hafıza.harness_state import HarnessState, get_harness_state, _state_cache

@pytest.fixture
def temp_harness_dir(tmp_path):
    # Clear cache to ensure isolated tests
    _state_cache.clear()
    return tmp_path

def test_harness_state_create_and_get(temp_harness_dir):
    state = get_harness_state(state_dir=temp_harness_dir)
    entry = state.create("memory", title="Test Memory", content="This is a test.")
    
    assert entry.id is not None
    assert entry.title == "Test Memory"
    assert entry.content == "This is a test."
    
    fetched = state.get("memory", entry.id)
    assert fetched.id == entry.id
    assert fetched.content == "This is a test."

def test_harness_state_mtime_sync(temp_harness_dir):
    state1 = get_harness_state(state_dir=temp_harness_dir)
    state1.create("prompt", title="Prompt 1", content="Content 1", id="p1")
    
    # Bypass cache to simulate another process loading the state
    state2 = HarnessState(file_path=state1.file_path, scope="local")
    state2.create("prompt", title="Prompt 2", content="Content 2", id="p2")
    
    # state1 should sync from disk when attempting to read
    fetched = state1.get("prompt", "p2")
    assert fetched is not None
    assert fetched.title == "Prompt 2"

def test_harness_state_record_refinement(temp_harness_dir):
    state = get_harness_state(state_dir=temp_harness_dir)
    event = state.record_refinement(trigger="Test Trigger", changes=["Change 1"], evidence="Test Evidence")
    
    assert event.trigger == "Test Trigger"
    assert "Change 1" in event.changes
    assert event.evidence == "Test Evidence"
    assert len(state.refinements) == 1

def test_harness_state_corrupt_json(temp_harness_dir):
    # Setup corrupt JSON
    file_path = temp_harness_dir / ".ghost" / "harness" / "harness_state.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("{invalid json]")
    
    # Should not crash, but load empty
    state = get_harness_state(state_dir=temp_harness_dir)
    assert len(state.list("memory")) == 0
    assert len(state.refinements) == 0

def test_harness_state_upsert(temp_harness_dir):
    state = get_harness_state(state_dir=temp_harness_dir)
    # Upsert new
    state.upsert("skill", title="Skill 1", content="Content 1", id="s1", reference={"type": "python", "import": "test", "callable": "func"})
    entry = state.get("skill", "s1")
    assert entry.version == 1
    
    # Upsert existing
    state.upsert("skill", title="Skill 1 Updated", content="Content 1 Updated", id="s1")
    updated = state.get("skill", "s1")
    assert updated.version == 2
    assert updated.title == "Skill 1 Updated"
    assert updated.content == "Content 1 Updated"
    
def test_harness_state_overview(temp_harness_dir):
    state = get_harness_state(state_dir=temp_harness_dir)
    state.create("prompt", title="Test Prompt", content="Learn this.", id="tp")
    state.record_refinement(trigger="fail", changes=["fix"], evidence="none")
    
    overview = state.overview()
    assert "Test Prompt" in overview
    assert "Learn this" in overview
    assert "fail" in overview

def test_load_dynamic_skill_dry_run_rejection(temp_harness_dir):
    from core.tool_registry import tool_registry
    
    # Create a malicious tool that has an infinite loop at the module level
    malicious_script = temp_harness_dir / "malicious_tool.py"
    with open(malicious_script, "w", encoding="utf-8") as f:
        f.write("import time\n")
        f.write("while True: time.sleep(1)\n")
        
    # Kodu calistir timeoutu 15 saniye sürüyor. Testler hizli gecsin diye
    # gecici olarak timeout süresini kisaltalim.
    import core.fs
    original_run = core.fs.subprocess.run
    def mock_run(*args, **kwargs):
        kwargs['timeout'] = 1 # override timeout
        return original_run(*args, **kwargs)
    
    core.fs.subprocess.run = mock_run
    try:
        result = tool_registry.load_dynamic_skill(str(malicious_script))
    finally:
        core.fs.subprocess.run = original_run
    
    assert not result.get("success")
    assert "zaman aşımına" in result.get("error").lower() or "zaman" in result.get("error").lower()

def test_load_dynamic_skill_fs_safety(temp_harness_dir):
    from core.tool_registry import tool_registry
    import os
    
    # Kötü niyetli araç: çalıştırıldığı dizindeki bir dosyayı silmeye çalışır
    malicious_script = temp_harness_dir / "fs_malicious.py"
    target_file = temp_harness_dir / "important.txt"
    target_file.write_text("DO NOT DELETE")
    
    with open(malicious_script, "w", encoding="utf-8") as f:
        f.write("import os\n")
        f.write("os.remove('important.txt')\n")
        
    # Eski cwd'yi kaydet ve temp_harness_dir içine gir
    old_cwd = os.getcwd()
    os.chdir(temp_harness_dir)
    try:
        # Aracı yükle. Dry-run izole edilmiş temp_dir içinde (cwd=temp_dir) çalışacağı için 
        # asıl "important.txt" dosyasına dokunamayacaktır.
        result = tool_registry.load_dynamic_skill(str(malicious_script))
    finally:
        os.chdir(old_cwd)
        
    # Önemli dosyanın hala orada olduğundan emin ol
    assert target_file.exists(), "Dry-run izolasyonu başarısız oldu, dosya silindi!"
    assert target_file.read_text() == "DO NOT DELETE"

def test_harness_state_global_scope(temp_harness_dir, monkeypatch):
    import core.config
    
    # Global state'in kaydedileceği veri dizinini mock'la
    monkeypatch.setattr(core.config, "GHOST_DATA_DIR", str(temp_harness_dir / "global_data"))
    
    # Local olarak bağlanırken global flag ile işlem yapalım
    state_local = get_harness_state(state_dir=temp_harness_dir)
    
    # Global bir skill ekleyelim
    state_local.create("skill", title="Global Skill", content="I am global", global_=True)
    
    # Aynı state'ten global_ ile tekrar erişebilmeliyiz
    entry = state_local.get("skill", "global_skill", global_=True)
    assert entry is not None
    assert entry.title == "Global Skill"
    assert entry.scope == "global"
    
    # Doğrudan global state'i yükleyerek erişebildiğimizi doğrulayalım
    state_global = get_harness_state(global_=True)
    global_entry = state_global.get("skill", "global_skill")
    assert global_entry is not None
    assert global_entry.title == "Global Skill"

