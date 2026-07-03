"""
ui/voice_ui.py — Sesli komut modu (varsayılan açılış arayüzü).
Ortada nefes alan / sesle büyüyüp küçülen bir "orb" (yuvarlak) bulunur.
build_voice(app) çağrıldığında frame döner, app.main_frame'e pack edilir.

Dışarıdan (STT / agentic loop / TTS pipeline) kontrol için:
    from ui.voice_ui import set_voice_state, set_voice_level

    set_voice_state(app, "listening", "Dinliyorum...")
    set_voice_level(app, rms_normalized)   # 0.0-1.0, mikrofon frame'i geldikçe çağır
    set_voice_state(app, "thinking", "Düşünüyorum...")
    set_voice_state(app, "speaking", "Konuşuyorum...")
    set_voice_state(app, "idle", "Bekleniyor...")

NOT: vosk.py / command_handler.py içeriğini görmediğim için bu entegrasyon
noktalarını sana bıraktım — aşağıda "Entegrasyon" notunda nereye ne
ekleyeceğin yazıyor.
"""
import customtkinter as ctk
import tkinter as tk
import math

from ui.ui import build_screenshot_button
from vison.screenshot import screenshot_al_ve_yorumla

# ── Renk sabitleri (diğer modlarla aynı Ghost teması) ────────────────────────
BG_MAIN     = "#0d0d0d"
CLR_ACCENT  = "#00FFcc"
CLR_DIM     = "#666666"
CLR_BORDER  = "#1e3028"

STATE_COLORS = {
    "idle":      "#12241d",   # soluk, kısık yeşil-siyah — nefes alma tonu
    "listening": "#00FFcc",   # tam accent — mikrofon açık
    "thinking":  "#00c9a3",   # biraz kısık + dönen halka — işleniyor
    "speaking":  "#33ffdd",   # en canlı ton — TTS çıktısı
}


class VoiceOrb(ctk.CTkFrame):
    """Ortadaki nefes alan / ses seviyesiyle büyüyüp küçülen orb widget'ı."""

    RADIUS_MIN = 28
    RADIUS_MAX = 55
    RINGS = 3  # dış glow katman sayısı

    def __init__(self, parent, size=160):
        super().__init__(parent, fg_color="transparent")
        self.size = size
        self.canvas = tk.Canvas(
            self, width=size, height=size,
            bg=BG_MAIN, highlightthickness=0
        )
        self.canvas.pack()

        self.state = "idle"
        self.level = 0.0          # dışarıdan set edilen hedef ses seviyesi (0-1)
        self._smoothed = 0.0      # yumuşatılmış seviye (ani sıçramaları önler)
        self._t = 0.0
        self._running = True

        self._animate()

    # ── Dışa açık API ─────────────────────────────────────────────────
    def set_state(self, state: str):
        if state in STATE_COLORS:
            self.state = state

    def set_level(self, level: float):
        """0.0-1.0 arası mikrofon genlik/RMS seviyesi."""
        self.level = max(0.0, min(1.0, level))

    def destroy(self):
        self._running = False
        super().destroy()

    # ── Animasyon döngüsü (~60fps) ───────────────────────────────────
    def _animate(self):
        if not self._running or not self.winfo_exists():
            return

        self._t += 0.05

        if self.state == "idle":
            # yavaş, sinüs tabanlı "nefes alma"
            target = 0.15 + 0.10 * (0.5 + 0.5 * math.sin(self._t))
        elif self.state == "thinking":
            target = 0.35 + 0.15 * (0.5 + 0.5 * math.sin(self._t * 2.2))
        else:
            # listening / speaking → gerçek ses seviyesi
            target = self.level

        self._smoothed += (target - self._smoothed) * 0.25
        self._draw(self._smoothed)
        self.after(16, self._animate)

    def _draw(self, level: float):
        c = self.canvas
        c.delete("all")
        cx = cy = self.size / 2
        base_r = self.RADIUS_MIN + (self.RADIUS_MAX - self.RADIUS_MIN) * level
        color = STATE_COLORS.get(self.state, CLR_ACCENT)

        # Dış glow halkaları — canvas'ta alpha yok, arka planla renk karıştırıp simüle ediyoruz
        for i in range(self.RINGS, 0, -1):
            ring_r = base_r + i * 8
            blend = self._blend(color, BG_MAIN, i / (self.RINGS + 1))
            c.create_oval(
                cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r,
                outline="", fill=blend
            )

        # Thinking modunda dönen ince halka
        if self.state == "thinking":
            angle = (self._t * 60) % 360
            c.create_arc(
                cx - base_r - 10, cy - base_r - 10,
                cx + base_r + 10, cy + base_r + 10,
                start=angle, extent=70,
                outline=CLR_ACCENT, width=2, style="arc"
            )

        # Ana çekirdek
        c.create_oval(
            cx - base_r, cy - base_r, cx + base_r, cy + base_r,
            outline="", fill=color
        )

        # İç parlaklık noktası — derinlik hissi
        core_r = base_r * 0.4
        c.create_oval(
            cx - core_r, cy - core_r - base_r * 0.15,
            cx + core_r, cy + core_r - base_r * 0.15,
            outline="", fill=self._blend(color, "#ffffff", 0.35)
        )

    @staticmethod
    def _blend(hex1: str, hex2: str, t: float) -> str:
        r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
        r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"


