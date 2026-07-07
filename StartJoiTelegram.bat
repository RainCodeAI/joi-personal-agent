@echo off
TITLE Joi Telegram Bridge
cd /d "%~dp0"
ECHO Joi Telegram bridge
ECHO -------------------
ECHO Requires:
ECHO   - the Joi backend already running (StartJoi.bat)
ECHO   - TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USER_IDS set in .env
ECHO   - the bridge and backend must share the SAME JOI_API_TOKEN
ECHO     (set a fixed JOI_API_TOKEN in .env so both processes match)
ECHO.

".venv312\Scripts\python.exe" -m app.integrations.telegram_bot
pause
