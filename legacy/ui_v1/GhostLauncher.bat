@echo off
title Ghost Operator V2 Launcher
color 0A

echo ===================================================
echo             GHOST OPERATOR V2 BASLATILIYOR
echo ===================================================
echo.
echo Ghost arayuzu yukleniyor... Lutfen bekleyin.

REM Eğer venv klasörü varsa onu aktif et
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Arka planda Local Bridge'i başlat (FastAPI)
echo Local Bridge (Masaustu Koprusu) baslatiliyor...
start /b python -m uvicorn local_bridge.main:app --host 0.0.0.0 --port 8000 > nul 2>&1

REM Arayüzü Başlat
python main.py

echo Kapatiliyor...
exit
