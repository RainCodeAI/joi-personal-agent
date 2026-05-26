@echo off
TITLE Joi Desktop Window
ECHO Starting Joi desktop window...
ECHO ----------------------------------
ECHO This starts the local API, Next.js UI, tray, and native desktop shell.
ECHO ----------------------------------

cd /d "%~dp0"
python desktop\tray_app.py
