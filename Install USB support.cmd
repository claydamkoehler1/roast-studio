@echo off
cd /d "%~dp0"
set "ROAST_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%ROAST_PY%" set "ROAST_PY=python"
"%ROAST_PY%" -m pip install --target .deps -r requirements.txt
pause
