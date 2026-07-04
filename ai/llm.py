import re
import os   
import requests
import platform
import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

# 1. ORTAK BİLİNÇ (State)
# ChatLLM'deki manuel 'mesaj_gecmisi' listesinin yerini alır
class GhostState(TypedDict):
    messages: Annotated[list, operator.add]
    son_istenen_dosya: str
    son_talimat: str

# 2. DÜĞÜMLER (Nodes)
def supervisor_node(state: GhostState):
    # ChatLLM (_raw_call) burada çalışır
    # Eğer model [KOD_ISTE: dosya | talimat] üretirse, bu bilgileri state'e kaydeder
    pass

def coder_node(state: GhostState):
    # QwenWorker burada çalışır
    # state["son_talimat"] ve state["son_istenen_dosya"] verilerini alıp kod üretir
    pass

# 3. KARAR MEKANİZMASI (Conditional Edge)
def yonlendirici(state: GhostState):
    son_mesaj = state["messages"][-1]
    if "[KOD_ISTE" in son_mesaj:
        return "coder" # Qwen'e yolla
    elif "[GOREV_BITTI" in son_mesaj:
        return END # Döngüyü bitir, Patron'a cevap ver
    else:
        return "tools" # command_handler'a yolla

# GRAPH İNŞASI
workflow = StateGraph(GhostState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("coder", coder_node)

workflow.set_entry_point("supervisor")
workflow.add_conditional_edges("supervisor", yonlendirici)
workflow.add_edge("coder", "supervisor") # Mühendis kodu yazınca tekrar Yöneticiye döner

ghost_brain = workflow.compile()

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
        
        [ARAÇ SEÇİMİ HİYERARŞİSİ VE KESİN KURALLAR]
        Eğer bir işlem için birden fazla araç uygun görünüyorsa, aşağıdaki hiyerarşiyi KESİNLİKLE takip et:

        1. ÖNCELİK (API ve İşletim Sistemi): Kendi içindeki yerel sistem komutları her zaman ilk tercihindir. 
        - Bir uygulama açılacaksa DAİMA [UYGULAMA_AC: ...] kullan.
        - Müzik veya playlist çalınacaksa DAİMA [ŞARKI_AÇ: ...] veya [PLAYLIST_AÇ: ...] kullan. Görsel olarak ekranda tıklamaya veya tarayıcıya girmeye ÇALIŞMA.
        - İnternette genel bir bilgi aranacaksa DAİMA [ARAMA: ...] kullan.

        2. ÖNCELİK (Tarayıcı ve Görsel Gözlem): Tarayıcı/Ekran araçlarını SADECE kendi API'nle çözemediğin spesifik UI işlemlerinde kullan.
        - Örnek: "Trendyol'dan ayakkabı fiyatlarına bak", "Ekranda şu an ne yazıyor oku" veya "Şu sitedeki butona tıkla" gibi doğrudan arayüz etkileşimi gereken durumlarda [GOZLEM_YAP: ...] kullan.
        
        [ÖLÜMCÜL KURAL - DÖNGÜ YASAĞI]
        AYNI aracı, AYNI parametrelerle üst üste İKİ KEZ ASLA KULLANMA!
        - Eğer [ARAMA] aracı sana "Hata" veya "Bulunamadı" diyorsa, ASLA tekrar arama yapma. Yenilgiyi kabul et ve Patron'a "Arama motoru API'si hata veriyor, internete çıkamıyorum" de.
        - Eğer [GOZLEM_YAP] ile sayfaya bakıp aradığın butonu/kutuyu bulamadıysan, inat edip tekrar [GOZLEM_YAP] ÇAĞIRMA. İşlemi iptal et ve Patron'a "Sitede aradığım butonu bulamadım" de.
        - Aynı aracı ikinci kez kullanınca bunu döngü olarak görüp seni atan bir mekanizmam var o yüzden tekrar deneme ilk seferde yapmaya çalış olmazsa tekrar etiket geçme!
        - Senden istenilen iş bittiğinde GÖREVİ TAMAMLA etiketini çağır ve sonucu ekrana bas.
        
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
