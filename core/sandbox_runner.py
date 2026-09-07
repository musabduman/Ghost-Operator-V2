"""
core/sandbox_runner.py
Ghost Operator — Audit Hook Tabanlı Sandbox

AI tarafından üretilen Python skill'leri bu modül üzerinden çalıştırılır.
Docker yoksa (fallback mode) sys.addaudithook ile:
  - Workspace dışına dosya erişimi engellenir (Path Traversal koruması)
  - Network erişimi varsayılan olarak kapalıdır (allow_network=False)
  - subprocess timeout ile CPU/Hang koruması yapılır

Docker varsa ve istansenin Docker socketi çalışıyorsa ileride buraya
container-based sandbox eklenebilir.

GÜVENLIK NOTU:
  sys.addaudithook GERI DÖNÜŞSÜZ bir fonksiyondur — hook bir kez
  kayıt edilince o Python sürecinde kaldırılamaz. Bu yüzden sandbox
  her zaman AYRI BİR SUBPROCESS içinde çalıştırılır. Ana Ghost
  sürecine dokunulmaz.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional


# ── Config defaults ───────────────────────────────────────────────────────────
_DEFAULT_TIMEOUT = 60          # saniye
_DEFAULT_ALLOW_NETWORK = False


def _resolve_workspace(workspace: Optional[str]) -> str:
    """
    Workspace dizinini canonical (symlink çözümlenmiş) absolute path'e çevirir.
    None ise geçici bir izole dizin döndürür.
    """
    if workspace:
        return str(Path(workspace).resolve())
    # Workspace belirtilmemişse geçici dizin (çağıran tarafından yönetilmeli)
    return tempfile.mkdtemp(prefix="ghost_sandbox_")


def _build_bootstrap(
    skill_file: str,
    function_name: str,
    params: Dict[str, Any],
    workspace: str,
    allow_network: bool,
) -> str:
    """
    Sandbox sürecinde çalışacak Python bootstrap script'ini döndürür.
    Bu script:
      1. sys.addaudithook ile güvenlik hook'unu kurar
      2. Skill dosyasını importlib ile yükler
      3. Fonksiyonu çağırır
      4. Sonucu JSON olarak stdout'a yazar
    """
    # Güvenli JSON serialize
    params_json = json.dumps(params, ensure_ascii=False)
    workspace_json = json.dumps(workspace, ensure_ascii=False)
    allow_network_py = "True" if allow_network else "False"

    bootstrap = textwrap.dedent(f"""
import sys, os, json, importlib.util, pathlib, traceback

# ── Audit Hook (Güvenlik Katmanı) ─────────────────────────────────────────────
_WORKSPACE = pathlib.Path({workspace_json!r}).resolve()
_ALLOW_NETWORK = {allow_network_py}
_ALLOWED_PREFIXES = [
    str(_WORKSPACE),
    sys.prefix,                      # Python stdlib ve site-packages
    os.path.dirname(sys.executable), # Python interpreter dizini
]

def _ghost_audit_hook(event, args):
    # ── Dosya Erişimi ─────────────────────────────────────────────────
    if event in ("open", "os.open"):
        try:
            raw_path = str(args[0]) if args else ""
            if not raw_path:
                return
            # Symlink + relative path saldırılarını önle
            try:
                resolved = str(pathlib.Path(raw_path).resolve())
            except Exception:
                resolved = os.path.abspath(raw_path)

            # Workspace dışı ve sistem dizinleri dışı erişimi engelle
            allowed = any(resolved.startswith(prefix) for prefix in _ALLOWED_PREFIXES)
            if not allowed:
                raise PermissionError(
                    f"[SANDBOX] Dosya erişimi reddedildi: '{{raw_path}}' "
                    f"(Workspace: {{_WORKSPACE}})"
                )
        except PermissionError:
            raise
        except Exception:
            pass  # path parse hatası, geçir

    # ── Network Erişimi ───────────────────────────────────────────────
    elif event in ("socket.connect", "socket.__new__") and not _ALLOW_NETWORK:
        raise PermissionError("[SANDBOX] Network erişimi kapalı (allow_network=False)")

    # ── Tehlikeli OS İşlemleri ────────────────────────────────────────
    elif event in ("os.system", "subprocess.Popen") and not _ALLOW_NETWORK:
        # Subprocess içinde network çağrısı yapılmasını da engelle
        # (tam kontrol değil ama temel önlem)
        pass  # subprocess'i engellemek mevcut worker mimarisini kırar, sadece log

