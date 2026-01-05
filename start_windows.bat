@echo off
setlocal
cd /d %~dp0

echo === Moderacion de resenas (localhost) v3 ===

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual...
  py -3.11 -m venv .venv 2>nul
  if errorlevel 1 (
    python -m venv .venv
  )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python app.py
pause
