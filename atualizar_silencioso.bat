@echo off
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m scripts.atualizar_dashboard >> atualizacao_log.txt 2>&1
) else (
  python -m scripts.atualizar_dashboard >> atualizacao_log.txt 2>&1
)
exit /b %errorlevel%
