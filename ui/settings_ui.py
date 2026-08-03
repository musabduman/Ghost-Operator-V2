"""
ui/settings_ui.py — Ghost Ayarlar Paneli.
apı_key.env dosyasından değerleri okur, değiştirir ve kaydeder.
"""
import os
import customtkinter as ctk

ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "apı_key.env"
)

def _read_env() -> dict:
    """apı_key.env dosyasını key=value sözlüğü olarak döndürür."""
    values = {}
    if not os.path.exists(ENV_PATH):
        return values
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values

def _write_env(values: dict):
    """Sözlüğü apı_key.env formatında yazar."""
    lines = []
    for k, v in values.items():
        lines.append(f'{k} = "{v}"\n')
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

def open_settings_window(app):
    """Ayarlar penceresini aç."""
    env = _read_env()

    win = ctk.CTkToplevel(app)
    win.title("Ghost Ayarları")
    win.geometry("640x520")
    win.attributes("-topmost", True)
    win.grab_set()
    win.configure(fg_color="#0a0a0a")

    # ── Başlık ─────────────────────────────────────────────────────────────────
    header = ctk.CTkFrame(win, fg_color="#111111", height=48, corner_radius=0)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(
        header, text="⚙  Ghost Ayarları",
        font=("Consolas", 14, "bold"), text_color="#00FFcc"
    ).pack(side="left", padx=16, pady=12)

    # ── Sekmeler ───────────────────────────────────────────────────────────────
    tabs = ctk.CTkTabview(win, fg_color="#0d0d0d", segmented_button_fg_color="#111111",
                          segmented_button_selected_color="#0f1a17",
                          segmented_button_selected_hover_color="#1a3028",
                          segmented_button_unselected_color="#111111",
                          text_color="#aaaaaa", text_color_disabled="#333333")
    tabs.pack(fill="both", expand=True, padx=0, pady=0)

    tabs.add("🤖 Model")
    tabs.add("🔑 API Anahtarları")
    tabs.add("🔊 Ses")
    tabs.add("📱 Telegram")

    entries = {}

    def _make_field(parent, label: str, key: str, is_secret: bool = False, row: int = 0):
        """Etiket + giriş alanı satırı oluşturur."""
        ctk.CTkLabel(
            parent, text=label,
            font=("Consolas", 11), text_color="#777777", anchor="w"
        ).grid(row=row, column=0, padx=16, pady=(10, 0), sticky="w")

        show = "*" if is_secret else ""
        entry = ctk.CTkEntry(
            parent,
            font=("Consolas", 12), fg_color="#111111",
            border_color="#222222", text_color="#eeeeee",
            height=36, show=show
        )
        entry.insert(0, env.get(key, ""))
        entry.grid(row=row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")

        if is_secret:
            visible = [False]
            def _toggle(e=entry, v=visible):
                v[0] = not v[0]
                e.configure(show="" if v[0] else "*")

            ctk.CTkButton(
                parent, text="👁", width=36, height=36,
                fg_color="transparent", hover_color="#1a1a1a",
                text_color="#555555", command=_toggle
            ).grid(row=row + 1, column=1, padx=(0, 12), pady=(2, 0))

        entries[key] = entry
        return entry

    # ── Model sekmesi ──────────────────────────────────────────────────────────
    model_tab = tabs.tab("🤖 Model")
    model_tab.grid_columnconfigure(0, weight=1)
    model_tab.grid_columnconfigure(1, weight=0)

    ctk.CTkLabel(
        model_tab,
        text="Supervisor (Yönetici) — Ollama üzerinde çalışır",
        font=("Consolas", 10), text_color="#444444", anchor="w"
    ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 0), sticky="w")

    _make_field(model_tab, "Supervisor Model Adı", "SUPERVISOR_MODEL", row=1)

    ctk.CTkLabel(
        model_tab,
        text="Worker (Kodlayıcı) — NVIDIA NIM üzerinde çalışır",
        font=("Consolas", 10), text_color="#444444", anchor="w"
    ).grid(row=3, column=0, columnspan=2, padx=16, pady=(16, 0), sticky="w")

    _make_field(model_tab, "Worker Model Adı", "WORKER_MODEL", row=4)
    _make_field(model_tab, "Ollama API URL", "OLLAMA_URL", row=6)

    # ── API Anahtarları sekmesi ────────────────────────────────────────────────
    api_tab = tabs.tab("🔑 API Anahtarları")
    api_tab.grid_columnconfigure(0, weight=1)
    api_tab.grid_columnconfigure(1, weight=0)

    _make_field(api_tab, "NVIDIA API Key", "NVIDIA_API_KEY", is_secret=True, row=0)
    _make_field(api_tab, "Google API Key", "GOOGLE_API_KEY", is_secret=True, row=2)
    _make_field(api_tab, "Google Search Engine ID", "SEARCH_ENGINE_ID", row=4)

    # ── Ses sekmesi ────────────────────────────────────────────────────────────
    ses_tab = tabs.tab("🔊 Ses")
    ses_tab.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        ses_tab, text="TTS Hızı (0.5 = yavaş, 1.0 = normal, 2.0 = hızlı)",
        font=("Consolas", 11), text_color="#777777", anchor="w"
    ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")

    speed_val = float(env.get("TTS_SPEED", "1.0"))
    speed_label = ctk.CTkLabel(ses_tab, text=f"{speed_val:.1f}x",
                               font=("Consolas", 12), text_color="#00FFcc")
    speed_label.grid(row=1, column=1, padx=(0, 16))

    speed_slider = ctk.CTkSlider(
        ses_tab, from_=0.5, to=2.0, number_of_steps=15,
        button_color="#00FFcc", button_hover_color="#00ddaa",
        progress_color="#0f3028"
    )
    speed_slider.set(speed_val)
    speed_slider.grid(row=1, column=0, padx=16, pady=4, sticky="ew")

    def _on_speed(val):
        speed_label.configure(text=f"{val:.1f}x")

    speed_slider.configure(command=_on_speed)
    entries["TTS_SPEED"] = speed_slider

    ses_tab.grid_columnconfigure(0, weight=1)
    ses_tab.grid_columnconfigure(1, weight=0)

    # ── Telegram sekmesi ───────────────────────────────────────────────────────
    tg_tab = tabs.tab("📱 Telegram")
    tg_tab.grid_columnconfigure(0, weight=1)
    tg_tab.grid_columnconfigure(1, weight=0)

    _make_field(tg_tab, "Telegram Bot Token", "TELEGRAM_BOT_TOKEN", is_secret=True, row=0)

    ctk.CTkLabel(
        tg_tab,
        text="İzin Verilen IP (sadece bu IP'den gelen mesajlar işlenir, boşsa herkese açık)",
        font=("Consolas", 10), text_color="#555555", anchor="w", wraplength=560
    ).grid(row=2, column=0, columnspan=2, padx=16, pady=(16, 0), sticky="w")

    _make_field(tg_tab, "İzin Verilen Kullanıcı IP'si", "TELEGRAM_ALLOWED_IP", row=3)

    # ── Kaydet / Kapat ─────────────────────────────────────────────────────────
    btn_bar = ctk.CTkFrame(win, fg_color="#111111", height=52, corner_radius=0)
    btn_bar.pack(fill="x", side="bottom")
    btn_bar.pack_propagate(False)

    status_label = ctk.CTkLabel(
        btn_bar, text="",
        font=("Consolas", 11), text_color="#4ec94e"
    )
    status_label.pack(side="left", padx=16)

    def _save():
        new_env = dict(env)  # mevcut değerleri koru
        for key, widget in entries.items():
            if isinstance(widget, ctk.CTkSlider):
                new_env[key] = f"{widget.get():.1f}"
            else:
                val = widget.get().strip()
                if val:  # Boş bırakılmışsa eski değer korunsun
                    new_env[key] = val
        _write_env(new_env)
        status_label.configure(text="✅ Kaydedildi! Bazı değişiklikler yeniden başlatma gerektirir.")
        win.after(3000, lambda: status_label.configure(text=""))

    ctk.CTkButton(
        btn_bar, text="💾  Kaydet", width=120, height=36,
        fg_color="#0f2a1a", hover_color="#1a4a2a",
        text_color="#4ec94e", font=("Consolas", 12, "bold"),
        border_width=1, border_color="#1a3a24",
        command=_save
    ).pack(side="right", padx=(8, 16), pady=8)

    ctk.CTkButton(
        btn_bar, text="Kapat", width=80, height=36,
        fg_color="transparent", hover_color="#1a1a1a",
        text_color="#555555", font=("Consolas", 12),
        command=win.destroy
    ).pack(side="right", padx=0, pady=8)
