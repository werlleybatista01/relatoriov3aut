@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

if not exist "templates\index.modular.html" (
  echo ERRO: template modular nao encontrado.
  exit /b 1
)

git pull --rebase --autostash
if errorlevel 1 exit /b 1

copy /Y "templates\index.modular.html" "index.html" >nul
git add -- index.html
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Restaura frontend modular v2.0"
  if errorlevel 1 exit /b 1
)

git push origin main
if not errorlevel 1 exit /b 0

echo O primeiro envio foi recusado. Sincronizando e tentando novamente...
git pull --rebase --autostash
if errorlevel 1 exit /b 1
copy /Y "templates\index.modular.html" "index.html" >nul
git add -- index.html
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Restaura frontend modular v2.0"
  if errorlevel 1 exit /b 1
)
git push origin main
exit /b %errorlevel%
