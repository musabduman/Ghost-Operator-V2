"""
ui/expanded_ui.py — Expanded (tam ekran) mod.
Sol sidebar: oturum listesi. Sağ alan: klasik chat + araç çubuğu.
"""
import customtkinter as ctk
from ui.ui import build_screenshot_button, build_media_buttons
from sessions.session_manager import list_sessions, _friendly_date


# ── Renk sabitleri (Ghost teması) ────────────────────────────────────────────
BG_SIDEBAR  = "#0d0d0d"
BG_MAIN     = "#111111"
BG_BUBBLE_AI   = "#1a1a1a"
BG_BUBBLE_USER = "#0f1a17"
CLR_ACCENT  = "#00FFcc"
CLR_DIM     = "#444444"
CLR_BORDER  = "#222222"
FONT_MONO   = ("Consolas", 12)
FONT_SMALL  = ("Consolas", 11)


def build_expanded(app) -> ctk.CTkFrame:
    outer = ctk.CTkFrame(app, fg_color="transparent")
    outer.pack_propagate(False)

    # İki sütun: sidebar | main
    outer.grid_columnconfigure(0, weight=0)
    outer.grid_columnconfigure(1, weight=1)
    outer.grid_rowconfigure(0, weight=1)

    _build_sidebar(app, outer)
    _build_main(app, outer)

    return outer


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _build_sidebar(app, parent):
    sidebar = ctk.CTkFrame(parent, width=200, fg_color=BG_SIDEBAR,
                           corner_radius=0, border_width=0)
    sidebar.grid(row=0, column=0, sticky="nsew")
    sidebar.grid_propagate(False)
    sidebar.grid_rowconfigure(2, weight=1)
    sidebar.grid_columnconfigure(0, weight=1)

    # Başlık
    ctk.CTkLabel(
        sidebar, text="GHOST OPERATOR",
        font=("Consolas", 13, "bold"), text_color="#3a3a3a"
    ).grid(row=0, column=0, padx=12, pady=(14, 6), sticky="w")

    # Yeni Sohbet butonu
    ctk.CTkButton(
        sidebar, text="＋  Yeni Sohbet",
        font=FONT_SMALL, height=30,
        fg_color="transparent", hover_color="#1a1a1a",
        text_color=CLR_ACCENT, border_width=1, border_color="#1e3028",
        command=app.new_session
    ).grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")

    # Scrollable oturum listesi
    scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent", corner_radius=0)
    scroll.grid(row=2, column=0, sticky="nsew", padx=4)

    app.session_list_frame = scroll  # dışarıdan yenilenebilsin
    _populate_sessions(app, scroll)

    # Alt: Küçült butonu
    ctk.CTkButton(
        sidebar, text="⤡  Küçük Moda Dön",
        font=FONT_SMALL, height=28,
        fg_color="transparent", hover_color="#1a1a1a",
        text_color=CLR_DIM, border_width=1, border_color=CLR_BORDER,
        command=app.compact_mode
    ).grid(row=3, column=0, padx=10, pady=10, sticky="ew")


def _populate_sessions(app, frame):
    """Oturum listesini sidebar'a doldurur."""
    for widget in frame.winfo_children():
        widget.destroy()

    sessions = list_sessions(40)

    if not sessions:
        ctk.CTkLabel(
            frame, text="Henüz oturum yok.",
            font=FONT_SMALL, text_color="#333333"
        ).pack(padx=8, pady=8, anchor="w")
        return

    for s in sessions:
        sid = s["id"]
        title = s["title"]
        date_str = _friendly_date(sid)
        is_active = (sid == app.current_session_id)

        row = ctk.CTkFrame(
            frame,
            fg_color="#0f1a17" if is_active else "transparent",
            corner_radius=6
        )
        row.pack(fill="x", padx=4, pady=2)

        # Sol aksan çizgisi (aktif oturum için)
        if is_active:
            accent = ctk.CTkFrame(row, width=3, fg_color=CLR_ACCENT, corner_radius=0)
            accent.pack(side="left", fill="y", padx=(0, 6))

        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, pady=4)

        ctk.CTkLabel(
            text_frame, text=title,
            font=FONT_SMALL,
            text_color=CLR_ACCENT if is_active else "#555555",
            anchor="w", wraplength=140
        ).pack(anchor="w", padx=4)

        ctk.CTkLabel(
            text_frame, text=date_str,
            font=("Consolas", 10), text_color="#2a3a2a" if is_active else "#2a2a2a",
            anchor="w"
        ).pack(anchor="w", padx=4)

        # Tıklama
        def _on_click(s_id=sid):
            app.switch_session(s_id)

        row.bind("<Button-1>", lambda e, fn=_on_click: fn())
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, fn=_on_click: fn())


# ── Ana Alan ──────────────────────────────────────────────────────────────────

def _build_main(app, parent):
    main = ctk.CTkFrame(parent, fg_color=BG_MAIN, corner_radius=0)
    main.grid(row=0, column=1, sticky="nsew")
    main.grid_rowconfigure(1, weight=1)
    main.grid_columnconfigure(0, weight=1)

    _build_topbar(app, main)
    _build_chat_area(app, main)
    _build_toolbar(app, main)
    _build_input_row(app, main)


