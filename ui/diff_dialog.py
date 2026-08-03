"""
ui/diff_dialog.py — Human-in-the-Loop: Dosya değişikliği diff gösterimi ve onay mekanizması.
"""
import os
import difflib
import threading
import customtkinter as ctk


def show_diff_dialog(app, dosya_yolu: str, eski_icerik: str, yeni_icerik: str,
                     aciklama: str, event: threading.Event, result_holder: dict):
    """
    Ana thread'e güvenle diff diyaloğu açar (app.after ile).
    LangGraph thread'i event.wait() ile bloke olur, kullanıcı onay/iptal
    verince event.set() çağrılır ve tool sonucu döner.
    """
    def _build():
        dialog = ctk.CTkToplevel(app)
        dialog.title(f"Değişiklik Onayı — {os.path.basename(dosya_yolu)}")
        dialog.geometry("860x580")
        dialog.attributes("-topmost", True)
        dialog.grab_set()  # Modal — arka plana tıklanamaz
        dialog.configure(fg_color="#0a0a0a")

        # ── Başlık ──────────────────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(dialog, fg_color="#111111", height=44, corner_radius=0)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        ctk.CTkLabel(
            header_frame,
            text=f"📄  {dosya_yolu}",
            font=("Consolas", 11), text_color="#888888", anchor="w"
        ).pack(side="left", padx=16, pady=12)

        # Dosya tipi badge
        ext = os.path.splitext(dosya_yolu)[1].lower()
        ctk.CTkLabel(
            header_frame,
            text=ext or "dosya",
            font=("Consolas", 10, "bold"), text_color="#00FFcc",
            fg_color="#0f1a17", corner_radius=4, padx=6, pady=2
        ).pack(side="right", padx=16)

        # ── Açıklama Alanı ──────────────────────────────────────────────────────
        aciklama_frame = ctk.CTkFrame(dialog, fg_color="#1a1c1a", corner_radius=0)
        aciklama_frame.pack(fill="x")
        
        ctk.CTkLabel(
            aciklama_frame,
            text="Ghost'un Açıklaması:",
            font=("Consolas", 10, "bold"), text_color="#00FFcc", anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 0))
        
        ctk.CTkLabel(
            aciklama_frame,
            text=aciklama,
            font=("Consolas", 11), text_color="#cccccc", anchor="w",
            wraplength=800, justify="left"
        ).pack(fill="x", padx=16, pady=(4, 8))

        # ── Diff alanı ──────────────────────────────────────────────────────────
        diff_scroll = ctk.CTkScrollableFrame(dialog, fg_color="#050505", corner_radius=0)
        diff_scroll.pack(fill="both", expand=True, padx=0, pady=0)

        diff_lines = list(difflib.unified_diff(
            eski_icerik.splitlines(keepends=True),
            yeni_icerik.splitlines(keepends=True),
            fromfile="Mevcut",
            tofile="Yeni",
            lineterm=""
        ))

        if not diff_lines:
            ctk.CTkLabel(
                diff_scroll, text="(Değişiklik yok — içerik aynı)",
                text_color="#444", font=("Consolas", 12)
            ).pack(pady=20)
        else:
            for line in diff_lines:
                raw = line.rstrip("\n").rstrip("\r")
                if raw.startswith("+++") or raw.startswith("---"):
                    fg, bg = "#888888", "#111111"
                elif raw.startswith("@@"):
                    fg, bg = "#569cd6", "#0d1a2a"
                elif raw.startswith("+"):
                    fg, bg = "#4ec94e", "#0d1a0d"
                elif raw.startswith("-"):
                    fg, bg = "#e05050", "#1a0d0d"
                else:
                    fg, bg = "#888888", "#0a0a0a"

                ctk.CTkLabel(
                    diff_scroll,
                    text=raw if raw else " ",
                    font=("Consolas", 11),
                    text_color=fg,
                    fg_color=bg,
                    anchor="w",
                    justify="left",
                    padx=8, pady=0,
                    corner_radius=0,
                    wraplength=800
                ).pack(fill="x", padx=0, pady=0)

        # ── İptal Sebebi Frame (başlangıçta gizli) ────────────────────────────
        reason_frame = ctk.CTkFrame(dialog, fg_color="#0f0f0f", corner_radius=0)

        ctk.CTkLabel(
            reason_frame,
            text="Neden iptal ediyorsun?  Ghost bu bilgiyi kullanarak farklı bir yol dener:",
            font=("Consolas", 11), text_color="#aaaaaa", anchor="w"
        ).pack(anchor="w", padx=16, pady=(10, 4))

        reason_row = ctk.CTkFrame(reason_frame, fg_color="transparent")
        reason_row.pack(fill="x", padx=16, pady=(0, 10))

        reason_entry = ctk.CTkEntry(
            reason_row,
            placeholder_text="Açıklama (boş bırakılabilir)...",
            font=("Consolas", 12), fg_color="#1a1a1a",
            border_color="#333333", text_color="#dddddd", height=36
        )
        reason_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def _send_reason():
            result_holder["approved"] = False
            result_holder["reason"] = reason_entry.get().strip()
            _safe_close()

        ctk.CTkButton(
            reason_row, text="Gönder", width=90, height=36,
            fg_color="#2a1a1a", hover_color="#4a1212",
            text_color="#e05050", font=("Consolas", 12),
            command=_send_reason
        ).pack(side="right")

        # ── Buton satırı ────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(dialog, fg_color="#111111", height=56, corner_radius=0)
        btn_frame.pack(fill="x")
        btn_frame.pack_propagate(False)

        def _on_approve(e=None):
            result_holder["approved"] = True
            result_holder["reason"] = ""
            _safe_close()

        def _on_cancel():
            btn_approve.configure(state="disabled")
            btn_cancel.configure(state="disabled")
            reason_frame.pack(fill="x", before=btn_frame)
            reason_entry.focus_set()
            # Enter'a basınca sebebi göndersin
            dialog.unbind("<Return>")
            dialog.bind("<Return>", lambda e: _send_reason())

        def _safe_close():
            if not event.is_set():
                event.set()
            try:
                dialog.grab_release()
                dialog.destroy()
            except Exception:
                pass

        # X ile kapatma → iptal sayılır
        def _on_x():
            result_holder["approved"] = False
            result_holder["reason"] = ""
            _safe_close()

        dialog.protocol("WM_DELETE_WINDOW", _on_x)
        
        # Enter tuşu varsayılan olarak "Onayla" yapar
        dialog.bind("<Return>", _on_approve)

        btn_approve = ctk.CTkButton(
            btn_frame, text="✅  Onayla (Enter)", width=150, height=36,
            fg_color="#0f2a1a", hover_color="#1a4a2a",
            text_color="#4ec94e", font=("Consolas", 12, "bold"),
            border_width=1, border_color="#1a3a24",
            command=_on_approve
        )
        btn_approve.pack(side="left", padx=(16, 8), pady=10)

        btn_cancel = ctk.CTkButton(
            btn_frame, text="❌  İptal",  width=140, height=36,
            fg_color="#2a0f0f", hover_color="#4a1212",
            text_color="#e05050", font=("Consolas", 12, "bold"),
            border_width=1, border_color="#3a1a1a",
            command=_on_cancel
        )
        btn_cancel.pack(side="left", padx=0, pady=10)

        ctk.CTkLabel(
            btn_frame,
            text="120 saniye içinde yanıt verilmezse otomatik onaylanır.",
            font=("Consolas", 10), text_color="#333333"
        ).pack(side="right", padx=16)

    app.after(0, _build)
