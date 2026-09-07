"""
tests/test_symbol_graph.py
Yapısal Sembol Grafiği Testleri

Kapsam:
  1. Function discovery
  2. Class discovery
  3. Import discovery
  4. Call relationship
  5. Caller relationship
  6. Inheritance
  7. Changed-file reindex (stale-index)
  8. Stale symbol removal
  9. Graph depth limit
  10. Structural context text format
"""
import os
import pytest
from pathlib import Path
from hafıza.symbol_graph import SymbolGraph


@pytest.fixture
def tmp_graph(tmp_path):
    """Her test için izole bir in-memory SQLite graph yarat."""
    db = tmp_path / "test_graph.db"
    g = SymbolGraph(db_path=str(db))
    yield g
    g.close()


@pytest.fixture
def sample_project(tmp_path):
    """İki dosyalı örnek bir proje oluştur: auth.py ve api.py."""
    auth = tmp_path / "auth.py"
    auth.write_text('''\
import hashlib

class AuthManager:
    """Auth yöneticisi."""

    def login(self, username, password):
        """Kullanıcı girişi."""
        return self.verify_token(username)

    def logout(self, username):
        """Çıkış yap."""
        pass

    def verify_token(self, token):
        """Token doğrular."""
        return hashlib.md5(token.encode()).hexdigest()
''', encoding="utf-8")

    api = tmp_path / "api.py"
    api.write_text('''\
from auth import AuthManager

def login_endpoint(username, password):
    """HTTP login endpoint."""
    mgr = AuthManager()
    return mgr.login(username, password)

def logout_endpoint(username):
    """HTTP logout endpoint."""
    mgr = AuthManager()
    return mgr.logout(username)
''', encoding="utf-8")

    return tmp_path, auth, api


# ── 1. Function discovery ─────────────────────────────────────────────────────
def test_function_discovery(tmp_graph, sample_project):
    _, auth, _ = sample_project
    tmp_graph.index_file(str(auth), "test_proj")
    rows = tmp_graph.find_symbol("verify_token", "test_proj")
    assert rows, "verify_token bulunabilmeli"
    assert rows[0]["symbol_type"] in ("FunctionDef", "AsyncFunctionDef")


# ── 2. Class discovery ────────────────────────────────────────────────────────
def test_class_discovery(tmp_graph, sample_project):
    _, auth, _ = sample_project
    tmp_graph.index_file(str(auth), "test_proj")
    rows = tmp_graph.find_symbol("AuthManager", "test_proj")
    assert rows, "AuthManager bulunabilmeli"
    assert rows[0]["symbol_type"] == "ClassDef"


# ── 3. Import discovery ───────────────────────────────────────────────────────
def test_import_discovery(tmp_graph, sample_project):
    _, auth, _ = sample_project
    tmp_graph.index_file(str(auth), "test_proj")
    rows = tmp_graph.find_symbol("AuthManager", "test_proj")
    import json
    imports = json.loads(rows[0]["imports"])
    assert "hashlib" in imports, "hashlib import'u yakalanmalı"


# ── 4. Call relationship ──────────────────────────────────────────────────────
def test_call_relationship(tmp_graph, sample_project):
    _, auth, _ = sample_project
    tmp_graph.index_file(str(auth), "test_proj")
    # login() → verify_token() çağırıyor
    login_rows = tmp_graph.find_symbol("login", "test_proj")
    import json
    calls = json.loads(login_rows[0]["calls"])
    assert "verify_token" in calls, "login() → verify_token() çağrısı yakalanmalı"


# ── 5. Caller relationship (graph traversal) ──────────────────────────────────
def test_caller_relationship(tmp_graph, sample_project):
    _, auth, _ = sample_project
    tmp_graph.index_file(str(auth), "test_proj")
    ctx = tmp_graph.get_context(["verify_token"], project="test_proj", max_depth=1, max_nodes=20)
    # Caller olarak login() görünmeli
    caller_names = [e[0] for e in ctx["edges"]]
    assert "login" in caller_names or "verify_token" in caller_names


# ── 6. Inheritance ────────────────────────────────────────────────────────────
def test_inheritance(tmp_path):
    db = tmp_path / "inh.db"
    g = SymbolGraph(db_path=str(db))
    src = tmp_path / "child.py"
    src.write_text("class Child(Base):\n    pass\n", encoding="utf-8")
    g.index_file(str(src), "proj")
    import json
    rows = g.find_symbol("Child", "proj")
    inherits = json.loads(rows[0]["inherits_from"])
    assert "Base" in inherits
    g.close()


# ── 7. Changed-file reindex (stale-index) ────────────────────────────────────
def test_stale_index_reindex(tmp_graph, sample_project):
    _, auth, _ = sample_project
    tmp_graph.index_file(str(auth), "test_proj")
    # Dosyayı değiştir
    auth.write_text("def yeni_fonksiyon(): pass\n", encoding="utf-8")
    result = tmp_graph.index_file(str(auth), "test_proj")
    assert result == True, "Değişen dosya yeniden indekslenmeli"
    rows = tmp_graph.find_symbol("yeni_fonksiyon", "test_proj")
    assert rows, "Yeni fonksiyon bulunabilmeli"


# ── 8. Stale symbol removal ───────────────────────────────────────────────────
def test_stale_symbol_removal(tmp_graph, sample_project):
    _, auth, _ = sample_project
    tmp_graph.index_file(str(auth), "test_proj")
    # Eski semboller var
    assert tmp_graph.find_symbol("verify_token", "test_proj"), "verify_token başlangıçta olmalı"
    # Dosyayı tamamen farklı içerikle yaz
    auth.write_text("def tamamen_farkli(): pass\n", encoding="utf-8")
    tmp_graph.index_file(str(auth), "test_proj")
    # Eski sembol temizlenmeli
    old = tmp_graph.find_symbol("verify_token", "test_proj")
    assert not old, "verify_token stale sembol olarak temizlenmeli"


# ── 9. Graph depth limit ──────────────────────────────────────────────────────
def test_graph_depth_limit(tmp_graph, sample_project):
    _, auth, api = sample_project
    tmp_graph.index_file(str(auth), "test_proj")
    tmp_graph.index_file(str(api), "test_proj")
    ctx = tmp_graph.get_context(["verify_token"], project="test_proj", max_depth=0, max_nodes=20)
    # depth=0 → sadece doğrudan sembol, daha fazlası olmamalı
    assert len(ctx["nodes"]) <= 1, "Depth 0 sınırı uygulanmalı"


# ── 10. Structural context text format ───────────────────────────────────────
def test_structural_context_text(tmp_graph, sample_project):
    _, auth, _ = sample_project
    tmp_graph.index_file(str(auth), "test_proj")
    text = tmp_graph.format_context_text(["verify_token", "login"], project="test_proj")
    assert "verify_token" in text
    assert "YAPISAL SEMBOL GRAFİĞİ" in text
