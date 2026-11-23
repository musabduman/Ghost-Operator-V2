from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
import sys
import os

# Üst dizindeki modüllere erişim için sys.path güncellemesi
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.append(base_dir)

from vison.vison import minimax_vision_analiz
from tools.whatsapp_tool import whatsapp_mesaj_gonder, whatsapp_ekrani_yorumla
from tools.browser_tool import browser_google_search
from core.fs import kodu_calistir, dosya_bul
from core.tool_registry import (
    TOOL_EKRAN_GORUNTUSU,
    TOOL_WHATSAPP_EKRANI_OKU,
    TOOL_WHATSAPP_MESAJ_GONDER,
    TOOL_BROWSER_SEARCH,
    TOOL_KODU_CALISTIR,
    TOOL_UYGULAMA_AC,
)
import PIL.ImageGrab
import base64
import hmac
from core.config import GHOST_TOKEN

app = FastAPI(title="Ghost Local Bridge API", description="Docker'daki Ghost Core ile Host makine arasındaki masaüstü köprüsü")

async def verify_token(x_ghost_token: str = Header(None)):
    if not x_ghost_token or not GHOST_TOKEN or not hmac.compare_digest(str(x_ghost_token), str(GHOST_TOKEN)):
        raise HTTPException(status_code=403, detail="Geçersiz veya eksik Ghost Token (Güvenlik İhlali)")
    return x_ghost_token

class ToolRequest(BaseModel):
    tool_adi: str
    parametreler: dict = {}

class DiffRequest(BaseModel):
    dosya_yolu: str
    eski_icerik: str
    yeni_icerik: str
    aciklama: str

def check_permission(tool_name: str) -> bool:
    perm_file = os.path.join(base_dir, "local_bridge", "permissions.json")
    if not os.path.exists(perm_file):
        return False  # Fail-closed: İzin dosyası yoksa reddet
    try:
        import json
        with open(perm_file, "r", encoding="utf-8") as f:
            perms = json.load(f)
        return bool(perms.get(tool_name, False))
    except Exception:
        return False  # Fail-closed: Hata veya bozuk dosya durumunda reddet

@app.post("/execute", dependencies=[Depends(verify_token)])
def execute_tool(req: ToolRequest):
    tool = req.tool_adi
    params = req.parametreler

    if not check_permission(tool):
        return {"basarili": False, "mesaj": f"GÜVENLİK ENGELİ: '{tool}' aracını kullanmak için gerekli izne sahip değilsin. Lütfen masaüstü uygulamasından (veya permissions.json dosyasından) bu araca izin ver."}

    try:
        if tool == TOOL_EKRAN_GORUNTUSU:
            soru = params.get("soru") or params.get("mesaj", "Ekranda ne var?")
            
            from core.config import TEMP_DIR
            kayit_yolu = os.path.join(TEMP_DIR, "bridge_screenshot.png")
            os.makedirs(os.path.dirname(kayit_yolu), exist_ok=True)
            
            ekran = PIL.ImageGrab.grab(all_screens=True)
            ekran.save(kayit_yolu)
            
            basarili, saf_kod, mesaj = minimax_vision_analiz(soru, kayit_yolu)
            return {"basarili": basarili, "saf_kod": saf_kod, "mesaj": mesaj}

        elif tool == TOOL_WHATSAPP_MESAJ_GONDER:
            kisi = params.get("kisi")
            mesaj = params.get("mesaj")
            sonuc = whatsapp_mesaj_gonder(kisi, mesaj)
            return {"mesaj": sonuc}

        elif tool == TOOL_WHATSAPP_EKRANI_OKU:
            sonuc = whatsapp_ekrani_yorumla()
            return {"mesaj": sonuc}

        elif tool == TOOL_BROWSER_SEARCH:
            sorgu = params.get("sorgu")
            sonuc = browser_google_search(sorgu)
            return {"mesaj": sonuc}

        elif tool == TOOL_KODU_CALISTIR:
            dosya_adi = params.get("dosya_adi")
            aktif_proje = params.get("aktif_proje")
            gercek_yol = dosya_bul(dosya_adi, aktif_proje)
            sonuc = kodu_calistir(gercek_yol)
            return {"sonuc": sonuc}

        elif tool == TOOL_UYGULAMA_AC:
            import subprocess
            uygulama_yolu = params.get("yol")
            if not os.path.exists(uygulama_yolu):
                return {"basarili": False, "mesaj": "Uygulama bulunamadı"}
            # Windows'ta arkaplanda aç (shell=True kaldırıldı, güvenli subprocess)
            subprocess.Popen([uygulama_yolu])
            return {"basarili": True, "mesaj": f"{uygulama_yolu} açıldı."}

        else:
            raise HTTPException(status_code=404, detail="Bilinmeyen masaüstü aracı")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/show_diff", dependencies=[Depends(verify_token)])
def show_diff(req: DiffRequest):
    import subprocess
    import tempfile
    import json
    
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(req.dict(), f, ensure_ascii=False)
        temp_path = f.name
        
    script_path = os.path.join(base_dir, "local_bridge", "diff_runner.py")
    try:
        res = subprocess.run(["python", script_path, temp_path], capture_output=True, text=True)
        os.remove(temp_path)
        return json.loads(res.stdout)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return {"approved": False, "reason": f"Diyalog açılamadı: {str(e)}"}

# Uvicorn ile çalıştırmak için:
# uvicorn local_bridge.main:app --host 0.0.0.0 --port 8000
