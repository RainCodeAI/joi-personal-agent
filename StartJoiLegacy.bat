@echo off
TITLE Joi Legacy Internal Client
ECHO Starting Joi legacy internal client...
ECHO ----------------------------------
ECHO Mode: Streamlit and tray-based migration fallback
ECHO ----------------------------------

cd /d "%~dp0"

IF NOT EXIST .env (
    ECHO Warning: .env file not found!
    PAUSE
)

python desktop/tray_app.py

IF %ERRORLEVEL% NEQ 0 (
    ECHO.
    ECHO Joi legacy client crashed with error code %ERRORLEVEL%.
    PAUSE
)
