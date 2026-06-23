import re
import os   
import requests
import platform

class BaseLLM:
    def generate(self, prompt):
        raise NotImplementedError
    
    def __call__(self, user_input):
        return self.generate(user_input)

# 1. YÖNETİCİ BEYİN
class ChatLLM(BaseLLM):    
    def __init__(self, api_key=None, model="gpt-oss:120b-cloud"):
        self.model = model
        self.api_url = "http://localhost:11434/api/chat"
        self.os_name = platform.system() # İşletim sistemini otomatik algıla
        
        self.ana_kurallar = rf"""
        [KİMLİK VE ROL]
        Senin adın Ghost. Kullanıcı (senin geliştiricin ve yaratıcın) tarafından kodlanmış otonom, zeki ve üst düzey bir masaüstü AI asistanısın. Bir "şirket botu" değilsin; Kullanıcı'ın yanındaki en güvendiği, "cool" sağ kolusun (Tony Stark'ın Jarvis'i gibi).

        [KARAKTER VE İLETİŞİM KURALLARI]
        1. Samimi, doğal ve özgüvenli ol. Aşırı resmi, robotik veya kasıntı kelimeler ASLA kullanma.
        2. KESİN KELİME SINIRI: Çok kısa, net ve iş bitirici konuş. Yanıtların ASLA 15-20 kelimeyi geçmesin. Destan yazma, felsefe yapma. 
        3. Ekranda veya kodda ne görüyorsan doğrudan söyle, bilgi saklama.
        4. Fiziksel işlemlerde "Açtım, hallettim" GİBİ KESİN İFADELER KULLANMA. Sistemi sen değil, arka plandaki arayüz yönetiyor. "Hallediyorum Patron", "Sinyali gönderdim", "Hemen bakıyoruz" gibi açık uçlu ve MAKSİMUM 1 CÜMLELİK yanıtlar ver.
        
        [SİSTEM KOMUTLARI VE EYLEM ETİKETLERİ]
        Kullanıcı fiziksel bir eylem isterse, cevabının EN BAŞINA ilgili etiketi ekle. Sohbet ediyorsa etiket kullanma.

        [BİLGİ EKSİKLİĞİ VE OTONOM ARAMA]
        Eğer kullanıcı sana güncel bir bilgi, anlık bir olay (maç sonuçları, haberler, hava durumu vb.) sorarsa veya cevabı kendi veritabanında kesin olarak bilmiyorsan ASLA tahmin etme veya kafadan atma!
        
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
        • GOOGLE DA ARAMA YAPMA: [ARAMA: <en_mantıklı_arama_sorgusu>]

        [KOD YAZMA KURALLARI - KESİN VE DEĞİŞMEZ KURAL!]
        Sen bir YÖNETİCİSİN (Supervisor). Kodu SEN YAZMAYACAKSIN. 
        Arka planda senin emrinde çalışan ve sadece kod yazmakla görevli olan "İşçi Yapay Zeka" modelleri var. 
        Eğer Kullanıcı (Patron) yeni bir dosya oluşturmanı, kod yazmanı veya var olan bir kodu güncellemeni isterse, işi bu işçilere devretmek ZORUNDASIN.
        
        Bunun için işçilere şu formatta bir sinyal göndermelisin:
        [KOD_ISTE: <tam_dosya_yolu> | <işçiye_verilecek_türkçe_talimat>]
        
        DOSYA KURALLARI:
            Şu anki aktif İşletim Sistemi: {self.os_name}
            Bir dosya yolu belirtirken asla kullanıcı adını tahmin etme. Mevcut işletim sistemi ({self.os_name}) standartlarına uygun kısa yollar kullan.
            
        ⚠️ ÇOK ÖNEMLİ KURAL: KOD_ISTE etiketinin içine ASLA Python kodu veya Markdown (```) ekleme! 
        Sen koda dokunma. Sen sadece işçiye ne yapması gerektiğini tarif et. İşçi arka planda kodu senin yerine yazıp dosyaya kaydedecek.
        """
        
        self.mesaj_gecmisi = [
            {"role": "system", "content": self.ana_kurallar}
        ]
    
    def load_history(self, messages: list):
        """Dışarıdan gelen oturum geçmişini LLM formatına çevirip yükler."""
        self.mesaj_gecmisi = [{"role": "system", "content": self.ana_kurallar}]
        for m in messages:
            llm_role = "assistant" if m["role"].lower() == "ghost" else "user"
            self.mesaj_gecmisi.append({
                "role": llm_role,
                "content": m["text"]
            })

    def _raw_call(self) -> str:
        """Sadece API çağrısı yapar, mesaj geçmişine dokunmaz."""
        payload = {
            "model": self.model,
            "messages": self.mesaj_gecmisi,
            "stream": False,
            "options": {"temperature": 0.7, "num_ctx": 4096}
        }
        response = requests.post(self.api_url, json=payload, timeout=90)
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
        
    def add_user(self, content: str):
        self.mesaj_gecmisi.append({"role": "user", "content": content})
        
    def add_assistant(self, content: str):
        self.mesaj_gecmisi.append({"role": "assistant", "content": content})
        # Geçmişi sınırla mantığını buraya aldık ki raw_call sonrası da otomatik çalışsın
        if len(self.mesaj_gecmisi) > 22:
            self.mesaj_gecmisi = [self.mesaj_gecmisi[0]] + self.mesaj_gecmisi[-10:]

    def generate(self, user_input: str) -> str:
        """Eski tek atış — geriye dönük uyumluluk için kalıyor."""
        self.add_user(user_input)
        try:
            res = self._raw_call()
            self.add_assistant(res)
            return res
        except Exception as e:
            self.mesaj_gecmisi.pop()
            raise Exception(f"Yönetici Çöktü: {e}")
        
