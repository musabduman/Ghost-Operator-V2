import os
import json
import platform
import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import requests

# 1. ORTAK BİLİNÇ (State)
class GhostState(TypedDict):
    messages: Annotated[list, operator.add]
    son_istenen_dosya: str
    son_talimat: str
    calisan_araclar: Annotated[list, operator.add]
    tool_calls: list


# ── JSON TOOL ŞEMASI (gpt-oss native tool calling) ──────────────────────────
# Eskiden bu liste ana_kurallar'ın içinde [ETİKET: <param>] formatında
# metin olarak yazılıyordu ve supervisor_node'un ürettiği ham metin regex'le
# taranıyordu. gpt-oss (cloud dahil) native function calling destekliyor,
# bu yüzden model artık "doğru formatta yazmayı hatırlamak" zorunda değil;
# hangi tool'u ne zaman çağıracağını API seviyesinde, tool_calls olarak
# structured döndürüyor.
TOOLS = [
    {"type": "function", "function": {
        "name": "arama",
        "description": "İnternette genel bir bilgi aramak için kullan (haber, güncel olay, tanım, maç skoru, hava durumu vb).",
        "parameters": {"type": "object", "properties": {
            "sorgu": {"type": "string", "description": "Aranacak sorgu"}
        }, "required": ["sorgu"]}
    }},
    {"type": "function", "function": {
        "name": "klasor_ac",
        "description": "Var olan bir klasörü dosya gezgininde açar.",
        "parameters": {"type": "object", "properties": {
            "yol": {"type": "string", "description": "Açılacak klasörün tam yolu"}
        }, "required": ["yol"]}
    }},
    {"type": "function", "function": {
        "name": "uygulama_ac",
        "description": "Bir masaüstü uygulamasını başlatır (örn: code, chrome, spotify, discord).",
        "parameters": {"type": "object", "properties": {
            "isim": {"type": "string", "description": "Uygulamanın sistem kısa adı"}
        }, "required": ["isim"]}
    }},
    {"type": "function", "function": {
        "name": "sarki_ac",
        "description": "Spotify'da belirli bir şarkıyı çalar. Müzik isteklerinde görsel/tarayıcı araçlarını DEĞİL, daima bunu kullan.",
        "parameters": {"type": "object", "properties": {
            "sarki": {"type": "string", "description": "Şarkı ve sanatçı adı"}
        }, "required": ["sarki"]}
    }},
    {"type": "function", "function": {
        "name": "playlist_ac",
        "description": "Spotify'da bir çalma listesini başlatır.",
        "parameters": {"type": "object", "properties": {
            "liste": {"type": "string", "description": "Çalma listesi adı"}
        }, "required": ["liste"]}
    }},
    {"type": "function", "function": {
        "name": "not_al",
        "description": "Kalıcı olarak hatırlanması gereken bir bilgiyi hafızaya kazır.",
        "parameters": {"type": "object", "properties": {
            "bilgi": {"type": "string", "description": "Hatırlanacak bilgi, 3. şahısla kısa özet"}
        }, "required": ["bilgi"]}
    }},
    {"type": "function", "function": {
        "name": "klasor_yap",
        "description": "Yeni bir klasör oluşturur. İçine .py/.txt gibi dosya konacaksa BUNU KULLANMA, dosya_yaz zaten klasörü kendi oluşturur.",
        "parameters": {"type": "object", "properties": {
            "yol": {"type": "string", "description": "Oluşturulacak klasörün tam yolu"}
        }, "required": ["yol"]}
    }},
    {"type": "function", "function": {
        "name": "klasor_incele",
        "description": "Bir klasörün içeriğini listeler (röntgen).",
        "parameters": {"type": "object", "properties": {
            "yol": {"type": "string", "description": "İncelenecek klasörün tam yolu"}
        }, "required": ["yol"]}
    }},
    {"type": "function", "function": {
        "name": "kodu_calistir",
        "description": "Bir Python dosyasını çalıştırıp çıktısını veya hatasını döndürür. Ayrıca daha önce üretilmiş dinamik tool script'lerini çalıştırmak için de kullanılır.",
        "parameters": {"type": "object", "properties": {
            "yol": {"type": "string", "description": "Çalıştırılacak dosyanın tam yolu"}
        }, "required": ["yol"]}
    }},
    {"type": "function", "function": {
        "name": "dosya_oku",
        "description": "Bir dosyanın içeriğini okur.",
        "parameters": {"type": "object", "properties": {
            "yol": {"type": "string", "description": "Okunacak dosyanın tam yolu"}
        }, "required": ["yol"]}
    }},
    {"type": "function", "function": {
        "name": "dosya_yaz",
        "description": "Bir dosyaya içerik yazar (üzerine yazar veya oluşturur). Klasör yoksa otomatik oluşturur.",
        "parameters": {"type": "object", "properties": {
            "yol": {"type": "string", "description": "Yazılacak dosyanın tam yolu"},
            "icerik": {"type": "string", "description": "Dosyaya yazılacak tam içerik"}
        }, "required": ["yol", "icerik"]}
    }},
    {"type": "function", "function": {
        "name": "gozlem_yap",
        "description": (
            "Bir web sayfasının veya masaüstünün buton/kutularını keşfeder. "
            "Steam/Trendyol/Yemeksepeti gibi e-ticaret, vitrin veya liste "
            "sayfalarında (ürün/fiyat varsa) site_oku YERİNE bunu kullan."
        ),
        "parameters": {"type": "object", "properties": {
            "hedef": {"type": "string", "description": "Tam URL veya 'masaustu'"}
        }, "required": ["hedef"]}
    }},
    {"type": "function", "function": {
        "name": "tarayici_tikla",
        "description": "Belirtilen URL'de bir buton veya linke tıklar.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "Tam URL"},
            "hedef": {"type": "string", "description": "Tıklanacak buton/link metni"}
        }, "required": ["url", "hedef"]}
    }},
    {"type": "function", "function": {
        "name": "tarayici_yaz",
        "description": "Belirtilen URL'deki bir kutuya metin yazar.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "Tam URL"},
            "kutu": {"type": "string", "description": "Kutunun adı veya placeholder'ı"},
            "metin": {"type": "string", "description": "Yazılacak metin"}
        }, "required": ["url", "kutu", "metin"]}
    }},
    {"type": "function", "function": {
        "name": "site_oku",
        "description": (
            "Wikipedia, haber veya blog gibi uzun metinli sayfaların içeriğini okur. "
            "Katalog/e-ticaret sayfaları için KULLANMA, onun yerine gozlem_yap kullan."
        ),
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "Tam URL"}
        }, "required": ["url"]}
    }},
    {"type": "function", "function": {
        "name": "ekran_goruntusu",
        "description": "Kullanıcının ekranına bakıp analiz eder (görsel gözlem / vizyon).",
        "parameters": {"type": "object", "properties": {
            "ne_arayacagim": {"type": "string", "description": "Ekranda nelere dikkat edileceği"}
        }, "required": ["ne_arayacagim"]}
    }},
    {"type": "function", "function": {
        "name": "kod_iste",
        "description": (
            "Yeni bir kod dosyası yazılmasını veya var olan bir dosyanın güncellenmesini "
            "işçi modele (Qwen) devreder. Kodu SEN yazmazsın, bu aracı çağırırsın."
        ),
        "parameters": {"type": "object", "properties": {
            "dosya": {"type": "string", "description": "tool/ klasörü altında tam dosya yolu, örn: tool/hava_durumu.py"},
            "talimat": {"type": "string", "description": "İşçiye verilecek net, doğal dilde kod yazma talimatı (Python kodu/markdown YAZMA)"}
        }, "required": ["dosya", "talimat"]}
    }},
    {"type": "function", "function": {
        "name": "gorev_bitti",
        "description": (
            "Aradığın bilgiye ulaştığında, işlemi tamamladığında veya sohbeti bitirdiğinde "
            "döngüden çıkmak için KESİNLİKLE bunu çağır."
        ),
        "parameters": {"type": "object", "properties": {
            "ozet": {"type": "string", "description": "Patrona verilecek nihai cevap veya özet"}
        }, "required": ["ozet"]}
    }},
]


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

        [ARAÇ ÇAĞIRMA KURALI]
        Kullanıcı fiziksel bir eylem isterse veya güncel/bilmediğin bir bilgi soruyorsa, sana tanımlanan tool'lardan (fonksiyonlardan) uygun olanını çağır. Sohbet ediyorsan hiçbir tool çağırma, doğrudan cevap ver. Aradığın bilgiye ulaştığında veya işlemi bitirdiğinde KESİNLİKLE gorev_bitti tool'unu çağır — bu, döngüden çıkmanın TEK yolu.

        [BİLGİ EKSİKLİĞİ VE OTONOM ARAMA]
        Eğer kullanıcı sana güncel bir bilgi, anlık bir olay (maç sonuçları, haberler, hava durumu vb.) sorarsa veya cevabı kendi veritabanında kesin olarak bilmiyorsan ASLA tahmin etme veya kafadan atma! arama tool'unu kullan.

        [POP-UP VE ENGEL AŞMA KURALI (SOKAK KURNAZLIĞI)]
        Eğer girdiğin bir sayfada makale veya ürün yerine "Yaş Doğrulama", "Çerezleri Kabul Et (Accept Cookies)" veya "18 Yaşından Büyük müsünüz?" gibi bir engel çıkarsa ASLA pes etme veya bunu kullanıcıya okuma!
        - Bu bir engeldir. İnisiyatif al!
        - Hemen tarayici_tikla aracıyla "Kabul Et", "Sayfayı Görüntüle" veya "Evet" butonlarına tıkla.
        - Eğer yaş girmen gerekiyorsa tarayici_yaz ile rastgele bir yetişkin yılı (örn: 1990) gir.
        - Engeli aştıktan sonra asıl görevine (okumaya veya gözlemlemeye) devam et.

        [TARAYICI AKIŞ KURALI - KESİN]
        Bir web sitesinde işlem yapman gerektiğinde şu sırayı takip et:
        ADIM 1 → Önce gozlem_yap ile sayfanın buton ve kutularını keşfet.
        ADIM 2 → Gözlem sonucuna göre tarayici_yaz ile yazı yaz.
        ADIM 3 (SAYFA TİPİNE GÖRE ARAÇ SEÇİMİ - ÇOK ÖNEMLİ!) → Hedef sayfaya ulaştığında sayfanın türüne göre şu iki araçtan birini seç:
        - A) KÜTÜPHANE/MAKALE: Eğer girdiğin sayfa Wikipedia, Haber veya Blog gibi uzun metinli bir sayfaysa doğrudan site_oku kullan.
        - B) MAĞAZA/KATALOG: Eğer girdiğin sayfa Steam, Trendyol, Yemeksepeti gibi bir E-ticaret, vitrin veya Liste sayfasıysa (ürünler ve fiyatlar varsa) ASLA site_oku KULLANMA. Bunun yerine gozlem_yap aracını çağır.
        ADIM 4 → Eğer girdiğin sayfada uzun bir makale, yazı veya bilgi okuman gerekiyorsa site_oku aracını kullan ve metni çek.
        ⚠️ Her adımda SADECE BİR tool çağır. Aynı turda birden fazla tool çağırma.
        ADIM 5 → Bilgiyi elde ettikten, sorunun cevabını bulduktan veya sayfayı okuduktan sonra KESİNLİKLE başka bir tarayıcı aracı çağırma. Doğrudan gorev_bitti tool'unu çağırarak süreci sonlandır.

        [YETENEK EKSİKLİĞİ VE OTOMATİK ARAÇ (TOOL) ÜRETİMİ - KRİTİK]
        1. Eğer Patron senden AÇIKÇA yeni bir araç/tool eklemeni isterse derhal kod_iste tool'unu çağır.
        2. KONTROLLÜ İNİSİYATİF: Patron senden teknik bir işlem (örn: sistem RAM'ini oku, anlık döviz çek, ekran parlaklığını kıs) istediğinde; eğer mevcut araçlarınla ve arama ile bunu ÇÖZEMİYORSAN, ASLA "Bunu yapamam" deme! İnisiyatif al ve sorunu çözecek yeni bir aracı otonom olarak üretmek için kod_iste kullan.
        3. DİKKAT: Sadece arama yaparak bulunabilecek basit bilgiler (örn: Hava durumu, maç skoru, vikipedi bilgisi) için DURDUK YERE KOD YAZMA. Sadece API bağlantısı, sistem kontrolü veya sürekli kullanılacak teknik bir altyapı gerekiyorsa inisiyatif al.
        4. DOSYA YOLU KURALI (ÖLÜMCÜL): kod_iste'nin dosya parametresinde KESİNLİKLE ama KESİNLİKLE "tool/<arac_adi>.py" şeklinde klasör adıyla tam yol ver. Asla sadece "arac_adi.py" deme! talimat parametresinde Qwen'e, sonucun terminale net bir şekilde "print" edilmesini emret.
        5. YENİ TOOL ekledikten sonra çalıştırmasını istemişse unutmadan kodu_calistir ile çalıştırıp cevabını ver.
        6. kod_iste'nin talimat parametresine ASLA Python kodu veya Markdown (```) ekleme! Sen koda dokunma, sadece işçiye ne yapması gerektiğini doğal dille tarif et.

        [ÇOKLU GÖREV VE BİRLEŞTİRME KURALI]
        Eğer kullanıcı senden tek bir mesajda iki farklı şey isterse (Örn: "Arama yap ve sonra şarkı aç"), araçları SIRAYLA tek tek çağır. İki araç işlemi de bittiğinde, araçlardan dönen sonuçları asla unutma ve KESİNLİKLE tek bir gorev_bitti çağrısı altında harmanlayarak Patron'a sun.

        [ARAÇ SEÇİMİ HİYERARŞİSİ VE KESİN KURALLAR]
        Eğer bir işlem için birden fazla araç uygun görünüyorsa, aşağıdaki hiyerarşiyi KESİNLİKLE takip et:

        1. ÖNCELİK (API ve İşletim Sistemi): Kendi içindeki yerel sistem komutları her zaman ilk tercihindir.
        - Bir uygulama açılacaksa DAİMA uygulama_ac kullan.
        - Müzik veya playlist çalınacaksa DAİMA sarki_ac veya playlist_ac kullan. Görsel olarak ekranda tıklamaya veya tarayıcıya girmeye ÇALIŞMA.
        - İnternette genel bir bilgi aranacaksa DAİMA arama kullan.

        2. ÖNCELİK (Tarayıcı ve Görsel Gözlem): Tarayıcı/Ekran araçlarını SADECE kendi API'nle çözemediğin spesifik UI işlemlerinde kullan.
        - Örnek: "Trendyol'dan ayakkabı fiyatlarına bak", "Ekranda şu an ne yazıyor oku" veya "Şu sitedeki butona tıkla" gibi doğrudan arayüz etkileşimi gereken durumlarda gozlem_yap kullan.

        [DÖNGÜ KORUMASI - SADECE GERÇEK TEKRARLARDA GEÇERLİ]
        Bu kural SADECE aynı görev içinde, bir aracı TAM OLARAK AYNI parametrelerle art arda tekrar denediğinde geçerli. Farklı bir şarkı, farklı bir arama sorgusu, ya da Patron'un yeni bir isteği için daha önce kullandığın bir aracı tekrar kullanmak tamamen normal ve serbest — bunu döngü sanma.
        - Bir araç "Hata" veya "Bulunamadı" derse, aynı parametreyle hemen tekrar deneme; Patron'a durumu açıkla, istersen alternatif öner.
        - gozlem_yap ile aradığın öğeyi bulamadıysan, aynı sayfada aynı şeyi tekrar arama; sonucu Patron'a bildir.
        - İşin bittiğinde gorev_bitti tool'unu çağır.

        [KOD YAZMA KURALLARI - KESİN VE DEĞİŞMEZ KURAL!]
        Sen bir YÖNETİCİSİN (Supervisor). Kodu SEN YAZMAYACAKSIN.
        Arka planda senin emrinde çalışan ve sadece kod yazmakla görevli olan "İşçi Yapay Zeka" modelleri var.
        Eğer Kullanıcı (Patron) yeni bir dosya oluşturmanı, kod yazmanı veya var olan bir kodu güncellemeni isterse, işi kod_iste tool'unu çağırarak bu işçilere devretmek ZORUNDASIN.

        DOSYA KURALLARI:
            Şu anki aktif İşletim Sistemi: {self.os_name}
            Bir dosya yolu belirtirken asla kullanıcı adını tahmin etme. Mevcut işletim sistemi ({self.os_name}) standartlarına uygun kısa yollar kullan.
        """

        tool_klasoru = os.path.join(os.getcwd(), "tools")
        if os.path.exists(tool_klasoru):
            scriptler = [dosya for dosya in os.listdir(tool_klasoru) if dosya.endswith(".py")]
            if scriptler:
                dinamik_araclar = "\n\n[OTONOM DİNAMİK ARAÇLAR]\nŞu an emrine amade hazır Python scriptleri (Mikroservisler) şunlardır:\n"
                for script in scriptler:
                    dinamik_araclar += f"- {script} -> Kullanmak için kodu_calistir tool'unu şu yolla çağır: {tool_klasoru}/{script}\n"

                self.ana_kurallar += dinamik_araclar

        self.mesaj_gecmisi = [{"role": "system", "content": self.ana_kurallar}]

    def load_history(self, gecmis_mesajlar: list):
        """Bir oturuma geçiş yapıldığında geçmiş mesajları yükler."""
        self.mesaj_gecmisi = [{"role": "system", "content": self.ana_kurallar}]
        for msg in gecmis_mesajlar:
            role = msg.get("role") if msg.get("role") in ("assistant", "tool", "user") else "user"
            temiz_msg = {"role": role, "content": msg.get("content", "")}
            if msg.get("tool_calls"):
                temiz_msg["tool_calls"] = msg["tool_calls"]
            self.mesaj_gecmisi.append(temiz_msg)

    def _raw_call(self, messages=None, tools=None) -> dict:
        """Artık ham metin değil, Ollama'nın döndürdüğü TAM message objesini
        döndürür (content + tool_calls + varsa thinking). Regex ile bu objenin
        içinden niyet çıkarmaya gerek yok, tool_calls zaten yapılandırılmış."""
        payload = {
            "model": self.model,
            "messages": messages if messages is not None else self.mesaj_gecmisi,
            "stream": False,
            "options": {"temperature": 0.7, "num_ctx": 4096}
        }
        if tools:
            payload["tools"] = tools

        response = requests.post(self.api_url, json=payload, timeout=90)
        response.raise_for_status()
        return response.json()["message"]


# 2. İŞÇİ BEYİN (değişmedi — Qwen zaten tool calling kullanmıyor, saf kod üretiyor)
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

            import re
            saf_kod = re.sub(r"^```[\w]*\n?", "", saf_kod)
            saf_kod = re.sub(r"\n?```$", "", saf_kod).strip()

            return saf_kod
        except Exception as e:
            raise Exception(f"Taşeron (Qwen) Çöktü: {e}")


# 3. ORKESTRA ŞEFİ
class GhostController:
    def __init__(self, tool_runner=None):
        # tool_runner artık ham metin değil, (isim: str, args: dict) alan bir
        # fonksiyon olmalı. command_handler.py tarafında _execute_tool_call.
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
            msg = self.supervisor._raw_call(state["messages"], tools=TOOLS)
            tool_calls = msg.get("tool_calls") or []

            dosya, talimat = "", ""
            if tool_calls and tool_calls[0]["function"]["name"] == "kod_iste":
                args = tool_calls[0]["function"]["arguments"]
                dosya = args.get("dosya", "")
                talimat = args.get("talimat", "")

            return {
                "messages": [msg],
                "tool_calls": tool_calls,
                "son_istenen_dosya": dosya,
                "son_talimat": talimat,
            }

        def tools_node(state: GhostState):
            tool_calls = state.get("tool_calls") or []
            if not tool_calls:
                return {"messages": []}

            call = tool_calls[0]
            isim = call["function"]["name"]
            args = call["function"]["arguments"]
            calisan_araclar = state.get("calisan_araclar", [])

            # İmza artık regex ile metinden çıkarılmıyor; tool_call zaten
            # yapılandırılmış (isim + args dict), doğrudan JSON'a çeviriyoruz.
            imza = f"{isim}::{json.dumps(args, sort_keys=True, ensure_ascii=False)}"

            if imza in calisan_araclar:
                gozlem = (
                    f"Bu araç ('{isim}') bu görevde aynı parametrelerle zaten denendi ve "
                    f"muhtemelen aynı sonucu (hata) verecek. TEKRAR ÇAĞIRMA. "
                    f"Patron'a durumu açıkla ve gorev_bitti ile bitir."
                )
                return {"messages": [{"role": "tool", "content": gozlem}]}

            gozlem = self.tool_runner(isim, args)
            return {
                "messages": [{"role": "tool", "content": gozlem}],
                "calisan_araclar": [imza],
            }

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
                # Eskiden [DOSYA_YAZ: ...] tag'i olarak paketlenip tools_node'a
                # gönderiliyordu ki regex onu yakalasın. Artık dosya_yaz tool'unu
                # doğrudan çağırıyoruz, ara paketleme adımına gerek yok.
                yazma_sonucu = self.tool_runner("dosya_yaz", {"yol": dosya_yolu, "icerik": saf_kod})
                return {"messages": [{"role": "tool", "content": f"Kod işçisi (Qwen) dosyayı yazdı. {yazma_sonucu}"}]}
            except Exception as e:
                return {"messages": [{"role": "tool", "content": f"[SİSTEM HATA] Taşeron çöktü: {e}"}]}

        def yonlendirici(state: GhostState):
            tool_calls = state.get("tool_calls") or []
            if not tool_calls:
                # Model tool çağırmadan düz metin cevap verdi (sohbet durumu)
                return END
            isim = tool_calls[0]["function"]["name"]
            if isim == "kod_iste":
                return "coder"
            if isim == "gorev_bitti":
                return END
            return "tools"

        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("coder", coder_node)
        workflow.add_node("tools", tools_node)

        workflow.set_entry_point("supervisor")
        workflow.add_conditional_edges("supervisor", yonlendirici)

        # Araç veya coder çalıştıktan sonra sonuçla birlikte Yöneticiye geri dön
        workflow.add_edge("tools", "supervisor")
        workflow.add_edge("coder", "supervisor")

        return workflow.compile()

    def _raw_supervisor_call(self) -> tuple[str, str]:
        baslangic_durumu = {
            "messages": self.supervisor.mesaj_gecmisi,
            "son_istenen_dosya": "",
            "son_talimat": "",
            "calisan_araclar": [],
            "tool_calls": [],
        }

        config = {"recursion_limit": 15}

        onceki_mesaj_sayisi = len(self.supervisor.mesaj_gecmisi)
        sonuc_state = self.graph.invoke(baslangic_durumu, config)
        yeni_mesajlar = sonuc_state["messages"][onceki_mesaj_sayisi:]

        # UI etiketi için: bu turda kod_iste çağrıldı mı?
        kod_yazildi_mi = any(
            m.get("role") == "assistant"
            and any(tc["function"]["name"] == "kod_iste" for tc in (m.get("tool_calls") or []))
            for m in yeni_mesajlar
        )

        # Nihai cevap artık serbest metinden regex ile temizlenmiyor;
        # gorev_bitti tool_call'ının 'ozet' argümanından doğrudan okunuyor.
        nihai_cevap = ""
        for m in yeni_mesajlar:
            if m.get("role") != "assistant":
                continue
            tool_calls = m.get("tool_calls") or []
            for tc in tool_calls:
                if tc["function"]["name"] == "gorev_bitti":
                    nihai_cevap = tc["function"]["arguments"].get("ozet", "")
            if not tool_calls and m.get("content"):
                # Model hiç tool çağırmadan düz cevap verdiyse (sohbet durumu)
                nihai_cevap = m["content"]

        # Kalıcı geçmişe bu turun TÜM mesajlarını (tool çağrıları + sonuçları
        # dahil) yapılandırılmış haliyle ekliyoruz. Eskiden tüm assistant
        # mesajları tek bir string'de eritilip öyle ekleniyordu; bu hem
        # modelin bir turda birden fazla etiket yazmasını normalleştiriyordu
        # hem de tool sonuçlarını kalıcı geçmişten tamamen siliyordu.
        self.supervisor.mesaj_gecmisi.extend(yeni_mesajlar)

        model_name = "Qwen 480B (Mühendis Kodladı)" if kod_yazildi_mi else "GPT-OSS 120B (Yönetici)"

        return nihai_cevap.strip() if nihai_cevap else "...", model_name

    def __call__(self, user_input):
        self.supervisor.mesaj_gecmisi.append({"role": "user", "content": user_input})
        cevap, model = self._raw_supervisor_call()
        return cevap, model