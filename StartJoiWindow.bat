@echo off
TITLE Joi Desktop Window
ECHO Starting Joi desktop window...
ECHO ----------------------------------
ECHO This starts the local API, Next.js UI, tray, and native desktop shell.
ECHO ----------------------------------

cd /d "%~dp0"
python -c "import webview, pystray, uvicorn" >nul 2>&1
if errorlevel 1 (
  ECHO Required native-launch dependencies are missing from this Python runtime.
  ECHO Install requirements with: python -m pip install -r requirements.txt
  pause
  exit /b 1
)

python desktop\tray_app.py
