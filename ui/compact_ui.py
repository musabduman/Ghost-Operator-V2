"""
ui/compact_ui.py — Compact mod UI (mevcut ghost görünümü).
build_compact(app) çağrıldığında frame döner, app.main_frame'e pack edilir.
"""
import customtkinter as ctk
from ui.ui import build_log_box, build_entry, build_media_buttons, build_screenshot_button


def build_compact(app) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(app, fg_color="transparent")

    # Başlık
    ctk.CTkLabel(
        frame, text="GHOST OPERATOR",
        font=("Consolas", 22, "bold"), text_color="#3F3F3F"
    ).pack(pady=(10, 0))

    # Model göstergesi
    app.model_label = ctk.CTkLabel(
        frame, text="Aktif Zeka: Bekliyor...",
        font=("Consolas", 11, "italic"), text_color="#888888"
    )
    app.model_label.pack(pady=(0, 3))

    # Genişlet butonu
    toggle_btn = ctk.CTkButton(
        frame, text="⤢ Tam Ekrana Geç",
        width=160, height=22,
        font=("Consolas", 10),
        fg_color="transparent", hover_color="#1a1a1a",
        text_color="#444444", border_width=1, border_color="#2a2a2a",
        command=app.expand_mode
    )
    toggle_btn.pack(pady=(0, 4))

    # Ekran yorumla butonu
    app.ss_button = build_screenshot_button(app)
    app.ss_button.pack(pady=(0, 5))

    # Log kutusu
    app.log_text = build_log_box(app)
    app.log_text.pack(pady=10)
    app.log_text.tag_config("green", foreground="#00FFcc")
    app.log_text.tag_config("red",   foreground="#FF3333")

    # Komut girişi
    app.entry = build_entry(app)
    app.entry.pack(pady=(5, 10))
    app.entry.bind("<Return>", app.command_handler.handle)

    # Medya butonları
    build_media_buttons(app).pack(pady=(0, 10))

    return frame