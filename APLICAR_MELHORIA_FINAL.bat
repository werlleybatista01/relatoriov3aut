@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Sincronizando com o GitHub...
git pull --rebase --autostash
if errorlevel 1 goto :erro

echo [2/4] Preparando a melhoria visual...
git add -- assets/css/style.css src/modules/bags.js tests/architecture.test.js tests/core.test.js APLICAR_MELHORIA_FINAL.bat
if errorlevel 1 goto :erro

git diff --cached --quiet
if not errorlevel 1 goto :sem_alteracao

echo [3/4] Criando o commit...
git commit -m "Adiciona resumo mensal de consumo de sacolas"
if errorlevel 1 goto :erro

echo [4/4] Enviando ao GitHub...
git push origin main
if errorlevel 1 goto :erro

echo.
echo MELHORIA PUBLICADA COM SUCESSO.
echo A automacao permanece ativa e atualizara os dados normalmente.
echo Site: https://werlleybatista01.github.io/relatoriov3aut/
goto :fim

:sem_alteracao
echo.
echo A melhoria ja esta aplicada. Nenhum novo commit foi necessario.
goto :fim

:erro
echo.
echo NAO FOI POSSIVEL PUBLICAR A MELHORIA.
echo Nenhuma tarefa agendada foi removida ou alterada.
echo Envie a mensagem exibida acima para analise.

:fim
pause
endlocal
