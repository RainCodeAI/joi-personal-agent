@echo off
TITLE Joi Personal Agent
ECHO Starting Joi System...
ECHO ----------------------------------
ECHO Mode: Full Features (Vision/Voice/Memory Active)
ECHO ----------------------------------

:: Navigate to the script's directory
cd /d "%~dp0"

:: Check if .env exists
IF NOT EXIST .env (
    ECHO Warning: .env file not found!
    PAUSE
)

:: Launch the Tray App using the local python environment
python desktop/tray_app.py

:: Pause only if it crashes immediately
IF %ERRORLEVEL% NEQ 0 (
    ECHO.
    ECHO Joi crashed with error code %ERRORLEVEL%.
    PAUSE
)
