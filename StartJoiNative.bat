@echo off
TITLE Joi Native Tray
ECHO Starting Joi native tray launcher...
ECHO ----------------------------------
ECHO Tray launcher will start the local API and web UI.
ECHO Press Ctrl+C here only if running without a packaged tray build.
ECHO ----------------------------------

cd /d "%~dp0"
python desktop\tray_app.py
