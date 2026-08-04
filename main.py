"""
Ghost Operator V2 - Ana Pencere
Compact ↔ Expanded mod geçişi ve oturum yönetimi burada.
"""
import customtkinter as ctk
import threading
import time
import pygame

from ai.konus import GhostSpeech
from core.tool_registry import tool_registry
from ai.librarian_agent import LibrarianAgent
from tools.telegram_tool import TelegramBridge
from handler.voice_handler import VoiceHandler
from handler.command_handler import CommandHandler
from uyandırma.signal_watcher import SignalWatcher
from vison.screenshot import screenshot_al_ve_yorumla

from ui.compact_ui import build_voice
from ui.expanded_ui import build_expanded, append_chat_bubble
from sessions.session_manager import (
    new_session_id, save_session, load_session, list_sessions
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

COMPACT_SIZE  = "380x520"
EXPANDED_SIZE = "1100x680"


class GhostOperatorUI(ctk.CTk):

    def __init__(self):
        super().__init__()

        # ── Oturum durumu ─────────────────────────────────────────────────────
        self.current_session_id = new_session_id()
        self._messages: list = []          # aktif oturumdaki mesajlar
        self._expanded = False             # şu an hangi modda?

        # __ Konuşma durumu  _________________________________
        self.voice_mode = False

        # ── Handler'lar ───────────────────────────────────────────────────────
        self.command_handler = CommandHandler(self)
        self.konus           = GhostSpeech(self)
        self.voice_handler   = VoiceHandler(self)
        self.signal_watcher  = SignalWatcher(self)
        self.librarian       = LibrarianAgent()
        
        from core.scheduler import Scheduler
        self.scheduler       = Scheduler(self)

        # ── Telegram köprüsü ──────────────────────────────────────────────────
        # Sadece burada instance oluşturuyoruz, gerçek polling _startup_sequence'ta
        # başlıyor (UI hazır olmadan self.after() çağırmak anlamsız).
        self.telegram_bridge = TelegramBridge(ui_callback=self._telegram_mesaji_isle)
        tool_registry.bind_handler(
            "telegram_mesaj_gonder",
            lambda mesaj: self.telegram_bridge.mesaj_gonder(mesaj)
        )

        # ── Pencere + UI ──────────────────────────────────────────────────────
        self._setup_window()
        self._load_compact()

        # ── Başlangıç ─────────────────────────────────────────────────────────
        self._play_startup_sound()
        self.after(500, self._startup_sequence)
        self.after(500, self.signal_watcher.start)
        self._create_lock()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Pencere ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title("Ghost Operator v2")
        self.geometry(COMPACT_SIZE)
        self.attributes("-alpha", 1)
        self.attributes("-topmost", True)
        self.bind("<FocusIn>",  lambda e: self.attributes("-alpha", 1))
        self.bind("<FocusOut>", lambda e: self.attributes("-alpha", 0.60))
        self.bind("<F9>", lambda e: screenshot_al_ve_yorumla(self)) 

    # ── Mod geçişleri ─────────────────────────────────────────────────────────

    def _clear_main_frame(self):
        if hasattr(self, "main_frame") and self.main_frame.winfo_exists():
            self.main_frame.destroy()
        # Artık geçersiz widget referanslarını da temizle
        for attr in ("voice_orb", "voice_status_label"):
            if hasattr(self, attr):
                delattr(self, attr)

    def _load_compact(self):
        self._clear_main_frame()
        self.geometry(COMPACT_SIZE)
        self.attributes("-topmost", True)
        
        # Artık compact modda Ses (Orb) Arayüzünü yüklüyoruz
        self.main_frame = build_voice(self) 
        self.main_frame.pack(fill="both", expand=True)
        self._expanded = False
        
        # Mevcut oturum mesajlarını log'a geri yaz
        # (Ses modunda log_text olmadığı için log() içindeki winfo_exists() koruması sayesinde sessizce geçilir)
        for m in self._messages:
            prefix = "[Sen]" if m["role"] == "user" else "[Ghost]"
            self.log(f"{prefix}: {m['text']}")

    def _load_expanded(self):
        self._clear_main_frame()
        self.geometry(EXPANDED_SIZE)
        self.attributes("-topmost", False)
        self.main_frame = build_expanded(self)
        self.main_frame.pack(fill="both", expand=True)
        self._expanded = True
        # Mevcut oturum mesajlarını chat balonlarına geri yaz
        for m in self._messages:
            append_chat_bubble(self, m["role"], m["text"])

    def compact_mode(self):
        self.voice_mode = True
        self._load_compact()                          # pencereyi küçült ve orb arayüzünü yükle
        self.after(500, self.voice_handler.start_listening)

    def expand_mode(self):
        if not self._expanded:
            # 1. Ses modunu ve mikrofon kilidini zorla kapat
            self.voice_mode = False
            self.voice_handler.is_listening = False
            
            # 2. Eğer Ghost o an konuşuyorsa sesini anında kes
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                
            # 3. Geniş arayüzü yükle
            self._load_expanded()

    # ── Oturum işlemleri ─────────────────────────────────────────────────────

    def new_session(self):
        """Aktif oturumu kaydeder, yeni oturum başlatır."""
        self._save_current_session()
        self.current_session_id = new_session_id()
        self._messages = []
        
        if hasattr(self, "command_handler") and hasattr(self.command_handler.controller,"supervisor"):
            self.command_handler.controller.supervisor.load_history(self._messages)
            
        if self._expanded:
            # Sidebar'ı yenile, chat alanını temizle
            from ui.expanded_ui import _populate_sessions
            _populate_sessions(self, self.session_list_frame)
            if hasattr(self, "_chat_bubbles"):
                for widget in self._chat_bubbles:
                    if widget.winfo_exists():
                        widget.destroy()
                self._chat_bubbles.clear()
        else:
            # Compact modda log_text widget'ı yok, sadece konsola bildir
            print("[SİSTEM]: Yeni oturum başlatıldı.")

    def switch_session(self, session_id: str):
        """Sidebar'dan oturum seçilince çağrılır."""
        self._save_current_session()
        self.current_session_id = session_id
        data = load_session(session_id)
        self._messages = data.get("messages", [])
        
        if hasattr(self, "command_handler") and hasattr(self.command_handler.controller,"supervisor"):
            self.command_handler.controller.supervisor.load_history(self._messages)

        if self._expanded:
            from ui.expanded_ui import _populate_sessions
            _populate_sessions(self, self.session_list_frame)
            if hasattr(self, "_chat_bubbles"):
                for widget in self._chat_bubbles:
                    if widget.winfo_exists():
                        widget.destroy()
                self._chat_bubbles.clear()
            for m in self._messages:
                append_chat_bubble(self, m["role"], m["text"])

    def _save_current_session(self):
        if self._messages:
            save_session(self.current_session_id, self._messages)

    # ── Mesaj kayıt API'si (command_handler buraya yazar) ────────────────────

    def record_message(self, role: str, text: str): 
        """
        role: 'user' veya 'ghost'
        Hem _messages listesine hem de aktif UI'ya yazar.
        """
        ts = int(time.time())
        self._messages.append({"role": role, "text": text, "ts": ts})

        # SQLite olay hafızasına kaydet
        if hasattr(self, "command_handler") and hasattr(self.command_handler, "episodic_db"):
            self.command_handler.episodic_db.mesaj_kaydet(self.current_session_id, role, text)

        if self._expanded:
            append_chat_bubble(self, role, text)
        else:
            #prefix = "[Sen]" if role == "user" else "[Ghost]"
            tag = "green" if role == "ghost" else ""
            #self.log(f"{prefix}: {text}", tag)
    
        # (Sohbet analizini artık arka planda Kütüphaneci SQLite üzerinden otomatik yapıyor)
                
    # ── Log (compact modda kullanılır) ────────────────────────────────────────
    def log(self, text: str, tag: str = ""):
        from core.logger import log_yaz

        # Seviye belirle
        seviye = "error" if tag == "red" else ("warning" if tag == "yellow" else "info")

        # Her logu kalıcı dosyaya yaz (Kütüphaneci logları hariç — filter içinde)
        log_yaz(text, seviye)

        # SİSTEM mesajları sadece terminale + dosyaya (UI'ya değil)
        if "SİSTEM" in text:
            print(text)
            return

        # Normal mesajı UI'ya yaz
        def _write():
            if hasattr(self, "log_text") and self.log_text.winfo_exists():
                self.log_text.insert("end", text + "\n", tag)
                self.log_text.see("end")
        self.after(0, _write)

    # ── Arayüzü ayaralar ────────────────────────────────────────    
    def set_model_label(self, text: str, color: str = "#888888"):
        def update_label():
            if hasattr(self, 'model_label') and self.model_label.winfo_exists():
                self.model_label.configure(text=text, text_color=color)
        
        self.after(0, update_label)
    
    # ── Başlangıç ─────────────────────────────────────────────────────────────

    def _play_startup_sound(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load("sistem_baslangic.mp3")
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Giriş sesinde hata: {e}")

    def _startup_sequence(self):
        self.log("[SİSTEM]: Uyanış protokolü başlatıldı...", "green")
        self.set_model_label("Aktif Durum: Sistem Uyanıyor...")
        self.librarian.start()  # Kütüphaneci döngüsünü başlat
        self.scheduler.start()  # Arka plan işçisini (Zamanlayıcı) başlat
        self.telegram_bridge.start_in_background()  # Telegram dinlemeyi başlat
        threading.Thread(target=self.command_handler.run_startup, daemon=True).start()

    def open_settings(self):
        """Ayarlar penceresini aç."""
        from ui.settings_ui import open_settings_window
        open_settings_window(self)

    # ── Telegram köprüsü ──────────────────────────────────────────────────────

    def _telegram_mesaji_isle(self, text: str, user: str, chat_id: int):
        """
        TelegramBridge, ayrı bir thread'den bunu çağırır. Tkinter thread-safe
        olmadığı için UI'ya dokunan her şey self.after(0, ...) ile ana thread'e
        gönderiliyor. Asıl işleme (GhostController çağrısı) ağ isteği yaptığı
        için burada, bu arka plan thread'inde kalıyor — UI'yı dondurmaz.
        """
        self.after(0, lambda: self.record_message("user", f"[Telegram/{user}]: {text}"))

        while getattr(self.command_handler, "su_an_mesgul", False):
            time.sleep(2)
        
        self.command_handler.su_an_mesgul = True
        try:
            cevap, _ = self.command_handler.controller(text)
        except Exception as e:
            cevap = f"[Hata] Telegram mesajı işlenirken bir sorun oluştu: {e}"
        finally:
            self.command_handler.su_an_mesgul = False

        self.after(0, lambda: self.record_message("ghost", cevap))

        try:
            self.telegram_bridge.mesaj_gonder(cevap, chat_id=chat_id)
        except Exception as e:
            print(f"[SİSTEM UYARISI] Telegram cevabı gönderilemedi: {e}")

    # ── Lock & Kapatma ────────────────────────────────────────────────────────

    def _create_lock(self):
        import os
        with open("ghost_mesgul.lock", "w") as f:
            f.write("mesgul")

    def _on_close(self):
        import os
        from tools.whatsapp_tool import whatsapp_kapat
        try:
            whatsapp_kapat()
        except Exception:
            pass
        self._save_current_session()          # ← kapanışta kaydet
        if hasattr(self, "librarian"):
            self.librarian.stop()             # Kütüphaneciyi durdur
        if os.path.exists("ghost_mesgul.lock"):
            os.remove("ghost_mesgul.lock")
        self.destroy()

if __name__ == "__main__":
    app = GhostOperatorUI()
    app.mainloop()