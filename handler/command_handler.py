"""
handlers/command_handler.py
Ghost'un "beyin merkezi" — komutları alır, yorumlar, eylemleri tetikler.
UI'a dokunmaz; sadece app.log() ve app.set_model_label() kullanır.
"""
import os
import re
import sys
import time
import json
import queue
import inspect
import spotipy
import traceback
import threading
import subprocess   
import PIL.ImageGrab
import importlib.util

from hafıza.rag_hafıza import Bellek
from hafıza.episodic_db import EpisodicDB
from kontrol.spotify import SpotifyManager
from ai.llm import GhostController, ChatLLM
from ui.compact_ui import set_voice_state
from vison.vison import minimax_vision_analiz
from tools.browser_tool import get_dom_elements
from tools.whatsapp_tool import whatsapp_mesaj_gonder, whatsapp_ekrani_yorumla
from core.fs import (
    akilli_yol_cozucu, derin_arama, kodu_calistir
)
 
KAPANIŞ_KELİMELERİ = ["uyku modu", "teşekkürler ghost", "kapan", "çıkış yap", "görüşürüz"]

SESLI_MOD_GECIS = ["sesli moda geç", "orb moduna geç", "arayüzü küçült", "küçük ekrana geç", "kompakt mod"]
YAZILI_MOD_GECIS = ["yazılı moda geç", "terminali aç", "arayüzü genişlet", "geniş ekrana geç", "sohbet moduna geç"]

MAX_DEPTH = 2

# proje_durumu tablosunu güncellemesi gereken, yol tabanlı çalışan araçlar.
# Değer: args içindeki hangi anahtarın "dosya/klasör yolu" olduğu.
DURUM_GUNCELLENECEK_ARACLAR = {
    "dosya_oku":       "yol",
    "dosya_yaz":       "yol",
    "klasor_incele":   "yol",
    "kodu_calistir":   "yol",
    "klasor_ac":       "yol",
    "klasor_yap":      "yol",
}
 
from core.tool_registry import tool_registry

