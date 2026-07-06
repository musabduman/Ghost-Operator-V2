"""
handlers/command_handler.py
Ghost'un "beyin merkezi" — komutları alır, yorumlar, eylemleri tetikler.
UI'a dokunmaz; sadece app.log() ve app.set_model_label() kullanır.
"""
import os
import re
import sys
import time
import queue
import spotipy
import traceback
import threading
import subprocess   
import PIL.ImageGrab

from handler.patterns import PATTERNS
from hafıza.rag_hafıza import Bellek
from core.planner import PlannerAgent
from kontrol.spotify import SpotifyManager
from ai.llm import GhostController, ChatLLM
from ui.compact_ui import set_voice_state
from vison.vison import minimax_vision_analiz
from tools.browser_tool import get_dom_elements
from core.fs import (
    akilli_yol_cozucu, alternatif_yol_bul, derin_arama, kodu_calistir
)
 
KAPANIŞ_KELİMELERİ = ["uyku modu", "teşekkürler ghost", "kapan", "çıkış yap", "görüşürüz"]

SESLI_MOD_GECIS = ["sesli moda geç", "orb moduna geç", "arayüzü küçült", "küçük ekrana geç", "kompakt mod"]
YAZILI_MOD_GECIS = ["yazılı moda geç", "terminali aç", "arayüzü genişlet", "geniş ekrana geç", "sohbet moduna geç"]

MAX_DEPTH = 2
 