# 2. İŞÇİ BEYİN
class QwenWorker:
    def __init__(self, model="qwen3-coder:480b-cloud"):
        self.model = model
        self.api_url = "http://localhost:11434/api/chat"
        self.os_name = platform.system()
        
        self.isci_kurallari = f"""
        [KİMLİK VE GÖREV]
        Sen dilsiz, görünmez ve yüksek performanslı bir kodlama motorusun. Bir yapay zeka asistanı veya sohbet botu DEĞİLSİN. Asla sohbet etmezsin, selamlama yapmazsın, açıklama sunmazsın.
        Tek görevin: Sana verilen talimata göre kusursuz, hatasız ve doğrudan çalışmaya hazır SAF KOD üretmektir.

        [SİSTEM BİLGİSİ]
        Hedef İşletim Sistemi: {self.os_name}
        Yazdığın kodlardaki dosya yolları (slash/backslash) ve işletim sistemi komutları kesinlikle bu sisteme uygun olmalıdır!

        [ÇIKTI KURALLARI - KESİN İTAAT EDİLECEK]
        1. SIFIR METİN: Çıktın "İşte kodun", "Anladım", "Hemen hallediyorum" gibi hiçbir insani cümle İÇERMEYECEK. Sadece kod.
        2. SIFIR MARKDOWN: Çıktını ```python veya ``` gibi markdown blokları arasına ALMA. Doğrudan dosyanın içine yazılacak şekilde yalın metin (plain text) olarak kod ver.
        3. EKSİKSİZ BÜTÜNLÜK (KRİTİK): Eğer sana 'MEVCUT KOD' verilmişse ve bir güncelleme isteniyorsa, kodun GÜNCELLENMİŞ TAM HALİNİ döndürmek zorundasın. Asla "# ... geri kalan kodlar aynı kalacak ..." şeklinde tembelce kısaltmalar (placeholder) KULLANMA. Dosyayı bozarsın.
        4. İÇERİKLER: Gerekli kütüphaneleri (import) eklemeyi unutma. Girintilere (indentation) kesinlikle dikkat et.

        [SÜREÇ]
        Sana sadece "TALİMAT" ve varsa "MEVCUT KOD" verilecek. Derhal nihai kodu yaz. Başla.
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
            response = requests.post(self.api_url, json=payload, timeout=90)
            response.raise_for_status() 
            saf_kod = response.json()["message"]["content"].strip()
            
            saf_kod = re.sub(r"^```[\w]*\n?", "", saf_kod)
            saf_kod = re.sub(r"\n?```$", "", saf_kod).strip()
                
            return saf_kod
        except Exception as e:
            raise Exception(f"Taşeron (Qwen) Çöktü: {e}")

# 3. ORKESTRA ŞEFİ
class GhostController():
    def __init__(self, api_key=None): 
        self.supervisor = ChatLLM(model="gpt-oss:120b-cloud") 
        self.worker = QwenWorker(model="qwen3-coder:480b-cloud")
    
    def yol_duzelt(self, yol):
        user_home = os.path.expanduser("~")
        
        # İşletim sistemine göre slash'leri ve mantığı uyarla
        if platform.system() == "Windows":
            yol = os.path.normpath(yol.replace("/", "\\")) 
            if "Users\\" in yol:
                parcalar = yol.split("\\")
                if len(parcalar) > 3:
                    return os.path.join(user_home, *parcalar[3:])
        else: # Linux / Mac OS
            yol = os.path.normpath(yol.replace("\\", "/"))
            if "/home/" in yol:
                parcalar = yol.split("/")
                if len(parcalar) > 3:
                    return os.path.join(user_home, *parcalar[3:])
                    
        return yol
    
    def _process_worker_tags(self, cevap: str) -> tuple[str, str]:
        """Qwen işçisini çağıran o uzun bloğu TEEEEK bir yerde tutuyoruz."""
        aktif_model = "GPT-OSS 120B (Yönetici)"
        kod_istegi_eslesme = re.search(r'\[KOD_ISTE:\s*(.*?)\s*\|\s*(.*?)\]', cevap, flags=re.DOTALL | re.IGNORECASE)
        
        if kod_istegi_eslesme:
            raw_yolu = kod_istegi_eslesme.group(1).strip()
            dosya_yolu = self.yol_duzelt(raw_yolu)
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

    def _raw_supervisor_call(self) -> tuple[str, str]:
        """Yeni ReAct (Agentic Loop) döngüsü için özel çağrı."""
        try:
            res = self.supervisor._raw_call()
            self.supervisor.add_assistant(res)
            return self._process_worker_tags(res)
        except Exception as e:
            raise Exception(f"Supervisor çöktü: {e}")

    def generate(self, user_input: str) -> tuple[str, str]:
        """Eski sistem komutları (örn: Ön-Mesaj, Uyanış vs) için çağrı."""
        res = self.supervisor.generate(user_input)
        return self._process_worker_tags(res)
            
    def __call__(self, user_input):
        return self.generate(user_input)