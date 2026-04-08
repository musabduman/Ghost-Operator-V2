import re
import os   
import requests

class BaseLLM:
    def generate(self, prompt):
        raise NotImplementedError
    def __call__(self, user_input):
        return self.generate(user_input)

# 1. YÖNETİCİ BEYİN
class ChatLLM(BaseLLM):    
    def __init__(self, api_key=None, model="gpt-oss:20b-cloud"):
        self.model = model
        self.api_url = "http://localhost:11434/api/chat"
        
        self.ana_kurallar = rf"""
        ... (BURAYA HİÇ DOKUNMADIM AYNEN KALSIN)
        """
        
        self.mesaj_gecmisi = [
            {"role": "system", "content": self.ana_kurallar}
        ]
    
    def generate(self, user_input):
        self.mesaj_gecmisi.append({"role": "user", "content": user_input})
        
        payload = {
            "model": self.model,
            "messages": self.mesaj_gecmisi,
            "stream": False,
            "options": {"temperature": 0.4, "num_ctx": 4096}
        }
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status() 
            res = response.json()["message"]["content"].strip()
            self.mesaj_gecmisi.append({"role": "assistant", "content": res})
            if len(self.mesaj_gecmisi) > 12:
                self.mesaj_gecmisi = [self.mesaj_gecmisi[0]] + self.mesaj_gecmisi[-5:]
            return res
        except Exception as e:
            self.mesaj_gecmisi.pop()
            raise Exception(f"Yönetici (Gemma) Çöktü: {e}")

# 2. İŞÇİ BEYİN
class QwenWorker:
    def __init__(self, model="qwen3-coder:480b-cloud"):
        self.model = model
        self.api_url = "http://localhost:11434/api/chat"
        
        self.isci_kurallari = """
        Sen sadece bir kod dönüştürme ve yazma motorusun...
        """

    def saf_kod_uret(self, talimat, mevcut_kod=""):
        istek = f"TALİMAT: {talimat}\n\n"
        if mevcut_kod:
            istek += f"MEVCUT KOD:\n{mevcut_kod}\n\nBunu talimata göre düzelt ve saf kodu ver."
            
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.isci_kurallari},
                {"role": "user", "content": istek}
            ],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status() 
            saf_kod = response.json()["message"]["content"].strip()
            
            if saf_kod.startswith("```"):
                saf_kod = "\n".join(saf_kod.split("\n")[1:-1])
                
            return saf_kod
        except Exception as e:
            raise Exception(f"Taşeron (Qwen) Çöktü: {e}")

# 3. ORKESTRA ŞEFİ
class GhostController():
    def __init__(self, api_key=None): 
        self.supervisor = ChatLLM(model="gpt-oss:20b-cloud") 
        self.worker = QwenWorker(model="qwen3-coder:480b-cloud")
    
    def yol_duzelt(self, yol):
        user_home = os.path.expanduser("~")
        yol = os.path.normpath(yol.replace("/", "\\")) 
        
        if "Users\\" in yol:
            parcalar = yol.split("\\")
            if len(parcalar) > 3:
                return os.path.join(user_home, *parcalar[3:])
        return yol
    
    def generate(self, user_input):
        cevap = self.supervisor.generate(user_input)
        aktif_model = "GPT-OSS 20B (Yönetici)"
        
        kod_istegi_eslesme = re.search(r'\[KOD_ISTE:\s*(.*?)\s*\|\s*(.*?)\]', cevap, flags=re.DOTALL | re.IGNORECASE)
        
        if kod_istegi_eslesme:
            raw_yolu = kod_istegi_eslesme.group(1).strip()
            dosya_yolu= self.yol_duzelt(raw_yolu)
            talimat = kod_istegi_eslesme.group(2).strip()
            aktif_model = "Qwen 480B (Mühendis Kodluyor...)"
            
            try:
                mevcut_kod = ""
                if os.path.exists(dosya_yolu):
                    try:
                        with open(dosya_yolu, "r", encoding="utf-8") as f:
                            mevcut_kod = f.read()
                    except Exception:
                        pass

                saf_kod = self.worker.saf_kod_uret(talimat=talimat, mevcut_kod=mevcut_kod)
                    
                ui_formati = f"[DOSYA_YAZ: {dosya_yolu}]\n<<<KOD_BASLANGIC>>>\n{saf_kod}\n<<<KOD_BITIS>>>"
                cevap = cevap.replace(kod_istegi_eslesme.group(0), ui_formati)
                
            except Exception as e:
                cevap = f"[SİSTEM HATA] Taşeron koda ulaşamadı: {e}"

        return cevap, aktif_model
            
    def __call__(self, user_input):
        return self.generate(user_input)