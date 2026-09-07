"""
hafıza/symbol_graph.py
Ghost Operator — İki Katmanlı Proje Belleği
  A) Semantic (ChromaDB, doğal dil araması)  — mevcut proje_kod_bellek.py bozulmadı
  B) Structural (SQLite, caller/callee/import/inheritance graph)  — YENİ bu dosya

Her sembol için tutulan metadata:
  project, file_path, module, symbol_name, symbol_type,
  class_name, parent_symbol, line_number, signature, docstring,
  imports, calls, called_by, inherits_from

Stale-index koruması: dosya hash'i saklanır, değişmemişse yeniden parse
edilmez. Değişmişse bu dosyanın eski tüm sembolleri temizlenir.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ── Config alanları (config.py'ye gerek duymadan da çalışabilir) ─────────────
def _default_graph_path() -> str:
    try:
        from core.config import DB_DIR
        return os.path.join(DB_DIR, "symbol_graph.db")
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Ghost_Data", "db", "symbol_graph.db")


# ── Veri sınıfı ───────────────────────────────────────────────────────────────
@dataclass
class SymbolNode:
    symbol_id: str            # unique: file_path::class_name::symbol_name::line
    project: str
    file_path: str
    module: str               # dosya yolundan türetilen modul adı
    symbol_name: str
    symbol_type: str          # FunctionDef | AsyncFunctionDef | ClassDef | Import
    class_name: str = ""      # hangi class içindeyse
    parent_symbol: str = ""   # iç-içe def için üst fonksiyon
    line_number: int = 0
    signature: str = ""
    docstring: str = ""
    imports: List[str] = field(default_factory=list)        # import edilen modüller
    calls: List[str] = field(default_factory=list)          # çağırdığı semboller
    called_by: List[str] = field(default_factory=list)      # bunu çağıran semboller
    inherits_from: List[str] = field(default_factory=list)  # miras aldığı class'lar


# ── AST Visitor ───────────────────────────────────────────────────────────────
class _SymbolVisitor(ast.NodeVisitor):
    """Tek bir dosyayı ziyaret ederek tüm sembol, import ve çağrı bilgilerini toplar."""

    def __init__(self, file_path: str, project: str, source: str):
        self.file_path = file_path
        self.project = project
        self.source = source
        self.module = _path_to_module(file_path)
        self.nodes: List[SymbolNode] = []
        self._imports: List[str] = []   # dosya düzeyinde importlar
        self._class_stack: List[str] = []   # iç içe class için
        self._func_stack: List[str] = []    # iç içe def için

    # ── Import topla ──────────────────────────────────────────────────────────
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self._imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        base = node.module or ""
        for alias in node.names:
            self._imports.append(f"{base}.{alias.name}" if base else alias.name)
        self.generic_visit(node)

    # ── Class ─────────────────────────────────────────────────────────────────
    def visit_ClassDef(self, node: ast.ClassDef):
        inherits = [_unparse(b) for b in node.bases]
        snode = SymbolNode(
            symbol_id=self._make_id(node.name, node.lineno),
            project=self.project,
            file_path=self.file_path,
            module=self.module,
            symbol_name=node.name,
            symbol_type="ClassDef",
            class_name=self._current_class(),
            parent_symbol=self._current_func(),
            line_number=node.lineno,
            signature=f"class {node.name}({', '.join(inherits)})" if inherits else f"class {node.name}",
            docstring=ast.get_docstring(node) or "",
            imports=list(self._imports),
            inherits_from=inherits,
        )
        self.nodes.append(snode)
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    # ── Function / AsyncFunction ───────────────────────────────────────────────
    def _visit_func(self, node):
        on_ek = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        args_str = _args_str(node.args)
        sig = f"{on_ek} {node.name}({args_str})"
        snode = SymbolNode(
            symbol_id=self._make_id(node.name, node.lineno),
            project=self.project,
            file_path=self.file_path,
            module=self.module,
            symbol_name=node.name,
            symbol_type=type(node).__name__,
            class_name=self._current_class(),
            parent_symbol=self._current_func(),
            line_number=node.lineno,
            signature=sig,
            docstring=ast.get_docstring(node) or "",
            imports=list(self._imports),
            calls=self._collect_calls(node),
        )
        self.nodes.append(snode)
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_FunctionDef = _visit_func
    visit_AsyncFunctionDef = _visit_func

    # ── Yardımcılar ───────────────────────────────────────────────────────────
    def _make_id(self, name: str, lineno: int) -> str:
        parts = [self.file_path, self._current_class(), name, str(lineno)]
        return "::".join(p for p in parts if p)

    def _current_class(self) -> str:
        return self._class_stack[-1] if self._class_stack else ""

    def _current_func(self) -> str:
        return self._func_stack[-1] if self._func_stack else ""

    def _collect_calls(self, func_node) -> List[str]:
        """Fonksiyon gövdesindeki tüm çağrıları (isim bazlı) döndürür."""
        calls: Set[str] = set()
        for child in ast.walk(func_node):
            if isinstance(child, ast.Call):
                name = _call_name(child)
                if name:
                    calls.add(name)
        return list(calls)


# ── Ana Graph Sınıfı ─────────────────────────────────────────────────────────
class SymbolGraph:
    """
    SQLite tabanlı yapısal (structural) sembol grafiği.
    İki aşamalı çalışır:
      1. index_file()   — tek dosyayı parse et, graph'a yaz
      2. get_context()  — verilen kök sembol(ler)den depth/limit ile komşuları getir
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_graph_path()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row   # ← satırları dict-like erişilebilir yap
        self._init_tables()

    # ── Tablo kurulumu ────────────────────────────────────────────────────────
    def _init_tables(self):
        c = self._conn
        c.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                symbol_id    TEXT PRIMARY KEY,
                project      TEXT,
                file_path    TEXT,
                module       TEXT,
                symbol_name  TEXT,
                symbol_type  TEXT,
                class_name   TEXT,
                parent_symbol TEXT,
                line_number  INTEGER,
                signature    TEXT,
                docstring    TEXT,
                imports      TEXT,    -- JSON list
                calls        TEXT,    -- JSON list
                inherits_from TEXT   -- JSON list
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS file_hashes (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT,
                project   TEXT
            )
        """)
        # Caller-callee ilişki tablosu (çağıran_id, çağrılan_sembol_adı)
        c.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                caller_id    TEXT,
                callee_name  TEXT,
                PRIMARY KEY (caller_id, callee_name)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_sym_project ON symbols(project)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sym_name ON symbols(symbol_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sym_file ON symbols(file_path)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_name)")
        c.commit()

    # ── Dosya indeksleme ──────────────────────────────────────────────────────
    def index_file(self, file_path: str, project: str) -> bool:
        """
        Dosyayı parse et. Hash aynıysa ATLA (stale-index koruması).
        Farklıysa eski sembolleri temizle, yenilerini yaz.
        Döndürür: True=indekslendi, False=hash aynı atlandı
        """
        file_path = str(Path(file_path).resolve())
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            print(f"[SYMBOL GRAPH] {file_path} okunamadı: {e}")
            return False

        new_hash = _sha256(source)
        cur = self._conn.execute(
            "SELECT file_hash FROM file_hashes WHERE file_path=?", (file_path,)
        )
        row = cur.fetchone()
        if row and row[0] == new_hash:
            return False   # değişmemiş

        # Eski semboller + çağrı ilişkilerini temizle
        self._clear_file(file_path)

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            print(f"[SYMBOL GRAPH] {file_path} parse hatası: {e}")
            return False

        visitor = _SymbolVisitor(file_path, project, source)
        visitor.visit(tree)

        for node in visitor.nodes:
            self._upsert_symbol(node)
            for callee in node.calls:
                self._conn.execute(
                    "INSERT OR REPLACE INTO calls(caller_id, callee_name) VALUES(?,?)",
                    (node.symbol_id, callee),
                )

        self._conn.execute(
            "INSERT OR REPLACE INTO file_hashes(file_path, file_hash, project) VALUES(?,?,?)",
            (file_path, new_hash, project),
        )
        self._conn.commit()
        return True

    def index_project(self, root_dir: str, project: str):
        """Tüm .py dosyalarını tarar (ilk kurulum veya tam yenileme için)."""
        root_dir = str(Path(root_dir).resolve())
        skip_dirs = {".git", "__pycache__", "venv", ".venv", "node_modules", ".pytest_cache"}
        changed = 0
        for kok, dizinler, dosyalar in os.walk(root_dir):
            dizinler[:] = [d for d in dizinler if d not in skip_dirs]
            for d in dosyalar:
                if d.endswith(".py"):
                    fpath = os.path.join(kok, d)
                    if self.index_file(fpath, project):
                        changed += 1
        print(f"[SYMBOL GRAPH] '{project}' — {changed} dosya güncellendi.")

    # ── Context / Graph traversal ─────────────────────────────────────────────
    def get_context(
        self,
        symbol_names: List[str],
        project: Optional[str] = None,
        max_depth: int = 2,
        max_nodes: int = 20,
    ) -> Dict[str, Any]:
        """
        Başlangıç sembollerinden derinlik limitiyle BFS yaparak
        tüm çağrı zincirini (caller + callee) toplar.
        Döndürür: { "nodes": [SymbolNode dict,...], "edges": [(from,to),...] }
        """
        visited_ids: Set[str] = set()
        result_nodes: List[Dict] = []
        edges: List[Tuple[str, str]] = []
        queue: List[Tuple[str, int]] = []  # (symbol_name, depth)

        for name in symbol_names:
            queue.append((name, 0))

        while queue and len(result_nodes) < max_nodes:
            current_name, depth = queue.pop(0)
            if depth > max_depth:
                continue

            rows = self._find_by_name(current_name, project)
            for row in rows:
                sid = row["symbol_id"]
                if sid in visited_ids:
                    continue
                visited_ids.add(sid)
                result_nodes.append(dict(row))

                if len(result_nodes) >= max_nodes:
                    break

                # Çağırdıkları (callees) → depth+1
                callees = self._get_callees(sid)
                for callee_name in callees:
                    edges.append((current_name, callee_name))
                    if depth + 1 <= max_depth:
                        queue.append((callee_name, depth + 1))

                # Kimin tarafından çağrılıyor (callers) → depth+1
                callers = self._get_callers(current_name)
                for caller_id, caller_name in callers:
                    edges.append((caller_name, current_name))
                    if caller_id not in visited_ids and depth + 1 <= max_depth:
                        queue.append((caller_name, depth + 1))

        return {"nodes": result_nodes, "edges": edges}

    def format_context_text(
        self,
        symbol_names: List[str],
        project: Optional[str] = None,
        max_depth: int = 2,
        max_nodes: int = 20,
    ) -> str:
        """
        get_context() çıktısını LLM prompt'una hazır okunabilir metne çevirir.
        Ağaç formatında, caller/callee ok'larıyla gösterir.
        """
        ctx = self.get_context(symbol_names, project=project, max_depth=max_depth, max_nodes=max_nodes)
        if not ctx["nodes"]:
            return ""

        lines = ["[YAPISAN SEMBOL GRAFİĞİ — Çağrı ve Bağımlılık İlişkileri]"]
        for n in ctx["nodes"]:
            loc = f"{os.path.basename(n['file_path'])}:{n['line_number']}"
            cls = f" [{n['class_name']}]" if n.get("class_name") else ""
            lines.append(f"  ▸ {n['signature']}{cls}  ({loc})")
            if n.get("docstring"):
                lines.append(f"      \"{n['docstring'][:80]}...\"" if len(n["docstring"]) > 80 else f"      \"{n['docstring']}\"")

        if ctx["edges"]:
            lines.append("")
            lines.append("  Çağrı İlişkileri:")
            seen_edges = set()
            for src, dst in ctx["edges"]:
                key = f"{src}→{dst}"
                if key not in seen_edges:
                    seen_edges.add(key)
                    lines.append(f"    {src} → {dst}")

        return "\n".join(lines)

    def find_symbol(self, name: str, project: Optional[str] = None) -> List[Dict]:
        """Tam sembol adıyla arama (test ve doğrudan sorgular için)."""
        return [dict(r) for r in self._find_by_name(name, project)]

    # ── Özel / Düşük seviye ──────────────────────────────────────────────────
    def _upsert_symbol(self, node: SymbolNode):
        self._conn.execute("""
            INSERT OR REPLACE INTO symbols VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            node.symbol_id,
            node.project,
            node.file_path,
            node.module,
            node.symbol_name,
            node.symbol_type,
            node.class_name,
            node.parent_symbol,
            node.line_number,
            node.signature,
            node.docstring,
            json.dumps(node.imports, ensure_ascii=False),
            json.dumps(node.calls, ensure_ascii=False),
            json.dumps(node.inherits_from, ensure_ascii=False),
        ))

    def _clear_file(self, file_path: str):
        self._conn.execute("DELETE FROM symbols WHERE file_path=?", (file_path,))
        old_ids = [
            r[0] for r in self._conn.execute(
                "SELECT symbol_id FROM symbols WHERE file_path=?", (file_path,)
            ).fetchall()
        ]
        if old_ids:
            placeholders = ",".join("?" * len(old_ids))
            self._conn.execute(f"DELETE FROM calls WHERE caller_id IN ({placeholders})", old_ids)
        self._conn.execute("DELETE FROM file_hashes WHERE file_path=?", (file_path,))
        self._conn.commit()

    def _find_by_name(self, name: str, project: Optional[str] = None):
        if project:
            return self._conn.execute(
                "SELECT * FROM symbols WHERE symbol_name=? AND project=?",
                (name, project)
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM symbols WHERE symbol_name=?", (name,)
        ).fetchall()

    def _get_callees(self, caller_id: str) -> List[str]:
        rows = self._conn.execute(
            "SELECT callee_name FROM calls WHERE caller_id=?", (caller_id,)
        ).fetchall()
        return [r[0] for r in rows]

    def _get_callers(self, callee_name: str) -> List[Tuple[str, str]]:
        """Verilen sembol adını çağıran caller_id'leri ve isimlerini döndürür."""
        rows = self._conn.execute(
            """SELECT c.caller_id, s.symbol_name
               FROM calls c
               LEFT JOIN symbols s ON s.symbol_id = c.caller_id
               WHERE c.callee_name=?""",
            (callee_name,)
        ).fetchall()
        return [(r[0], r[1] or r[0]) for r in rows]

    def close(self):
        self._conn.close()


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────
def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _path_to_module(file_path: str) -> str:
    p = Path(file_path)
    return p.stem  # basit: dosya adından

def _unparse(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return getattr(node, "id", "?")

def _args_str(args: ast.arguments) -> str:
    all_args = [a.arg for a in (args.posonlyargs + args.args)]
    if args.vararg:
        all_args.append(f"*{args.vararg.arg}")
    if args.kwarg:
        all_args.append(f"**{args.kwarg.arg}")
    return ", ".join(all_args)

def _call_name(node: ast.Call) -> Optional[str]:
    """ast.Call'dan çağrılan fonksiyon/metod adını döndürür."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


# ── Singleton ─────────────────────────────────────────────────────────────────
_graph_instance: Optional[SymbolGraph] = None

def get_symbol_graph(db_path: Optional[str] = None) -> SymbolGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = SymbolGraph(db_path)
    return _graph_instance
