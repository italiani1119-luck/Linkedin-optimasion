@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment belum ada. Jalankan setup.bat dulu.
  pause
  exit /b 1
)
set PYTHONIOENCODING=utf-8
echo Dashboard: http://127.0.0.1:8080  (biarkan jendela ini terbuka)
".venv\Scripts\python.exe" app.py
pause
