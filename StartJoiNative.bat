@echo off
TITLE Joi Native Tray
ECHO Starting Joi native tray launcher...
ECHO ----------------------------------
ECHO Tray launcher will start the local API and web UI.
ECHO Press Ctrl+C here only if running without a packaged tray build.
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
