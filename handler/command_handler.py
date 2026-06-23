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

from hafıza.rag_hafıza import Bellek
from ai.llm import GhostController, ChatLLM
from tools.google_tool import ghost_search_tool
from handler.patterns import PATTERNS
from kontrol.spotify import SpotifyManager
from kontrol.güvenlik import guvenlik_kontrolu
from kontrol.kontrol import google_arama
from core.planner import PlannerAgent
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
        # 1. Kelimeleri ayır ve TAM eşleşme ara (Böylece "karar" kelimesi içindeki "ara" hecesi sistemi tetiklemez)
        eylem_kelimeleri = {"aç", "yaz", "oluştur", "ara", "çal", "kapat", "sil", "kur", "incele", "oku", "çalıştır", "bul", "test"}
        kelimeler = set(user_input.lower().split())
        is_action = bool(kelimeler.intersection(eylem_kelimeleri))
        
        # 2. Eğer fiziksel bir komut yoksa, Planlayıcıyı HİÇ YORMA!
        if not is_action:
            self.app.set_model_label("Aktif Durum: Sohbet Ediyor...")
            self._process(user_input, is_background=False)
            return

        # 3. Eğer fiziksel komut varsa, eski ağır sanayi sistemini çalıştır
        threading.Thread(target=self._quick_ack, args=(user_input,), daemon=True).start()
        self._plan_and_execute(user_input)

    def _quick_ack(self, user_input):
        """Claude'un temiz yapısı: Sadece ön-mesajı üretir ve seslendirir."""
        self.app.set_model_label("Aktif Durum: Operasyon Başlıyor...")
        on_mesaj_prompt = (
            f"GİZLİ SİSTEM BİLGİSİ: Kullanıcı senden şu işi istedi: '{user_input}'. "
            f"Sen şu an arka planda bu işin planlamasını ve hazırlığını yapıyorsun. "
            f"Kullanıcıya süreci devraldığını ve çalışmaya başladığını belirten ÇOK KISA, havalı ve samimi bir cümle kur. "
            f"(Örn: 'Hemen hallediyorum Patron.', 'Sistemleri tarıyorum, arkana yaslan.') "
            f"SADECE cümleyi yaz, asla etiket kullanma."
        )
        try:
            on_mesaj, _ = self.controller(on_mesaj_prompt)
            self.app.log(f"SİSTEM (Ön mesaj) {on_mesaj}")
            
            # Sadece konuş, bittikten sonra bir şey tetiklemene gerek yok çünkü plan zaten arkada çalışıyor!
            if self.app.voice_mode:
                self.app.konus.speak(on_mesaj)
        except Exception as e:
            self.app.log(f"SİSTEM HATA (Ön-Mesaj): {e}", "red")

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
        
        # Araç sonuçlarını mesaj geçmişine ekleyerek modeli besle
        self.controller.supervisor.mesaj_gecmisi.append({
            "role": "user", "content": user_input
        })
        
        for adim in range(5):  # max 5 adım, sonsuz döngü önlemi
            response, model = self.controller._raw_supervisor_call()
            self._update_model_label(model)

            # Araç var mı kontrol et
            sonuc = self._araclari_calistir(response)
            
            if sonuc is None:
                # Araç yok = model bitti, kullanıcıya göster
                display = self._clean_response_for_display(response)
                self.app.record_message("ghost", display)
                if self.app.voice_mode:
                    self.app.konus.speak(display)
                return
            
            # Araç sonucunu modele geri besle, döngü devam eder
            self.controller.supervisor.mesaj_gecmisi.append({
                "role": "user",
                "content": f"[ARAÇ SONUCU - Adım {adim+1}]: {sonuc}\nDevam et, gerekirse başka araç kullan."
            })
        
        self.app.log("SİSTEM: Maksimum adım aşıldı.", "red")

    def _araclari_calistir(self, response: str) -> str | None:
        """Regex ile eşleşen ilk aracı çalıştırır ve sonucunu string döner."""
        
        # İstisna 1: Çift parametreli araç (Dosya Yazma)
        m = PATTERNS["dosya_yaz"].search(response)
        if m:
            path = akilli_yol_cozucu(m.group(1).strip())
            code = m.group(2).strip()
            return self._tool_write_file(path, code)

        # Diğer standart araçlar
        # Format: (Pattern Adı, Çalıştırılacak Fonksiyon, Yol Çözücü Gerekli mi?)
        standart_araclar = [
            ("arama", self._tool_search, False),
            ("klasor_ac", self._tool_open_folder, True),
            ("uygulama_ac", self._tool_open_app, False),
            ("sarki_ac", self._tool_play_song, False),
            ("playlist_ac", self._tool_play_playlist, False),
            ("not_al", self._tool_save_note, False),
            ("klasor_yap", self._tool_make_folder, True),
            ("klasor_incele", self._tool_inspect_folder, True),
            ("kodu_calistir", self._tool_run_code, True),
            ("dosya_oku", self._tool_read_file, True)
        ]

        for pattern_adi, func, yol_coz in standart_araclar:
            m = PATTERNS[pattern_adi].search(response)
            if m:
                param = m.group(1).strip()
                # Eğer araca giren veri bir dosya yoluysa, akıllı çözücüyü kullan
                if yol_coz:
                    param = akilli_yol_cozucu(param)
                try:
                    return func(param)
                except Exception as e:
                    return f"Araç hatası ({pattern_adi}): {e}"
                    
        return None
    
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
    
    # ── Planlama ve Yürütme ──────────────────────────────────────────────
    def _plan_and_execute(self, user_input: str):
        self.app.set_model_label("Aktif Durum: Planlayıcı Düşünüyor...")
        
        adimlar = self.planner.plan_olustur(user_input)
        
        self.app.log(f"SİSTEM: Operasyon planlandı. ({len(adimlar)} Adım)", "green")
        
        if len(adimlar) > 1:
            self.app.log_collapsible_plan(adimlar)

        # 1. Bütün adımları kuyruğa diz (Eski direkt _process çağrısını siliyoruz)
        for adim in adimlar:
            self.islem_kuyrugu.put((adim,user_input))
            
        # 2. Eğer arkada çalışan bir işçi yoksa, işçiyi (thread'i) uyandır
        if not self.su_an_mesgul:
            threading.Thread(target=self._kuyruk_tuketici, daemon=True).start()

    # ── İşelem sırası ──────────────────────────────────────────────
    def _kuyruk_tuketici(self):
        """Kuyruktaki görevleri sırayla çalıştıran motor."""
        self.su_an_mesgul = True

        while not self.islem_kuyrugu.empty():
            görev, original_input = self.islem_kuyrugu.get()
            
            # Queue.get() elemanı sildiği için, boşsa son adımdır!
             
            is_last_step = self.islem_kuyrugu.empty() 
            if is_last_step:
                # SON ADIM: Ghost'un ağzındaki bandı söküyoruz, konuşsun!
                gelişmiş_komut = (
                    f"GİZLİ SİSTEM BİLGİSİ: Kullanıcının sana asıl sorusu şuydu: '{original_input}'.\n"
                    f"Arka plan planlamasının SON aşamasındayız. Şu anki Görev: '{görev}'.\n"
                    f"Eğer eylem gerekiyorsa uygun [ETİKET] ile eylemi yap, ARDINDAN doğrudan "
                    f"kullanıcının asıl sorusunu yanıtlayacak şekilde doğal, samimi ve havalı bir sohbet cümlesi kur."
                )
                self._process(gelişmiş_komut, depth=0, is_background=False)
            else:
                # ARA ADIM: Sessiz ol, gevezelik yapma, sadece etiketi bas
                gelişmiş_komut = (
                    f"GİZLİ SİSTEM BİLGİSİ: Arka planda şu görevi yapıyorsun: '{görev}'. "
                    f"SADECE ve SADECE gerekli eylem etiketini kullan. HİÇBİR sohbet veya açıklama metni yazma."
                )
                self._process(gelişmiş_komut, depth=0, is_background=True)

            self.islem_kuyrugu.task_done()
            
        self.su_an_mesgul = False
        self.app.set_model_label("Aktif Durum: Bekliyor...")

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