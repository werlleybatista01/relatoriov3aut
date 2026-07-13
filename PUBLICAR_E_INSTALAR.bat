@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".git" (
  echo ERRO: extraia este pacote dentro da pasta do repositorio:
  echo C:\Users\werlley.batista\Documents\GitHub\relatoriov3aut
  pause
  exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
  echo ERRO: Git nao foi encontrado.
  pause
  exit /b 1
)

echo [1/4] Sincronizando com o GitHub...
git pull --rebase --autostash
if errorlevel 1 goto :falha

echo [2/4] Preparando somente os arquivos publicos revisados...
for /f "usebackq delims=" %%F in ("%~dp0ARQUIVOS_PUBLICACAO.txt") do (
  if exist "%%F" git add -- "%%F"
)
if errorlevel 1 goto :falha

git diff --cached --quiet
if errorlevel 1 (
  echo [3/4] Criando o commit de producao...
  git commit -m "Publica dashboard modular v2.0 em producao"
  if errorlevel 1 goto :falha
) else (
  echo [3/4] O commit de producao ja esta preparado.
)

echo [4/4] Enviando ao GitHub...
git push origin main
if errorlevel 1 goto :falha

echo.
echo Publicacao concluida. Iniciando a troca segura da automacao...
call "%~dp0instalar_producao.bat"
exit /b %errorlevel%

:falha
echo.
echo A publicacao nao foi concluida. Nenhuma tarefa do Windows foi alterada.
pause
exit /b 1
