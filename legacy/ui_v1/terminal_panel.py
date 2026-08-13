"""
ui/terminal_panel.py — Ghost + Kullanıcı ortak terminal yüzeyi.

Tasarım prensipleri (önerilere göre düzeltildi):
  1. CWD Python'da takip edilir, her cd değişince episodic_db ile senkronize edilir.
  2. Ghost kendi execution'ını kodu_calistir tool'u üzerinden yapar (ayrı process).
     Bu panel sadece kullanıcıya + Ghost'un terminal_cikti_oku tool'una aittir.
  3. "Temizle" sadece görsel temizleme. "Projeyi Kapat" ayrı aksiyondur.
  4. Çıktı tamponu (deque): Ghost'un terminal_cikti_oku tool'u buradan okur.
"""
import os
import subprocess
import threading
from collections import deque
import customtkinter as ctk

# Global çıktı tamponu — Ghost buradan okur
TERMINAL_OUTPUT_BUFFER: deque = deque(maxlen=200)


def build_terminal_panel(app, parent) -> ctk.CTkFrame:
    """Terminal panelini oluşturur ve frame döndürür (başlangıçta gizli)."""

    # ── CWD takibi (mutable list — closure'da değiştirilebilir) ──────────────
    cwd = [_get_initial_cwd(app)]

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

    # CWD etiketi (tıklanabilir kısaltma)
    cwd_label = ctk.CTkLabel(
        header, text=_short_cwd(cwd[0]),
        font=("Consolas", 10), text_color="#444444"
    )
    cwd_label.pack(side="left", padx=8)

    # Proje banner (başlangıçta gizli)
    project_label = ctk.CTkLabel(
        header, text="",
        font=("Consolas", 10, "bold"), text_color="#00FFcc"
    )
    project_label.pack(side="left", padx=4)

    # Sağ: Projeyi Kapat | Temizle
    def _kapat_proje():
        """Proje state'ini sıfırla (episodic_db'den sil), banner temizle."""
        try:
            db = app.command_handler.episodic_db
            proje_adi = db.proje_adi_bul(cwd[0])
            if proje_adi and not proje_adi.startswith("_bilinmiyor::"):
                db.proje_durumu_sil(proje_adi)
                _append(output, f"[Terminal] '{proje_adi}' projesi kapatıldı. State temizlendi.\n", "#e05050")
                project_label.configure(text="")
                app.after(0, lambda: app.command_handler._sorulmus_dizinler.discard(cwd[0])
                          if hasattr(app.command_handler, "_sorulmus_dizinler")
                          else None)
        except Exception as e:
            _append(output, f"[Hata] Proje kapatılamadı: {e}\n", "#e05050")

    def _temizle():
        """Sadece görsel temizlik — state'e dokunmaz."""
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.configure(state="disabled")
        TERMINAL_OUTPUT_BUFFER.clear()

    ctk.CTkButton(
        header, text="✕ Projeyi Kapat", width=110, height=20,
        fg_color="transparent", hover_color="#2a0f0f",
        text_color="#555555", font=("Consolas", 10),
        command=_kapat_proje
    ).pack(side="right", padx=(0, 4))

    ctk.CTkButton(
        header, text="☰ Temizle", width=70, height=20,
        fg_color="transparent", hover_color="#1a1a1a",
        text_color="#333333", font=("Consolas", 10),
        command=_temizle
    ).pack(side="right", padx=0)

    # ── Giriş satırı (Önce bottom'a packliyoruz ki output ezip geçmesin) ──────
    input_row = ctk.CTkFrame(frame, fg_color="#0a0a0a", height=36, corner_radius=0)
    input_row.pack(side="bottom", fill="x")
    input_row.pack_propagate(False)

    ctk.CTkLabel(
        input_row, text="$",
        text_color="#00FFcc", font=("Consolas", 14, "bold")
    ).pack(side="left", padx=(10, 4), pady=6)

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
    output.pack(side="top", fill="both", expand=True, padx=0, pady=0)


    cmd_entry = ctk.CTkEntry(
        input_row,
        fg_color="#0a0a0a", text_color="#00FF41",
        border_width=0, font=("Consolas", 12),
        placeholder_text="komut yaz...",
        placeholder_text_color="#2a2a2a"
    )
    cmd_entry.pack(side="left", fill="x", expand=True, padx=4, pady=6)

    # ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────

    def _append(tb, text: str, color: str = "#00FF41"):
        """Thread-safe çıktı ekleme."""
        TERMINAL_OUTPUT_BUFFER.append(text.rstrip())
        def _w():
            tb.configure(state="normal")
            tb.insert("end", text)
            tb.configure(state="disabled")
            tb.see("end")
        app.after(0, _w)

    def _update_cwd_ui(new_cwd: str):
        """CWD etiketini güncelle."""
        app.after(0, lambda: cwd_label.configure(text=_short_cwd(new_cwd)))

    def _check_project(new_cwd: str, manual_cd: bool = False):
        """CWD değişince proje bağlamını kontrol et — episodic_db ile senkronize."""
        try:
            if not hasattr(app, "command_handler"):
                return
            db = getattr(app.command_handler, "episodic_db", None)
            if db is None:
                return

            proje_adi = db.proje_adi_bul(new_cwd)
            tetikleyici_mesaj = ""

            if proje_adi and not proje_adi.startswith("_bilinmiyor::"):
                # Bilinen proje — banner göster, durumu güncelle
                durum = db.durum_getir(proje_adi)
                banner = f"📂 {proje_adi}"
                son_ozet = durum.get("son_gorev_ozeti", "") if durum else ""
                if son_ozet:
                    banner += f"  |  Son: {son_ozet[:50]}"
                app.after(0, lambda b=banner: project_label.configure(text=b, text_color="#00FFcc"))
                _append(output, f"\n[Terminal → Ghost] Proje: {proje_adi}\n", "#2a5a45")
                # Ghost state'ini güncelle (sessizce)
                db.durum_guncelle(
                    proje_adi=proje_adi,
                    aktif_dizin=new_cwd,
                    dokunulan_dosya=None,
                    gorev_ozeti=son_ozet
                )
                
                if manual_cd and not app.command_handler.su_an_mesgul:
                    tetikleyici_mesaj = f"[SİSTEM TETİKLEYİCİSİ]: Patron terminalden daha önce çalıştığımız '{proje_adi}' projesinin klasörüne ({new_cwd}) giriş yaptı. Projenin son durumu: '{son_ozet}'. Patron'a bu projeyi hatırladığını belirten ve ne yapmak istediğini (veya projede yeni bir şey var mı diye kontrol edip etmemen gerektiğini) soran ÇOK KISA bir hoş geldin mesajı ver."
            else:
                # Bilinmeyen dizin
                app.after(0, lambda: project_label.configure(
                    text=f"📂 {os.path.basename(new_cwd)} (tanımsız)",
                    text_color="#888888"
                ))
                # Oturumda ilk kez geliyorsa Ghost'a soru sormak için işaretle
                sorulmus = getattr(app.command_handler, "_sorulmus_dizinler", set())
                sorulmus.discard(new_cwd)  # Terminal'den cd ile gelince tekrar sor
                
                if manual_cd and not app.command_handler.su_an_mesgul:
                    try:
                        dosyalar = os.listdir(new_cwd)[:8]
                        dosya_bilgisi = ", ".join(dosyalar)
                    except Exception:
                        dosya_bilgisi = "(Okunamadı)"
                    tetikleyici_mesaj = f"[SİSTEM TETİKLEYİCİSİ]: Patron terminalden yeni/bilinmeyen bir klasöre ({new_cwd}) giriş yaptı. Klasörün içinde şunlar var: {dosya_bilgisi}. Patron'a buranın yeni bir proje olup olmadığını veya ne yapmak istediğini soran ÇOK KISA bir mesaj ver."

            # Eğer Ghost boşta ise ve manuel bir dizin değişimi yapıldıysa proaktif olarak tepki ver
            if tetikleyici_mesaj:
                import threading as _th
                _th.Thread(
                    target=app.command_handler._orchestrate_task,
                    args=(tetikleyici_mesaj,),
                    daemon=True
                ).start()

        except Exception as e:
            print(f"[Terminal] Proje bağlamı hatası: {e}")

    # ── Komut çalıştırma ──────────────────────────────────────────────────────

    def run_command(event=None):
        cmd = cmd_entry.get().strip()
        if not cmd:
            return
        cmd_entry.delete(0, "end")

        # cd komutunu Python'da işle (cwd kalıcı olsun)
        if _is_cd(cmd):
            target = cmd[2:].strip() if len(cmd) > 2 else ""
            if not target or target == "~":
                new_cwd = os.path.expanduser("~")
            elif target == "..":
                new_cwd = os.path.dirname(cwd[0])
            elif os.path.isabs(target):
                new_cwd = os.path.normpath(target)
            else:
                new_cwd = os.path.normpath(os.path.join(cwd[0], target))

            if os.path.isdir(new_cwd):
                cwd[0] = new_cwd
                _update_cwd_ui(new_cwd)
                _append(output, f"$ cd → {new_cwd}\n", "#666666")
                threading.Thread(target=_check_project, args=(new_cwd, True), daemon=True).start()
            else:
                _append(output, f"[Hata] Dizin bulunamadı: {new_cwd}\n", "#e05050")
            return

        # Normal komut
        _append(output, f"$ {cmd}\n", "#00FFcc")

        def _run():
            try:
                proc = subprocess.Popen(
                    cmd, shell=True, cwd=cwd[0],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace"
                )
                for line in proc.stdout:
                    _append(output, line, "#00FF41")
                proc.wait()
                rc = proc.returncode
                suffix = f"[kod: {rc}]\n"
                color = "#e05050" if rc != 0 else "#333333"
                _append(output, suffix, color)
            except Exception as e:
                _append(output, f"[Hata] {e}\n", "#e05050")

        threading.Thread(target=_run, daemon=True).start()

    cmd_entry.bind("<Return>", run_command)

    ctk.CTkButton(
        input_row, text="↵", width=34, height=26,
        fg_color="#0f1a0f", hover_color="#1a3a1a",
        text_color="#00FFcc", font=("Consolas", 14),
        command=run_command
    ).pack(side="right", padx=(4, 8), pady=5)

    # İlk yükleme: proje bağlamını kontrol et
    threading.Thread(target=_check_project, args=(cwd[0],), daemon=True).start()

    return frame


