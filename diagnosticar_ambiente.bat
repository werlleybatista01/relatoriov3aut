@echo off
cd /d "%~dp0"
set /p ORIGEM=Informe a pasta da automacao atual:
python -m scripts.diagnosticar_ambiente "%ORIGEM%"
pause
