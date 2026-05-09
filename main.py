"""
Ghost Operator V2 - Ana Pencere
Sadece UI mantığı burada. İş mantığı handlers/ altında.
"""
import customtkinter as ctk
import threading
import pygame

from handler.voice_handler import VoiceHandler
from ui.ui import build_log_box, build_entry, build_media_buttons, build_screenshot_button
from handler.command_handler import CommandHandler
from ai.konus import GhostSpeech
from hafıza.rag_hafıza import Bellek
from kontrol.spotify import SpotifyManager
from uyandırma.signal_watcher import SignalWatcher

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class GhostOperatorUI(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.command_handler = CommandHandler(self)
        self.konus = GhostSpeech(self)
        self.voice_handler = VoiceHandler(self)            
        self.signal_watcher  = SignalWatcher(self)

        self._build_window()
        self._build_ui()

        self._play_startup_sound()
        self.after(500, self._startup_sequence)
        self.after(500, self.signal_watcher.start)

        self._create_lock()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Pencere kurulumu ──────────────────────────────────────────────────────
    def _build_window(self):
        self.title("Ghost Operator v2")
        self.geometry("380x500")
        self.attributes("-alpha", 0.98)
        self.attributes("-topmost", True)
        self.bind("<FocusIn>",  lambda e: self.attributes("-alpha", 0.98))
        self.bind("<FocusOut>", lambda e: self.attributes("-alpha", 0.60))

    def _build_ui(self):
        # Başlık
        ctk.CTkLabel(
            self, text="GHOST OPERATOR",
            font=("Consolas", 22, "bold"), text_color="#3F3F3F"
        ).pack(pady=(10, 0))

        # Aktif model göstergesi
        self.model_label = ctk.CTkLabel(
            self, text="Aktif Zeka: Bekliyor...",
            font=("Consolas", 11, "italic"), text_color="#888888"
        )
        self.model_label.pack(pady=(0, 5))

        # Ekran yorumla butonu
        self.ss_button = build_screenshot_button(self)
        self.ss_button.pack(pady=(0, 5))

        # Log ekranı
        self.log_text = build_log_box(self)
        self.log_text.pack(pady=10)
        self.log_text.tag_config("green", foreground="#00FFcc")
        self.log_text.tag_config("red",   foreground="#FF3333")
        self.log("Sistem Hazır. Patrondan komut bekliyor...\n")

        # Komut girişi
        self.entry = build_entry(self)
        self.entry.pack(pady=(5, 20))
        self.entry.bind("<Return>", self.command_handler.handle)

        # Medya butonları
        build_media_buttons(self).pack(pady=(0, 10))

    # ── Yardımcı log metodu ───────────────────────────────────────────────────

    def log(self, text: str, tag: str = ""):
        """Thread-safe log yazma."""
        def _write():
            self.log_text.insert("end", text + "\n", tag)
            self.log_text.see("end")
        self.after(0, _write)
    
    def log_collapsible_plan(self, adimlar: list):
        """Çok adımlı görevleri gizlenebilir bir buton ile ekrana basar."""
        def _build():
            import time
            # Her plana benzersiz bir ID veriyoruz ki butonlar karışmasın
            tag_name = f"plan_{int(time.time() * 1000)}"
            
            # Bu tag'e sahip metinleri başlangıçta gizle (elide=True) ve rengini loş yap
            self.log_text.tag_config(tag_name, elide=True, foreground="#888888")
            
            # Durum tutucu (gizli mi açık mı?)
            state = {"hidden": True}
            
            def toggle():
                state["hidden"] = not state["hidden"]
                self.log_text.tag_config(tag_name, elide=state["hidden"])
                btn.configure(text="▼ Düşünme sürecini gizle" if not state["hidden"] else "▶ Düşünme sürecini göster")
                self.log_text.see("end")

            # Metin kutusunun içine gömülecek şık buton
            btn = ctk.CTkButton(
                self.log_text, 
                text="▶ Düşünme sürecini göster", 
                command=toggle,
                width=180, height=20,
                fg_color="transparent", hover_color="#2a2a2a", text_color="#aaaaaa",
                font=("Consolas", 11, "italic"),
                anchor="w" # Sola hizalı
            )
            
            # Butonu ve gizli adımları ekrana yaz
            self.log_text.insert("end", "\n")
            self.log_text.window_create("end", window=btn)
            self.log_text.insert("end", "\n")
            
            for i, adim in enumerate(adimlar, 1):
                prefix = "   └─" if i == len(adimlar) else "   ├─"
                self.log_text.insert("end", f"{prefix} Adım {i}: {adim}\n", tag_name)
            
            self.log_text.see("end")
            
        self.after(0, _build)
    
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
        self.set_model_label("Aktif Zeka: Sistem Uyanıyor...")
        threading.Thread(target=self.command_handler.run_startup, daemon=True).start()

    # ── Lock dosyası ──────────────────────────────────────────────────────────

    def _create_lock(self):
        import os
        with open("ghost_mesgul.lock", "w") as f:
            f.write("mesgul")

    def _on_close(self):
        import os
        if os.path.exists("ghost_mesgul.lock"):
            os.remove("ghost_mesgul.lock")
        self.destroy()


if __name__ == "__main__":
    app = GhostOperatorUI()
    app.mainloop()