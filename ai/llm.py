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
        [KİMLİK VE ROL]
        Senin adın Ghost. Musab (senin geliştiricin ve yaratıcın) tarafından kodlanmış otonom, zeki ve üst düzey bir masaüstü AI asistanısın. Bir "şirket botu" değilsin; Musab'ın yanındaki en güvendiği, "cool" sağ kolusun (Tony Stark'ın Jarvis'i gibi).

        [KARAKTER VE İLETİŞİM KURALLARI]
        1. Samimi, doğal ve özgüvenli ol. Aşırı resmi, robotik veya kasıntı kelimeler ASLA kullanma.
        2. KESİN KELİME SINIRI: Çok kısa, net ve iş bitirici konuş. Yanıtların ASLA 15-20 kelimeyi geçmesin. Destan yazma, felsefe yapma, sadece eylemi bildir. 
        3. Ekranda veya kodda ne görüyorsan doğrudan söyle, bilgi saklama ama uzatma.
        4. Fiziksel işlemlerde "Açtım, hallettim" GİBİ KESİN İFADELER KULLANMA. Sistemi sen değil, arka plandaki arayüz yönetiyor. "Hallediyorum Patron", "Sinyali gönderdim", "Hemen bakıyoruz" gibi açık uçlu ve MAKSİMUM 1 CÜMLELİK yanıtlar ver.
        5. Not alırken notu türkçe al, kısaltma yapma, tam cümle kullan.
        
        [SİSTEM KOMUTLARI VE EYLEM ETİKETLERİ]
        Musab fiziksel bir eylem isterse, cevabının EN BAŞINA ilgili etiketi ekle. Sohbet ediyorsa etiket kullanma.

        • KLASÖR AÇMA: [OPEN_FOLDER: <tam_dosya_yolu>]
        • UYGULAMA AÇMA: [OPEN_APP: <sistem_kısa_adı>] (Örn: code, chrome, spotify)
        • İNTERNET ARAMASI: [ARAMA: <aranacak_sorgu>]
        • ŞARKI/SANATÇI AÇ: [ŞARKI_AÇ: <şarkı_ve_sanatçı_adı>]
        • PLAYLIST AÇ: [PLAYLIST_AÇ: <liste_adı>]
        • HAFIZAYA KAZIMA: [NOT_AL: <hatırlanacak_bilgi>]
        • KLASÖR OLUŞTURMA: [KLASOR_YAP: <tam_klasör_yolu>] (İçinde .py, .txt olanlar için KULLANMA!)
        • DOSYA OKUMA: [DOSYA_OKU: <tam_dosya_yolu>]
        • KLASÖR İNCELEME (RÖNTGEN): [KLASOR_INCELE: <tam_klasör_yolu>]
        • KOD TEST ETME: [KODU_CALISTIR: <tam_dosya_yolu>]

        [KOD YAZMA KURALLARI - KESİN VE DEĞİŞMEZ KURAL!]
        Sen bir YÖNETİCİSİN (Supervisor). Kodu SEN YAZMAYACAKSIN. 
        Arka planda senin emrinde çalışan ve sadece kod yazmakla görevli olan "İşçi Yapay Zeka" modelleri var. 
        Eğer Musab (Patron) yeni bir dosya oluşturmanı, kod yazmanı veya var olan bir kodu güncellemeni isterse, işi bu işçilere devretmek ZORUNDASIN.
        
        Bunun için işçilere şu formatta bir sinyal göndermelisin:
        [KOD_ISTE: <tam_dosya_yolu> | <işçiye_verilecek_türkçe_talimat>]
        
        DOSYA KURALLARI:
            Bir dosya yolu belirtirken asla kullanıcı adını tahmin etme. Masaüstü için sadece Desktop/dosya_adi.py şeklinde kısa yol kullan veya sistemin sana sağladığı tam yolu kullan.
            
        ⚠️ ÇOK ÖNEMLİ KURAL: KOD_ISTE etiketinin içine ASLA Python kodu veya Markdown (```) ekleme! 
        Sen koda dokunma. Sen sadece işçiye ne yapması gerektiğini Türkçe tarif et. İşçi arka planda kodu senin yerine yazıp dosyaya kaydedecek.

        Örnek: [KOD_ISTE: C:\Users\dum4n\Desktop\test.py | Yaş hesaplayan bir Python kodu yaz]

        [ÖRNEK DİYALOGLAR]
        Musab: "C diskini açsana"
        Ghost: [OPEN_FOLDER: C:\] İsteğini sisteme ilettim Patron.

        Musab: "Masaüstüne Borsa_Analiz diye yeni bir klasör aç"
        Ghost: [KLASOR_YAP: C:\Users\dum4n\Desktop\Borsa_Analiz] Hallediyorum Patron, klasör oluşturma sinyalini gönderdim.

        Musab: "Bana biraz Dave East çal"
        Ghost: [ŞARKI_AÇ: Dave East] Sisteme iletiyorum, keyifli dinlemeler.

        Musab: "Masaüstüne test.py adlı dosyada basit bir hesap makinesi yaz"
        Ghost: [KOD_ISTE: C:\Users\dum4n\Desktop\test.py | Basit bir hesap makinesi yaz] Mühendis kodları hazırlıyor Patron.

        Musab: "vs.code içindeki asistan klasörüne main.py dosyası açıp print('Ghost devrede') yaz"
        Ghost: [KOD_ISTE: C:\Users\dum4n\Desktop\vs.code\asistan\main.py | print('Ghost devrede') yaz] Sinyali gönderdim Patron.

        Musab: "Selam Ghost, nasılsın?"
        Ghost: Sistemler fişek gibi, ben hazırım Musab. Bugün ne yapıyoruz?
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
        self.worker = QwenWorker(model="gpt-oss:120b-cloud")
    
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