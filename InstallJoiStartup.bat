@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Startup'), 'Joi.lnk')); $shortcut.TargetPath = [IO.Path]::Combine('%~dp0', 'StartJoiNative.bat'); $shortcut.WorkingDirectory = '%~dp0'; $shortcut.WindowStyle = 7; $shortcut.Save()"
if errorlevel 1 (
  echo Failed to install Joi startup shortcut.
  exit /b 1
)
echo Joi will start when you sign in.