# ── Yardımcı fonksiyonlar (modül seviyesi) ────────────────────────────────────

def _get_initial_cwd(app) -> str:
    """Son aktif proje dizinini veya masaüstünü döndür."""
    default = os.path.expanduser("~\\Desktop")
    try:
        if hasattr(app, "command_handler") and hasattr(app.command_handler, "episodic_db"):
            proje = app.command_handler.episodic_db.son_aktif_projeyi_getir()
            if proje and proje.get("aktif_dizin") and os.path.isdir(proje["aktif_dizin"]):
                return proje["aktif_dizin"]
    except Exception:
        pass
    return default


def _short_cwd(path: str, max_len: int = 40) -> str:
    """Uzun yolu kısalt: C:\\Users\\...\\KriptoDashboard → ...\\KriptoDashboard"""
    if len(path) <= max_len:
        return path
    parts = path.replace("/", "\\").split("\\")
    short = "...\\" + "\\".join(parts[-2:]) if len(parts) >= 2 else path
    return short


def _is_cd(cmd: str) -> bool:
    """Komut bir cd çağrısı mı?"""
    lower = cmd.lower().strip()
    return lower == "cd" or lower.startswith("cd ") or lower.startswith("cd\t")


def get_terminal_output(last_n: int = 50) -> str:
    """
    Ghost'un terminal_cikti_oku tool'u tarafından çağrılır.
    Son N satırı döndürür.
    """
    lines = list(TERMINAL_OUTPUT_BUFFER)
    return "\n".join(lines[-last_n:]) if lines else "(Terminal çıktısı boş)"
