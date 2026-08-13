import customtkinter as ctk
import tkinter as tk
import math

from PIL import Image, ImageDraw, ImageTk

# ── Renk Sabitleri (Daha modern ve koyu bir terminal teması) ───────────
BG_MAIN     = "#050505"  # Tam siyahtan bir tık aydınlık, daha şık
CLR_ACCENT  = "#00FFcc"
CLR_DIM     = "#333333"
CLR_BORDER  = "#1a1a1a"

STATE_COLORS = {
    "idle":      "#1a332a",   # Soluk zümrüt
    "listening": "#00FFcc",   # Ana neon
    "thinking":  "#b266ff",   # İşlem yaparken farklılaşması için neon mor/eflatun
    "speaking":  "#33ffdd",   # Açık cyan
}

STATE_TEXTS = {
    "idle":      "S T A N D B Y",
    "listening": "L I S T E N I N G . . .",
    "thinking":  "P R O C E S S I N G . . .",
    "speaking":  "O P E R A T O R  S P E A K I N G"
}

class VoiceOrb(ctk.CTkFrame):
    """Modern, holografik enerji halkası widget'ı."""

    RADIUS_MIN   = 35
    RADIUS_MAX   = 65
    GLOW_MAX     = 110
    SUPERSAMPLE  = 2      # 2x anti-aliasing için yeterlidir, performansı artırır
    FPS_MS       = 33

    def __init__(self, parent, size=240):
        super().__init__(parent, fg_color="transparent")
        self.size = size
        self.label = tk.Label(self, bg=BG_MAIN, bd=0, highlightthickness=0)
        self.label.pack()

        self.state = "idle"
        self.level = 0.0          
        self._smoothed = 0.0      
        self._t = 0.0
        self._running = True
        self._photo = None        

        self._animate()

    def set_state(self, state: str):
        if state in STATE_COLORS:
            self.state = state

    def set_level(self, level: float):
        self.level = max(0.0, min(1.0, level))

    def destroy(self):
        self._running = False
        super().destroy()

    def _animate(self):
        if not self._running or not self.winfo_exists():
            return

        self._t += 0.06 # Animasyon hızını biraz artırdık, daha akıcı hissettirir

        if self.state == "idle":
            target = 0.1 + 0.05 * math.sin(self._t * 0.8)
        elif self.state == "thinking":
            target = 0.25 + 0.1 * math.sin(self._t * 3.0)
        else:
            target = self.level

        self._smoothed += (target - self._smoothed) * 0.3
        self._render(self._smoothed)
        self.after(self.FPS_MS, self._animate)

    def _render(self, level: float):
        ss = self.SUPERSAMPLE
        S = self.size * ss
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx = cy = S / 2

        base_r = (self.RADIUS_MIN + (self.RADIUS_MAX - self.RADIUS_MIN) * level) * ss
        color = STATE_COLORS.get(self.state, CLR_ACCENT)
        rgb = self._hex_to_rgb(color)

        # 1. En Dış Katman: Yumuşak Glow Yayılımı
        glow_r = (self.GLOW_MAX + (self.RADIUS_MAX - self.RADIUS_MIN) * level * 0.8) * ss
        steps = 25
        for i in range(steps, 0, -1):
            t = i / steps
            r = base_r + (glow_r - base_r) * t
            alpha = int(45 * (1 - t) ** 2)
            if alpha > 0:
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*rgb, alpha))

        # 2. Orta Katman: Dönen Kesik Çizgiler (Holografik Ring Etkisi)
        ring_r = base_r * 1.3
        ring_width = max(1, 2 * ss)
        angle_offset = (self._t * 40) % 360
        
        # Dinleme modunda dış halka daha hızlı ve ters yönde döner
        if self.state in ["listening", "speaking"]:
            angle_offset = -(self._t * 70) % 360

        for angle in range(0, 360, 45):
            draw.arc(
                [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
                start=angle + angle_offset, end=angle + 25 + angle_offset,
                fill=(*rgb, 180), width=ring_width
            )

        # 3. Ana Çekirdek (Core): Katı görünüm yerine iç içe geçmiş ince halkalar
        inner_r = base_r * 0.85
        draw.ellipse([cx - base_r, cy - base_r, cx + base_r, cy + base_r], outline=(*rgb, 200), width=max(1, 3 * ss))
        draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill=(*rgb, 50), outline=(*rgb, 120), width=max(1, 1 * ss))

        # Supersampling küçültme
        img = img.resize((self.size, self.size), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.label.configure(image=self._photo)

    @staticmethod
    def _hex_to_rgb(hexcolor: str):
        h = hexcolor.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def build_voice(app) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(app, fg_color=BG_MAIN, corner_radius=0)

    # Üst Başlık
    header_frame = ctk.CTkFrame(frame, fg_color="transparent")
    header_frame.pack(pady=(40, 0))
    
    ctk.CTkLabel(
        header_frame, text="G. H. O. S. T.",
        font=("Consolas", 26, "bold"), text_color=CLR_ACCENT
    ).pack()
    
    ctk.CTkLabel(
        header_frame, text="// VOICE TERMINAL ACTIVE",
        font=("Consolas", 10), text_color=CLR_DIM
    ).pack(pady=(2, 0))

    # Merkez Animasyon
    orb_holder = ctk.CTkFrame(frame, fg_color="transparent")
    orb_holder.pack(expand=True, fill="both")

    app.voice_orb = VoiceOrb(orb_holder, size=280)
    app.voice_orb.place(relx=0.5, rely=0.45, anchor="center")

    # Durum Metni (Eskiden olmayan, arayüze kalite katan kısım)
    app.voice_status_label = ctk.CTkLabel(
        orb_holder, text=STATE_TEXTS["idle"],
        font=("Consolas", 12, "bold"), text_color="#aaaaaa"
    )
    app.voice_status_label.place(relx=0.5, rely=0.85, anchor="center")

    # Alt Buton
    ctk.CTkButton(
        frame, text="[ TAM EKRAN MODU ]",
        width=200, height=36,
        font=("Consolas", 12, "bold"),
        fg_color="transparent", hover_color="#0a1a15",
        text_color=CLR_ACCENT, border_width=1, border_color="#004d3d",
        corner_radius=4,
        command=app.expand_mode
    ).pack(pady=(0, 30))

    return frame

def set_voice_state(app, state: str, status_text: str = None):
    if hasattr(app, "voice_orb") and app.voice_orb.winfo_exists():
        app.voice_orb.set_state(state)

    if hasattr(app, "voice_status_label") and app.voice_status_label.winfo_exists():
        if state in STATE_TEXTS:
            color = STATE_COLORS.get(state, "#aaaaaa")
            app.voice_status_label.configure(text=STATE_TEXTS[state], text_color=color)


def set_voice_level(app, level: float):
    if hasattr(app, "voice_orb") and app.voice_orb.winfo_exists():
        app.voice_orb.set_level(level)