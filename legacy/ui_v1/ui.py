"""
ui/widgets.py — Tekrar kullanılabilir UI bileşenleri.
Tüm widget'lar burada üretilir; main_window sadece pack() çağırır.
"""
import customtkinter as ctk
 
def build_screenshot_button(parent) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        text="📸 Ekranı Yorumla (F9)",
        width=360, height=35,
        font=("Consolas", 13),
        fg_color="#2a2a2a",
        hover_color="#3a3a3a",
    )