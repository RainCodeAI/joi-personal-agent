@echo off
TITLE Joi Web Stack
ECHO Starting Joi primary web stack...
ECHO ----------------------------------
ECHO Backend:  http://localhost:8000
ECHO Frontend: http://localhost:3000
ECHO Telegram: bridge (enabled if TELEGRAM_BOT_TOKEN is set in .env)
ECHO ----------------------------------

cd /d "%~dp0"

REM Generate a random API token if one is not already set. Uses the .NET
REM Framework RNG (Create().GetBytes) so it works in Windows PowerShell 5.1 —
REM the static GetBytes(int) overload is .NET 6+ only and silently fails on 5.1,
REM which used to leave the token blank/whitespace (illegal HTTP header).
if "%JOI_API_TOKEN%"=="" (
  for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_')"`) do set "JOI_API_TOKEN=%%T"
)
REM The frontend reaches the backend through its same-origin /api/backend proxy,
REM which injects JOI_API_TOKEN server-side. The token is intentionally NOT
REM exposed to the browser as NEXT_PUBLIC_JOI_API_TOKEN.

start "Joi API" cmd /k "cd /d ""%~dp0"" && python -m uvicorn app.api.main:app --reload"
start "Joi Web" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

REM Telegram bridge — launched from the same session, so it inherits the same
REM JOI_API_TOKEN as the backend (they always match). No-ops cleanly if
REM TELEGRAM_BOT_TOKEN is not set in .env, so it is safe to always start.
start "Joi Telegram" cmd /k "cd /d ""%~dp0"" && .venv312\Scripts\python.exe -m app.integrations.telegram_bot"
