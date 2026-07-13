@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".git" (
  echo ERRO: extraia este hotfix na raiz do repositorio relatoriov3aut.
  pause
  exit /b 1
)

schtasks /End /TN "Atualizar Dashboard Almoxarifado V2" >nul 2>&1

git pull --rebase --autostash
if errorlevel 1 goto :falha

git add -- APLICAR_HOTFIX2.bat CHANGELOG.md scripts/atualizar_dashboard.py src/core/formatters.js tests/core.test.js tests/test_updater.py
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Evita atualizacoes repetidas sem mudanca nos dados"
  if errorlevel 1 goto :falha
)

git push origin main
if errorlevel 1 goto :falha

call "%~dp0atualizar_silencioso.bat"
if errorlevel 1 goto :falha

echo.
echo HOTFIX 2 APLICADO COM SUCESSO.
echo A tarefa V2 continuara executando a cada 5 minutos, mas so publicara
echo quando os dados mudarem ou quando virar a data de referencia.
pause
exit /b 0

:falha
echo.
echo Nao foi possivel aplicar o Hotfix 2.
echo A tarefa agendada continua cadastrada e tentara novamente no proximo ciclo.
pause
exit /b 1
