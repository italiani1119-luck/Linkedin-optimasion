@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python tidak ditemukan. Install Python 3.10+ dari https://python.org lalu jalankan ulang.
  pause
  exit /b 1
)
echo Membuat virtual environment...
python -m venv .venv
if errorlevel 1 (
  echo [X] Gagal membuat virtual environment.
  pause
  exit /b 1
)
echo Memasang dependensi...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Pemasangan normal gagal ^(biasanya karena antivirus/proxy memeriksa SSL^).
  echo Mencoba ulang dengan trusted-host...
  ".venv\Scripts\python.exe" -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
)
if errorlevel 1 (
  echo [X] Gagal memasang dependensi.
  pause
  exit /b 1
)
echo.
echo [OK] Setup selesai. Jalankan run.bat untuk memulai.
pause
