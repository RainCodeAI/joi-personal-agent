@echo off
TITLE Joi Web Stack
ECHO Starting Joi primary web stack...
ECHO ----------------------------------
ECHO Backend:  http://localhost:8000
ECHO Frontend: http://localhost:3000
ECHO ----------------------------------

cd /d "%~dp0"

if "%JOI_API_TOKEN%"=="" (
  for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).TrimEnd('=').Replace('+','-').Replace('/','_')"`) do set "JOI_API_TOKEN=%%T"
)
REM The frontend reaches the backend through its same-origin /api/backend proxy,
REM which injects JOI_API_TOKEN server-side. The token is intentionally NOT
REM exposed to the browser as NEXT_PUBLIC_JOI_API_TOKEN.

start "Joi API" cmd /k "cd /d ""%~dp0"" && python -m uvicorn app.api.main:app --reload"
start "Joi Web" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
