@echo off
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m scripts.atualizar_dashboard
) else (
  python -m scripts.atualizar_dashboard
)
set "RESULTADO=%errorlevel%"
echo.
if "%RESULTADO%"=="0" (
  echo Atualizacao concluida com sucesso.
) else (
  echo A atualizacao falhou. Consulte atualizacao_log.txt.
)
pause
exit /b %RESULTADO%
