@echo off
rem Klik dua kali file ini untuk menjalankan Tradecorp CRM di laptop.
rem Pertama kali: otomatis menyiapkan Python, library, .env, dan data contoh.
cd /d "%~dp0"
title Tradecorp CRM

python --version >nul 2>nul
if errorlevel 1 (
  echo Python belum terpasang. Pasang dari https://www.python.org/downloads/windows/
  echo dan centang "Add python.exe to PATH", lalu jalankan file ini lagi.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Menyiapkan pertama kali, tunggu sebentar...
  python -m venv .venv || goto gagal
)

echo Memeriksa library...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || goto gagal

if not exist ".env" (
  ".venv\Scripts\python.exe" -c "import secrets; open('.env','w').write('SECRET_KEY='+secrets.token_hex(32)+'\nCRM_DEMO_NOW=2026-11-12T10:00:00+07:00\n')" || goto gagal
)

if not exist "instance\crm.db" (
  echo Mengisi data contoh...
  ".venv\Scripts\python.exe" -m flask --app run.py seed || goto gagal
)

echo.
echo Aplikasi jalan di http://127.0.0.1:5100  (login: gil / demo123)
echo Tutup jendela ini untuk menghentikan aplikasi.
echo.
start "" cmd /c "timeout /t 4 >nul & start http://127.0.0.1:5100"
".venv\Scripts\python.exe" run.py
pause
exit /b 0

:gagal
echo.
echo Ada yang gagal. Foto layar ini dan kirim ke IT.
pause
exit /b 1
