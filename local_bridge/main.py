from fastapi import FastAPI, HTTPException
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
import PIL.ImageGrab
import base64

app = FastAPI(title="Ghost Local Bridge API", description="Docker'daki Ghost Core ile Host makine arasındaki masaüstü köprüsü")

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
        return True # Varsayılan olarak izin ver
    try:
        import json
        with open(perm_file, "r", encoding="utf-8") as f:
            perms = json.load(f)
        return perms.get(tool_name, True)
    except:
        return True

@app.post("/execute")
def execute_tool(req: ToolRequest):
    tool = req.tool_adi
    params = req.parametreler

    if not check_permission(tool):
        return {"basarili": False, "mesaj": f"GÜVENLİK ENGELİ: '{tool}' aracını kullanmak için gerekli izne sahip değilsin. Lütfen masaüstü uygulamasından (veya permissions.json dosyasından) bu araca izin ver."}

    try:
        if tool == "ekran_goruntusu":
            soru = params.get("soru", "Ekranda ne var?")
            
            from core.config import TEMP_DIR
            kayit_yolu = os.path.join(TEMP_DIR, "bridge_screenshot.png")
            os.makedirs(os.path.dirname(kayit_yolu), exist_ok=True)
            
            ekran = PIL.ImageGrab.grab(all_screens=True)
            ekran.save(kayit_yolu)
            
            basarili, saf_kod, mesaj = minimax_vision_analiz(soru, kayit_yolu)
            return {"basarili": basarili, "saf_kod": saf_kod, "mesaj": mesaj}

        elif tool == "whatsapp_mesaj_gonder":
            kisi = params.get("kisi")
            mesaj = params.get("mesaj")
            sonuc = whatsapp_mesaj_gonder(kisi, mesaj)
            return {"mesaj": sonuc}

        elif tool == "whatsapp_ekrani_oku":
            sonuc = whatsapp_ekrani_yorumla()
            return {"mesaj": sonuc}

        elif tool == "browser_search":
            sorgu = params.get("sorgu")
            sonuc = browser_google_search(sorgu)
            return {"mesaj": sonuc}

        elif tool == "kodu_calistir":
            dosya_adi = params.get("dosya_adi")
            aktif_proje = params.get("aktif_proje")
            gercek_yol = dosya_bul(dosya_adi, aktif_proje)
            sonuc = kodu_calistir(gercek_yol)
            return {"sonuc": sonuc}

        elif tool == "uygulama_ac":
            import subprocess
            uygulama_yolu = params.get("yol")
            if not os.path.exists(uygulama_yolu):
                return {"basarili": False, "mesaj": "Uygulama bulunamadı"}
            # Windows'ta arkaplanda aç
            subprocess.Popen([uygulama_yolu], shell=True)
            return {"basarili": True, "mesaj": f"{uygulama_yolu} açıldı."}

        else:
            raise HTTPException(status_code=404, detail="Bilinmeyen masaüstü aracı")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/show_diff")
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
