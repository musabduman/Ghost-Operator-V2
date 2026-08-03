"""
ui/terminal_panel.py — Inline terminal paneli.
Expanded mod toolbar'ındaki >_ butonuyla aç/kapat yapılır.
"""
import os
import subprocess
import threading
import customtkinter as ctk


def build_terminal_panel(app, parent) -> ctk.CTkFrame:
    """Terminal panelini oluşturur ve frame döndürür (başlangıçta gizli)."""

    frame = ctk.CTkFrame(parent, fg_color="#050505", corner_radius=0, height=240)
    frame.pack_propagate(False)

    # ── Header ─────────────────────────────────────────────────────────────────
    header = ctk.CTkFrame(frame, fg_color="#0d0d0d", height=28, corner_radius=0)
    header.pack(fill="x")
    header.pack_propagate(False)

    ctk.CTkLabel(
        header, text=">_  Terminal",
        font=("Consolas", 11, "bold"), text_color="#00FFcc"
    ).pack(side="left", padx=12)

    # Aktif proje dizinini göster
    app._terminal_cwd_label = ctk.CTkLabel(
        header, text="cwd: ~",
        font=("Consolas", 10), text_color="#444444"
    )
    app._terminal_cwd_label.pack(side="left", padx=8)

    # Temizle butonu
    def _clear_output():
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.configure(state="disabled")

    ctk.CTkButton(
        header, text="✕ Temizle", width=70, height=20,
        fg_color="transparent", hover_color="#1a1a1a",
        text_color="#555555", font=("Consolas", 10),
        command=_clear_output
    ).pack(side="right", padx=8)

    # ── Çıktı alanı ────────────────────────────────────────────────────────────
    output = ctk.CTkTextbox(
        frame,
        fg_color="#020202",
        text_color="#00FF41",
        font=("Consolas", 12),
        state="disabled",
        wrap="none",
        scrollbar_button_color="#111111",
        scrollbar_button_hover_color="#1a1a1a"
    )
    output.pack(fill="both", expand=True, padx=0, pady=0)

    # ── Giriş satırı ──────────────────────────────────────────────────────────
    input_row = ctk.CTkFrame(frame, fg_color="#0a0a0a", height=36, corner_radius=0)
    input_row.pack(fill="x")
    input_row.pack_propagate(False)

    ctk.CTkLabel(
        input_row, text="$",
        text_color="#00FFcc", font=("Consolas", 14, "bold")
    ).pack(side="left", padx=(10, 4), pady=6)

    cmd_entry = ctk.CTkEntry(
        input_row,
        fg_color="#0a0a0a", text_color="#00FF41",
        border_width=0, font=("Consolas", 12),
        placeholder_text="komut yaz...",
        placeholder_text_color="#2a2a2a"
    )
    cmd_entry.pack(side="left", fill="x", expand=True, padx=4, pady=6)

    def _get_cwd() -> str:
        """Son aktif proje dizinini bul, yoksa masaüstü."""
        default = os.path.expanduser("~\\Desktop")
        try:
            if hasattr(app, "command_handler") and hasattr(app.command_handler, "episodic_db"):
                proje = app.command_handler.episodic_db.son_aktif_projeyi_getir()
                if proje and proje.get("aktif_dizin") and os.path.isdir(proje["aktif_dizin"]):
                    cwd = proje["aktif_dizin"]
                    app.after(0, lambda: app._terminal_cwd_label.configure(text=f"cwd: {cwd}"))
                    return cwd
        except Exception:
            pass
        return default

    def _append(text: str, color: str = "#00FF41"):
        output.configure(state="normal")
        # CTkTextbox renk tag'i desteklemez ama biz sadece yeşil/kırmızı kullanıyoruz
        output.insert("end", text)
        output.configure(state="disabled")
        output.see("end")

    def run_command(event=None):
        cmd = cmd_entry.get().strip()
        if not cmd:
            return
        cmd_entry.delete(0, "end")
        cwd = _get_cwd()

        app.after(0, lambda: _append(f"$ {cmd}\n"))

        def _run():
            try:
                proc = subprocess.Popen(
                    cmd, shell=True, cwd=cwd,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace"
                )
                for line in proc.stdout:
                    app.after(0, lambda l=line: _append(l))
                proc.wait()
                rc = proc.returncode
                suffix = f"[Çıktı kodu: {rc}]\n"
                app.after(0, lambda: _append(suffix))
            except Exception as e:
                app.after(0, lambda: _append(f"HATA: {e}\n"))

        threading.Thread(target=_run, daemon=True).start()

    cmd_entry.bind("<Return>", run_command)

    ctk.CTkButton(
        input_row, text="↵", width=34, height=26,
        fg_color="#0f1a0f", hover_color="#1a3a1a",
        text_color="#00FFcc", font=("Consolas", 14),
        command=run_command
    ).pack(side="right", padx=(4, 8), pady=5)

    # İlk cwd labelı güncelle
    app.after(500, _get_cwd)

    return frame