class CommandHandler:
 
    def __init__(self, app):
        self.app = app
        self.son_komut_sesli = False
        self.bellek = Bellek()
        self.episodic_db = EpisodicDB()
        self.controller = GhostController(tool_runner=self._execute_tool_call)
        # gorev_bitti asla _execute_tool_call'dan geçmediği için aktif_plan'ı
        # sıfırlamanın tek güvenilir yeri: GhostController'ın her turu
        # (başarılı/başarısız/limit aşımı fark etmez) kesin olarak bitirdiği an.
        self.controller.on_task_end = self.gorevi_sonlandir
        self.spotify = SpotifyManager()
        self.islem_kuyrugu = queue.Queue()
        self.su_an_mesgul = False  

        # Single Source of Truth: Tüm çalıştırma fonksiyonlarını tool_registry'ye bağla
        tool_registry.bind_handler("arama", self._tool_search)
        tool_registry.bind_handler("klasor_ac", self._tool_open_folder)
        tool_registry.bind_handler("uygulama_ac", self._tool_open_app)
        tool_registry.bind_handler("sarki_ac", self._tool_play_song)
        tool_registry.bind_handler("playlist_ac", self._tool_play_playlist)
        tool_registry.bind_handler("not_al", self._tool_save_note)
        tool_registry.bind_handler("klasor_yap", self._tool_make_folder)
        tool_registry.bind_handler("klasor_incele", self._tool_inspect_folder)
        tool_registry.bind_handler("kodu_calistir", self._tool_run_code)
        tool_registry.bind_handler("dosya_oku", self._tool_read_file)
        tool_registry.bind_handler("dosya_yaz", self._tool_write_file)
        tool_registry.bind_handler("gozlem_yap", self._tool_browser_observe)
        tool_registry.bind_handler("tarayici_tikla", self._tool_browser_click)
        tool_registry.bind_handler("tarayici_yaz", self._tool_browser_type)
        tool_registry.bind_handler("site_oku", self._tool_read_website)
        tool_registry.bind_handler("ekran_goruntusu", self._tool_take_screenshot)
        tool_registry.bind_handler("whatsapp_mesaj_gonder", self._tool_whatsapp_gonder)
        tool_registry.bind_handler("whatsapp_ekrani_oku", self._tool_whatsapp_oku)
        tool_registry.bind_handler("arac_calistir", self._tool_arac_calistir)
        tool_registry.bind_handler("araclari_listele", self._tool_araclari_listele)
        tool_registry.bind_handler("durum_getir", self._tool_durum_getir)
        tool_registry.bind_handler("proje_adi_ayarla", self._tool_proje_adi_ayarla)
        tool_registry.bind_handler("uzun_gorev_plani_yap", self._tool_uzun_gorev_plani_yap)
        
        self.aktif_plan = None
        self._sorulmus_dizinler: set = set()  # Aynı oturumda aynı dizin için tekrar sormayı engelle

    # ---> YENİ EKLENEN MERKEZİ KONUŞMA VE DİNLEME YÖNETİCİSİ <---
    def _asistan_konus(self, metin: str):
        self.app.is_speaking = True

        if not getattr(self.app, "_expanded", True):
            from ui.compact_ui import set_voice_state
            self.app.after(0, lambda: set_voice_state(self.app, "speaking", "Konuşuyorum..."))

        def konusma_bitti_callback():
            self.app.is_speaking = False
            if getattr(self.app, "voice_mode", False) and not getattr(self.app, "_expanded", True):
                from ui.compact_ui import set_voice_state
                self.app.after(0, lambda: set_voice_state(self.app, "listening", "Dinliyorum..."))
                self.app.after(300, self.app.voice_handler.start_listening)

        try:
            self.app.konus.speak(metin, on_complete=konusma_bitti_callback)
        except Exception as e:
            self.app.log(f"Ses motoru hatası: {e}", "red")
            self.app.is_speaking = False

    # ── Dışarıdan çağrılan giriş noktaları ───────────────────────────────────
    # ── Dışarıdan çağrılan giriş noktaları ───────────────────────────────────
    def _set_ui_entry_state(self, state: str, placeholder: str = ""):
        def update():
            if hasattr(self.app, 'entry') and self.app.entry.winfo_exists():
                if state == "normal":
                    self.app.entry.delete(0, "end")   # eski yazıyı temizle
                self.app.entry.configure(state=state)
                if placeholder:
                    self.app.entry.configure(placeholder_text=placeholder)
        self.app.after(0, update)

    def handle(self, event=None, voice_text=None):
        if self.su_an_mesgul:
            return

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
            self.app.record_message("user", user_input)
            self.app.record_message("ghost", "Anlaşıldı Patron, nöbetçi moduna geçiyorum.")
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
        self.su_an_mesgul = True
        self._set_ui_entry_state("disabled", placeholder="Ghost düşünüyor...")

        try:
            if getattr(self.app, "_expanded", True):
                sistem_notu = "[SİSTEM BİLGİSİ: Şu an GENİŞ/YAZILI terminal arayüzündesin. İstediğin kadar detaylı, uzun, maddeli ve teknik cevaplar verebilirsin.]\n"
            else:
                sistem_notu = "[SİSTEM BİLGİSİ: Şu an KOMPAKT/SESLİ arayüzdesin. Cevaplarını çok KISA, NET ve bir sesli asistanın konuşacağı doğallıkta (maksimum 1-2 cümle) ver. Uzun listeler veya kod blokları KULLANMA.]\n"
                
            zengin_input = f"{sistem_notu}{self._enrich_with_memory(user_input)}"

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
            self._agentic_loop(zengin_input)

        finally:
            self.su_an_mesgul = False
            self._set_ui_entry_state("normal", placeholder="Komut yaz...")

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
            self.app.record_message("ghost", cevap)
            self._asistan_konus(cevap)
            # Başarılı açılışta da mikrofonu başlat
            self.app.after(300, self.app.voice_handler.start_listening)

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
            
            # cevap artık gorev_bitti tool_call'ının 'ozet' argümanından geliyor,
            # zaten temiz metin — regex ile tag temizlemeye gerek kalmadı.
            final_mesaji = cevap.strip() if cevap else ""
            
            if final_mesaji:
                self.app.record_message("ghost", final_mesaji)
                if self.app.voice_mode:
                    self._asistan_konus(final_mesaji)
                    
        except Exception as e:
            self.app.log(f"SİSTEM: LangGraph Döngüsü Kırıldı: {e}", "red")
            hata_mesaji = "Patron, işlem sırasında bir hata oluştu."
            self.app.record_message("ghost", hata_mesaji)
            if self.app.voice_mode:
                self._asistan_konus(hata_mesaji)

    def _execute_tool_call(self, isim: str, args: dict) -> str:
        """llm.py'nin tools_node'u tarafından çağrılır. tool_registry üzerinden
        otomatik parametre dizilimi ve yol çözümü ile çalıştırılır."""
        try:
            result = tool_registry.execute(isim, args, self)
            success = self._sonuc_basarili_mi(result)

            # Eğer bir plan aktifse ve bu araç plan yapma aracı değilse, sonuca hatırlatma ekle
            if self.aktif_plan and isim not in ["uzun_gorev_plani_yap", "gorev_bitti"]:
                hedef = self.aktif_plan["hedef"]
                result = f"{result}\n\n[SİSTEM HATIRLATMASI: Şu an '{hedef}' hedefine yönelik uzun görev planını yürütüyorsun. Planına sadık kal ve işin bittiyse sıradaki adıma geç. Tüm plan bittiyse gorev_bitti çağır.]"

            # NOT: 'gorev_bitti' bu fonksiyondan HİÇ geçmez (yonlendirici onu
            # doğrudan critic/END'e yönlendirir, "tools" node'una uğramaz).
            # Bu yüzden plan sıfırlama artık burada değil, GhostController
            # tarafında her _raw_supervisor_call bitişinde (on_task_end) yapılıyor.
            # (Eskiden burada "if isim == 'gorev_bitti': self.aktif_plan = None"
            # vardı ama hiç çalışmayan ölü koddu — bkz. handle_task_end.)

        except Exception as e:
            result = f"Araç çalışırken çöktü: {str(e)}"
            success = False
            self.app.log(f"SİSTEM HATA DETAYI ({isim}):\n{traceback.format_exc()}", "red")

        self.app.log(f"🛠️ ARAÇ: {isim.upper()} | DURUM: {'✅' if success else '❌'}", "yellow")
        self.app.log(f"   Param: {args} | Çıktı: {str(result)[:80]}...", "yellow")

        # SQLite'a araç logunu kaydet
        if hasattr(self, "episodic_db"):
            self.episodic_db.arac_log_kaydet(
                self.app.current_session_id,
                isim,
                args,
                str(result),
                success
            )

        # Dosya/klasör bazlı bir araçsa, proje durum hafızasını güncelle
        proje_notu = None
        if success and isim in DURUM_GUNCELLENECEK_ARACLAR:
            proje_notu = self._proje_durumu_guncelle(isim, args)

        donen_metin = f"tool={isim}\nsuccess={str(success).lower()}\nresult={result}"
        if proje_notu:
            donen_metin += f"\n\n{proje_notu}"
        return donen_metin

    @staticmethod
    def _sonuc_basarili_mi(result) -> bool:
        """
        Bir tool sonucunun gerçekten başarılı mı yoksa hata mesajı mı
        olduğunu anlamaya çalışır. NOT: Bu hâlâ string-önekine dayalı,
        yani KIRILGAN bir sezgi — kod tabanındaki araçların (whatsapp_tool,
        browser_tool vb.) çoğu exception fırlatmak yerine "HATA: ..." diye
        başlayan bir string döndürüyor, exception fırlatmıyor. Kalıcı ve
        sağlam çözüm tool_registry.execute()'un (result, success) şeklinde
        yapılandırılmış bir tuple döndürmesi olurdu — registry dosyasını
        görünce onu da düzeltelim.
        """
        sonuc_str = str(result).strip()
        if sonuc_str.startswith("Bilinmeyen araç"):
            return False
        if sonuc_str.startswith("Araç çalışırken çöktü"):
            return False
        # Kod tabanında hata mesajları tutarsız şekilde "HATA:", "Hata:",
        # "[SİSTEM HATA]" gibi çeşitli öneklerle dönüyor — hepsini yakala.
        if sonuc_str.lower().startswith("hata") or sonuc_str.startswith("[SİSTEM HATA"):
            return False
        return True

    def gorevi_sonlandir(self):
        """
        GhostController her _raw_supervisor_call bitiminde (görev tamamlandı,
        sohbet cevabı döndü ya da recursion limit'e çarpıp vazgeçti — hepsinde)
        bunu çağırır. Eskiden aktif_plan sıfırlaması _execute_tool_call içinde
        'gorev_bitti' geldiğinde yapılıyordu ama gorev_bitti o fonksiyona HİÇ
        uğramıyor (yonlendirici onu doğrudan critic/END'e yönlendiriyor), yani
        o satır hiç çalışmıyordu ve aktif_plan bir kere set edildikten sonra
        uygulama kapanana kadar HER gelecek göreve sızıyordu. Artık üst
        seviyede, her turun kesin olarak bittiği tek yerde sıfırlanıyor.
        """
        self.aktif_plan = None

    def _proje_durumu_guncelle(self, isim: str, args: dict) -> str:
        """
        proje_durumu tablosunu günceller. Kök dizin proje_yol_haritasi'nda
        biliniyorsa sessizce günceller. Bilinmiyorsa geçici bir anahtar altında
        durumu tutar ve modele Patron'a bir kereliğine proje adını sorup
        proje_adi_ayarla ile kaydetmesini söyleyen bir sistem notu döndürür.
        """
        yol_anahtari = DURUM_GUNCELLENECEK_ARACLAR.get(isim)
        yol = args.get(yol_anahtari) if yol_anahtari else None
        if not yol:
            return None

        aktif_dizin = os.path.dirname(yol) if (os.path.isfile(yol) or "." in os.path.basename(yol)) else yol

        try:
            bilinen_proje = self.episodic_db.proje_adi_bul(yol)

            if bilinen_proje:
                self.episodic_db.durum_guncelle(
                    proje_adi=bilinen_proje,
                    aktif_dizin=aktif_dizin,
                    dokunulan_dosya=yol,
                    gorev_ozeti=f"Son işlem: {isim} -> {os.path.basename(yol)}"
                )
                return None

            # Bilinmeyen kök dizin: durumu geçici bir anahtar altında tut
            gecici_anahtar = f"_bilinmiyor::{aktif_dizin}"
            self.episodic_db.durum_guncelle(
                proje_adi=gecici_anahtar,
                aktif_dizin=aktif_dizin,
                dokunulan_dosya=yol,
                gorev_ozeti=f"Son işlem: {isim} -> {os.path.basename(yol)} (proje adı henüz belirlenmedi)"
            )

            # Bu dizin için daha önce sorduk mu? Aynı oturumda tekrar sorma.
            if aktif_dizin in self._sorulmus_dizinler:
                return None
            self._sorulmus_dizinler.add(aktif_dizin)

            return (
                f"[SİSTEM NOTU: '{aktif_dizin}' dizini için kayıtlı bir proje adı yok. "
                f"Eğer bu bir proje klasörüyse, Patron'a bu klasör için ne isim vermek istediğini BİR KERELİĞİNE sor, "
                f"cevabı alınca proje_adi_ayarla(kok_dizin='{aktif_dizin}', proje_adi=<cevap>) aracını çağırıp kaydet. "
                f"Sıradan/geçici bir dosya işlemiyse sormana gerek yok, sessizce devam et.]"
            )
        except Exception as e:
            self.app.log(f"SİSTEM UYARISI: Proje durumu güncellenemedi: {e}", "yellow")
            return None

    def _tool_proje_adi_ayarla(self, kok_dizin: str, proje_adi: str) -> str:
        self.episodic_db.proje_adi_ayarla(kok_dizin, proje_adi)

        # Geçici anahtar altında tutulan durum varsa gerçek proje adına taşı
        gecici_anahtar = f"_bilinmiyor::{kok_dizin}"
        gecici_durum = self.episodic_db.durum_getir(gecici_anahtar)
        if gecici_durum:
            dosyalar = json.loads(gecici_durum["son_dokunulan_dosyalar"]) if gecici_durum["son_dokunulan_dosyalar"] else []
            self.episodic_db.durum_guncelle(
                proje_adi=proje_adi,
                aktif_dizin=gecici_durum["aktif_dizin"],
                gorev_ozeti=gecici_durum["son_gorev_ozeti"]
            )
            for dosya in reversed(dosyalar):
                self.episodic_db.durum_guncelle(proje_adi=proje_adi, dokunulan_dosya=dosya)
            self.episodic_db.proje_durumu_sil(gecici_anahtar)

        self.app.log(f"SİSTEM: '{kok_dizin}' artık '{proje_adi}' projesi olarak kayıtlı.", "green")
        return f"'{kok_dizin}' dizini bundan sonra '{proje_adi}' projesi olarak hatırlanacak."

    def _enrich_with_memory(self, user_input: str) -> str:
        # Eğer sistem mesajıysa belleğe sormaya gerek yok
        if "GİZLİ SİSTEM BİLGİSİ" in user_input:
            return user_input
            
        memories = self.bellek.sorgula(soru=user_input, limit=2)
        if not memories:
            return user_input
            
        context = "\n- ".join(memories)
        return (
            f"[SİSTEM NOTU (Hafıza): Geçmiş konuşmalardan/hafızadan şunları hatırlıyorsun:\n"
            f"- {context}\n"
            f"Bu bilgi kullanıcının isteğiyle ilgiliyse yanıtında veya aksiyonlarında kullanabilirsin.]\n"
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

    def _tool_browser_click(self, url: str, hedef: str) -> str:
        self.app.log(f"SİSTEM: '{url}' adresinde '{hedef}' öğesine tıklanıyor...", "green")
        from tools.browser_tool import browser_interact
        return browser_interact(url, "tikla", hedef)
    
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

    def _tool_uzun_gorev_plani_yap(self, hedef: str, adimlar: list) -> str:
        # Web/Node.js projelerini otomatik tespit et; eksik adımları enjekte et
        hedef_lower = hedef.lower()
        is_web = any(k in hedef_lower for k in ["web", "site", "html", "node", "npm", "react", "uygulama"])
        is_node = any(k in hedef_lower for k in ["node", "npm", "express", "server.js", "package.json"])

        # Proje klasörünü ilk adımda bul (klasor_yap / klasor_ac söz geçiyor mu?)
        proje_klasor_adimi_var = any(
            any(k in str(a).lower() for k in ["klasor_yap", "klasör", "mkdir", "oluştur"])
            for a in adimlar
        )

        # npm install adımı eksikse ve Node projesi ise sona ekle
        npm_adimi_var = any("npm install" in str(a).lower() for a in adimlar)
        ac_adimi_var = any(any(k in str(a).lower() for k in ["aç", "ac", "başlat", "tarayıcı"]) for a in adimlar)

        enjekte_edilenler = []
        if is_node and not npm_adimi_var:
            enjekte_edilenler.append("kodu_calistir ile 'npm install' komutunu çalıştır (bağımlılıkları kur)")
        if is_web and not ac_adimi_var:
            if is_node:
                enjekte_edilenler.append("kodu_calistir ile projeyi başlat (node server.js veya npm start) ve Patron'a localhost adresini bildir")
            else:
                enjekte_edilenler.append("uygulama_ac ile index.html dosyasını tarayıcıda aç")

        adimlar_son = list(adimlar) + enjekte_edilenler

        self.aktif_plan = {
            "hedef": hedef,
            "adimlar": adimlar_son
        }
        plan_str = "\n".join(f"{i+1}. {a}" for i, a in enumerate(adimlar_son))

        ekstra_not = ""
        if enjekte_edilenler:
            ekstra_not = f"\n\n[SİSTEM: {len(enjekte_edilenler)} adım otomatik eklendi: {', '.join(enjekte_edilenler)}]"

        return (
            f"Plan başarıyla kaydedildi. HEDEF: {hedef}\n"
            f"ADIMLAR:\n{plan_str}{ekstra_not}\n\n"
            f"[PROJE PROTOKOLÜ HATIRLATMASI]: Her dosyayı sırayla yaz. "
            f"Bir dosya bitmeden diğerine geçme. "
            f"Tüm dosyalar yazılıp bağımlılıklar kurulunca projeyi çalıştır, ardından gorev_bitti çağır."
        )

    def _tool_browser_type(self, url: str, kutu: str, metin: str) -> str:
        self.app.log(f"SİSTEM: '{url}' adresinde '{kutu}' öğesine '{metin}' yazılıyor...", "green")
        from tools.browser_tool import browser_interact
        return browser_interact(url, "yaz", kutu, metin)

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

    def _tool_whatsapp_gonder(self, kisi: str, mesaj: str) -> str:
        self.app.log(f"SİSTEM: WhatsApp'tan '{kisi}' kişisine mesaj gönderiliyor...", "green")
        return whatsapp_mesaj_gonder(kisi, mesaj)

    def _tool_whatsapp_oku(self) -> str:
        self.app.log("SİSTEM: WhatsApp ekranı Vision ile okunuyor...", "green")
        return whatsapp_ekrani_yorumla()

    def _tool_arac_calistir(self, dosya: str, fonksiyon: str, parametreler: dict) -> str:
        try:
            mod = self._tool_modulunu_al(dosya)
        except Exception as e:
            return f"HATA: '{dosya}' import edilemedi: {e}"

        fn = getattr(mod, fonksiyon, None)
        if fn is None:
            mevcut = [n for n in dir(mod) if not n.startswith("_")]
            return f"HATA: '{fonksiyon}' bulunamadı. '{dosya}' içindeki fonksiyonlar: {mevcut}"

        self.app.log(f"SİSTEM: {dosya}::{fonksiyon}({parametreler}) çalıştırılıyor...", "green")
        try:
            return str(fn(**(parametreler or {})))
        except TypeError as e:
            imza = inspect.signature(fn)
            return f"HATA: Parametre uyuşmazlığı. Doğru imza: {fonksiyon}{imza}. Hata: {e}"
        except Exception as e:
            return f"HATA: Çalıştırma hatası: {e}"

    def _tool_araclari_listele(self) -> str:
        tools_dir = self._tools_dir()
        ozet = []
        for dosya in sorted(os.listdir(tools_dir)):
            if not dosya.endswith(".py") or dosya.startswith("_"):
                continue
            try:
                mod = self._tool_modulunu_al(dosya)
            except Exception as e:
                ozet.append(f"{dosya}: import hatası ({e})")
                continue
            for isim, fn in inspect.getmembers(mod, inspect.isfunction):
                if isim.startswith("_") or fn.__module__ != mod.__name__:
                    continue
                ilk_satir = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else ""
                ozet.append(f"{dosya}::{isim}{inspect.signature(fn)} - {ilk_satir}")
        return "\n".join(ozet) if ozet else "tools/ klasöründe fonksiyon bulunamadı."

    def _tools_dir(self) -> str:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")

    def _tool_modulunu_al(self, dosya: str):
        tools_dir = self._tools_dir()
        yol = os.path.join(tools_dir, dosya)
        mod_adi = f"tools.{os.path.splitext(dosya)[0]}"

        # Modül daha önce import edildiyse CACHE'DEN dön - state (örn. bir
        # tarayıcı oturumu) böylece çağrılar arasında canlı kalır.
        if mod_adi in sys.modules:
            return sys.modules[mod_adi]

        spec = importlib.util.spec_from_file_location(mod_adi, yol)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_adi] = mod
        spec.loader.exec_module(mod)
        return mod
   
    def _tool_mission_complete(self, nihai_cevap: str) -> str:
        return f"GÖREV_TAMAMLANDI_SİNYALİ: {nihai_cevap}"
    
    def _tool_take_screenshot(self, ne_arayacagim: str) -> str:
        self.app.log(f"SİSTEM: Ghost otonom olarak ekrana bakıyor... Soru: '{ne_arayacagim}'", "green")
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
            basarili_mi, saf_kod, mesaj = minimax_vision_analiz(ne_arayacagim, kayit_yolu)
            
            if basarili_mi and saf_kod:
                return f"GÖZLEM SONUCU: Ekranda şu kod bulundu:\n\n{saf_kod}\n\nLütfen Kullanıcının asıl isteğine göre bu kodu kullanarak işlem yap."
            
            return f"GÖZLEM SONUCU: {mesaj}\n\n[ÖLÜMCÜL SİSTEM TALİMATI: Ekranı başarıyla gördün ve özetledin. ŞİMDİ ARAÇ KULLANMAYI DERHAL BIRAK. Hiçbir [ETİKET] kullanmadan, doğrudan gördüklerini Patron'a kendi havalı tarzınla açıkla ve görevi bitir.]"
            
        except Exception as e:
            self.app.deiconify()
            return f"SİSTEM HATASI: Ekran görüntüsü alınamadı, hata: {str(e)}"
        
    def _tool_search(self, sorgu: str) -> str:
        self.app.log(f"SİSTEM: Plan A - DuckDuckGo ile hızlı arama yapılıyor: '{sorgu}'...", "green")
        from tools.google_tool import search_duckduckgo, _format_results
        
        try:
            ddg_results = search_duckduckgo(sorgu)
            formatted = _format_results(ddg_results)
            
            if formatted:
                return (f"DuckDuckGo Arama Sonuçları ('{sorgu}'):\n\n{formatted}\n\n"
                    f"[GİZLİ SİSTEM TALİMATI: Aradığın cevabı (örneğin playlist adı, maç skoru) bu özetlerde bulduysan, "
                    f"başka bir siteye girmeden DOĞRUDAN ilgili aracı (örneğin [PLAYLIST_AÇ: ...], [UYGULAMA_AC: ...]) "
                    f"kullan. Eğer detaylı bir makale okuman ŞART ise [SİTE_OKU: <url>] kullan.]")
                    
            else:
                raise Exception("DuckDuckGo sonuç döndürmedi.")
                
        except Exception as e:
            self.app.log(f"SİSTEM UYARISI: DDG başarısız ({str(e)[:30]}). Plan B (Fiziksel Tarayıcı) başlıyor...", "yellow")
            
            from tools.browser_tool import browser_google_search
            try:
                arama_sonuclari = browser_google_search(sorgu)
                if "başarısız oldu" in arama_sonuclari or "çekilemedi" in arama_sonuclari:
                    raise Exception("Tarayıcı metin çekemedi.")
                
                self.app.log("SİSTEM: Plan B başarılı. Tarayıcı sonuçları alındı.", "green")
                return (f"{arama_sonuclari}\n\n"
                        f"[GİZLİ SİSTEM TALİMATI: Aradığın bilgi için uygun bir kaynak bulduysan, "
                        f"[SİTE_OKU: <url>] aracını kullan.]")
            
            except Exception as e2:
                self.app.log("SİSTEM HATA: Tarayıcı DOM'u çöktü. Plan C (LLaVA Görsel) başlıyor...", "yellow")
                return self._visual_search_fallback(sorgu)
   
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
                            
    def _tool_durum_getir(self, proje_adi: str) -> str:
        """
        proje_adi boş/"son"/"en son" gibi verilirse en son aktif olan projeyi getirir.
        Aksi halde belirtilen proje adına ait durumu getirir.
        """
        proje_adi = (proje_adi or "").strip().lower()

        if not proje_adi or proje_adi in ("son", "en son", "son proje", "kaldığımız yer"):
            durum = self.episodic_db.son_aktif_projeyi_getir()
        else:
            durum = self.episodic_db.durum_getir(proje_adi)

        if not durum:
            projeler = self.episodic_db.tum_projeleri_listele()
            if projeler:
                isimler = ", ".join(p["proje_adi"] for p in projeler)
                return f"'{proje_adi}' için kayıtlı durum bulunamadı. Bilinen projeler: {isimler}"
            return "Henüz kayıtlı hiçbir proje durumu yok."

        dosyalar = json.loads(durum["son_dokunulan_dosyalar"]) if durum["son_dokunulan_dosyalar"] else []
        return (
            f"Proje: {durum['proje_adi']}\n"
            f"Aktif Dizin: {durum['aktif_dizin']}\n"
            f"Son Dokunulan Dosyalar: {', '.join(dosyalar[:5])}\n"
            f"Son Görev Özeti: {durum['son_gorev_ozeti']}"
        )

    def _tool_open_folder(self, yol: str) -> str:
        if os.path.exists(yol):
            os.startfile(yol)
            self.app.log(f"SİSTEM: '{yol}' açıldı.", "green")
            return f"'{yol}' klasörü başarıyla açıldı."
        
        real = derin_arama(yol)
        if real:
            os.startfile(real)
            self.app.log(f"SİSTEM: Bulundu → {real}", "green")
            return f"Klasör bulundu ve açıldı: '{real}'"
            
        return "Klasör bulunamadı."
    
    def _tool_open_app(self, isim: str) -> str:
        isim = isim.lower()
        self.app.log(f"SİSTEM: '{isim}' başlatılıyor...", "green")
        
        if sys.platform.startswith("win"):
            SPECIAL = {
                "cursor": os.path.expanduser(r"~\AppData\Local\Programs\cursor\Cursor.exe"),    
                "discord": (os.path.expanduser(r"~\AppData\Local\Discord\Update.exe") ,["--processStart", "Discord.exe"]),
                "whatsapp": "whatsapp://"
            }
            if isim in SPECIAL:
                app = SPECIAL[isim]
                if isinstance(app, tuple):
                    subprocess.Popen([app[0]] + app[1])
                else:
                    os.startfile(app)
            else:
                os.system(f"start {isim}")
                
        elif sys.platform.startswith("linux"):
            SPECIAL = {
                "cursor": "cursor",
                "discord": "discord",
                "whatsapp": "whatsapp-for-linux"
            }
            komut = SPECIAL.get(isim, isim)
            os.system(f"nohup {komut} >/dev/null 2>&1 &")
            
        return f"'{isim}' uygulaması başlatıldı komutu verildi."

    def _tool_play_song(self, sarki: str) -> str:
        self.app.log(f"SİSTEM: Spotify'da '{sarki}' aranıyor...", "green")
        try:
            result = self.spotify.play_specific_song(sarki)
            return f"Spotify Sonucu: {result}"

        except spotipy.exceptions.SpotifyException as e:
            if "No active device" in str(e) or "DEVICE_ISSUE" in str(e) or getattr(e, "http_status", None) == 404:
                self.app.log("SİSTEM: Aktif cihaz yok, Spotify açılıp uyandırılıyor...", "yellow")
                self._tool_open_app("spotify")
                time.sleep(2)
                try:
                    device_id = self.spotify.wake_active_device()
                    if not device_id:
                        return ("HATA: Spotify'da hiç kayıtlı cihaz bulunamadı. "
                                "[ÖLÜMCÜL SİSTEM TALİMATI: Bu bir CİHAZ sorunudur, şarkı adıyla ilgisi yok. "
                                "BAŞKA BİR ŞARKI DENEME. Patron'a Spotify uygulamasını açıp bir şeye tıklamasını "
                                "söyleyerek [GOREV_BITTI: ...] ile işlemi hemen sonlandır.]")
                    time.sleep(1.5)
                    result = self.spotify.play_specific_song(sarki)
                    return f"Spotify Sonucu (cihaz uyandırıldıktan sonra): {result}"
                except Exception as e2:
                    return (f"HATA: Cihaz uyandırılamadı: {e2}. "
                            f"[ÖLÜMCÜL SİSTEM TALİMATI: Bu CİHAZ bağlantı sorunu, başka şarkı denemenin faydası yok. "
                            f"[GOREV_BITTI: Patron, Spotify cihaz bağlantısında sorun var, uygulamayı kontrol eder misin?] kullan.]")

            return (f"HATA: Spotify hatası: {e}. "
                    f"[ÖLÜMCÜL SİSTEM TALİMATI: Başka bir şarkı deneme, sorun teknik. "
                    f"[GOREV_BITTI: Patron, Spotify'da teknik bir sorun oluştu.] kullan.]")
        
    def _tool_play_playlist(self, liste: str) -> str:
        self.app.log(f"SİSTEM: '{liste}' listesi aranıyor...", "green")
        result = self.spotify.play_playlist(liste)
        return f"Spotify Sonucu: {result}"

    def _tool_save_note(self, bilgi: str) -> str:
        self.bellek.bellege_yaz(bilgi)
        self.app.log(f"SİSTEM: Beyne kazındı → '{bilgi}'", "green")
        return "Not başarıyla belleğe kaydedildi."

    def _tool_make_folder(self, yol: str) -> str:
        os.makedirs(yol, exist_ok=True)
        self.app.log(f"SİSTEM: Klasör oluşturuldu → {yol}", "green")
        return f"'{yol}' dizininde klasör başarıyla oluşturuldu."

    def _tool_inspect_folder(self, yol: str) -> str:
        if os.path.isdir(yol):
            files = ", ".join(os.listdir(yol)) or "Klasör boş."
            self.app.log(f"SİSTEM: Klasör tarandı → {yol}", "green")
            return f"Klasör İçeriği: {files}"
        return "Belirtilen yol bir klasör değil veya bulunamadı."

    def _tool_write_file(self, yol: str, icerik: str) -> str:
        # Göreceli yol ya da sadece dosya adı verilmişse → tools/ klasörüne yönlendir
        # Mutlak yol verilmişse (C:\... gibi) dokunma
        if not os.path.isabs(yol):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            yol = os.path.join(base_dir, "tools", yol)

        folder = os.path.dirname(yol)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            f.write(icerik)
        self.app.log(f"SİSTEM: Dosya yazıldı → {yol}", "green")
        return f"Kod başarıyla '{yol}' konumuna kaydedildi."

    def _tool_run_code(self, yol: str) -> str:
        self.app.log(f"SİSTEM: '{yol}' çalıştırılıyor...", "green")
        result = kodu_calistir(yol)
        if result["basarili"]:
            self.app.log(f"SİSTEM ✅ Başarılı:\n{result['cikti'][:100]}...", "green")
            return f"Kod başarıyla çalıştı. Çıktı:\n{result['cikti']}"
        
        self.app.log("SİSTEM ⚠️ Hata tespit edildi...", "red")
        return f"Kod çalıştırılırken hata verdi. Lütfen hatayı inceleyip düzelt:\n{result['hata']}"

    def _tool_read_file(self, yol: str) -> str:
        if os.path.isfile(yol):
            content = open(yol, encoding="utf-8").read()
            self.app.log(f"SİSTEM: '{yol}' okundu.", "green")
            return f"Dosya İçeriği:\n{content}"
            
        folder = os.path.dirname(yol)
        if os.path.isdir(folder):
            files = ", ".join(os.listdir(folder)) or "Klasör boş."
            return f"Hedeflenen dosya bulunamadı. Klasörün içindeki mevcut dosyalar: {files}"
            
        return "Dosya veya dizin tamamen geçersiz."