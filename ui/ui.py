"""
ui/widgets.py — Tekrar kullanılabilir UI bileşenleri.
Tüm widget'lar burada üretilir; main_window sadece pack() çağırır.
"""
import customtkinter as ctk
from kontrol.kontrol import muzik_kontrol
 
 
def build_log_box(parent) -> ctk.CTkTextbox:
    return ctk.CTkTextbox(
        parent,
        width=340, height=250,
        font=("Consolas", 13),
        fg_color="#1e1e1e",
        border_color="#333333",
        border_width=1,
    )
 
 
def build_entry(parent) -> ctk.CTkEntry:
    return ctk.CTkEntry(
        parent,
        placeholder_text="Patrondan komut bekliyor...",
        width=340, height=40,
        font=("Consolas", 14),
    )
 
 
def build_screenshot_button(parent) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        text="📸 Ekranı Yorumla (F9)",
        width=360, height=35,
        font=("Consolas", 13),
        fg_color="#2a2a2a",
        hover_color="#3a3a3a",
    )
 
 
def build_media_buttons(parent) -> ctk.CTkFrame:
    """⏮ ⏯ ⏭ butonlarını bir frame içinde döndürür."""
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    BTN = dict(width=40, height=30, fg_color="#333333", hover_color="#444444")
 
    ctk.CTkButton(frame, text="⏮", command=lambda: muzik_kontrol("önceki"), **BTN).pack(side="left", padx=5)
    ctk.CTkButton(frame, text="⏯", command=lambda: muzik_kontrol("durdur"),  **BTN).pack(side="left", padx=5)
    ctk.CTkButton(frame, text="⏭", command=lambda: muzik_kontrol("sonraki"), **BTN).pack(side="left", padx=5)
 
    return frame