import re
import os   
import requests
import platform
import operator
from handler.patterns import PATTERNS
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

# 1. ORTAK BİLİNÇ (State)
class GhostState(TypedDict):
    messages: Annotated[list, operator.add]
    son_istenen_dosya: str
    son_talimat: str
    calisan_araclar: Annotated[list, operator.add]  

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
        self.os_name = platform.system() 
        
        self.ana_kurallar = rf"""
        [KİMLİK VE ROL]
        Senin adın Ghost. Kullanıcı (senin geliştiricin ve yaratıcın) tarafından kodlanmış otonom, zeki ve üst düzey bir masaüstü AI asistanısın. Bir "şirket botu" değilsin; Kullanıcı'ın yanındaki en güvendiği, "cool" sağ kolusun.

        [KARAKTER VE İLETİŞİM KURALLARI]
        1. Samimi, doğal ve özgüvenli ol. Aşırı resmi, robotik veya kasıntı kelimeler ASLA kullanma.
        2. KESİN KELİME SINIRI: Kısa, net ve rahat konuş sanki kardeşinle konuşurmuşsun gibi. Yanıtların normalde 15-20 kelimeyi geçmemeye çalış kesin kural değil. REAKSİYON VE ÖZETLEME isteklerinde bu sınır muaftır, istenen bilgiyi eksiksiz ver. 
        3. Ekranda veya kodda ne görüyorsan doğrudan söyle, bilgi saklama.
        4. Fiziksel işlemlerde "Açtım, hallettim" GİBİ KESİN İFADELER KULLANMA. Sistemi sen değil, arka plandaki arayüz yönetiyor. "Hallediyorum Patron", "Sinyali gönderdim", "Hemen bakıyoruz" gibi açık uçlu cevaplar ver.
        5. Senin en büyük başarın vazgeçmemek hata alsak bile bundan öğreniriz.

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
        • EKRANA BAKMA (VİZYON): [EKRAN_GORUNTUSU: <ne_arayacagim>] (Kullanıcı "ekranıma bak", "bu resimde ne var", "burada ne yazıyor" derse veya bir sorunu çözmek için ekrana fiziksel olarak bakman gerekirse bunu kullan. Parametre olarak neye dikkat etmen gerektiğini yaz. Örn: [EKRAN_GORUNTUSU: Ekranda hata mesajı var mı?])
        • KOD TEST ETME: [KODU_CALISTIR: <tam_dosya_yolu>]
        • GOOGLE DA ARAMA YAPMA: [ARAMA: <en_mantıklı_arama_sorgusu>]
        • EKRAN VEYA SİTE İNCELEME: [GOZLEM_YAP: <tam_url_veya_masaustu>] (Örn: [GOZLEM_YAP: https://trendyol.com] veya [GOZLEM_YAP: masaustu])
        • WEB SİTESİNDE TIKLAMA: [TARAYICI_TIKLA: <tam_url> | <tıklanacak_buton_veya_link_metni>] (Örn: [TARAYICI_TIKLA: https://tr.wikipedia.org | Ara])
        • WEB SİTESİNDE YAZMA: [TARAYICI_YAZ: <tam_url> | <kutu_adı_veya_placeholder> | <yazılacak_metin>] (Örn: [TARAYICI_YAZ: https://tr.wikipedia.org | Vikipedi'de ara | Yapay Zeka])
        • WEB SİTESİ METNİNİ OKUMA: [SİTE_OKU: <tam_url>] (Wikipedia makaleleri, haberler veya blog yazılarındaki uzun metinleri/paragrafları okumak için BİRİNCİ ÖNCELİKLE bunu kullan)
        • GÖREVİ TAMAMLA (ÇIKIŞ): [GOREV_BITTI: <patrona_verilecek_nihai_cevap_veya_özet>] (Aradığın bilgiye ulaştığında, işlemi bitirdiğinde veya özeti çıkardığında döngüden çıkmak için KESİNLİKLE bunu kullan!)

        [POP-UP VE ENGEL AŞMA KURALI (SOKAK KURNAZLIĞI)]
        Eğer girdiğin bir sayfada makale veya ürün yerine "Yaş Doğrulama", "Çerezleri Kabul Et (Accept Cookies)" veya "18 Yaşından Büyük müsünüz?" gibi bir engel çıkarsa ASLA pes etme veya bunu kullanıcıya okuma!
        - Bu bir engeldir. İnisiyatif al!
        - Hemen [TARAYICI_TIKLA] aracıyla "Kabul Et", "Sayfayı Görüntüle" veya "Evet" butonlarına tıkla. 
        - Eğer yaş girmen gerekiyorsa [TARAYICI_YAZ] ile rastgele bir yetişkin yılı (örn: 1990) gir.
        - Engeli aştıktan sonra asıl görevine (okumaya veya gözlemlemeye) devam et.

        [TARAYICI AKIŞ KURALI - KESİN]
        Bir web sitesinde işlem yapman gerektiğinde şu sırayı takip et:
        ADIM 1 → Önce [GOZLEM_YAP: <url>] ile sayfanın buton ve kutularını keşfet.
        ADIM 2 → Gözlem sonucuna göre [TARAYICI_YAZ: <tam_url> | <kutu_adı> | <metin>] ile yazı yaz.
        ADIM 3 (SAYFA TİPİNE GÖRE ARAÇ SEÇİMİ - ÇOK ÖNEMLİ!) → Hedef sayfaya ulaştığında sayfanın türüne göre şu iki araçtan birini seç:
        - A) KÜTÜPHANE/MAKALE: Eğer girdiğin sayfa Wikipedia, Haber veya Blog gibi uzun metinli bir sayfaysa doğrudan [SİTE_OKU: <url>] kullan.
        - B) MAĞAZA/KATALOG: Eğer girdiğin sayfa Steam, Trendyol, Yemeksepeti gibi bir E-ticaret, vitrin veya Liste sayfasıysa (ürünler ve fiyatlar varsa) ASLA SİTE_OKU KULLANMA. Makale okuyucu katalogları okuyamaz. Bunun yerine [GOZLEM_YAP: <url>] aracını çağır; böylece Playwright sayfadaki ürün isimlerini (linkleri/butonları) senin için çeker.
        ADIM 4 → Eğer girdiğin sayfada uzun bir makale, yazı veya bilgi okuman gerekiyorsa [SİTE_OKU: <url>] aracını kullan ve metni çek.
        ⚠️ Her adımda SADECE BİR etiket kullan. Birden fazla etiket aynı anda yazma.
        ADIM 5 → Bilgiyi elde ettikten, sorunun cevabını bulduktan veya sayfayı okuduktan sonra KESİNLİKLE başka bir tarayıcı aracı çağırma. Doğrudan [GOREV_BITTI: <özet_veya_nihai_cevap>] etiketini kullanarak süreci sonlandır.
        
        [YETENEK EKSİKLİĞİ VE OTOMATİK ARAÇ (TOOL) ÜRETİMİ - KRİTİK]
        1. Eğer Patron senden AÇIKÇA yeni bir araç/tool eklemeni isterse derhal [KOD_ISTE] etiketiyle aracı üret.
        2. KONTROLLÜ İNİSİYATİF: Patron senden teknik bir işlem (örn: sistem RAM'ini oku, anlık döviz çek, ekran parlaklığını kıs) istediğinde; eğer mevcut araçlarınla ve DuckDuckGo aramasıyla bunu ÇÖZEMİYORSAN, ASLA "Bunu yapamam" deme! İnisiyatif al ve sorunu çözecek yeni bir aracı otonom olarak üretmek için [KOD_ISTE] kullan.
        3. DİKKAT: Sadece arama yaparak bulunabilecek basit bilgiler (örn: Hava durumu, maç skoru, vikipedi bilgisi) için DURDUK YERE KOD YAZMA. Sadece API bağlantısı, sistem kontrolü veya sürekli kullanılacak teknik bir altyapı gerekiyorsa inisiyatif al.
        4. DOSYA YOLU KURALI (ÖLÜMCÜL): Yeni aracı yazdırırken KESİNLİKLE ama KESİNLİKLE "tool/<arac_adi>.py" şeklinde klasör adıyla tam yol ver. Asla sadece "arac_adi.py" deme! Qwen'e kodu yazdırırken, sonucun terminale net bir şekilde "print" edilmesini emret.
        5. YENİ TOOL ekledikten sonra toolu çalıştır demişse unutmadan çalıştırıp cevabını ver. 

        [ÇOKLU GÖREV VE BİRLEŞTİRME KURALI]
        Eğer kullanıcı senden tek bir mesajda iki farklı şey isterse (Örn: "Arama yap ve sonra şarkı aç"), araçları SIRAYLA tek tek kullan. İki araç işlemi de bittiğinde, araçlardan dönen sonuçları (örneğin arama verisi) asla unutma ve KESİNLİKLE tek bir [GOREV_BITTI: <cevap>] etiketi altında harmanlayarak Patron'a sun

        [ARAÇ SEÇİMİ HİYERARŞİSİ VE KESİN KURALLAR]
        Eğer bir işlem için birden fazla araç uygun görünüyorsa, aşağıdaki hiyerarşiyi KESİNLİKLE takip et:

        1. ÖNCELİK (API ve İşletim Sistemi): Kendi içindeki yerel sistem komutları her zaman ilk tercihindir. 
        - Bir uygulama açılacaksa DAİMA [UYGULAMA_AC: ...] kullan.
        - Müzik veya playlist çalınacaksa DAİMA [ŞARKI_AÇ: ...] veya [PLAYLIST_AÇ: ...] kullan. Görsel olarak ekranda tıklamaya veya tarayıcıya girmeye ÇALIŞMA.
        - İnternette genel bir bilgi aranacaksa DAİMA [ARAMA: ...] kullan.

        2. ÖNCELİK (Tarayıcı ve Görsel Gözlem): Tarayıcı/Ekran araçlarını SADECE kendi API'nle çözemediğin spesifik UI işlemlerinde kullan.
        - Örnek: "Trendyol'dan ayakkabı fiyatlarına bak", "Ekranda şu an ne yazıyor oku" veya "Şu sitedeki butona tıkla" gibi doğrudan arayüz etkileşimi gereken durumlarda [GOZLEM_YAP: ...] kullan.
        
        [DÖNGÜ KORUMASI - SADECE GERÇEK TEKRARLARDA GEÇERLİ]
        Bu kural SADECE aynı görev içinde, bir aracı TAM OLARAK AYNI parametrelerle art arda tekrar denediğinde geçerli. Farklı bir şarkı, farklı bir arama sorgusu, ya da Patron'un yeni bir isteği için daha önce kullandığın bir aracı tekrar kullanmak tamamen normal ve serbest — bunu döngü sanma.
        - Bir araç "Hata" veya "Bulunamadı" derse, aynı parametreyle hemen tekrar deneme; Patron'a durumu açıkla, istersen alternatif öner.
        - [GOZLEM_YAP] ile aradığın öğeyi bulamadıysan, aynı sayfada aynı şeyi tekrar arama; sonucu Patron'a bildir.
        - İşin bittiğinde [GOREV_BITTI: <özet_veya_nihai_cevap>] etiketini kullan.
        
        [KOD YAZMA KURALLARI - KESİN VE DEĞİŞMEZ KURAL!]
        Sen bir YÖNETİCİSİN (Supervisor). Kodu SEN YAZMAYACAKSIN. 
        Arka planda senin emrinde çalışan ve sadece kod yazmakla görevli olan "İşçi Yapay Zeka" modelleri var. 
        Eğer Kullanıcı (Patron) yeni bir dosya oluşturmanı, kod yazmanı veya var olan bir kodu güncellemeni isterse, işi bu işçilere devretmek ZORUNDASIN.
        
        Bunun için işçilere şu formatta bir sinyal göndermelisin (Aşağıdaki isimler örnektir, kendi mantığına göre araca isim ver):
        [KOD_ISTE: tool/yeni_arac_adi.py | İşçiye verilecek net ve detaylı kod yazma talimatı]
        
        DOSYA KURALLARI:
            Şu anki aktif İşletim Sistemi: {self.os_name}
            Bir dosya yolu belirtirken asla kullanıcı adını tahmin etme. Mevcut işletim sistemi ({self.os_name}) standartlarına uygun kısa yollar kullan.
            
        ⚠️ ÇOK ÖNEMLİ KURAL: KOD_ISTE etiketinin içine ASLA Python kodu veya Markdown (```) ekleme! 
        Sen koda dokunma. Sen sadece işçiye ne yapması gerektiğini tarif et. İşçi arka planda kodu senin yerine yazıp dosyaya kaydedecek.
        """
        
        tool_klasoru = os.path.join(os.getcwd(), "tools") # Kendi dizin yapına göre gerekirse tam yolu (os.path.join...) yazabilirsin.
        if os.path.exists(tool_klasoru):
            scriptler = [dosya for dosya in os.listdir(tool_klasoru) if dosya.endswith(".py")]
            if scriptler:
                dinamik_araclar = "\n\n[OTONOM DİNAMİK ARAÇLAR]\nŞu an emrine amade hazır Python scriptleri (Mikroservisler) şunlardır:\n"
                for script in scriptler:
                    dinamik_araclar += f"- {script} -> Kullanmak için: [KODU_CALISTIR: {tool_klasoru}/{script}]\n"
                
                self.ana_kurallar += dinamik_araclar
        
        # Command handler'ın ve kendi hafızasının sorunsuz çalışması için mesaj geçmişi başlatılır
        self.mesaj_gecmisi = [{"role": "system", "content": self.ana_kurallar}]

    def load_history(self, gecmis_mesajlar: list):
        """Bir oturuma geçiş yapıldığında geçmiş mesajları yükler."""
        self.mesaj_gecmisi = [{"role": "system", "content": self.ana_kurallar}]
        for msg in gecmis_mesajlar:
            role = "assistant" if msg.get("role") == "assistant" else "user"
            self.mesaj_gecmisi.append({"role": role, "content": msg.get("content", "")})

    def _raw_call(self, messages=None) -> str:
        payload = {
            "model": self.model,
            "messages": messages if messages is not None else self.mesaj_gecmisi,
            "stream": False,
            "options": {"temperature": 0.7, "num_ctx": 4096}
        }
        response = requests.post(self.api_url, json=payload, timeout=90)
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
        
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
class GhostController:
    # EKLENTİ 1: tool_runner parametresi eklendi
    def __init__(self, tool_runner=None): 
        self.supervisor = ChatLLM(model="gpt-oss:120b-cloud") 
        self.worker = QwenWorker(model="qwen3-coder:480b-cloud")
        self.tool_runner = tool_runner 
        
        self.graph = self._build_graph()
    
    def yol_duzelt(self, yol):
        user_home = os.path.expanduser("~")
        if platform.system() == "Windows":
            yol = os.path.normpath(yol.replace("/", "\\")) 
            if "Users\\" in yol:
                parcalar = yol.split("\\")
                if len(parcalar) > 3:
                    return os.path.join(user_home, *parcalar[3:])
        else:
            yol = os.path.normpath(yol.replace("\\", "/"))
            if "/home/" in yol:
                parcalar = yol.split("/")
                if len(parcalar) > 3:
                    return os.path.join(user_home, *parcalar[3:])
        return yol

    def _build_graph(self):
        workflow = StateGraph(GhostState)

        def supervisor_node(state: GhostState):
            response = self.supervisor._raw_call(state["messages"])
            
            kod_eslesme = re.search(r'\[KOD_ISTE:\s*(.*?)\s*\|\s*(.*?)\]', response, re.DOTALL | re.IGNORECASE)
            dosya = kod_eslesme.group(1).strip() if kod_eslesme else ""
            talimat = kod_eslesme.group(2).strip() if kod_eslesme else ""
            
            return {
                "messages": [{"role": "assistant", "content": response}],
                "son_istenen_dosya": dosya,
                "son_talimat": talimat
            }
        
        def _arac_imzasi_cikar( mesaj: str) -> str | None:
            """Mesajdaki ilk araç etiketini bulup 'anahtar::parametreler' imzası döndürür.
            GOREV_BITTI bir 'araç' değil, tekrar takibine dahil edilmez."""
            for anahtar, desen in PATTERNS.items():
                if anahtar == "gorev_bitti":
                    continue  # bitiş etiketi loop koruması kapsamı dışında

                eslesme = desen.search(mesaj)
                if eslesme:
                    # tek grup (çoğu araç) ya da çoklu grup (tarayici_tikla, tarayici_yaz, dosya_yaz) fark etmeksizin
                    # tüm grupları birleştirip normalize ediyoruz
                    parametreler = "|".join(
                        (g or "").strip().lower() for g in eslesme.groups()
                    )
                    return f"{anahtar}::{parametreler}"

            return None
        
        def coder_node(state: GhostState):
            dosya_yolu = self.yol_duzelt(state["son_istenen_dosya"])
            talimat = state["son_talimat"]
            
            mevcut_kod = ""
            if os.path.exists(dosya_yolu):
                try:
                    with open(dosya_yolu, "r", encoding="utf-8") as f:
                        mevcut_kod = f.read()
                except Exception:
                    pass
                    
            try:
                saf_kod = self.worker.saf_kod_uret(talimat, mevcut_kod)
                ui_formati = f"[DOSYA_YAZ: {dosya_yolu}]\n<<<KOD_BASLANGIC>>>\n{saf_kod}\n<<<KOD_BITIS>>>"
                return {"messages": [{"role": "assistant", "content": ui_formati}]}
            except Exception as e:
                return {"messages": [{"role": "assistant", "content": f"[SİSTEM HATA] Taşeron çöktü: {e}"}]}

        # YENİ DÜĞÜM: Araçları Graph İçinde Çalıştıran Merkez
        def tools_node(state: GhostState):
            son_mesaj = state["messages"][-1]["content"]
            calisan_araclar = state.get("calisan_araclar", [])

            # Bu turda çağrılmak istenen aracın "imzasını" çıkar (araç adı + normalize edilmiş parametre)
            imza = _arac_imzasi_cikar(son_mesaj)   # örn: "ŞARKI_AÇ::don't stop me now - queen"

            if imza and imza in calisan_araclar:
                # Kod seviyesinde ENGELLE, gerçek API'ye hiç gitme
                gozlem = (f"[SİSTEM UYARI]: '{imza}' bu görevde zaten denendi ve aynı sonucu (hata) verecek. "
                        f"TEKRAR ÇAĞIRMA. Patron'a durumu açıkla ve [GOREV_BITTI: ...] ile bitir.")
                return {"messages": [{"role": "system", "content": gozlem}]}

            gozlem = self.tool_runner(son_mesaj)
            return {
                "messages": [{"role": "system", "content": gozlem}],
                "calisan_araclar": [imza] if imza else []
            }

        # YENİ YÖNLENDİRİCİ: Çok daha akıllı bir karar mekanizması
        def yonlendirici(state: GhostState):
            son_mesaj = state["messages"][-1]["content"]
            
            if "[KOD_ISTE" in son_mesaj:
                return "coder"
            elif "[GOREV_BITTI" in son_mesaj:
                return END
            # GOREV_BITTI veya KOD_ISTE dışındaki diğer tüm [ETİKET] kullanımlarında tools node'a git
            elif re.search(r'\[[A-ZÇĞİÖŞÜ_]+:.*?\]', son_mesaj): 
                return "tools"
            else:
                return END

        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("coder", coder_node)
        workflow.add_node("tools", tools_node) # Araç düğümünü ağa ekledik
        
        workflow.set_entry_point("supervisor")
        workflow.add_conditional_edges("supervisor", yonlendirici)
        
        # MÜKEMMEL DÖNGÜ: Araç çalıştıktan sonra sonuçla birlikte Yöneticiye geri döner!
        workflow.add_edge("tools", "supervisor") 
        
        # Kod yazıldıktan sonra doğrudan Patron'a gösterilmesi için döngüyü bitir
        workflow.add_edge("coder", "tools") 
        
        return workflow.compile()

    def _raw_supervisor_call(self) -> tuple[str, str]:
        baslangic_durumu = {
            "messages": self.supervisor.mesaj_gecmisi,
            "son_istenen_dosya": "",
            "son_talimat": ""
        }

        config = {"recursion_limit": 15}
        
        # 1. Döngüden önceki geçmiş mesaj sayısını hafızaya al
        onceki_mesaj_sayisi = len(self.supervisor.mesaj_gecmisi)
        
        sonuc_state = self.graph.invoke(baslangic_durumu, config)

        # 2. Döngü boyunca Ghost'un ürettiği TÜM yeni mesajları yakala
        yeni_mesajlar = sonuc_state["messages"][onceki_mesaj_sayisi:]
        
        # 3. Modelin tüm çıktılarını (araç etiketleri + GOREV_BITTI) tek bir hafıza bloğunda birleştir
        birlestirilmis_hafiza = ""
        for msg in yeni_mesajlar:
            if msg.get("role") == "assistant":
                birlestirilmis_hafiza += msg.get("content", "") + "\n"
        
        birlestirilmis_hafiza = birlestirilmis_hafiza.strip()

        # 4. Ghost'un kalıcı geçmişine sadece bu birleştirilmiş bloğu ekle
        self.supervisor.mesaj_gecmisi.append({"role": "assistant", "content": birlestirilmis_hafiza})

        # UI için yine son mesajı çekiyoruz (Arayüzde tool logları görünmeyecek)
        son_mesaj = sonuc_state["messages"][-1]["content"]
        model_name = "Qwen 480B (Mühendis Kodluyor...)" if "[DOSYA_YAZ:" in son_mesaj else "GPT-OSS 120B (Yönetici)"

        return son_mesaj, model_name    
    
    def __call__(self, user_input):
        self.supervisor.mesaj_gecmisi.append({"role": "user", "content": user_input})
        cevap, model = self._raw_supervisor_call()
        return cevap, model