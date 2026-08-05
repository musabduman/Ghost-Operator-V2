"""
core/logger.py — Ghost kalıcı log sistemi.
Rotating file handler: max 5 MB, 3 yedek dosya.
Hafıza (Kütüphaneci) logları isteğe göre filtrelenebilir.
"""
import os
import logging
from logging.handlers import RotatingFileHandler

from core.config import LOG_DIR
LOG_FILE = os.path.join(LOG_DIR, "ghost.log")

# Hafıza (Kütüphaneci) loglarını dosyaya yazma — sadece terminale gitsin
MEMORY_PREFIXES = ("[KÜTÜPHANECİ]", "[SİSTEM - KÜTÜPHANECİ]")


class _MemoryFilter(logging.Filter):
    """Kütüphaneci loglarını dosyadan filtreler."""
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(msg.startswith(p) for p in MEMORY_PREFIXES)


def _build_logger() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("ghost")
    if logger.handlers:
        return logger  # Zaten kurulu, tekrar yapılandırma

    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # root logger'a taşma

    # Rotating: max 5 MB, 3 yedek (ghost.log, ghost.log.1, ghost.log.2)
    fh = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.addFilter(_MemoryFilter())
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)
    return logger


# Uygulama genelinde tek logger instance
ghost_logger = _build_logger()


def log_yaz(metin: str, seviye: str = "info"):
    """
    app.log() tarafından çağrılır.
    seviye: 'info' | 'warning' | 'error' | 'debug'
    """
    fn = getattr(ghost_logger, seviye.lower(), ghost_logger.info)
    fn(metin)
