"""
ui/memory_viewer.py — Ghost Hafıza Görüntüleyici.
SQLite tabloları ve ChromaDB RAG kayıtlarını okunabilir tablo formatında gösterir.
"""
import os
import json
import datetime
import customtkinter as ctk

DB_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "Ghost_Memory", "ghost_memory.db")

# ── Renk sabitleri ────────────────────────────────────────────────────────────
BG       = "#0a0a0a"
BG_ROW   = "#0f0f0f"
BG_ALT   = "#111111"
BG_HEAD  = "#0d1a0d"
CLR_ACC  = "#00FFcc"
CLR_DIM  = "#444444"
CLR_OK   = "#4ec94e"
CLR_ERR  = "#e05050"
CLR_WARN = "#f0a030"
MONO     = ("Consolas", 11)
MONO_SM  = ("Consolas", 10)


def open_memory_viewer(app):
    """Hafıza görüntüleyici penceresini aç."""
    win = ctk.CTkToplevel(app)
    win.title("Ghost — Hafıza Görüntüleyici")
    win.geometry("1050x640")
    win.attributes("-topmost", True)
    win.configure(fg_color=BG)

    # ── Başlık ─────────────────────────────────────────────────────────────────
    header = ctk.CTkFrame(win, fg_color="#0d0d0d", height=44, corner_radius=0)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(header, text="🗄  Ghost Hafıza Görüntüleyici",
                 font=("Consolas", 13, "bold"), text_color=CLR_ACC).pack(side="left", padx=16, pady=12)

    refresh_btn = ctk.CTkButton(header, text="↻ Yenile", width=80, height=28,
                                 fg_color="transparent", hover_color="#1a2a1a",
                                 text_color=CLR_DIM, font=MONO_SM,
                                 border_width=1, border_color="#222")
    refresh_btn.pack(side="right", padx=16)

    # ── Sekmeler ───────────────────────────────────────────────────────────────
    tabs = ctk.CTkTabview(win, fg_color="#0d0d0d",
                          segmented_button_fg_color="#111",
                          segmented_button_selected_color="#0f1a17",
                          segmented_button_selected_hover_color="#1a3028",
                          segmented_button_unselected_color="#111",
                          text_color="#aaa")
    tabs.pack(fill="both", expand=True)

    tabs.add("💬 Sohbet Geçmişi")
    tabs.add("🛠 Araç Logları")
    tabs.add("📁 Projeler")
    tabs.add("🧠 RAG Bellek")

    def _load_all():
        _load_sohbet(tabs.tab("💬 Sohbet Geçmişi"))
        _load_arac(tabs.tab("🛠 Araç Logları"))
        _load_projeler(tabs.tab("📁 Projeler"))
        _load_rag(tabs.tab("🧠 RAG Bellek"), app)

    refresh_btn.configure(command=_load_all)
    _load_all()


# ── Yardımcı: Kaydırılabilir tablo ───────────────────────────────────────────

def _tablo_olustur(parent, sutunlar: list[tuple[str, int]]) -> ctk.CTkScrollableFrame:
    """
    Başlıklı, satır renkli bir tablo. sutunlar = [(başlık, genişlik), ...]
    Döndürülen scrollframe'e satır CTkLabel'ları pack edilir.
    """
    wrapper = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
    wrapper.pack(fill="both", expand=True, padx=0, pady=0)

    # Başlık satırı
    head_row = ctk.CTkFrame(wrapper, fg_color=BG_HEAD, height=30, corner_radius=0)
    head_row.pack(fill="x", padx=4, pady=(4, 0))
    head_row.pack_propagate(False)

    for title, width in sutunlar:
        ctk.CTkLabel(head_row, text=title, width=width,
                     font=("Consolas", 11, "bold"), text_color=CLR_ACC,
                     anchor="w").pack(side="left", padx=(6, 0))

    # Scroll alanı
    scroll = ctk.CTkScrollableFrame(wrapper, fg_color=BG, corner_radius=0,
                                    scrollbar_button_color="#1a1a1a")
    scroll.pack(fill="both", expand=True, padx=4, pady=(0, 4))
    return scroll


