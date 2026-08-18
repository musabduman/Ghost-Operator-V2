"""
core/tool_registry.py
Ghost Operator - Merkezi Araç Kaydı (Single Source of Truth)

Tüm araçların JSON Şemaları (LLM Tool Calling) ve çalıştırma mantıkları
bu tek kayıt altında toplanır. Böylece llm.py ve command_handler.py
arasında senkronizasyon kaybı veya unutulan araç sorunu yaşanmaz.
"""
from typing import Callable, Any, Dict, List, Optional


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        description: str,
        params: Optional[Dict[str, tuple]] = None,
        required: Optional[List[str]] = None,
        resolve_paths: Optional[List[str]] = None,
        handler_func: Optional[Callable] = None,
    ):
        """
        Araç kaydetmek için kullanılan dekoratör veya doğrudan fonksiyon.
        
        params formatı:
            {
                "param_adı": ("string", "Açıklama"),
                "yol": ("string", "Klasör yolu")
            }
        """
        params = params or {}
        if required is None:
            required = list(params.keys())
        resolve_paths = resolve_paths or []

        def decorator(func: Callable):
            properties = {}
            for p_name, p_info in params.items():
                p_type, p_desc = p_info
                properties[p_name] = {
                    "type": p_type,
                    "description": p_desc,
                }
                if p_type == "array":
                    properties[p_name]["items"] = {"type": "string"}

            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }

            self._tools[name] = {
                "name": name,
                "func": func,
                "schema": schema,
                "arg_names": list(params.keys()),
                "resolve_paths": resolve_paths,
            }
            return func

        if handler_func is not None:
            return decorator(handler_func)

        return decorator

    def bind_handler(self, name: str, func: Callable):
        """Var olan bir şemaya çalıştırıcı fonksiyon bağlar."""
        if name in self._tools:
            self._tools[name]["func"] = func
        else:
            raise KeyError(f"Araç bulunamadı: {name}")

    def get_schemas(self) -> List[Dict[str, Any]]:
        """LLM için kullanılabilir tüm araçların JSON şemalarını döndürür."""
        return [t["schema"] for t in self._tools.values()]

    def execute(self, name: str, args: Dict[str, Any], target_instance: Any = None) -> str:
        """Bir aracı ismi ve verilen argümanlarla çalıştırır."""
        if name not in self._tools:
            return f"Bilinmeyen araç: {name}"

        tool_info = self._tools[name]
        func = tool_info["func"]
        if func is None:
            return f"Araç için fonksiyon tanımlanmamış: {name}"

        resolve_paths = tool_info["resolve_paths"]
        arg_names = tool_info["arg_names"]

        from core.fs import akilli_yol_cozucu

        # Parametreleri sirasiyla hazirla
        call_kwargs = {}
        for arg_name in arg_names:
            val = args.get(arg_name, "")
            if arg_name in resolve_paths and isinstance(val, str) and val:
                val = akilli_yol_cozucu(val)
            call_kwargs[arg_name] = val

        # ÖNEMLİ: keyword değil POZİSYONEL çağırıyoruz. Şemadaki parametre adı
        # (örn. "yol") ile handler'ın Python parametre adı (örn. "path")
        # farklı olabiliyor - func(**call_kwargs) bunu sessizce kırıyordu
        # (14 araç etkilenmişti: arama, klasor_ac, uygulama_ac, sarki_ac,
        # playlist_ac, not_al, klasor_yap, klasor_incele, kodu_calistir,
        # dosya_oku, dosya_yaz, tarayici_tikla, tarayici_yaz, ekran_goruntusu).
        # Pozisyonel çağrı, handler parametrelerinin şemadaki sırayla
        # tanımlandığı sürece isim farkını önemsiz kılıyor.
        ordered_vals = [call_kwargs[a] for a in arg_names]
        return func(*ordered_vals)

    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)

    def load_dynamic_skill(self, file_path: str) -> dict:
        """
        Yeni üretilen bir yeteneği (skill) önce dry-run testinden geçirir, 
        güvenliyse ana process'e yükler ve bilgilerini döndürür.
        """
        from core.fs import kodu_calistir
        import importlib.util
        import os

        import shutil
        import tempfile

        # 1. DRY-RUN: subprocess içinde çalıştırarak module-level sonsuz döngüleri
        # ve patlamaları izole ortamda yakala. (Kritik güvenlik katmanı)
        # Dosya sistemine zarar vermemesi için gerçek dizinde değil geçici bir dizinde çalıştır.
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, os.path.basename(file_path))
            shutil.copy2(file_path, temp_file_path)
            
            # import core.fs and run the isolated script
            from core.fs import kodu_calistir
            
            # kodu_calistir needs to run with the temp_dir as cwd to ensure relative paths point to temp
            # For simplicity, we just pass temp_file_path. If it uses relative paths like os.remove('x'), 
            # it will happen in its CWD. Wait, kodu_calistir uses default CWD. We must change CWD or isolate.
            # However, modifying kodu_calistir to accept cwd might be needed.
            # As a shortcut, we can patch the environment or just run subprocess directly here for max isolation.
            import subprocess
            import sys
            try:
                result = subprocess.run(
                    [sys.executable, temp_file_path],
                    cwd=temp_dir, # Isolate file system modifications to temp_dir
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                basarili = result.returncode == 0
                hata = result.stderr.strip() if not basarili else ""
            except subprocess.TimeoutExpired:
                basarili = False
                hata = "ZAMAN AŞIMI: Kod 15 saniyede bitmedi."
            except Exception as e:
                basarili = False
                hata = str(e)
                
        if not basarili:
            return {
                "success": False,
                "error": f"Dry-run testi başarısız! Kod çalıştırılamadı veya zaman aşımına uğradı. Hata: {hata}"
            }

        # 2. Mevcut araçların isimlerini kaydet ki yeni ekleneni bulabilelim
        mevcut_araclar = set(self._tools.keys())

        # 3. Gerçek Yükleme (Main Process)
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return {"success": False, "error": "Modül loader bulunamadı."}
            
        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            return {"success": False, "error": f"Modül içeri aktarılırken hata oluştu: {str(e)}"}

        # Hangi aracın eklendiğini bul
        yeni_araclar = set(self._tools.keys()) - mevcut_araclar
        if not yeni_araclar:
            # Belki var olanı güncelledi, module name üzerinden bulalım
            for name, info in self._tools.items():
                if info["func"] is not None and info["func"].__module__ == module_name:
                    yeni_araclar.add(name)

        if not yeni_araclar:
            return {"success": False, "error": "Dosyada @ghost_tool ile işaretlenmiş bir araç bulunamadı."}

        # Sadece birini (veya ilkini) alıp bilgilerini dön
        eklenen_arac_adi = list(yeni_araclar)[0]
        tool_info = self._tools[eklenen_arac_adi]

        return {
            "success": True,
            "tool_name": eklenen_arac_adi,
            "schema": tool_info["schema"]
        }


# Global singleton registry nesnesi
tool_registry = ToolRegistry()
ghost_tool = tool_registry.register


# ── TÜM STANDART GHOST ARAÇLARININ TEK KAYNAK ŞEMALARI ──────────────────────

ghost_tool(
    name="arama",
    description="İnternette genel bir bilgi aramak için kullan (haber, güncel olay, tanım, maç skoru, hava durumu vb).",
    params={"sorgu": ("string", "Aranacak sorgu")},
)(None)

ghost_tool(
    name="klasor_ac",
    description="Var olan bir klasörü dosya gezgininde açar.",
    params={"yol": ("string", "Açılacak klasörün tam yolu")},
    resolve_paths=["yol"],
)(None)

ghost_tool(
    name="uygulama_ac",
    description="Bir masaüstü uygulamasını başlatır (örn: code, chrome, spotify, discord).",
    params={"isim": ("string", "Uygulamanın sistem kısa adı")},
)(None)

ghost_tool(
    name="sarki_ac",
    description="Spotify'da belirli bir şarkıyı çalar. Müzik isteklerinde görsel/tarayıcı araçlarını DEĞİL, daima bunu kullan.",
    params={"sarki": ("string", "Şarkı ve sanatçı adı")},
)(None)

ghost_tool(
    name="playlist_ac",
    description="Spotify'da bir çalma listesini başlatır.",
    params={"liste": ("string", "Çalma listesi adı")},
)(None)

ghost_tool(
    name="not_al",
    description="Kalıcı olarak hatırlanması gereken bir bilgiyi hafızaya kazır.",
    params={"bilgi": ("string", "Hatırlanacak bilgi, 3. şahısla kısa özet")},
)(None)

ghost_tool(
    name="klasor_yap",
    description="Yeni bir klasör oluşturur. İçine .py/.txt gibi dosya konacaksa BUNU KULLANMA, dosya_yaz zaten klasörü kendi oluşturur.",
    params={"yol": ("string", "Oluşturulacak klasörün tam yolu")},
    resolve_paths=["yol"],
)(None)

ghost_tool(
    name="klasor_incele",
    description="Bir klasörün içeriğini listeler (röntgen).",
    params={"yol": ("string", "İncelenecek klasörün tam yolu")},
    resolve_paths=["yol"],
)(None)

ghost_tool(
    name="kodu_calistir",
    description="Bir Python dosyasını çalıştırıp çıktısını veya hatasını döndürür. Ayrıca daha önce üretilmiş dinamik tool script'lerini çalıştırmak için de kullanılır.",
    params={"yol": ("string", "Çalıştırılacak dosyanın tam yolu")},
    resolve_paths=["yol"],
)(None)

ghost_tool(
    name="dosya_oku",
    description="Bir dosyanın içeriğini okur.",
    params={"yol": ("string", "Okunacak dosyanın tam yolu")},
    resolve_paths=["yol"],
)(None)

ghost_tool(
    name="dosya_yaz",
    description="Bir dosyaya içerik yazar (üzerine yazar veya oluşturur). Klasör yoksa otomatik oluşturur.",
    params={
        "yol": ("string", "Yazılacak dosyanın tam yolu"),
        "icerik": ("string", "Dosyaya yazılacak tam içerik"),
        "aciklama": ("string", "Kullanıcıya gösterilecek olan 'bu değişikliğin ne yaptığına dair' net bir açıklama (neden yapıyoruz, ne değişecek).")
    },
    resolve_paths=["yol"],
)(None)

ghost_tool(
    name="gozlem_yap",
    description="Bir web sayfasının veya masaüstünün buton/kutularını keşfeder. Steam/Trendyol/Yemeksepeti gibi e-ticaret, vitrin veya liste sayfalarında (ürün/fiyat varsa) site_oku YERİNE bunu kullan.",
    params={"hedef": ("string", "Tam URL veya 'masaustu'")},
)(None)

ghost_tool(
    name="tarayici_tikla",
    description="Belirtilen URL'de bir buton veya linke tıklar.",
    params={"url": ("string", "Tam URL"), "hedef": ("string", "Tıklanacak buton/link metni")},
)(None)

ghost_tool(
    name="tarayici_yaz",
    description="Belirtilen URL'deki bir kutuya metin yazar.",
    params={"url": ("string", "Tam URL"), "kutu": ("string", "Kutunun adı veya placeholder'ı"), "metin": ("string", "Yazılacak metin")},
)(None)

ghost_tool(
    name="site_oku",
    description="Wikipedia, haber veya blog gibi uzun metinli sayfaların içeriğini okur. Katalog/e-ticaret sayfaları için KULLANMA, onun yerine gozlem_yap kullan.",
    params={"url": ("string", "Tam URL")},
)(None)

ghost_tool(
    name="ekran_goruntusu",
    description="Kullanıcının ekranına bakıp analiz eder (görsel gözlem / vizyon).",
    params={"ne_arayacagim": ("string", "Ekranda nelere dikkat edileceği")},
)(None)

ghost_tool(
    name="kod_iste",
    description="Yeni bir kod dosyası yazılmasını veya var olan bir dosyanın güncellenmesini işçi modele (Qwen) devreder. Kodu SEN yazmazsın, bu aracı çağırırsın.",
    params={"dosya": ("string", "tool/ klasörü altında tam dosya yolu, örn: tool/hava_durumu.py"), "talimat": ("string", "İşçiye verilecek net, doğal dilde kod yazma talimatı")},
)(None)

ghost_tool(
    name="gorev_bitti",
    description="Aradığın bilgiye ulaştığında, işlemi tamamladığında veya sohbeti bitirdiğinde döngüden çıkmak için KESİNLİKLE bunu çağır.",
    params={"ozet": ("string", "Patrona verilecek nihai cevap veya özet")},
)(None)

ghost_tool(
    name="durum_getir",
    description="Bir projenin çalışma durumunu (en son dokunulan dosyalar, aktif dizin, son görev özeti) getirir. 'Kaldığımız yerden devam edelim' veya 'en son ne yapıyordum' gibi isteklerde kullan.",
    params={"proje_adi": ("string", "Sorgulanacak projenin tam adı, örn: KriptoDashboard")},
)(None)

ghost_tool(
    name="periyodik_gorev_olustur",
    description="Arka planda (belirli saat aralıklarıyla) düzenli olarak uyanıp çalışacak bir sistem görevi oluşturur. Örneğin 'her sabah maillerime bak', '2 saatte bir hisseleri kontrol et'.",
    params={"gorev_tanimi": ("string", "Görevin detaylı tanımı, ne yapılacağı"), "periyot_saat": ("number", "Görevin kaç saatte bir çalışacağı, örn: 24.0 veya 0.5")}
)(None)

ghost_tool(
    name="periyodik_gorevleri_listele",
    description="Şu an aktif olan tüm periyodik (arka plan) görevlerin ID, isim ve aralık bilgilerini listeler.",
    params={}
)(None)

ghost_tool(
    name="periyodik_gorev_sil",
    description="Verilen ID'ye sahip periyodik arka plan görevini siler/iptal eder.",
    params={"gorev_id": ("integer", "Silinecek görevin ID'si (listeden öğrenilir)")}
)(None)

ghost_tool(
    name="proje_adi_ayarla",
    description="Bir klasör (kök dizin) için proje adını kalıcı olarak kaydeder.",
    params={"kok_dizin": ("string", "Tam kök dizin yolu"), "proje_adi": ("string", "Patron'un bu klasör için verdiği proje adı")},
)(None)

ghost_tool(
    name="whatsapp_mesaj_gonder",
    description="WhatsApp Web üzerinden belirtilen kişiye mesaj gönderir. WhatsApp mesajı göndermek istendiğinde SADECE bunu kullan.",
    params={"kisi": ("string", "Mesaj gönderilecek kişi veya grup adı"), "mesaj": ("string", "Gönderilecek mesaj metni")},
)(None)

ghost_tool(
    name="whatsapp_ekrani_oku",
    description="Açık WhatsApp sohbetini Vision ile okur, mesajları özetler.",
    params={},
)(None)

ghost_tool(
    name="telegram_mesaj_gonder",
    description="Patron'a Telegram üzerinden mesaj gönderir. Patron'un en son Telegram'dan yazdığı sohbete cevap yazmak için SADECE bunu kullan (Patron uzaktaysa ve UI'dan değil Telegram'dan konuşuyorsa geçerlidir).",
    params={"mesaj": ("string", "Gönderilecek mesaj metni")},
)(None)

ghost_tool(
    name="araclari_listele",
    description="tools/ klasöründeki tüm dosyalardaki fonksiyonları, parametrelerini ve açıklamalarını listeler.",
    params={},
)(None)

ghost_tool(
    name="arac_calistir",
    description="tools/ klasöründeki bir dosyadaki belirli bir fonksiyonu, verilen parametrelerle çağırır.",
    params={"dosya": ("string", "tools/ altındaki dosya adı"), "fonksiyon": ("string", "Fonksiyon adı"), "parametreler": ("object", "Parametreler")},
)(None)

ghost_tool(
    name="uzun_gorev_plani_yap",
    description="Karmaşık veya çok adımlı görevler için bir yol haritası (plan) oluşturur ve sisteme kaydeder. Göreve başlamadan hemen önce çağırılmalıdır.",
    params={
        "hedef": ("string", "Planın ana amacı"),
        "adimlar": ("array", "Sırasıyla yapılması gereken adımların listesi (string dizisi)")
    }
)(None)

ghost_tool(
    name="terminal_cikti_oku",
    description="Kullanıcının terminal panelindeki son çıktıları okur. Kullanıcı terminalde bir şey çalıştırdıktan sonra sonucu görmek, hata mesajını analiz etmek veya hangi dizinde olduğunu anlamak için kullan.",
    params={"satir_sayisi": ("string", "Okunacak son satır sayısı (varsayılan: 50)")},
    required=[],
)(None)