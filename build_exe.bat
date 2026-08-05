@echo off
echo Ghost 2.0 Uygulamasi Derleniyor...
echo Bu islem birkac dakika surebilir. Lutfen bekleyin.

REM PyInstaller yuklu degilse yukle
pip install pyinstaller

REM Gerekli klasorleri (UI, Assets, Local Bridge) dahil ederek derle
REM windowed: Konsol penceresi gorunmesin
REM onefile: Tek bir exe olsun (biraz yavas acilabilir ama tasimasi kolay)
REM icon= (Istersen bir icon eklenebilir)

pyinstaller --noconfirm --onefile --windowed --add-data "ui;ui" --add-data "local_bridge;local_bridge" --add-data "core;core" GhostApp.py

echo Derleme tamamlandi!
echo ghost_app.exe "dist" klasoru icerisinde bulunabilir.
exit
