@echo off
setlocal EnableExtensions
cd /d "%~dp0"

fltmc >nul 2>&1
if errorlevel 1 (
  echo Solicitando permissao de administrador...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

if not exist ".git" (
  echo ERRO: execute este instalador na raiz do repositorio relatoriov3aut.
  echo Pasta esperada: C:\Users\werlley.batista\Documents\GitHub\relatoriov3aut
  pause
  exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
  echo ERRO: Git nao foi encontrado.
  pause
  exit /b 1
)

where py >nul 2>&1
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo ERRO: Python 3 nao foi encontrado.
    pause
    exit /b 1
  )
  set "PY=python"
)

echo [1/7] Atualizando o codigo do GitHub...
git pull --rebase --autostash
if errorlevel 1 goto :falha

echo [2/7] Preservando e preparando a configuracao local...
%PY% -m scripts.preparar_producao
if errorlevel 1 goto :falha

echo [3/7] Fazendo backup e pausando a automacao anterior...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\gerenciar_tarefas_producao.ps1" -Mode Prepare -RepoDir "%~dp0."
if errorlevel 1 goto :rollback

echo [4/7] Garantindo o frontend modular no GitHub...
call "%~dp0scripts\garantir_frontend_modular.bat"
if errorlevel 1 goto :rollback

echo [5/7] Instalando dependencias Python...
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto :rollback

echo [6/7] Validando uma atualizacao completa e o envio automatico...
call "%~dp0atualizar_silencioso.bat"
if errorlevel 1 goto :rollback

echo [7/7] Ativando a nova tarefa a cada 5 minutos...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\gerenciar_tarefas_producao.ps1" -Mode Activate -RepoDir "%~dp0."
if errorlevel 1 goto :rollback

echo.
echo INSTALACAO CONCLUIDA.
echo A tarefa "Atualizar Dashboard Almoxarifado V2" esta ativa.
echo Os proximos dados serao enviados automaticamente ao GitHub.
echo Site: https://werlleybatista01.github.io/relatoriov3aut/
pause
exit /b 0

:rollback
echo A validacao falhou. Reativando a automacao anterior...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\gerenciar_tarefas_producao.ps1" -Mode Rollback -RepoDir "%~dp0."

:falha
echo.
echo INSTALACAO NAO CONCLUIDA.
echo Consulte atualizacao_log.txt e tente novamente.
pause
exit /b 1
