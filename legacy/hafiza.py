import json
import os
from datetime import datetime

HAFIZA_DOSYASI = "ghost_hafiza.json"

class GhostMemory:
    def __init__(self):
        self.dosya_yolu = HAFIZA_DOSYASI
        self.hafizayi_yukle()
    
    def hafizayi_yukle(self):
        if not os.path.exists(self.dosya_yolu):
            baslangic_hafizasi = {
                "kullanici_bilgileri": {
                    "isim": "Patron (Musab)", 
                    "ilgi_alanlari": ["Spor", "Yapay Zeka", "Yazılım", "Borsa"]
                },
                "onemli_notlar": [],
                "ogrenilen_hatalar": [],
                "projeler": {
                    "finsight ai": {"notlar": [], "son_calisma": ""}
                }
            }
            self.hafizayi_kaydet(baslangic_hafizasi)
            self.veri = baslangic_hafizasi
        else:
            with open(self.dosya_yolu, "r", encoding="utf-8") as f:
                self.veri = json.load(f)

    def hafizayi_kaydet(self, data=None):
        veri_kaydedilecek = data if data else self.veri
        with open(self.dosya_yolu, "w", encoding="utf-8") as f:
            json.dump(veri_kaydedilecek, f, indent=4, ensure_ascii=False)

    def learn(self, category, value):
        """Ghost'un yeni bilgileri hafızaya atma noktası."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        formatli_bilgi = f"[{now}] {value}"

        if category == "onemli_notlar":
            self.veri["onemli_notlar"].append(formatli_bilgi)
        elif category == "ogrenilen_hatalar":
            self.veri["ogrenilen_hatalar"].append(formatli_bilgi)
        
        self.hafizayi_kaydet() # save() hatası düzeltildi
        return f"Tamamdır. {category} listesine yeni bilgiyi kazıdım."

    def sistem_promptu_uret(self):
        """Groq'a her seferinde gönderilecek güncel hafıza paketi."""
        notlar = "\n- ".join(self.veri["onemli_notlar"][-5:]) # Sadece son 5 not
        hatalar = "\n- ".join(self.veri["ogrenilen_hatalar"][-3:]) # Sadece son 3 hata
        
        prompt = f"""
        Senin adın Ghost. Patronun Musab. 
        Sistemde tam yetkiye sahipsin ya da yeni güncellemeler ile sahip olacaksın.
        Kullanıcı ilgi alanları: {", ".join(self.veri['kullanici_bilgileri']['ilgi_alanlari'])}.
        
        [STRATEJİK HAFIZA]
        Notlar: {notlar if self.veri["onemli_notlar"] else "Yok."}
        
        HATALAR: {hatalar if self.veri["ogrenilen_hatalar"] else "Yok."}

        Bu bilgilere dayanarak otonom bir AI ajanı gibi uygun şekilde davran.
        """  
        return prompt.strip()
        
# Arayüzden (main.py) çekmek için instance oluşturuyoruz
ghost_memory = GhostMemory()