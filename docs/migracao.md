# Migração para produção

## Procedimento automatizado

1. Executar `git pull` no repositório local.
2. Executar `instalar_producao.bat` como administrador.
3. O instalador prepara `config.env` sem exibir nem substituir a senha.
4. A pasta legada e as ações das tarefas antigas são registradas em um backup no Desktop.
5. As tarefas antigas que chamam a automação V8 são desativadas, não excluídas.
6. O atualizador V2 é executado uma vez e precisa terminar com código zero.
7. Somente após essa validação é criada a tarefa V2, com intervalo de 5 minutos.

Se o passo 6 falhar, o instalador reativa imediatamente as tarefas anteriores.

## Rollback

Execute `restaurar_automacao_anterior.bat`. O script:

1. remove a tarefa V2;
2. lê o registro da migração mais recente;
3. reativa as tarefas V8 que foram desativadas;
4. mantém intactos o backup e todos os arquivos da automação anterior.

O retorno do código publicado pode ser feito pelo histórico do Git. O rollback
local não apaga commits nem dados.
