"""
handlers/command_handler.py
Ghost'un "beyin merkezi" — komutları alır, yorumlar, eylemleri tetikler.
UI'a dokunmaz; sadece app.log() ve app.set_model_label() kullanır.
"""
import os
import re
import traceback
import threading

from hafıza.rag_hafıza import Bellek
from ai.llm import GhostController, ChatLLM
from patterns import PATTERNS
from kontrol.spotify import SpotifyManager
from kontrol.güvenlik import guvenlik_kontrolu
from fs import (
    akilli_yol_cozucu, alternatif_yol_bul, derin_arama, kodu_calistir
)
from kontrol.kontrol import google_arama
 
KAPANIŞ_KELİMELERİ = ["uyku modu", "teşekkürler ghost", "kapan", "çıkış yap", "görüşürüz"]
 
MAX_DEPTH = 2
 
 
class CommandHandler:
 
    def __init__(self, app):
        self.app = app
        self.son_komut_sesli = False
        self.bellek = Bellek()
        self.controller = GhostController()
        self.spotify = SpotifyManager()
    # ── Dışarıdan çağrılan giriş noktaları ───────────────────────────────────
 
    def handle(self, event=None):
        """Entry'deki komutu alıp işleme döngüsünü başlatır."""
        self.son_komut_sesli = (event is None)
        user_input = self.app.entry.get().strip()
        if not user_input:
            return
 
        if any(k in user_input.lower() for k in KAPANIŞ_KELİMELERİ):
            self.app.log(f"\nSen: {user_input}")
            self.app.log("Ghost: Anlaşıldı Patron, nöbetçi moduna geçiyorum.", "green")
            self.app.after(2000, self.app.destroy)
            return
 
        self.app.log(f"\nSen: {user_input}")
        self.app.entry.delete(0, "end")
        self.app.log("Ghost düşünüyor...")
        self.app.set_model_label("Aktif Zeka: Yönlendiriliyor...")
 
        threading.Thread(
            target=lambda: self._process(user_input, depth=0),
            daemon=True
        ).start()
 
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
            self.app.log(f"Ghost: {cevap}")
            self.app.konus.speak(cevap)
            self.app.after(0, self.app.voice_handler.start_listening)
        except Exception as e:
            self.app.log(f"SİSTEM HATA (Uyanış): {e}", "red")
 
    # ── Ana işleme döngüsü ────────────────────────────────────────────────────
 
    def _process(self, user_input: str, depth: int = 0):
        if depth > MAX_DEPTH:
            self.app.log("SİSTEM: Maksimum döngü derinliğine ulaşıldı.", "red")
            return
        action_taken = False
 
        try:
            enriched = self._enrich_with_memory(user_input) 
            response, model = self.controller(enriched)
            self._update_model_label(model)
 
            display = self._clean_response_for_display(response)
            self.app.log(f"Ghost: {display}")
 
            if self.son_komut_sesli:
                self.app.konus.speak(
                    display,
                    on_complete=lambda: self.app.after(0, self.app.voice_handler.start_listening)
                )
 
            if not guvenlik_kontrolu(user_input):
                self.app.log("SİSTEM: Tehlikeli komut algılandı! İşlem reddedildi.", "red")
                return
 
            # Her eylemi kendi metoduna delege et
            action_taken |= self._handle_open_folder(response)
            action_taken |= self._handle_open_app(response)
            action_taken |= self._handle_play_song(response)
            action_taken |= self._handle_play_playlist(response)
            action_taken |= self._handle_search(response)
            action_taken |= self._handle_save_note(response)
            action_taken |= self._handle_make_folder(response)
            action_taken |= self._handle_inspect_folder(response, user_input, depth)
            action_taken |= self._handle_write_file(response)
            action_taken |= self._handle_run_code(response, depth)
            if not action_taken:
                self._handle_read_file(response, user_input, depth)
 
        except Exception:
            self.app.log(f"SİSTEM HATA:\n{traceback.format_exc()}", "red")
 
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
        return result
 
    # ── Model label güncellemesi ──────────────────────────────────────────────
 
    def _update_model_label(self, model: str):
        color = "#00FFcc" if "oss" in model.lower() else "#FF9500"
        self.app.set_model_label(f"Aktif Zeka: {model}", color)
 
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
        SPECIAL = {
            "cursor":   r"C:\Users\dum4n\AppData\Local\Programs\cursor\Cursor.exe",
            "whatsapp": "whatsapp://",
            "discord":  r"C:\Users\dum4n\AppData\Local\Discord\Update.exe --processStart Discord.exe",
        }
        try:
            os.startfile(SPECIAL[name]) if name in SPECIAL else os.system(f"start {name}")
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
                    import time; time.sleep(2)
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
 
    def _handle_search(self, response: str) -> bool:
        m = PATTERNS["arama"].search(response)
        if not m:
            return False
        query = m.group(1).strip()
        google_arama(query)
        self.app.log(f"SİSTEM: Google'da '{query}' aranıyor...", "green")
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
            threading.Thread(target=lambda: self._process(prompt, depth + 1), daemon=True).start()
        else:
            self.app.log(f"SİSTEM HATA: Klasör bulunamadı → {path}", "red")
        return True
 
    def _handle_write_file(self, response: str) -> bool:
        m = PATTERNS["dosya_yaz"].search(response)
        if not m:
            return False
        raw_path = m.group(1).strip()
        path     = os.path.normpath(raw_path)
        code     = m.group(2).strip()
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
            threading.Thread(target=lambda: self._process(prompt, depth + 1), daemon=True).start()
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
                threading.Thread(target=lambda: self._process(prompt, depth + 1), daemon=True).start()
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
            threading.Thread(target=lambda: self._process(prompt, depth + 1), daemon=True).start()