def _satir_ekle(frame, degerler: list, renk_idx: int = 0,
                sutun_genislikler: list[int] = None, renkler: list = None):
    """Tek bir veri satırı ekler."""
    bg = BG_ALT if renk_idx % 2 == 0 else BG_ROW
    row = ctk.CTkFrame(frame, fg_color=bg, height=26, corner_radius=0)
    row.pack(fill="x", pady=0)
    row.pack_propagate(False)

    for i, val in enumerate(degerler):
        w = (sutun_genislikler[i] if sutun_genislikler and i < len(sutun_genislikler) else 120)
        color = (renkler[i] if renkler and i < len(renkler) else "#cccccc")
        text = str(val)[:80] if val is not None else "—"
        ctk.CTkLabel(row, text=text, width=w,
                     font=MONO_SM, text_color=color,
                     anchor="w", wraplength=w - 10).pack(side="left", padx=(6, 0))


def _ts_fmt(ts) -> str:
    """Unix timestamp → okunabilir tarih."""
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%d.%m %H:%M:%S")
    except Exception:
        return str(ts)


# ── Sohbet Geçmişi ────────────────────────────────────────────────────────────

def _load_sohbet(parent):
    for w in parent.winfo_children():
        w.destroy()

    import sqlite3
    if not os.path.exists(DB_PATH):
        ctk.CTkLabel(parent, text="Veritabanı bulunamadı:\n" + DB_PATH,
                     text_color=CLR_ERR, font=MONO).pack(pady=20)
        return

    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            "SELECT id, session_id, timestamp, role, content FROM sohbet_gecmisi ORDER BY id DESC LIMIT 200"
        ).fetchall()
        con.close()
    except Exception as e:
        ctk.CTkLabel(parent, text=f"Hata: {e}", text_color=CLR_ERR, font=MONO).pack(pady=20)
        return

    sutunlar = [("ID", 45), ("Oturum", 130), ("Zaman", 110), ("Rol", 60), ("İçerik", 520)]
    genislikler = [s[1] for s in sutunlar]
    scroll = _tablo_olustur(parent, sutunlar)

    for i, (rid, sid, ts, role, content) in enumerate(rows):
        role_color = CLR_ACC if role == "ghost" else "#88ddbb"
        _satir_ekle(scroll,
                    [rid, sid[-8:] if sid else "?", _ts_fmt(ts), role, content],
                    renk_idx=i,
                    sutun_genislikler=genislikler,
                    renkler=["#666", "#555", "#666", role_color, "#cccccc"])

    ctk.CTkLabel(parent, text=f"  {len(rows)} kayıt (son 200)",
                 font=MONO_SM, text_color=CLR_DIM).pack(anchor="w", padx=8, pady=2)


# ── Araç Logları ──────────────────────────────────────────────────────────────

def _load_arac(parent):
    for w in parent.winfo_children():
        w.destroy()

    import sqlite3
    if not os.path.exists(DB_PATH):
        ctk.CTkLabel(parent, text="Veritabanı bulunamadı", text_color=CLR_ERR, font=MONO).pack(pady=20)
        return

    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            "SELECT id, timestamp, tool_name, arguments, result, success FROM arac_gunlukleri ORDER BY id DESC LIMIT 200"
        ).fetchall()
        con.close()
    except Exception as e:
        ctk.CTkLabel(parent, text=f"Hata: {e}", text_color=CLR_ERR, font=MONO).pack(pady=20)
        return

    sutunlar = [("ID", 45), ("Zaman", 100), ("Araç", 130), ("Parametreler", 240), ("Sonuç", 280), ("✓", 40)]
    genislikler = [s[1] for s in sutunlar]
    scroll = _tablo_olustur(parent, sutunlar)

    for i, (rid, ts, tool, args, result, success) in enumerate(rows):
        ok_color = CLR_OK if success else CLR_ERR
        ok_text  = "✓" if success else "✗"
        args_str = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
        _satir_ekle(scroll,
                    [rid, _ts_fmt(ts), tool, args_str, result, ok_text],
                    renk_idx=i,
                    sutun_genislikler=genislikler,
                    renkler=["#666", "#666", CLR_ACC, "#aaa", "#ccc", ok_color])

    ctk.CTkLabel(parent, text=f"  {len(rows)} kayıt (son 200)",
                 font=MONO_SM, text_color=CLR_DIM).pack(anchor="w", padx=8, pady=2)


