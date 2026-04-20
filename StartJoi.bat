@echo off
TITLE Joi Web Stack
ECHO Starting Joi primary web stack...
ECHO ----------------------------------
ECHO Backend:  http://localhost:8000
ECHO Frontend: http://localhost:3000
ECHO ----------------------------------

cd /d "%~dp0"

start "Joi API" cmd /k "cd /d ""%~dp0"" && python -m uvicorn app.api.main:app --reload"
start "Joi Web" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
