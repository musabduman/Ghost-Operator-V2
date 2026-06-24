"""
handlers/command_handler.py
Ghost'un "beyin merkezi" — komutları alır, yorumlar, eylemleri tetikler.
UI'a dokunmaz; sadece app.log() ve app.set_model_label() kullanır.
"""
import os
import re
import sys
import time
import traceback
import threading
import queue
import subprocess   
import PIL.ImageGrab

from handler.patterns import PATTERNS
from hafıza.rag_hafıza import Bellek
from core.planner import PlannerAgent
from kontrol.spotify import SpotifyManager
from ai.llm import GhostController, ChatLLM
from kontrol.kontrol import google_arama
from vison.vison import llava_vision_analiz
from kontrol.güvenlik import guvenlik_kontrolu
from tools.google_tool import ghost_search_tool
from tools.browser_tool import get_dom_elements
from core.fs import (
    akilli_yol_cozucu, alternatif_yol_bul, derin_arama, kodu_calistir
)
 
KAPANIŞ_KELİMELERİ = ["uyku modu", "teşekkürler ghost", "kapan", "çıkış yap", "görüşürüz"]
 
MAX_DEPTH = 2
 
class CommandHandler:
 
    def __init__(self, app):
        self.app = app
        self.son_komut_sesli = False
        self.bellek = Bellek()
        self.controller = GhostController()
        self.spotify = SpotifyManager()
        self.planner = PlannerAgent()
        self.islem_kuyrugu = queue.Queue()
        self.su_an_mesgul = False  
        
        # Araç Kayıt Defteri (Tool Registry)
        # Format: "pattern_adi": (çalışacak_fonksiyon, yol_cozucu_kullanilsin_mi, parametre_sayisi)
        self.TOOL_REGISTRY = {
            "arama": {"func": self._tool_search, "yol_coz": False, "param_count": 1},
            "klasor_ac": {"func": self._tool_open_folder, "yol_coz": True, "param_count": 1},
            "uygulama_ac": {"func": self._tool_open_app, "yol_coz": False, "param_count": 1},
            "sarki_ac": {"func": self._tool_play_song, "yol_coz": False, "param_count": 1},
            "playlist_ac": {"func": self._tool_play_playlist, "yol_coz": False, "param_count": 1},
            "not_al": {"func": self._tool_save_note, "yol_coz": False, "param_count": 1},
            "klasor_yap": {"func": self._tool_make_folder, "yol_coz": True, "param_count": 1},
            "klasor_incele": {"func": self._tool_inspect_folder, "yol_coz": True, "param_count": 1},
            "kodu_calistir": {"func": self._tool_run_code, "yol_coz": True, "param_count": 1},
            "dosya_oku": {"func": self._tool_read_file, "yol_coz": True, "param_count": 1},
            "dosya_yaz": {"func": self._tool_write_file, "yol_coz": True, "param_count": 2}, # 2 Parametreli tek araç
            "gozlem_yap": {"func": self._tool_browser_observe, "yol_coz": False, "param_count": 1},
            # Format: [TARAYICI_TIKLA: url | buton_adi]
            "tarayici_tikla": re.compile(r'\[\s*TARAYICI_TIKLA\s*:\s*(.*?)\s*\|\s*(.*?)\s*\]', re.IGNORECASE),
            # Format: [TARAYICI_YAZ: url | kutu_adi | yazilacak_metin]
            "tarayici_yaz": re.compile(r'\[\s*TARAYICI_YAZ\s*:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\]', re.IGNORECASE),
        }

    # ── Dışarıdan çağrılan giriş noktaları ───────────────────────────────────
    def handle(self, event=None):
        """Entry'deki komutu alıp işleme döngüsünü başlatır."""
        self.son_komut_sesli = (event is None)
        
        if not self.son_komut_sesli:
            self.app.voice_mode = False

        user_input = self.app.entry.get().strip()
        if not user_input:
            return
 
        if any(k in user_input.lower() for k in KAPANIŞ_KELİMELERİ):
            self.app.record_message(f"\nSen: {user_input}")
            self.app.record_message("Ghost: Anlaşıldı Patron, nöbetçi moduna geçiyorum.", "green")
            self.app.after(2000, self.app.destroy)
            return
 
        self.app.record_message("user", user_input)
        self.app.entry.delete(0, "end")
        #self.app.record_message("Ghost", "Düşünüyor...")
        self.app.set_model_label("Aktif Durum: Yönlendiriliyor...")
 
        threading.Thread(
            target=self._orchestrate_task,
            args=(user_input,),
            daemon=True
        ).start()
    
    def _orchestrate_task(self, user_input):
        # Sadece açık sohbet kalıplarını filtrele
        sohbet_kaliplari = ["nasılsın", "ne haber", "teşekkür", "merhaba", "selam", "iyi misin"]
        
        if any(k in user_input.lower() for k in sohbet_kaliplari):
            self.app.set_model_label("Aktif Durum: Sohbet Ediyor...")
            try:
                response, model = self.controller(user_input)
                self._update_model_label(model)
                display = self._clean_response_for_display(response)
                if display and display.strip():
                    self.app.record_message("ghost", display)
            except Exception as e:
                self.app.log(f"SİSTEM HATA: {e}", "red")
            return

        # Geri kalan her şey agentic loop
        self.app.set_model_label("Aktif Durum: Operasyon Başlıyor...")
        self._agentic_loop(user_input)
        
    def run_startup(self):
        """Uyanış cümlesi + ilk dinleme döngüsünü başlatır."""
        prompt = (
            "GİZLİ SİSTEM BİLGİSİ: Ghost, az önce nöbetçi modundan uyandırıldın. "
            "Hazır olduğunu bildiren o çok kısa, havalı giriş cümleni söyle. "
            "Örneklerden SADECE birini seç. "
            "(Örn: Dinliyorum. Örn: Efendim. Örn: Nasıl yardımcı olabilirim.)"
        )
        try:
            cevap, model = self.controller(prompt)
            self._update_model_label(model)
            self.app.record_message("ghost" ,cevap)
            self.app.konus.speak(cevap)
            self.app.after(0, self.app.voice_handler.start_listening)
 
        except Exception as e:
            self.app.log(f"SİSTEM HATA (Uyanış): {e}", "red")
 
    # ── Ana işleme döngüsü ────────────────────────────────────────────────────
    def _agentic_loop(self, user_input: str):
        """Gerçek ReAct döngüsü — model bitmediğini söyleyene kadar döner."""
        orijinal_hafiza_yedegi = list(self.controller.supervisor.mesaj_gecmisi)

        # Kullanıcının asıl sorusunu sisteme ekle
        self.controller.supervisor.add_user(user_input)
        
        # Sonsuz döngü koruması: Ghost'un aynı aracı üst üste çağırmasını engeller
        gecmis_arac_cagrilari = set() 
        final_mesaji = ""

        for adim in range(5):  # max 5 adım, sonsuz döngü önlemi
            response, model = self.controller._raw_supervisor_call()
            self._update_model_label(model)

            # Araç var mı kontrol et
            sonuc = self._araclari_calistir(response)

            if sonuc is None:
                # ÇIKIŞ ŞARTI: Etiket yoksa işlem başarıyla bitmiştir.
                final_mesaji = self._clean_response_for_display(response)
                self.app.record_message("ghost", final_mesaji)
                if self.app.voice_mode:
                    self.app.konus.speak(final_mesaji)
                break
            
            # KORUMA: Ghost aynı aracı tekrar çağırdıysa
            if response in gecmis_arac_cagrilari:
                self.app.log("SİSTEM UYARISI: Ghost aynı aracı tekrar denedi, döngü kırılıyor.", "red")
                final_mesaji = "Sanırım burada bir döngüye girdim Patron. Başka bir yoldan ilerleyelim mi?"
                self.app.record_message("ghost", final_mesaji)
                break # <--- İŞTE SİLDİĞİN VE EKRANI SPAMLEYEN O EKSİK KOMUT
                
            gecmis_arac_cagrilari.add(response)
            
            # Araç sonucunu "SYSTEM" olarak modele besle
            self.controller.supervisor.mesaj_gecmisi.append({
                "role": "system",
                "content": (
                    f"[SİSTEM BİLDİRİMİ - ARAÇ ÇIKTISI - ADIM {adim+1}]\n"
                    f"{sonuc}\n\n"
                    f"GİZLİ TALİMAT: Eğer görev tamamlandıysa ve kullanıcıya son cevabı vereceksen, "
                    f"HİÇBİR [ETİKET] KULLANMA. Doğrudan doğal ve havalı karakterinle cevap yaz."
                )
            })
        
        # SİNSİ BUG'IN ÇÖZÜMÜ: Sadece final_mesaji boşsa (yani 5 adım başarısız dolduysa) uyar
        if not final_mesaji:
            self.app.log("SİSTEM: Maksimum işlem adımı aşıldı (5/5).", "red")
            final_mesaji = "Patron, bu işlem beklediğimden çok daha uzun sürdü. Sistemi yormamak için durdurdum."
            self.app.record_message("ghost", final_mesaji)
            
        # Hafızayı ilk temiz haline döndür
        self.controller.supervisor.mesaj_gecmisi = orijinal_hafiza_yedegi
        
        # Sadece asıl soruyu ve döngüden çıkan o tek temiz cevabı ana hafızaya ekle
        if final_mesaji:
            self.controller.supervisor.add_user(user_input)
            self.controller.supervisor.add_assistant(final_mesaji)
                
    def _araclari_calistir(self, response: str) -> str | None:
        """Metin içindeki tüm araçları sırayla çalıştırıp yapılandırılmış sonuç (OBSERVATION) döner."""
        bulunan_araclar = []

        # 1. Bütün patternleri tara ve eşleşmeleri metindeki konumlarına göre listeye ekle
        for pattern_adi, regex in PATTERNS.items():
            if pattern_adi not in self.TOOL_REGISTRY:
                continue
            
            # finditer ile metin içindeki tüm aynı ve farklı etiketleri bul
            for match in regex.finditer(response):
                bulunan_araclar.append({
                    "isim": pattern_adi,
                    "match": match,
                    "baslangic_indeksi": match.start()
                })

        if not bulunan_araclar:
            return None

        # 2. Araçları modelin metne yazdığı sıraya (kronolojik) göre diz
        bulunan_araclar.sort(key=lambda x: x["baslangic_indeksi"])

        # Sonsuz döngü veya Ghost'un delirmesini önlemek için max 2 araç limiti
        MAX_TOOL = 2
        bulunan_araclar = bulunan_araclar[:MAX_TOOL]

        sonuclar = []
        
        # 3. Araçları sırayla Ateşle
        for adim, arac in enumerate(bulunan_araclar):
            pattern_adi = arac["isim"]
            m = arac["match"]
            ayar = self.TOOL_REGISTRY[pattern_adi]
            
            # Parametreleri dinamik olarak çek
            parametreler = []
            for i in range(1, ayar["param_count"] + 1):
                # Regex'i toleranslı (strip vb.) hale getir
                param = m.group(i).strip()
                # Yalnızca ilk parametre yol ise akıllı çözücüden geçir
                if i == 1 and ayar["yol_coz"]: 
                    param = akilli_yol_cozucu(param)
                parametreler.append(param)

            try:
                # Aracı çalıştır (*parametreler ile listeyi unpack yapıyoruz)
                result = ayar["func"](*parametreler)
                success = True
            except Exception as e:
                # LLM'in kafası karışmasın diye ona kısa mesaj
                result = f"Araç çalışırken çöktü: {str(e)}"
                success = False
                
                # Senin arka planda hatayı görebilmen için tam Traceback
                self.app.log(f"SİSTEM HATA DETAYI ({pattern_adi}):\n{traceback.format_exc()}", "red")

            # Sistem arayüzüne (Geliştirici paneline) detaylı log bas
            self.app.log(f"🛠️ [ADIM {adim+1}/{len(bulunan_araclar)}] ARAÇ: {pattern_adi.upper()} | DURUM: {'✅' if success else '❌'}", "yellow")
            self.app.log(f"   Param: {parametreler} | Çıktı: {str(result)[:50]}...", "yellow")

            # 4. Modele Yapılandırılmış Geri Bildirim (Observation) oluştur
            sonuclar.append(
                f"OBSERVATION [Adım {adim+1}]:\n"
                f"tool={pattern_adi}\n"
                f"success={str(success).lower()}\n"
                f"result={result}\n"
                f"{'-'*20}"
            )

        # Tüm tool'ların sonucunu modele tek bir blok halinde gönder
        return "\n".join(sonuclar)
    
    # ── Bellek zenginleştirme ─────────────────────────────────────────────────
    def _enrich_with_memory(self, user_input: str) -> str:
        if "GİZLİ SİSTEM BİLGİSİ" in user_input:
            return user_input
        memories = self.bellek.sorgula(soru=user_input, limit=2)
        if not memories:
            return user_input
        context = "\n- ".join(memories)
        return (
            f"[GİZLİ BİLGİ: Kullanıcı bu komutu SESLİ olarak verdi. "
            f"Asla uzun cevap verme, saniyeler içinde sadece eylem etiketini kullan.]\n"
            f"Kullanıcı: {user_input}\n"
            f"[SİSTEM NOTU: Geçmiş hafızandan şu bilgileri hatırlıyorsun:\n"
            f"- {context}\n"
            f"Eğer bu bilgiler kullanıcının sorusuyla ilgiliyse cevaplarken kullan.]\n\n"
            f"Kullanıcı Komutu: {user_input}"
        )
 
    # ── Ekran temizliği ───────────────────────────────────────────────────────
    @staticmethod
    def _clean_response_for_display(response: str) -> str:
        # 1. Mühendis kod bloklarını şık ikonlara çevir
        result = re.sub(
            r'\[.*?KOD_BASLANGIC>>>.*?<<<KOD_BITIS>>>',
            '[⚙️ Kod dosyaya yazılıyor...]',
            response,
            flags=re.IGNORECASE | re.DOTALL,
        )
        result = re.sub(
            r'\[KOD_ISTE:.*?\]',
            '[🛠️ Mühendise sinyal gönderildi...]',
            result,
            flags=re.IGNORECASE,
        )

        # 2. Arka plan sistem etiketlerini tamamen yok et (örn: [OPEN_APP: chrome])
        etiketler = r'\[(?:OPEN_FOLDER|OPEN_APP|ARAMA|ŞARKI_AÇ|PLAYLIST_AÇ|NOT_AL|KLASOR_YAP|DOSYA_OKU|KLASOR_INCELE|KODU_CALISTIR|DOSYA_YAZ):.*?\]'
        result = re.sub(etiketler, '', result, flags=re.IGNORECASE)
        
        # 3. Planlayıcının ürettiği boş/sessiz hedefleri ([TASARIM], [KONTEKST_BELİR]) sil
        result = re.sub(r'\[[A-Z_İĞÜŞÖÇ]+\]', '', result)
        
        # Geriye sadece tertemiz muhabbet kalır
        return result.strip()
        
    # ── Model label güncellemesi ──────────────────────────────────────────────
    def _update_model_label(self, model: str):
        color = "#00FFcc" if "oss" in model.lower() else "#FF9500"
        self.app.set_model_label(f"Aktif Durum: {model}", color)
    
    # ── Web sitesinde tıklama ──────────────────────────────────────────────
    def _tool_browser_click(self, url: str, hedef_metin: str) -> str:
        self.app.log(f"SİSTEM: '{url}' adresinde '{hedef_metin}' öğesine tıklanıyor...", "green")
        from tools.browser_tool import browser_interact
        return browser_interact(url, "tikla", hedef_metin)

    # ── Web sitesinde yazma ──────────────────────────────────────────────
    def _tool_browser_type(self, url: str, hedef_metin: str, yazi_icerigi: str) -> str:
        self.app.log(f"SİSTEM: '{url}' adresinde '{hedef_metin}' öğesine '{yazi_icerigi}' yazılıyor...", "green")
        from tools.browser_tool import browser_interact
        return browser_interact(url, "yaz", hedef_metin, yazi_icerigi)

    # ── Web sitesi ve Masaüstünğ görebilme ──────────────────────────────────────────────
    def _tool_browser_observe(self, hedef: str) -> str:
        hedef = hedef.lower().strip()
        
        # 1. DURUM: HEDEF BİR WEB SİTESİ İSE (DOM + Vision Fallback)
        if hedef.startswith("http") or "www" in hedef or ".com" in hedef:
            self.app.log(f"SİSTEM: '{hedef}' için DOM analizi başlatılıyor...", "green")
            try:
                if not hedef.startswith("http"):
                    hedef = "https://" + hedef
                    
                dom_sonucu = get_dom_elements(hedef)
                if "Hatası" not in dom_sonucu:
                    return f"TARAYICI DOM GÖZLEMİ (Başarılı):\n{dom_sonucu}"
            except Exception as e:
                self.app.log(f"SİSTEM UYARISI: DOM çekilemedi ({e}), Görsel (Vision) Modele geçiliyor...", "yellow")
                
            soru = f"Şu an tarayıcıda '{hedef}' açık. Etkileşime girilebilecek (tıklanabilir veya yazı yazılabilir) temel öğeler nelerdir? Konumlarını 'sağ üst', 'merkez' gibi genel ifadelerle belirt."

        # 2. DURUM: HEDEF MASAÜSTÜ/EKRAN İSE (Doğrudan Vision'a Geç)
        else:
            self.app.log("SİSTEM: Doğrudan masaüstü analizi için LLaVA Gözleri Açılıyor...", "green")
            soru = "Şu an bilgisayarın masaüstü ekranına bakıyorsun. Ekranda hangi uygulamalar, açık pencereler veya tıklanabilir öğeler var? Konumlarını belirt."

        # LLaVA Vision İşlemi (Hem masaüstü hem de çöken tarayıcı için ortak nokta)
        kayit_yolu = os.path.join(os.path.expanduser("~"), "ghost_temp_vision.png")
        try:
            ekran = PIL.ImageGrab.grab(all_screens=True)
            ekran.save(kayit_yolu)
            
            _, _, mesaj = llava_vision_analiz(soru, kayit_yolu)
            return f"GÖRSEL GÖZLEM:\n{mesaj}"
            
        except Exception as e:
            return f"Gözlem tamamen başarısız oldu: {str(e)}"

    # ── Google arama yapabilme ────────────────────────────────────────────────────
    def _tool_search(self, query: str) -> str:
        self.app.log(f"SİSTEM: Google'da '{query}' aranıyor...", "green")
        arama_sonuclari = ghost_search_tool(query) 
        if arama_sonuclari:
            return f"Arama Sonuçları:\n{arama_sonuclari}"
        return "İnternette sonuç bulunamadı."
        
    # ── Eylem işleyicileri ────────────────────────────────────────────────────
    def _tool_open_folder(self, path: str) -> str:
        if os.path.exists(path):
            os.startfile(path)
            self.app.log(f"SİSTEM: '{path}' açıldı.", "green")
            return f"'{path}' klasörü başarıyla açıldı."
        
        real = derin_arama(path)
        if real:
            os.startfile(real)
            self.app.log(f"SİSTEM: Bulundu → {real}", "green")
            return f"Klasör bulundu ve açıldı: '{real}'"
            
        return "Klasör bulunamadı."
    
    # ── Uygulama açma ────────────────────────────────────────────────────
    def _tool_open_app(self, name: str) -> str:
        name = name.lower()
        self.app.log(f"SİSTEM: '{name}' başlatılıyor...", "green")
        
        if sys.platform.startswith("win"):
            SPECIAL = {
                "cursor": os.path.expanduser(r"~\AppData\Local\Programs\cursor\Cursor.exe"),    
                "discord": (os.path.expanduser(r"~\AppData\Local\Discord\Update.exe") ,["--processStart", "Discord.exe"]),
                "whatsapp": "whatsapp://"
            }
            if name in SPECIAL:
                app = SPECIAL[name]
                if isinstance(app, tuple):
                    subprocess.Popen([app[0]] + app[1])
                else:
                    os.startfile(app)
            else:
                os.system(f"start {name}")
                
        elif sys.platform.startswith("linux"):
            SPECIAL = {
                "cursor": "cursor",
                "discord": "discord",
                "whatsapp": "whatsapp-for-linux"
            }
            komut = SPECIAL.get(name, name)
            os.system(f"nohup {komut} >/dev/null 2>&1 &")
            
        return f"'{name}' uygulaması başlatıldı komutu verildi."

    # ── Müzik çalma ────────────────────────────────────────────────────
    def _tool_play_song(self, song: str) -> str:
        self.app.log(f"SİSTEM: Spotify'da '{song}' aranıyor...", "green")
        try:
            result = self.spotify.play_specific_song(song)
            return f"Spotify Sonucu: {result}"
        except Exception as e:
            # Cihaz kapalıysa playlist ile dürtme mantığı
            if any(k in str(e).lower() for k in ["device", "active", "not found"]):
                try:
                    self.spotify.play_playlist("mesela yanii")
                    time.sleep(2)
                    self.spotify.play_specific_song(song)
                    return f"Cihaz uyandırıldı ve '{song}' açıldı."
                except Exception as e2:
                    return f"Cihaz uyandırılamadı: {e2}"
            return f"Spotify Hatası: {e}"

    # ── Playlist açma ────────────────────────────────────────────────────
    def _tool_play_playlist(self, playlist: str) -> str:
        self.app.log(f"SİSTEM: '{playlist}' listesi aranıyor...", "green")
        result = self.spotify.play_playlist(playlist)
        return f"Spotify Sonucu: {result}"

    # ── Hafızaya not etme ────────────────────────────────────────────────────
    def _tool_save_note(self, note: str) -> str:
        self.bellek.bellege_yaz(note)
        self.app.log(f"SİSTEM: Beyne kazındı → '{note}'", "green")
        return "Not başarıyla belleğe kaydedildi."

    # ── Klasör oluşturma ────────────────────────────────────────────────────
    def _tool_make_folder(self, path: str) -> str:
        os.makedirs(path, exist_ok=True)
        self.app.log(f"SİSTEM: Klasör oluşturuldu → {path}", "green")
        return f"'{path}' dizininde klasör başarıyla oluşturuldu."

    # ── Klasörde gezinme ────────────────────────────────────────────────────
    def _tool_inspect_folder(self, path: str) -> str:
        if os.path.isdir(path):
            files = ", ".join(os.listdir(path)) or "Klasör boş."
            self.app.log(f"SİSTEM: Klasör tarandı → {path}", "green")
            return f"Klasör İçeriği: {files}"
        return "Belirtilen yol bir klasör değil veya bulunamadı."

    # ── Dosya yazma ────────────────────────────────────────────────────
    def _tool_write_file(self, path: str, code: str) -> str:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        self.app.log(f"SİSTEM: Dosya yazıldı → {path}", "green")
        return f"Kod başarıyla '{path}' konumuna kaydedildi."

    # ── Kod Çalıştırma ────────────────────────────────────────────────────
    def _tool_run_code(self, path: str) -> str:
        self.app.log(f"SİSTEM: '{path}' çalıştırılıyor...", "green")
        result = kodu_calistir(path)
        if result["basarili"]:
            self.app.log(f"SİSTEM ✅ Başarılı:\n{result['cikti'][:100]}...", "green")
            return f"Kod başarıyla çalıştı. Çıktı:\n{result['cikti']}"
        
        self.app.log("SİSTEM ⚠️ Hata tespit edildi...", "red")
        return f"Kod çalıştırılırken hata verdi. Lütfen hatayı inceleyip düzelt:\n{result['hata']}"

    # ── Dosya Okuma ────────────────────────────────────────────────────
    def _tool_read_file(self, path: str) -> str:
        if os.path.isfile(path):
            content = open(path, encoding="utf-8").read()
            self.app.log(f"SİSTEM: '{path}' okundu.", "green")
            return f"Dosya İçeriği:\n{content}"
            
        # Dosya yoksa, klasörü kontrol et
        folder = os.path.dirname(path)
        if os.path.isdir(folder):
            files = ", ".join(os.listdir(folder)) or "Klasör boş."
            return f"Hedeflenen dosya bulunamadı. Klasörün içindeki mevcut dosyalar: {files}"
            
        return "Dosya veya dizin tamamen geçersiz."