def build_voice(app) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(app, fg_color=BG_MAIN, corner_radius=0)

    ctk.CTkLabel(
        frame, text="GHOST OPERATOR",
        font=("Consolas", 20, "bold"), text_color="#aaaaaa"
    ).pack(pady=(20, 0))

    app.model_label = ctk.CTkLabel(
        frame, text="Aktif Zeka: Bekliyor...",
        font=("Consolas", 11, "italic"), text_color="#aaaaaa"
    )
    app.model_label.pack(pady=(0, 10))

    # Diğer modlarla tutarlı: genişlet butonu
    ctk.CTkButton(
        frame, text="⤢ Tam Ekrana Geç",
        width=160, height=24,
        font=("Consolas", 11),
        fg_color="transparent", hover_color="#1a1a1a",
        text_color="#666666", border_width=1, border_color="#a3a3a3",
        command=app.expand_mode
    ).pack(pady=(0, 10))

    # ── Orb ──
    app.voice_orb = VoiceOrb(frame, size=160)
    app.voice_orb.pack(pady=10)

    # Durum yazısı (Dinliyorum / Düşünüyorum / Konuşuyorum)
    app.voice_status_label = ctk.CTkLabel(
        frame, text="Bekleniyor...",
        font=("Consolas", 13), text_color=CLR_ACCENT
    )
    app.voice_status_label.pack(pady=(10, 15))

    # Metin girişi yedek olarak duruyor (sesli komut çalışmazsa / gürültülü ortam)
    app.entry = ctk.CTkEntry(
        frame, placeholder_text="...ya da yaz",
        width=300, height=36,
        font=("Consolas", 13),
        fg_color="#111111", border_color="#1e1e1e", border_width=1,
    )
    app.entry.pack(pady=(0, 10))
    app.entry.bind("<Return>", app.command_handler.handle)

    # Ekranı yorumla butonu
    app.ss_button = build_screenshot_button(frame)
    app.ss_button.configure(width=280, height=32, font=("Consolas", 12),
                             command=lambda: screenshot_al_ve_yorumla(app))
    app.ss_button.pack(pady=(0, 15))

    return frame


# ── command_handler / vosk / TTS'den çağrılacak yardımcı fonksiyonlar ────────

def set_voice_state(app, state: str, status_text: str = None):
    if hasattr(app, "voice_orb"):
        app.voice_orb.set_state(state)
    if status_text and hasattr(app, "voice_status_label"):
        app.voice_status_label.configure(text=status_text)


def set_voice_level(app, level: float):
    if hasattr(app, "voice_orb"):
        app.voice_orb.set_level(level)