"""
ui/compact_ui.py — Compact mod UI (mevcut ghost görünümü).
build_compact(app) çağrıldığında frame döner, app.main_frame'e pack edilir.
"""
import customtkinter as ctk
from ui.ui import build_log_box, build_entry, build_media_buttons, build_screenshot_button

CLR_ACCENT  = "#00FFcc"
BG_MAIN     = "#0d0d0d"

def build_compact(app) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(app, fg_color=BG_MAIN, corner_radius=0)

    # Başlık
    ctk.CTkLabel(
        frame, text="GHOST OPERATOR",
        font=("Consolas", 22, "bold"), text_color="#aaaaaa"
    ).pack(pady=(15, 0))

    # Model göstergesi
    app.model_label = ctk.CTkLabel(
        frame, text="Aktif Zeka: Bekliyor...",
        font=("Consolas", 11, "italic"), text_color="#aaaaaa"
    )
    app.model_label.pack(pady=(0, 5))

    # Genişlet butonu
    toggle_btn = ctk.CTkButton(
        frame, text="⤢ Tam Ekrana Geç",
        width=160, height=24,
        font=("Consolas", 11),
        fg_color="transparent", hover_color="#1a1a1a",
        text_color="#666666", border_width=1, border_color="#1e1e1e",
        command=app.expand_mode
    )
    toggle_btn.pack(pady=(0, 8))

    # Ekran yorumla butonu
    app.ss_button = build_screenshot_button(frame)
    app.ss_button.pack(pady=(0, 8))

    # Log kutusu
    app.log_text = build_log_box(frame)
    app.log_text.pack(pady=5, padx=20)
    app.log_text.tag_config("green", foreground=CLR_ACCENT)
    app.log_text.tag_config("red",   foreground="#FF3333")

    # Komut girişi
    app.entry = build_entry(frame)
    app.entry.pack(pady=(5, 10),padx=20)
    app.entry.bind("<Return>", app.command_handler.handle)

    # Medya butonları
    build_media_buttons(frame).pack(pady=(0, 15))

    return frame