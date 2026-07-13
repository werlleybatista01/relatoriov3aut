@echo off
setlocal EnableExtensions
set "REPO=%USERPROFILE%\Documents\GitHub\relatoriov3aut"
set "REMOTE=https://github.com/werlleybatista01/relatoriov3aut.git"

where git >nul 2>&1
if errorlevel 1 (
  echo ERRO: Git nao foi encontrado neste computador.
  pause
  exit /b 1
)

if not exist "%REPO%\.git" (
  echo Baixando o repositorio de producao...
  if not exist "%USERPROFILE%\Documents\GitHub" mkdir "%USERPROFILE%\Documents\GitHub"
  git clone "%REMOTE%" "%REPO%"
  if errorlevel 1 goto :falha
) else (
  echo Atualizando os arquivos de producao...
  git -C "%REPO%" pull --rebase --autostash
  if errorlevel 1 goto :falha
)

call "%REPO%\instalar_producao.bat"
exit /b %errorlevel%

:falha
echo.
echo Nao foi possivel atualizar o repositorio.
echo Nenhuma tarefa do Windows foi alterada.
pause
exit /b 1
