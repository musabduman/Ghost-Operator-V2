FROM python:3.11-slim

WORKDIR /app

# Sistem gereksinimleri (Playwright veya diğer araçlar için gerekirse)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Gereksinimleri yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Çekirdek kodu kopyala
COPY . .

# Ortam değişkenleri
ENV PYTHONUNBUFFERED=1
ENV GHOST_DATA_DIR=/app/Ghost_Data
ENV USE_LOCAL_BRIDGE=True
ENV LOCAL_BRIDGE_URL=http://host.docker.internal:8000/execute

# Portu aç
EXPOSE 8001

# Core sunucuyu başlat
CMD ["uvicorn", "core_server:app", "--host", "0.0.0.0", "--port", "8001"]