# ── Projeler ──────────────────────────────────────────────────────────────────

def _load_projeler(parent):
    for w in parent.winfo_children():
        w.destroy()

    import sqlite3
    if not os.path.exists(DB_PATH):
        ctk.CTkLabel(parent, text="Veritabanı bulunamadı", text_color=CLR_ERR, font=MONO).pack(pady=20)
        return

    try:
        con = sqlite3.connect(DB_PATH)
        durumlar = con.execute(
            "SELECT proje_adi, aktif_dizin, son_dokunulan_dosyalar, son_gorev_ozeti, guncelleme_zamani "
            "FROM proje_durumu ORDER BY guncelleme_zamani DESC"
        ).fetchall()
        harita = con.execute(
            "SELECT kok_dizin, proje_adi, olusturma_zamani FROM proje_yol_haritasi ORDER BY olusturma_zamani DESC"
        ).fetchall()
        con.close()
    except Exception as e:
        ctk.CTkLabel(parent, text=f"Hata: {e}", text_color=CLR_ERR, font=MONO).pack(pady=20)
        return

    # Proje Durumları
    ctk.CTkLabel(parent, text="Proje Durumları", font=("Consolas", 12, "bold"),
                 text_color=CLR_ACC).pack(anchor="w", padx=10, pady=(8, 2))

    sut1 = [("Proje Adı", 160), ("Aktif Dizin", 240), ("Son Görev", 300), ("Güncelleme", 110)]
    sc1 = _tablo_olustur(parent, sut1)
    for i, (adi, dizin, dosyalar, ozet, zaman) in enumerate(durumlar):
        _satir_ekle(sc1, [adi, dizin, ozet, _ts_fmt(zaman)],
                    renk_idx=i, sutun_genislikler=[s[1] for s in sut1],
                    renkler=[CLR_ACC, "#aaa", "#ccc", "#666"])

    # Yol Haritası
    ctk.CTkLabel(parent, text="Yol Haritası (Proje Klasörleri)",
                 font=("Consolas", 12, "bold"), text_color=CLR_ACC).pack(anchor="w", padx=10, pady=(10, 2))

    sut2 = [("Kök Dizin", 360), ("Proje Adı", 200), ("Oluşturma", 110)]
    sc2 = _tablo_olustur(parent, sut2)
    for i, (kok, adi, zaman) in enumerate(harita):
        _satir_ekle(sc2, [kok, adi, _ts_fmt(zaman)],
                    renk_idx=i, sutun_genislikler=[s[1] for s in sut2],
                    renkler=["#aaa", CLR_ACC, "#666"])


# ── RAG / ChromaDB ────────────────────────────────────────────────────────────

def _load_rag(parent, app):
    for w in parent.winfo_children():
        w.destroy()

    try:
        from hafıza.rag_hafıza import Bellek
        bellek = Bellek()
        # Tüm kayıtları çek
        sonuc = bellek.collection.get(include=["documents", "metadatas"])
        docs     = sonuc.get("documents", [])
        metas    = sonuc.get("metadatas", [])
        ids_list = sonuc.get("ids", [])
    except Exception as e:
        ctk.CTkLabel(parent, text=f"ChromaDB yüklenemedi: {e}",
                     text_color=CLR_ERR, font=MONO).pack(pady=20)
        return

    ctk.CTkLabel(parent, text=f"  Toplam {len(docs)} RAG kaydı  |  Koleksiyon: 'bellek'",
                 font=MONO_SM, text_color=CLR_DIM).pack(anchor="w", padx=8, pady=(6, 2))

    sutunlar = [("ID (kısa)", 90), ("İçerik", 560), ("Metadata", 280)]
    genislikler = [s[1] for s in sutunlar]
    scroll = _tablo_olustur(parent, sutunlar)

    for i, (doc_id, doc, meta) in enumerate(zip(ids_list, docs, metas)):
        short_id = doc_id[:8] + "…" if len(doc_id) > 8 else doc_id
        meta_str = json.dumps(meta, ensure_ascii=False) if meta else "—"
        _satir_ekle(scroll,
                    [short_id, doc, meta_str],
                    renk_idx=i,
                    sutun_genislikler=genislikler,
                    renkler=["#555", "#cccccc", "#777"])
