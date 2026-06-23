"""
Ghost Operator V2 - Ana Pencere
Compact ↔ Expanded mod geçişi ve oturum yönetimi burada.
"""
import customtkinter as ctk
import threading
import time
import pygame

from ai.memory_agent import MemoryAgent
from handler.voice_handler import VoiceHandler
from handler.command_handler import CommandHandler
from ai.konus import GhostSpeech
from hafıza.rag_hafıza import Bellek
from kontrol.spotify import SpotifyManager
from uyandırma.signal_watcher import SignalWatcher

from ui.compact_ui import build_compact
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
        self.memory_agent    = MemoryAgent()

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
        self.attributes("-alpha", 0.98)
        self.attributes("-topmost", True)
        self.bind("<FocusIn>",  lambda e: self.attributes("-alpha", 0.98))
        self.bind("<FocusOut>", lambda e: self.attributes("-alpha", 0.60))

    # ── Mod geçişleri ─────────────────────────────────────────────────────────

    def _clear_main_frame(self):
        if hasattr(self, "main_frame") and self.main_frame.winfo_exists():
            self.main_frame.destroy()

    def _load_compact(self):
        self._clear_main_frame()
        self.geometry(COMPACT_SIZE)
        self.attributes("-topmost", True)
        self.main_frame = build_compact(self)
        self.main_frame.pack(fill="both", expand=True)
        self._expanded = False
        # Mevcut oturum mesajlarını log'a geri yaz
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
        if self._expanded:
            self._load_compact()

    def expand_mode(self):
        if not self._expanded:
            self._load_expanded()

    # ── Oturum işlemleri ─────────────────────────────────────────────────────

    def new_session(self):
        """Aktif oturumu kaydeder, yeni oturum başlatır."""
        self._save_current_session()
        self.current_session_id = new_session_id()
        self._messages = []
        if self._expanded:
            # Sidebar'ı yenile, chat alanını temizle
            from ui.expanded_ui import _populate_sessions
            _populate_sessions(self, self.session_list_frame)
            for widget in self.chat_scroll.winfo_children():
                widget.destroy()
        else:
            self.log_text.delete("1.0", "end")
            self.log("Yeni oturum başlatıldı.\n", "green")

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
            for widget in self.chat_scroll.winfo_children():
                widget.destroy()
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

        if self._expanded:
            append_chat_bubble(self, role, text)
        else:
            #prefix = "[Sen]" if role == "user" else "[Ghost]"
            tag = "green" if role == "ghost" else ""
            #self.log(f"{prefix}: {text}", tag)
    
        # Ghost cevabından sonra çift mesajı birlikte gönder (daha iyi context)
        if role == "ghost":
            # Son user mesajını bul
            user_msg = next(
                (m["text"] for m in reversed(self._messages[:-1]) if m["role"] == "user"),
                ""
            )
            if user_msg:
                combined = f"Kullanıcı: {user_msg}\nGhost: {text}"
                self.memory_agent.asenkron_kaydet(combined)
                
    # ── Log (compact modda kullanılır) ────────────────────────────────────────
    def log(self, text: str, tag: str = ""):
        # EĞER MESAJ BİR SİSTEM BİLGİSİYSE, SADECE TERMİNALE BAS VE ÇIK
        if "SİSTEM" in text:
            print(text)
            return

        # SİSTEM DEĞİLSE (Yani normal sohbetse) EKRANA YAZ
        def _write():
            if hasattr(self, "log_text") and self.log_text.winfo_exists():
                self.log_text.insert("end", text + "\n", tag)
                self.log_text.see("end")
        self.after(0, _write)

    def log_collapsible_plan(self, adimlar: list):
        # PLANLARI EKRANDA GİZLE/GÖSTER YAPMAK YERİNE DOĞRUDAN TERMİNALE BASIYORUZ
        print("\n" + "="*40)
        print("🛠️ OPERASYON PLANI:")
        for i, adim in enumerate(adimlar, 1):
            prefix = "   └─" if i == len(adimlar) else "   ├─"
            print(f"{prefix} Adım {i}: {adim}")
        print("="*40 + "\n")
        
    def set_model_label(self, text: str, color: str = "#888888"):
        self.after(0, lambda: self.model_label.configure(text=text, text_color=color))

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
        threading.Thread(target=self.command_handler.run_startup, daemon=True).start()

    # ── Lock & Kapatma ────────────────────────────────────────────────────────

    def _create_lock(self):
        import os
        with open("ghost_mesgul.lock", "w") as f:
            f.write("mesgul")

    def _on_close(self):
        import os
        self._save_current_session()          # ← kapanışta kaydet
        if os.path.exists("ghost_mesgul.lock"):
            os.remove("ghost_mesgul.lock")
        self.destroy()


if __name__ == "__main__":
    app = GhostOperatorUI()
    app.mainloop()