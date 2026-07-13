@echo off
setlocal
cd /d "%~dp0"

echo [1/5] Sincronizando com o GitHub...
git pull --rebase --autostash
if errorlevel 1 goto :erro

echo [2/5] Preparando as melhorias finais...
git add -- index.html templates/index.modular.html assets/css/style.css src/app.js src/main.js src/modules/bags.js tests/architecture.test.js tests/core.test.js APLICAR_MELHORIA_FINAL.bat
if errorlevel 1 goto :erro

git diff --cached --quiet
if not errorlevel 1 goto :sem_alteracao

echo [3/5] Criando o commit...
git commit -m "Finaliza consumo mensal responsivo e atualizacao sem cache"
if errorlevel 1 goto :erro

echo [4/5] Enviando ao GitHub...
git push origin main
if errorlevel 1 goto :erro

echo [5/5] Ajustando a tarefa automatica para 5 minutos...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$n='Atualizar Dashboard Almoxarifado V2'; $g=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5); Set-ScheduledTask -TaskName $n -Trigger $g | Out-Null"
if errorlevel 1 echo AVISO: execute este arquivo como administrador para ajustar o intervalo da tarefa.

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