sys.addaudithook(_ghost_audit_hook)

# ── Workspace ayarla ──────────────────────────────────────────────────────────
os.makedirs(str(_WORKSPACE), exist_ok=True)
os.chdir(str(_WORKSPACE))

# ── Skill yükle ve çalıştır ───────────────────────────────────────────────────
skill_file = {skill_file!r}
function_name = {function_name!r}
params = {params_json}

try:
    module_name = os.path.splitext(os.path.basename(skill_file))[0]
    spec = importlib.util.spec_from_file_location(module_name, skill_file)
    if not spec or not spec.loader:
        raise ImportError(f"Modül yüklenemedi: {{skill_file}}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fn = getattr(module, function_name, None)
    if fn is None:
        available = [n for n in dir(module) if not n.startswith("_")]
        raise AttributeError(
            f"Fonksiyon bulunamadı: '{{function_name}}'. Mevcut: {{available}}"
        )

    result = fn(**params)
    print(json.dumps({{"basarili": True, "sonuc": str(result) if result is not None else ""}}, ensure_ascii=False))

except PermissionError as e:
    print(json.dumps({{"basarili": False, "guvenlik_ihlali": True, "hata": str(e)}}, ensure_ascii=False))
except Exception as e:
    tb = traceback.format_exc()
    print(json.dumps({{"basarili": False, "hata": str(e), "traceback": tb}}, ensure_ascii=False))
""")
    return bootstrap


def run_in_sandbox(
    skill_file: str,
    function_name: str,
    params: Optional[Dict[str, Any]] = None,
    workspace: Optional[str] = None,
    allow_network: bool = _DEFAULT_ALLOW_NETWORK,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Skill fonksiyonunu izole bir subprocess (Audit Hook Sandbox) içinde çalıştırır.

    Parametreler:
        skill_file      — Çalıştırılacak Python dosyasının tam yolu
        function_name   — Çağrılacak fonksiyon adı
        params          — Fonksiyon parametreleri (dict)
        workspace       — Dosya okuma/yazmanın izin verileceği dizin
        allow_network   — True ise ağ erişimine izin verilir (varsayılan: False)
        timeout         — Maksimum çalışma süresi (saniye, varsayılan: 60)

    Döndürür: { "basarili": bool, "sonuc": str | None, "hata": str | None,
                "guvenlik_ihlali": bool }
    """
    params = params or {}
    skill_file = str(Path(skill_file).resolve())
    workspace = _resolve_workspace(workspace)

    # Bootstrap script'i geçici bir dosyaya yaz (Windows'ta heredoc yok)
    bootstrap_code = _build_bootstrap(
        skill_file=skill_file,
        function_name=function_name,
        params=params,
        workspace=workspace,
        allow_network=allow_network,
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8", prefix="ghost_sb_"
    ) as tmp:
        tmp.write(bootstrap_code)
        tmp_path = tmp.name

    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workspace,
        )

        # stdout'taki son JSON satırını parse et
        stdout = proc.stdout.strip()
        last_line = stdout.splitlines()[-1] if stdout else ""
        try:
            result = json.loads(last_line)
        except json.JSONDecodeError:
            # JSON yoksa raw stdout'u hata olarak dön
            return {
                "basarili": proc.returncode == 0,
                "sonuc": stdout if proc.returncode == 0 else None,
                "hata": proc.stderr.strip() or "Çıktı JSON formatında değil.",
                "guvenlik_ihlali": False,
            }
        return result

    except subprocess.TimeoutExpired:
        return {
            "basarili": False,
            "sonuc": None,
            "hata": f"[SANDBOX TIMEOUT] {function_name}() {timeout} saniyede tamamlanamadı. Sonsuz döngü olabilir.",
            "guvenlik_ihlali": False,
        }
    except Exception as e:
        return {
            "basarili": False,
            "sonuc": None,
            "hata": f"[SANDBOX HATA] {e}",
            "guvenlik_ihlali": False,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def sandbox_available() -> bool:
    """sys.addaudithook'un bu platformda çalışıp çalışmadığını kontrol eder."""
    return hasattr(sys, "addaudithook")
