"""
core/ollama_health.py — Ollama sağlık kontrolü ve otomatik başlatma.

RAG / Embedding çağrılarından önce Ollama'nın ayakta olup olmadığını kontrol
eder.  Kapalıysa arka planda sessizce ``ollama serve`` çalıştırır ve kısa bir
süre bekler.  Başarısızsa LangGraph'a basılabilecek temiz, tek satırlık bir
hata mesajı üretir — ham traceback veya HTML çöplüğü asla dışarı sızmaz.
"""

import logging
import os
import shutil
import subprocess
import sys
import threading
import time

import requests

logger = logging.getLogger("ghost.ollama_health")

# ── Yapılandırma ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL: str = os.getenv("GHOST_EMBEDDING_MODEL", "qwen3-embedding:0.6b")

_HEALTH_ENDPOINT = f"{OLLAMA_BASE_URL}/api/tags"
_BOOT_TIMEOUT_SEC = 8          # ``ollama serve`` sonrası bekleme süresi
_HEALTH_CHECK_TIMEOUT_SEC = 3  # health-check HTTP isteği zaman aşımı
_BOOT_LOCK = threading.Lock()  # Eşzamanlı iki thread'in birlikte boot denemesini engeller
_ALREADY_BOOTED = False        # Oturum boyunca sadece bir kez otomatik başlatmayı dene


# ── Hata Özetleyici (State Hijyeni) ──────────────────────────────────────────

def format_embedding_error(exc: Exception) -> str:
    """Ham exception'ı LangGraph context'ine uygun temiz tek satıra çevirir.

    Kurallar:
      - HTTPError 404                            → Model bulunamadı
      - Timeout                                  → Zaman aşımı
      - ConnectionError / ConnectionRefusedError → Ollama servisi erişilemez
      - Diğer                                    → İlk 120 karakter özet
    """
    exc_type = type(exc).__name__
    msg = str(exc)

    if isinstance(exc, requests.exceptions.HTTPError):
        status = getattr(exc.response, "status_code", None)
        if status == 404:
            return (
                f"'{EMBEDDING_MODEL}' modeli Ollama'da bulunamadı. "
                f"'ollama pull {EMBEDDING_MODEL}' ile çekmeyi dene."
            )
        return f"Ollama HTTP hatası: {status} — {msg[:100]}"

    if isinstance(exc, (requests.exceptions.Timeout, TimeoutError)):
        return "Ollama embedding isteği zaman aşımına uğradı."

    if isinstance(exc, (requests.exceptions.ConnectionError, ConnectionRefusedError)):
        return (
            f"Ollama embedding servisine ulaşılamadı "
            f"({OLLAMA_BASE_URL} bağlantı reddedildi)."
        )

    # Genel fallback — çöplük olmasın
    clean = f"{exc_type}: {msg}"
    if len(clean) > 120:
        clean = clean[:117] + "..."
    return clean


# ── Sağlık Kontrolü ─────────────────────────────────────────────────────────

def is_ollama_alive() -> bool:
    """Ollama API'sinin yanıt verip vermediğini kontrol eder."""
    try:
        r = requests.get(_HEALTH_ENDPOINT, timeout=_HEALTH_CHECK_TIMEOUT_SEC)
        return r.status_code == 200
    except Exception:
        return False


# ── Otomatik Başlatma ────────────────────────────────────────────────────────

def _find_ollama_exe() -> str | None:
    """PATH'te veya bilinen konumlarda ollama yürütülebilir dosyasını arar."""
    found = shutil.which("ollama")
    if found:
        return found

    # Windows varsayılan kurulum yolu
    if sys.platform == "win32":
        candidate = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs", "Ollama", "ollama.exe",
        )
        if os.path.isfile(candidate):
            return candidate

    return None


def _try_boot_ollama() -> bool:
    """Ollama kapalıysa arka planda sessizce başlatır.

    Oturum boyunca yalnızca **bir kez** denenir (sonsuz yeniden başlatma
    döngüsünü önlemek için).  Başarılıysa True, değilse False döner.
    """
    global _ALREADY_BOOTED

    if _ALREADY_BOOTED:
        return False

    with _BOOT_LOCK:
        # Double-check: lock alana kadar başka thread başlatmış olabilir
        if _ALREADY_BOOTED:
            return False
        _ALREADY_BOOTED = True

        exe = _find_ollama_exe()
        if not exe:
            logger.warning("[OLLAMA] ollama yürütülebilir dosyası bulunamadı, otomatik başlatma atlanıyor.")
            return False

        logger.info(f"[OLLAMA] Servis kapalı, arka planda başlatılıyor: {exe} serve")

        try:
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = (
                    subprocess.CREATE_NO_WINDOW
                    | subprocess.DETACHED_PROCESS
                )

            subprocess.Popen(
                [exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
        except Exception as e:
            logger.warning(f"[OLLAMA] Başlatma komutu çalıştırılamadı: {e}")
            return False

        # Kısa aralıklarla yokla
        deadline = time.monotonic() + _BOOT_TIMEOUT_SEC
        while time.monotonic() < deadline:
            time.sleep(0.5)
            if is_ollama_alive():
                logger.info("[OLLAMA] Servis başarıyla başlatıldı.")
                return True

        logger.warning("[OLLAMA] Servis belirtilen sürede ayağa kalkmadı.")
        return False


# ── Ana Giriş Noktası ────────────────────────────────────────────────────────

def ensure_ollama() -> str | None:
    """Ollama'nın erişilebilir olmasını sağlar.

    Returns:
        ``None``  → Ollama hazır, sorun yok.
        ``str``   → Temiz hata mesajı (LangGraph'a aktarılabilir).
    """
    if is_ollama_alive():
        return None

    logger.info("[OLLAMA] Servis yanıt vermiyor, otomatik başlatma deneniyor...")

    if _try_boot_ollama():
        return None

    return (
        f"Ollama embedding servisi ({OLLAMA_BASE_URL}) erişilemez durumda "
        f"ve otomatik başlatma başarısız oldu. Hafıza olmadan devam ediliyor."
    )
