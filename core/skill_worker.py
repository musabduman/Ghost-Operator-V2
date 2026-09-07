import sys
import os
import importlib.util
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import traceback
import json
from pathlib import Path

app = FastAPI(title="Ghost Skill Worker", description="İzole yetenek çalıştırma ortamı")

class ExecutionRequest(BaseModel):
    dosya: str
    fonksiyon: str
    parametreler: dict = {}
    aktif_proje: str = None
    allow_network: bool = False  # varsayılan: network kapalı

@app.post("/execute")
def execute_skill(req: ExecutionRequest):
    # Workspace: aktif proje dizini ya da dosyanın bulunduğu klasör
    workspace = req.aktif_proje if req.aktif_proje and os.path.isdir(req.aktif_proje) else str(Path(req.dosya).parent)
    
    try:
        from core.sandbox_runner import run_in_sandbox, sandbox_available
        
        if sandbox_available():
            # Audit Hook Sandbox (tercih edilen)
            result = run_in_sandbox(
                skill_file=req.dosya,
                function_name=req.fonksiyon,
                params=req.parametreler or {},
                workspace=workspace,
                allow_network=req.allow_network,
                timeout=60,
            )
            return result
        else:
            # Fallback: temel subprocess (audit hook yoksa — nadir)
            return _fallback_execute(req, workspace)
            
    except Exception as e:
        tb = traceback.format_exc()
        return {"basarili": False, "hata": f"Worker iç hatası: {e}\n{tb}"}


def _fallback_execute(req: ExecutionRequest, workspace: str) -> dict:
    """Sandbox kullanılamadığında basit importlib ile çalıştırma (fallback)."""
    old_cwd = os.getcwd()
    if workspace and os.path.isdir(workspace):
        os.chdir(workspace)
    try:
        module_name = os.path.splitext(os.path.basename(req.dosya))[0]
        spec = importlib.util.spec_from_file_location(module_name, req.dosya)
        if not spec or not spec.loader:
            return {"basarili": False, "hata": f"'{req.dosya}' için modül loader bulunamadı."}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fn = getattr(module, req.fonksiyon, None)
        if not fn:
            available = [n for n in dir(module) if not n.startswith("_")]
            return {"basarili": False, "hata": f"'{req.fonksiyon}' bulunamadı. Mevcut: {available}"}
        result = fn(**(req.parametreler or {}))
        return {"basarili": True, "sonuc": str(result) if result is not None else "Başarılı."}
    except TypeError as e:
        import inspect
        try:
            sig = inspect.signature(fn)
            return {"basarili": False, "hata": f"Parametre uyuşmazlığı. Beklenen: {req.fonksiyon}{sig}. Hata: {e}"}
        except Exception:
            return {"basarili": False, "hata": str(e)}
    except Exception as e:
        tb = traceback.format_exc()
        return {"basarili": False, "hata": f"Çalıştırma hatası: {e}\n\nDetay:\n{tb}"}
    finally:
        os.chdir(old_cwd)


if __name__ == "__main__":
    port = int(os.environ.get("SKILL_WORKER_PORT", 8002))
    uvicorn.run(app, host="127.0.0.1", port=port)
