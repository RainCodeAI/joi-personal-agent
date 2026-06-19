@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "$path = [IO.Path]::Combine([Environment]::GetFolderPath('Startup'), 'Joi.lnk'); if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }"
if errorlevel 1 (
  echo Failed to remove Joi startup shortcut.
  exit /b 1
)
echo Joi startup shortcut removed.
