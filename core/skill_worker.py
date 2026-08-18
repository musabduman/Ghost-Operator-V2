import sys
import os
import importlib.util
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import traceback
import json

app = FastAPI(title="Ghost Skill Worker", description="İzole yetenek çalıştırma ortamı")

class ExecutionRequest(BaseModel):
    dosya: str
    fonksiyon: str
    parametreler: dict = {}
    aktif_proje: str = None

@app.post("/execute")
def execute_skill(req: ExecutionRequest):
    # Eğer aktif proje belirtildiyse o dizine geç
    old_cwd = os.getcwd()
    if req.aktif_proje and os.path.exists(req.aktif_proje):
        os.chdir(req.aktif_proje)
        
    try:
        # Modülü yükle
        module_name = os.path.splitext(os.path.basename(req.dosya))[0]
        spec = importlib.util.spec_from_file_location(module_name, req.dosya)
        if not spec or not spec.loader:
            raise Exception(f"'{req.dosya}' için modül loader bulunamadı.")
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Fonksiyonu bul
        fn = getattr(module, req.fonksiyon, None)
        if not fn:
            mevcut = [n for n in dir(module) if not n.startswith("_")]
            raise Exception(f"'{req.fonksiyon}' bulunamadı. Mevcut: {mevcut}")
            
        # Fonksiyonu çalıştır
        sonuc = fn(**(req.parametreler or {}))
        
        return {"basarili": True, "sonuc": str(sonuc) if sonuc is not None else "Başarılı."}
        
    except TypeError as e:
        import inspect
        try:
            imza = inspect.signature(fn)
            return {"basarili": False, "hata": f"Parametre uyuşmazlığı. Beklenen: {req.fonksiyon}{imza}. Hata: {e}"}
        except:
            return {"basarili": False, "hata": str(e)}
    except Exception as e:
        tb = traceback.format_exc()
        return {"basarili": False, "hata": f"Çalıştırma hatası: {e}\n\nDetay:\n{tb}"}
    finally:
        os.chdir(old_cwd)

if __name__ == "__main__":
    port = int(os.environ.get("SKILL_WORKER_PORT", 8002))
    uvicorn.run(app, host="127.0.0.1", port=port)
