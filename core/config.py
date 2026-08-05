import os

# Docker'a geçtiğimizde bunu environment variable olarak vereceğiz (Örn: /app/data)
# Şimdilik masaüstünde çalıştığı için kullanıcı dizininde sabit bir klasör seçiyoruz.
GHOST_DATA_DIR = os.getenv("GHOST_DATA_DIR", os.path.join(os.path.expanduser("~"), "Ghost_Data"))

# Docker'a geçildiğinde True yapılacak ve HTTP üzerinden masaüstü servisine bağlanılacak
USE_LOCAL_BRIDGE = os.getenv("USE_LOCAL_BRIDGE", "False").lower() == "true"
LOCAL_BRIDGE_URL = os.getenv("LOCAL_BRIDGE_URL", "http://host.docker.internal:8000/execute")

# Masaüstü uygulaması Docker'daki Core API'yi mi kullanacak?
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
