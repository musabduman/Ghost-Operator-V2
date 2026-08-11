import os

# Docker'a geçtiğimizde bunu environment variable olarak vereceğiz (Örn: /app/data)
# Şimdilik masaüstünde çalıştığı için kullanıcı dizininde sabit bir klasör seçiyoruz.
GHOST_DATA_DIR = os.getenv("GHOST_DATA_DIR", os.path.join(os.path.expanduser("~"), "Ghost_Data"))

# Docker'a geçildiğinde True yapılacak ve HTTP üzerinden masaüstü servisine bağlanılacak
USE_LOCAL_BRIDGE = os.getenv("USE_LOCAL_BRIDGE", "False").lower() == "true"
LOCAL_BRIDGE_URL = os.getenv("LOCAL_BRIDGE_URL", "http://host.docker.internal:8000/execute")

# Masaüstü uygulaması Docker'daki Core API'yi mi kullanacak?
# Yerel çalıştırmada False bırak. Docker'da çalıştırırken USE_DOCKER_CORE=True ortam değişkeniyle override et.
USE_DOCKER_CORE = os.getenv("USE_DOCKER_CORE", "False").lower() == "true"
CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8001/chat")

# Veritabanları (EpisodicDB, ChromaDB)
DB_DIR = os.path.join(GHOST_DATA_DIR, "db")

# Loglar
LOG_DIR = os.path.join(GHOST_DATA_DIR, "logs")

# Geçici dosyalar (Screenshot, geçici okumalar vb.)
TEMP_DIR = os.path.join(GHOST_DATA_DIR, "temp")

# Klasörleri otomatik oluştur
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ── Kullanıcı Tercihleri (Tema, Dil, Kurallar) ──────────────────────────────
import json
USER_PREFS_FILE = os.path.join(GHOST_DATA_DIR, "user_prefs.json")

def load_user_prefs() -> dict:
    import uuid
    defaults = {
        "theme_bg": "#1e1e24",
        "theme_fg": "#ffffff",
        "language": "Türkçe",
        "custom_rules": "",
        "ghost_token": uuid.uuid4().hex  # Güvenlik için varsayılan token
    }
    if not os.path.exists(USER_PREFS_FILE):
        save_user_prefs(defaults)
        return defaults
    try:
        with open(USER_PREFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # Eksik anahtarları (özellikle token'ı) default ile doldur
            changed = False
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
                    changed = True
            
            if changed:
                save_user_prefs(data)
                
            return data
    except Exception:
        return defaults

def save_user_prefs(prefs: dict):
    with open(USER_PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=4)

_prefs_cache = load_user_prefs()
GHOST_TOKEN = _prefs_cache.get("ghost_token")
