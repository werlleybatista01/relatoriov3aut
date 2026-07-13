@echo off
setlocal
cd /d "%~dp0"

fltmc >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\gerenciar_tarefas_producao.ps1" -Mode Rollback -RepoDir "%~dp0."
if errorlevel 1 (
  echo Nao foi possivel concluir o rollback.
) else (
  echo A tarefa V2 foi removida e as tarefas anteriores foram reativadas.
)
pause