def _build_topbar(app, parent):
    bar = ctk.CTkFrame(parent, fg_color="transparent", height=44,
                       border_width=0)
    bar.grid(row=0, column=0, sticky="ew", padx=0)
    bar.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        bar, text="GHOST OPERATOR  v2",
        font=("Consolas", 15, "bold"), text_color="#3a3a3a"
    ).grid(row=0, column=0, padx=16, pady=10)

    app.model_label = ctk.CTkLabel(
        bar, text="Aktif Zeka: Bekliyor...",
        font=("Consolas", 11, "italic"), text_color="#555555"
    )
    app.model_label.grid(row=0, column=1, padx=8)

    # Sağ: ekran yorumla
    app.ss_button = build_screenshot_button(app)
    app.ss_button.configure(width=180, height=28, font=("Consolas", 11))
    app.ss_button.grid(row=0, column=2, padx=12)


def _build_chat_area(app, parent):
    app.chat_scroll = ctk.CTkScrollableFrame(
        parent,
        fg_color="#0e0e0e",
        corner_radius=0,
        scrollbar_button_color="#1e1e1e",
        scrollbar_button_hover_color="#2a2a2a"
    )
    app.chat_scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
    app.chat_scroll.grid_columnconfigure(0, weight=1)


def _build_toolbar(app, parent):
    bar = ctk.CTkFrame(parent, fg_color="#0d0d0d", height=36, corner_radius=0)
    bar.grid(row=2, column=0, sticky="ew")

    BTN = dict(
        font=("Consolas", 11), height=24,
        fg_color="transparent", hover_color="#1a1a1a",
        text_color="#444444", border_width=1, border_color="#1e1e1e"
    )
    from kontrol.kontrol import muzik_kontrol
    ctk.CTkButton(bar, text="⏮", width=32, command=lambda: muzik_kontrol("önceki"), **BTN).pack(side="left", padx=(8, 2), pady=6)
    ctk.CTkButton(bar, text="⏯", width=32, command=lambda: muzik_kontrol("durdur"),  **BTN).pack(side="left", padx=2, pady=6)
    ctk.CTkButton(bar, text="⏭", width=32, command=lambda: muzik_kontrol("sonraki"), **BTN).pack(side="left", padx=2, pady=6)

    ctk.CTkLabel(bar, text="|", text_color="#222222", font=FONT_SMALL).pack(side="left", padx=6)

    ctk.CTkButton(bar, text="🧠 RAG Bellek", width=100, **BTN).pack(side="left", padx=2, pady=6)


def _build_input_row(app, parent):
    row = ctk.CTkFrame(parent, fg_color="#0d0d0d", corner_radius=0)
    row.grid(row=3, column=0, sticky="ew", padx=0, pady=0)
    row.grid_columnconfigure(0, weight=1)

    app.entry = ctk.CTkEntry(
        row,
        placeholder_text="Komut yaz...",
        height=44,
        font=("Consolas", 14),
        fg_color="#111111",
        border_color="#1e1e1e",
        border_width=1,
    )
    app.entry.grid(row=0, column=0, padx=(12, 6), pady=10, sticky="ew")
    app.entry.bind("<Return>", app.command_handler.handle)

    ctk.CTkButton(
        row, text="↑", width=44, height=44,
        font=("Consolas", 18, "bold"),
        fg_color="#0f1a17", hover_color="#1a3028",
        text_color=CLR_ACCENT, border_width=1, border_color="#1e3028",
        command=lambda: app.command_handler.handle(None)
    ).grid(row=0, column=1, padx=(0, 12), pady=10)


# ── Chat bubble helper (main.py'den çağrılır) ─────────────────────────────────

def append_chat_bubble(app, role: str, text: str):
    """
    role: 'ghost' veya 'user'
    Expanded moddayken chat scroll alanına baloncuk ekler.
    """
    if not hasattr(app, "chat_scroll") or not app.chat_scroll.winfo_exists():
        return

    is_user = (role == "user")
    container = ctk.CTkFrame(app.chat_scroll, fg_color="transparent")
    container.pack(fill="x", padx=12, pady=(4, 0))

    name_color = "#555555" if is_user else "#2a5a45"
    name = "Sen" if is_user else "Ghost"
    ctk.CTkLabel(
        container, text=name,
        font=("Consolas", 10), text_color=name_color,
        anchor="e" if is_user else "w"
    ).pack(anchor="e" if is_user else "w")

    bubble = ctk.CTkLabel(
        container,
        text=text,
        font=("Consolas", 12),
        fg_color=BG_BUBBLE_USER if is_user else BG_BUBBLE_AI,
        text_color=CLR_ACCENT if not is_user else "#88ddbb",
        corner_radius=10,
        wraplength=520,
        justify="left",
        anchor="w",
        padx=12, pady=8
    )
    bubble.pack(anchor="e" if is_user else "w", pady=(2, 4))

    # Scroll'u en alta götür
    app.after(50, lambda: app.chat_scroll._parent_canvas.yview_moveto(1.0))