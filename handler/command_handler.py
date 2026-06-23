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
 
    def _process(self, user_input: str, depth: int = 0, on_done: threading.Event = None, is_background : bool = False):
        if depth > MAX_DEPTH:
            self.app.log("SİSTEM: Maksimum döngü derinliğine ulaşıldı.", "red")
            if on_done:
                on_done.set()
                return
            
        action_taken = False
        
        try:
            enriched = self._enrich_with_memory(user_input) 
            response, model = self.controller(enriched)
            self._update_model_label(model)
 
            display = self._clean_response_for_display(response)
            if display:
                if is_background:
                    #Arka plan işlemlerini chat balonuna atma, sadece gizlice loga bas
                    self.app.log(f"SİSTEM (Arka Plan Sesli Düşünce): {display}", "green")
                else:
                    # Final adımı! Chat balonuna yaz ve seslendir
                    self.app.record_message("ghost" ,display)
                    if self.app.voice_mode:
                        self.app.konus.speak(
                            display,
                            on_complete=lambda: self.app.after(800, self.app.voice_handler.start_listening)
                        )
            else:
                if not is_background and self.app.voice_mode:
                    self.app.after(800, self.app.voice_handler.start_listening)
                    
            if not guvenlik_kontrolu(user_input):
                self.app.log("SİSTEM: Tehlikeli komut algılandı! İşlem reddedildi.", "red")
                return
 
            # Her eylemi kendi metoduna delege et
            action_taken |= self._handle_open_folder(response)
            action_taken |= self._handle_open_app(response)
            action_taken |= self._handle_play_song(response)
            action_taken |= self._handle_play_playlist(response)
            action_taken |= self._handle_search(response, user_input,depth)
            action_taken |= self._handle_save_note(response)
            action_taken |= self._handle_make_folder(response)
            action_taken |= self._handle_inspect_folder(response, user_input, depth)
            action_taken |= self._handle_write_file(response)
            action_taken |= self._handle_run_code(response, depth)
            if not action_taken:
                self._handle_read_file(response, user_input, depth)
 
        except Exception:
            self.app.log(f"SİSTEM HATA:\n{traceback.format_exc()}", "red")
        
        finally:
            if on_done:
                on_done.set()

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

    def _handle_search(self, response: str, user_input: str, depth: int) -> bool:
        m = PATTERNS["arama"].search(response)
        if not m:
            return False
            
        query = m.group(1).strip()
        self.app.log(f"SİSTEM: Google'da '{query}' aranıyor...", "green")
        
        try:
            # 1. Aramayı yap ve sonuçları al (google_tool.py veya yazdığın araçtan dönecek)
            # return_results=True gibi bir mantıkla veriyi geri alman lazım
            arama_sonuclari = ghost_search_tool(query) 
            
            # 2. Eğer sonuç bulduysan, Ghost'a tekrar gizli bir mesaj gönder:
            if arama_sonuclari:
                self.app.log("SİSTEM: Veriler çekildi, Ghost sentezliyor...", "green")
                prompt = (
                    f"GİZLİ SİSTEM BİLGİSİ: '{query}' için internette arama yaptım ve şu sonuçları buldum:\n"
                    f"{arama_sonuclari}\n\n"
                    f"Şimdi bu bilgileri kullanarak kullanıcının şu sorusuna doğal, havalı ve kısa bir cevap ver: '{user_input}'. "
                    f"KESİNLİKLE [ARAMA: ...] etiketini tekrar kullanma!"
                )
                # 3. Döngüyü tekrar çalıştır (Derinliği 1 artırarak)
                self._process(prompt, depth + 1,is_background = False)
            else:
                # 4. Sonuç yoksa Ghost'a bulamadığını söyle
                prompt = f"GİZLİ SİSTEM BİLGİSİ: İnternette arama yaptım ama sonuç bulamadım. Kullanıcıya bunu uygun dille söyle."
                self._process(prompt, depth + 1, is_background = False) 
                
        except Exception as e:
            self.app.log(f"SİSTEM HATA (Arama): {e}", "red")
            
        return True

    # ── Eylem işleyicileri ────────────────────────────────────────────────────
 
    def _handle_open_folder(self, response: str) -> bool:
        m = PATTERNS["klasor_ac"].search(response)
        if not m:
            return False
        path = akilli_yol_cozucu(m.group(1))
        if os.path.exists(path):
            os.startfile(path)
            self.app.log(f"SİSTEM: '{path}' açıldı.", "green")
        else:
            self.app.log("SİSTEM: Derin arama yapılıyor...")
            real = derin_arama(path)
            if real:
                os.startfile(real)
                self.app.log(f"SİSTEM: Bulundu → {real}", "green")
            else:
                self.app.log("SİSTEM HATA: Klasör bulunamadı.", "red")
        return True
 
    def _handle_open_app(self, response: str) -> bool:
        m = PATTERNS["uygulama_ac"].search(response)
        if not m:
            return False
            
        name = m.group(1).strip().lower()
        self.app.log(f"SİSTEM: '{name}' başlatılıyor...", "green")
        
        # İşletim sistemine göre yollar ve komutlar
        if sys.platform.startswith("win"):
            # Windows yolları (dum4n yerine genel kullanıcı dizini ~ kullanıldı)
            SPECIAL = {
                "cursor": os.path.expanduser(r"~\AppData\Local\Programs\cursor\Cursor.exe"),    
                "discord": (os.path.expanduser(r"~\AppData\Local\Discord\Update.exe") ,["--processStart", "Discord.exe"]),
                "whatsapp": "whatsapp://"
            }
            try:
                if name in SPECIAL:
                    app = SPECIAL[name]
                    if isinstance(app, tuple):
                        subprocess.Popen([app[0]] + app[1])
                    else:
                        os.startfile(app)
                else:
                    os.system(f"start {name}")
            except Exception as e:
                self.app.log(f"SİSTEM HATA: Uygulama açılamadı. {e}", "red")
        
        elif sys.platform.startswith("linux"):
            # Zorin OS / Linux için komutlar
            SPECIAL = {
                "cursor": "cursor",   # Genelde PATH içindedir veya alias atanmıştır
                "discord": "discord",
                "whatsapp": "whatsapp-for-linux" # veya kullandığın web wrapper
            }
            try:
                # Linux'ta arkaplanda çalıştırmak için nohup veya & kullanılır
                komut = SPECIAL.get(name, name)
                os.system(f"nohup {komut} >/dev/null 2>&1 &")
            except Exception as e:
                self.app.log(f"SİSTEM HATA: Uygulama açılamadı. {e}", "red")
                
        return True
 
    def _handle_play_song(self, response: str) -> bool:
        m = PATTERNS["sarki_ac"].search(response)
        if not m:
            return False
        song = m.group(1).strip()
        self.app.log(f"SİSTEM: Spotify'da '{song}' aranıyor...", "green")
        try:
            result = self.spotify.play_specific_song(song)
            self.app.log(f"SİSTEM: {result}", "green")
        except Exception as e:
            if any(k in str(e).lower() for k in ["device", "active", "not found"]):
                try:
                    self.spotify.play_playlist("mesela yanii")
                    time.sleep(2)
                    self.app.log(f"SİSTEM: Cihaz uyandırıldı, '{song}' açıldı.", "green")
                except Exception as e2:
                    self.app.log(f"SİSTEM HATA: Cihaz uyandırılamadı. {e2}", "red")
            else:
                self.app.log(f"SİSTEM HATA (Spotify): {e}", "red")
        return True
 
    def _handle_play_playlist(self, response: str) -> bool:
        m = PATTERNS["playlist_ac"].search(response)
        if not m:
            return False
        playlist = m.group(1).strip()
        self.app.log(f"SİSTEM: '{playlist}' listesi aranıyor...", "green")
        try:
            result = self.spotify.play_playlist(playlist)
            self.app.log(f"SİSTEM: {result}", "green")
        except Exception as e:
            self.app.log(f"SİSTEM HATA (Spotify): {e}", "red")
        return True
 
    def _handle_save_note(self, response: str) -> bool:
        m = PATTERNS["not_al"].search(response)
        if not m:
            return False
        note = m.group(1).strip()
        self.bellek.bellege_yaz(note)
        self.app.log(f"SİSTEM: Beyne kazındı → '{note}'", "green")
        return True
 
    def _handle_make_folder(self, response: str) -> bool:
        m = PATTERNS["klasor_yap"].search(response)
        if not m:
            return False
        path = akilli_yol_cozucu(m.group(1))
        try:
            os.makedirs(path, exist_ok=True)
            self.app.log(f"SİSTEM: Klasör oluşturuldu → {path}", "green")
        except Exception as e:
            self.app.log(f"SİSTEM HATA (Klasör Yap): {e}", "red")
        return True
 
    def _handle_inspect_folder(self, response: str, user_input: str, depth: int) -> bool:
        m = PATTERNS["klasor_incele"].search(response)
        if not m:
            return False
        path = akilli_yol_cozucu(m.group(1))
        if os.path.isdir(path):
            files = ", ".join(os.listdir(path)) or "Klasör boş."
            self.app.log(f"SİSTEM: Klasör tarandı → {files}", "green")
            prompt = (
                f"GİZLİ SİSTEM BİLGİSİ: '{path}' klasörünün içeriği: {files}\n"
                f"Kullanıcının isteğine göre doğru dosyayı seç ve işleme devam et."
            )
            self._process(prompt, depth + 1)
        else:
            self.app.log(f"SİSTEM HATA: Klasör bulunamadı → {path}", "red")
        return True
 
    def _handle_write_file(self, response: str) -> bool:
        m = PATTERNS["dosya_yaz"].search(response)
        if not m:
            return False
        raw_path = m.group(1).strip()
        path = akilli_yol_cozucu(raw_path)
        code = m.group(2).strip()
        try:
            folder = os.path.dirname(path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            self.app.log(f"SİSTEM: Dosya yazıldı → {path}", "green")
        except Exception as e:
            self.app.log(f"SİSTEM HATA (Dosya Yazma): {e}", "red")
        return True
 
    def _handle_run_code(self, response: str, depth: int) -> bool:
        m = PATTERNS["kodu_calistir"].search(response)
        if not m:
            return False
        path = akilli_yol_cozucu(m.group(1))
        self.app.log(f"SİSTEM: '{path}' çalıştırılıyor...", "green")
        result = kodu_calistir(path)
        if result["basarili"]:
            self.app.log(f"SİSTEM ✅ Başarılı:\n{result['cikti']}", "green")
        elif depth < MAX_DEPTH:
            self.app.log("SİSTEM ⚠️ Hata tespit edildi, Ghost düzeltiyor...", "red")
            prompt = (
                f"GİZLİ SİSTEM BİLGİSİ: '{path}' çalıştırdım, hata:\n\n{result['hata']}\n\n"
                f"Önce [DOSYA_OKU: {path}] ile oku, hatayı düzelt ve SADECE şu formatla kaydet:\n"
                f"[DOSYA_YAZ: {path}]\n<<<KOD_BASLANGIC>>>\n(kod)\n<<<KOD_BITIS>>>\n"
                f"Sonra [KODU_CALISTIR: {path}] ile test et."
            )
            self._process(prompt, depth + 1)
        else:
            self.app.log(f"SİSTEM: 2 deneme başarısız. Son hata:\n{result['hata']}", "red")
        return True
 
    def _handle_read_file(self, response: str, user_input: str, depth: int):
        m = PATTERNS["dosya_oku"].search(response)
        if not m or "GİZLİ SİSTEM BİLGİSİ" in user_input:
            return
        path = akilli_yol_cozucu(m.group(1))
        if os.path.isfile(path):
            try:
                content = open(path, encoding="utf-8").read()
                self.app.log(f"SİSTEM: '{path}' okundu, Ghost analiz ediyor...", "green")
                prompt = (
                    f"GİZLİ SİSTEM BİLGİSİ: '{path}' dosyasının içeriği:\n\n{content}\n\n"
                    f"Kullanıcının isteğine dön ve bu içeriğe göre hareket et.\n"
                    f"Kod değiştirilecekse SADECE şu formatı kullan:\n"
                    f"[DOSYA_YAZ: {path}]\n<<<KOD_BASLANGIC>>>\n(yeni_kod)\n<<<KOD_BITIS>>>\n"
                    f"Sadece soru sorulduysa DOSYA_YAZ ETİKETİNİ KULLANMA, Türkçe cevapla."
                )
                self._process(prompt, depth + 1)
            except Exception as e:
                self.app.log(f"SİSTEM HATA (Dosya Okuma): {e}", "red")
        else:
            folder = os.path.dirname(path)
            if os.path.isdir(folder):
                files = ", ".join(os.listdir(folder)) or "Klasör boş."
                self.app.log("SİSTEM HATA: Dosya bulunamadı! Klasör röntgenleniyor...", "red")
                prompt = (
                    f"GİZLİ SİSTEM BİLGİSİ: '{path}' dosyası YOK. "
                    f"Klasörde şunlar var: {files}. "
                    f"Kullanıcıya dosyanın olmadığını söyle ve mevcut dosyaları listele, hangisine bakacağını sor."
                )
            else:
                self.app.log("SİSTEM HATA: Klasör yolu da geçersiz!", "red")
                prompt = f"GİZLİ SİSTEM BİLGİSİ: '{path}' tamamen geçersiz bir yol. Kullanıcıya bildir."
            
            self._process(prompt, depth + 1)