"""
sessions/session_manager.py — Oturum kayıt ve yükleme.
Her oturum sessions/ klasöründe ayrı bir JSON dosyasıdır.
"""
import json
import os
from datetime import datetime

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions")


def _ensure_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def new_session_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def save_session(session_id: str, messages: list):
    """messages: [{"role": "ghost"/"user", "text": "...", "ts": 123}]"""
    _ensure_dir()
    title = _extract_title(messages)
    data = {"id": session_id, "title": title, "messages": messages}
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> dict:
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if not os.path.exists(path):
        return {"id": session_id, "title": "Yeni Oturum", "messages": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_sessions(limit: int = 30) -> list:
    """En yeni oturumlar önce gelecek şekilde döner."""
    _ensure_dir()
    files = sorted(
        [f for f in os.listdir(SESSIONS_DIR) if f.endswith(".json")],
        reverse=True
    )[:limit]
    sessions = []
    for fname in files:
        path = os.path.join(SESSIONS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions.append({
                "id": data.get("id", fname[:-5]),
                "title": data.get("title", "Oturum"),
            })
        except Exception:
            continue
    return sessions


def _extract_title(messages: list) -> str:
    """İlk kullanıcı mesajından başlık üretir."""
    for m in messages:
        if m.get("role") == "user" and m.get("text"):
            text = m["text"].strip()
            return text[:40] + ("..." if len(text) > 40 else "")
    return f"Oturum {datetime.now().strftime('%H:%M')}"


def _friendly_date(session_id: str) -> str:
    """'2025-06-20_143022' → 'bugün / dün / Pzt / 20 Haz'"""
    try:
        dt = datetime.strptime(session_id, "%Y-%m-%d_%H%M%S")
        today = datetime.now().date()
        delta = (today - dt.date()).days
        if delta == 0:
            return dt.strftime("%H:%M")
        elif delta == 1:
            return "dün"
        elif delta < 7:
            days_tr = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
            return days_tr[dt.weekday()]
        else:
            months_tr = ["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"]
            return f"{dt.day} {months_tr[dt.month - 1]}"
    except Exception:
        return ""