class CommandHandler:
 
    def __init__(self, app):
        self.app = app
        self.son_komut_sesli = False
        self.bellek = Bellek()
        self.controller = GhostController(tool_runner=self._araclari_calistir)        
        self.spotify = SpotifyManager()
        self.planner = PlannerAgent()
        self.islem_kuyrugu = queue.Queue()
        self.su_an_mesgul = False  
        
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
            "dosya_yaz": {"func": self._tool_write_file, "yol_coz": True, "param_count": 2},
            "gozlem_yap": {"func": self._tool_browser_observe, "yol_coz": False, "param_count": 1},
            "tarayici_tikla": {"func": self._tool_browser_click, "yol_coz": False, "param_count": 2},
            "tarayici_yaz": {"func": self._tool_browser_type, "yol_coz": False, "param_count": 3},
            "site_oku": {"func": self._tool_read_website, "yol_coz": False, "param_count": 1},
            "gorev_bitti": {"func": self._tool_mission_complete, "yol_coz": False, "param_count": 1},
            "ekran_goruntusu": {"func": self._tool_take_screenshot, "yol_coz": False, "param_count": 1},
        }

    # ---> YENİ EKLENEN MERKEZİ KONUŞMA VE DİNLEME YÖNETİCİSİ <---
    def _asistan_konus(self, metin: str):
        """Asistanın sesli yanıt vermesini ve mikrofonun GÜVENLİ ŞEKİLDE yeniden açılmasını sağlar."""
        self.app.is_speaking = True  # Kendi sesini duymaması için kulakları kapatır
        
        if not getattr(self.app, "_expanded", True):
            set_voice_state(self.app, "speaking", "Konuşuyorum...")
            
        try:
            self.app.konus.speak(metin) # Asistan konuşur
        except Exception as e:
            self.app.log(f"Ses motoru hatası: {e}", "red")
        finally:
            self.app.is_speaking = False  # Konuşma bitti, kulakları geri aç
            
            # Eğer hala sesli moddaysak sağır kalmamak için mikrofonu yeniden başlat
            if self.app.voice_mode:
                if not getattr(self.app, "_expanded", True):
                    set_voice_state(self.app, "listening", "Dinliyorum...")
                # Son yankıların bitmesi için 300ms bekleyip döngüyü sıfırlıyoruz
                self.app.after(300, self.app.voice_handler.start_listening)

    # ── Dışarıdan çağrılan giriş noktaları ───────────────────────────────────
    def handle(self, event=None, voice_text=None):
        self.son_komut_sesli = (event is None)
        
        if not self.son_komut_sesli:
            self.app.voice_mode = False

        if self.son_komut_sesli and voice_text:
            user_input = voice_text.strip()
        elif hasattr(self.app, 'entry') and self.app.entry.winfo_exists():
            user_input = self.app.entry.get().strip()
        else:
            user_input = ""

        if not user_input:
            return
        
        if any(k in user_input.lower() for k in KAPANIŞ_KELİMELERİ):
            self.app.record_message(f"\nSen: {user_input}")
            self.app.record_message("Ghost: Anlaşıldı Patron, nöbetçi moduna geçiyorum.", "green")
            self.app.after(2000, self.app.destroy)
            return

        lower_input = user_input.lower()
        gecis_yapildi = False
        
        if any(k in lower_input for k in SESLI_MOD_GECIS):
            self.app.compact_mode()
            gecis_mesaji = "Sesli arayüze geçiyorum Patron."
            gecis_yapildi = True

        elif any(k in lower_input for k in YAZILI_MOD_GECIS):
            self.app.expand_mode()
            gecis_mesaji = "Terminal arayüzüne geçiyorum Patron."
            gecis_yapildi = True

        if gecis_yapildi:
            self.app.record_message("ghost", gecis_mesaji)
            
            if hasattr(self.app, 'entry') and self.app.entry.winfo_exists():
                self.app.entry.delete(0, "end")
            
            if self.app.voice_mode:
                self._asistan_konus(gecis_mesaji)
            
            kelime_sayisi = len(user_input.split())
            if kelime_sayisi <= 4: 
                return
             
        self.app.record_message("user", user_input)
        
        if hasattr(self.app, 'entry') and self.app.entry.winfo_exists():
            self.app.entry.delete(0, "end")
            
        self.app.set_model_label("Aktif Durum: Yönlendiriliyor...")
        
        if not getattr(self.app, "_expanded", True):
            set_voice_state(self.app, "thinking", "Düşünüyorum...")

        threading.Thread(
            target=self._orchestrate_task,
            args=(user_input,),
            daemon=True
        ).start()
    
    def _orchestrate_task(self, user_input):

        if getattr(self.app, "_expanded", True):
            sistem_notu = "[SİSTEM BİLGİSİ: Şu an GENİŞ/YAZILI terminal arayüzündesin. İstediğin kadar detaylı, uzun, maddeli ve teknik cevaplar verebilirsin.]\n"
        else:
            sistem_notu = "[SİSTEM BİLGİSİ: Şu an KOMPAKT/SESLİ arayüzdesin. Cevaplarını çok KISA, NET ve bir sesli asistanın konuşacağı doğallıkta (maksimum 1-2 cümle) ver. Uzun listeler veya kod blokları KULLANMA.]\n"
            
        zengin_input = f"{sistem_notu}Kullanıcı Komutu: {user_input}"

        sohbet_kaliplari = ["nasılsın", "ne haber", "teşekkür", "merhaba", "selam", "iyi misin","nasıl gidiyor"]
        
        if any(k in user_input.lower() for k in sohbet_kaliplari):
            self.app.set_model_label("Aktif Durum: Sohbet Ediyor...")
            try:
                response, model = self.controller(zengin_input)
                self._update_model_label(model)
                display = self._clean_response_for_display(response)
                
                if display and display.strip():
                    self.app.record_message("ghost", display)
                    if self.app.voice_mode:
                        self._asistan_konus(display)
                            
            except Exception as e:
                self.app.log(f"SİSTEM HATA: {e}", "red")
                if self.app.voice_mode:
                    self._asistan_konus("Sistemde bir hata oluştu Patron.")
            return

        self.app.set_model_label("Aktif Durum: Operasyon Başlıyor...")
        self._agentic_loop(user_input)

    def run_startup(self):
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
            
            self._asistan_konus(cevap)
 
        except Exception as e:
            self.app.log(f"SİSTEM HATA (Uyanış): {e}", "red")
            # Hata olsa bile sağır kalmaması için mikrofonu başlatıyoruz
            self.app.after(300, self.app.voice_handler.start_listening)
 
    def _agentic_loop(self, user_input: str):
        # Kullanıcı isteğini modelin kök hafızasına ekle
        self.controller.supervisor.mesaj_gecmisi.append({"role": "user", "content": user_input})
        
        try:
            # Sihir burada gerçekleşir! LangGraph arka planda araçları çalıştırır, 
            # düşünür ve işi bittiğinde nihai cevabı döndürür.
            cevap, model = self.controller._raw_supervisor_call()
            self._update_model_label(model)
            
            # İşçinin veya Yöneticinin nihai cevabını temizle
            final_mesaji = self._clean_response_for_display(cevap)
            
            if final_mesaji:
                self.app.record_message("ghost", final_mesaji)
                if self.app.voice_mode:
                    self._asistan_konus(final_mesaji)
                    
            # Geriye dönük uyumluluk: Eğer çıktı içinde kod dosyası varsa _araclari_calistir onu yakalayıp kaydetsin
            if "[DOSYA_YAZ:" in cevap:
                self._araclari_calistir(cevap)
                
        except Exception as e:
            self.app.log(f"SİSTEM: LangGraph Döngüsü Kırıldı: {e}", "red")
            hata_mesaji = "Patron, işlem sırasında bir hata oluştu."
            self.app.record_message("ghost", hata_mesaji)
            if self.app.voice_mode:
                self._asistan_konus(hata_mesaji)

    def _araclari_calistir(self, response: str) -> str | None:
        bulunan_araclar = []

        for pattern_adi, regex in PATTERNS.items():
            if pattern_adi not in self.TOOL_REGISTRY:
                continue
            
            for match in regex.finditer(response):
                bulunan_araclar.append({
                    "isim": pattern_adi,
                    "match": match,
                    "baslangic_indeksi": match.start()
                })

        if not bulunan_araclar:
            return None

        bulunan_araclar.sort(key=lambda x: x["baslangic_indeksi"])

        MAX_TOOL = 5
        bulunan_araclar = bulunan_araclar[:MAX_TOOL]

        sonuclar = []
        
        for adim, arac in enumerate(bulunan_araclar):
            pattern_adi = arac["isim"]
            m = arac["match"]
            ayar = self.TOOL_REGISTRY[pattern_adi]
            
            parametreler = []
            for i in range(1, ayar["param_count"] + 1):
                param = m.group(i).strip()
                if i == 1 and ayar["yol_coz"]: 
                    param = akilli_yol_cozucu(param)
                parametreler.append(param)

            try:
                result = ayar["func"](*parametreler)
                success = True
            except Exception as e:
                result = f"Araç çalışırken çöktü: {str(e)}"
                success = False
                self.app.log(f"SİSTEM HATA DETAYI ({pattern_adi}):\n{traceback.format_exc()}", "red")

            self.app.log(f"🛠️ [ADIM {adim+1}/{len(bulunan_araclar)}] ARAÇ: {pattern_adi.upper()} | DURUM: {'✅' if success else '❌'}", "yellow")
            self.app.log(f"   Param: {parametreler} | Çıktı: {str(result)[:50]}...", "yellow")

            sonuclar.append(
                f"OBSERVATION [Adım {adim+1}]:\n"
                f"tool={pattern_adi}\n"
                f"success={str(success).lower()}\n"
                f"result={result}\n"
                f"{'-'*20}"
            )

        return "\n".join(sonuclar)
    
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
 
    @staticmethod
    def _clean_response_for_display(response: str) -> str:
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

        # GOREV_BITTI özel durum: etiketi kaldır ama İÇERİĞİNİ KORU
        result = re.sub(
            r'\[GOREV_BITTI:\s*(.*?)\]',
            r'\1',
            result,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # GOREV_BITTI artık aşağıdaki listede yok — yukarıda ayrı işlendi
        etiketler = r'\[(?:OPEN_FOLDER|OPEN_APP|ARAMA|ŞARKI_AÇ|PLAYLIST_AÇ|NOT_AL|KLASOR_YAP|DOSYA_OKU|KLASOR_INCELE|KODU_CALISTIR|DOSYA_YAZ|TARAYICI_TIKLA|TARAYICI_YAZ|GOZLEM_YAP|SİTE_OKU|EKRAN_GORUNTUSU):.*?\]'        
        result = re.sub(etiketler, '', result, flags=re.IGNORECASE)

        result = re.sub(r'\[[A-Z_İĞÜŞÖÇ]+\]', '', result)

        return result.strip()
        
    def _update_model_label(self, model: str):
        try:
            color = "#00FFcc" if "oss" in model.lower() else "#FF9500"
            self.app.set_model_label(f"Aktif Durum: {model}", color)
        except Exception as e:
            pass

    def _tool_browser_click(self, url: str, hedef_metin: str) -> str:
        self.app.log(f"SİSTEM: '{url}' adresinde '{hedef_metin}' öğesine tıklanıyor...", "green")
        from tools.browser_tool import browser_interact
        return browser_interact(url, "tikla", hedef_metin)
    
    def _tool_read_website(self, url: str) -> str:
        self.app.log(f"SİSTEM: '{url}' içeriği (metin olarak) okunuyor...", "green")
        from tools.google_tool import read_webpage
        
        try:
            icerik = read_webpage(url)
            if icerik and "okunamadı" not in icerik:
                return (f"SİTE İÇERİĞİ ({url}):\n\n{icerik[:3500]}...\n\n"
                        f"[ÖLÜMCÜL SİSTEM TALİMATI: Sayfayı başarıyla okudun! ŞİMDİ ARAÇ KULLANMAYI DERHAL BIRAK. "
                        f"Asla yeni bir [ETİKET] yazma. Sadece yukarıdaki metne bakarak Patron'a cevabını ver. "
                        f"Eğer aradığın bilgi metinde yoksa, 'Patron, metinde bulamadım' de ama ASLA başka araç arama!]")
            
            return f"Site metni okunamadı: {url}"
        except Exception as e:
            return f"Okuma sırasında hata oluştu: {str(e)}"
        
    def _tool_browser_type(self, url: str, hedef_metin: str, yazi_icerigi: str) -> str:
        self.app.log(f"SİSTEM: '{url}' adresinde '{hedef_metin}' öğesine '{yazi_icerigi}' yazılıyor...", "green")
        from tools.browser_tool import browser_interact
        return browser_interact(url, "yaz", hedef_metin, yazi_icerigi)

    def _tool_browser_observe(self, hedef: str) -> str:
        hedef = hedef.lower().strip()
        
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

        else:
            self.app.log("SİSTEM: Doğrudan masaüstü analizi için LLaVA Gözleri Açılıyor...", "green")
            soru = "Şu an bilgisayarın masaüstü ekranına bakıyorsun. Ekranda hangi uygulamalar, açık pencereler veya tıklanabilir öğeler var? Konumlarını belirt."

        kayit_yolu = os.path.join(os.path.expanduser("~"), "ghost_temp_vision.png")
        try:
            ekran = PIL.ImageGrab.grab(all_screens=True)
            ekran.save(kayit_yolu)
            
            _, _, mesaj = minimax_vision_analiz(soru, kayit_yolu)
            return f"GÖRSEL GÖZLEM:\n{mesaj}"
            
        except Exception as e:
            return f"Gözlem tamamen başarısız oldu: {str(e)}"
        
    def _tool_mission_complete(self, nihai_cevap: str) -> str:
        return f"GÖREV_TAMAMLANDI_SİNYALİ: {nihai_cevap}"
    
    def _tool_take_screenshot(self, soru: str) -> str:
        self.app.log(f"SİSTEM: Ghost otonom olarak ekrana bakıyor... Soru: '{soru}'", "green")
        kayit_yolu = os.path.join(os.path.expanduser("~"), "ghost_auto_screenshot.png")
        
        try:
            self.app.iconify()
            time.sleep(0.5) 
            
            import PIL.ImageGrab
            ekran = PIL.ImageGrab.grab(all_screens=True)
            ekran.save(kayit_yolu)
            
            self.app.deiconify()
            
            self.app.set_model_label("Aktif Durum: Görüntü İşleniyor (Vision)", "#a352cc")

            from vison.vison import minimax_vision_analiz
            basarili_mi, saf_kod, mesaj = minimax_vision_analiz(soru, kayit_yolu)
            
            if basarili_mi and saf_kod:
                return f"GÖZLEM SONUCU: Ekranda şu kod bulundu:\n\n{saf_kod}\n\nLütfen Kullanıcının asıl isteğine göre bu kodu kullanarak işlem yap."
            
            return f"GÖZLEM SONUCU: {mesaj}\n\n[ÖLÜMCÜL SİSTEM TALİMATI: Ekranı başarıyla gördün ve özetledin. ŞİMDİ ARAÇ KULLANMAYI DERHAL BIRAK. Hiçbir [ETİKET] kullanmadan, doğrudan gördüklerini Patron'a kendi havalı tarzınla açıkla ve görevi bitir.]"
            
        except Exception as e:
            self.app.deiconify()
            return f"SİSTEM HATASI: Ekran görüntüsü alınamadı, hata: {str(e)}"
        
    def _tool_search(self, query: str) -> str:
        self.app.log(f"SİSTEM: Plan A - DuckDuckGo ile hızlı arama yapılıyor: '{query}'...", "green")
        from tools.google_tool import search_duckduckgo, _format_results
        
        try:
            ddg_results = search_duckduckgo(query)
            formatted = _format_results(ddg_results)
            
            if formatted:
                return (f"DuckDuckGo Arama Sonuçları ('{query}'):\n\n{formatted}\n\n"
                        f"[GİZLİ SİSTEM TALİMATI: Aradığın bilgi için uygun bir kaynak bulduysan, "
                        f"hiç vakit kaybetmeden [SİTE_OKU: <url>] aracını kullan ve sitenin içine gir.]")
            else:
                raise Exception("DuckDuckGo sonuç döndürmedi.")
                
        except Exception as e:
            self.app.log(f"SİSTEM UYARISI: DDG başarısız ({str(e)[:30]}). Plan B (Fiziksel Tarayıcı) başlıyor...", "yellow")
            
            from tools.browser_tool import browser_google_search
            try:
                arama_sonuclari = browser_google_search(query)
                if "başarısız oldu" in arama_sonuclari or "çekilemedi" in arama_sonuclari:
                    raise Exception("Tarayıcı metin çekemedi.")
                
                self.app.log("SİSTEM: Plan B başarılı. Tarayıcı sonuçları alındı.", "green")
                return (f"{arama_sonuclari}\n\n"
                        f"[GİZLİ SİSTEM TALİMATI: Aradığın bilgi için uygun bir kaynak bulduysan, "
                        f"[SİTE_OKU: <url>] aracını kullan.]")
            
            except Exception as e2:
                self.app.log("SİSTEM HATA: Tarayıcı DOM'u çöktü. Plan C (LLaVA Görsel) başlıyor...", "yellow")
                return self._visual_search_fallback(query)
   
    def _visual_search_fallback(self, query: str) -> str:
        import urllib.parse
        from playwright.sync_api import sync_playwright
        
        safe_query = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={safe_query}"
        kayit_yolu = os.path.join(os.path.expanduser("~"), "ghost_temp_search.png")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(2000)
                
                try:
                    page.get_by_text("Tümünü reddet", exact=False).first.click(timeout=2000)
                except:
                    pass
                    
                page.screenshot(path=kayit_yolu)
                browser.close()
            
            self.app.log("SİSTEM: Ekran görüntüsü alındı, LLaVA analiz ediyor...", "green")
            
            soru = f"Bu bir Google arama sonuç sayfası. Kullanıcının '{query}' araması için ekranda (özellikle üstte ve ortadaki büyük panellerde, maç skorlarında veya bilgi kutularında) yazan net cevabı bul ve bana sadece o cevabı söyle."
            
            _, _, mesaj = minimax_vision_analiz(soru, kayit_yolu)
            return f"API'ler çöktü ama Tarayıcı+Görsel Zeka ile şu sonucu buldum:\n{mesaj}"
            
        except Exception as e:
            return f"Maalesef Görsel Arama B Planı da başarısız oldu: {str(e)}\nLütfen Kullanıcıya internet bağlantısı sorunu olduğunu söyle."
                            
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

    def _tool_play_song(self, song: str) -> str:
        self.app.log(f"SİSTEM: Spotify'da '{song}' aranıyor...", "green")
        
        try:
            result = self.spotify.play_specific_song(song)
            return f"Spotify Sonucu: {result}"
        
        except spotipy.exceptions.SpotifyException as e:
            if "No active device" in str(e) or getattr(e, "http_status", None) == 404:
                self.app.log("SİSTEM: Aktif cihaz yok, Spotify açılıp uyandırılıyor...", "yellow")
                self._tool_open_app("spotify")     # senin önerdiğin: kendi açsın
                time.sleep(2)                       # uygulamanın cihaz olarak görünmesi için bekle
        
                try:
                    device_id = self.spotify.wake_active_device()
        
                    if not device_id:
                        return "HATA: Spotify açıldı ama hâlâ aktif cihaz yok. Patron'a Spotify'da bir şeye tıklamasını söyle. TEKRAR DENEME."
                    time.sleep(1.5)
                    result = self.spotify.play_specific_song(song)
        
                    return f"Spotify Sonucu (cihaz uyandırıldıktan sonra): {result}"
        
                except Exception as e2:
                    return f"HATA: Cihaz uyandırılamadı: {e2}. TEKRAR DENEME, Patron'a bildir."
        
            return f"HATA: Spotify hatası: {e}. TEKRAR DENEME."
        
    def _tool_play_playlist(self, playlist: str) -> str:
        self.app.log(f"SİSTEM: '{playlist}' listesi aranıyor...", "green")
        result = self.spotify.play_playlist(playlist)
        return f"Spotify Sonucu: {result}"

    def _tool_save_note(self, note: str) -> str:
        self.bellek.bellege_yaz(note)
        self.app.log(f"SİSTEM: Beyne kazındı → '{note}'", "green")
        return "Not başarıyla belleğe kaydedildi."

    def _tool_make_folder(self, path: str) -> str:
        os.makedirs(path, exist_ok=True)
        self.app.log(f"SİSTEM: Klasör oluşturuldu → {path}", "green")
        return f"'{path}' dizininde klasör başarıyla oluşturuldu."

    def _tool_inspect_folder(self, path: str) -> str:
        if os.path.isdir(path):
            files = ", ".join(os.listdir(path)) or "Klasör boş."
            self.app.log(f"SİSTEM: Klasör tarandı → {path}", "green")
            return f"Klasör İçeriği: {files}"
        return "Belirtilen yol bir klasör değil veya bulunamadı."

    def _tool_write_file(self, path: str, code: str) -> str:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        self.app.log(f"SİSTEM: Dosya yazıldı → {path}", "green")
        return f"Kod başarıyla '{path}' konumuna kaydedildi."

    def _tool_run_code(self, path: str) -> str:
        self.app.log(f"SİSTEM: '{path}' çalıştırılıyor...", "green")
        result = kodu_calistir(path)
        if result["basarili"]:
            self.app.log(f"SİSTEM ✅ Başarılı:\n{result['cikti'][:100]}...", "green")
            return f"Kod başarıyla çalıştı. Çıktı:\n{result['cikti']}"
        
        self.app.log("SİSTEM ⚠️ Hata tespit edildi...", "red")
        return f"Kod çalıştırılırken hata verdi. Lütfen hatayı inceleyip düzelt:\n{result['hata']}"

    def _tool_read_file(self, path: str) -> str:
        if os.path.isfile(path):
            content = open(path, encoding="utf-8").read()
            self.app.log(f"SİSTEM: '{path}' okundu.", "green")
            return f"Dosya İçeriği:\n{content}"
            
        folder = os.path.dirname(path)
        if os.path.isdir(folder):
            files = ", ".join(os.listdir(folder)) or "Klasör boş."
            return f"Hedeflenen dosya bulunamadı. Klasörün içindeki mevcut dosyalar: {files}"
            
        return "Dosya veya dizin tamamen geçersiz."