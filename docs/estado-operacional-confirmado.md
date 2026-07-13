# Estado operacional confirmado em 13/07/2026

## Conclusões

- O arquivo chamado pelos BATs é `atualizar_index_github.py`.
- Esse arquivo se identifica como **V8**.
- O arquivo V9 existe separadamente, mas não substituiu o nome ativo.
- O estado local registra `version: 8`.
- O Agendador foi configurado para executar a cada **5 minutos**.
- O `config.env` aponta o `index.html` para o repositório local do GitHub.
- Portanto, o `index.html` existente na pasta `automacao` não é a cópia
  operacional mais atual e não deve ser usado como fonte final do front-end.
- O log mostra execuções estáveis até 15:46 de 10/07/2026.
- Às 15:56 iniciou uma execução que deixou o lock ativo; as execuções
  posteriores foram bloqueadas. Antes de remover um lock, é obrigatório
  confirmar no Gerenciador de Tarefas que não existe processo Python ativo.

## Classificação V9 disponível

O cadastro enviado possui 504 códigos:

- 66 devolvíveis;
- 86 de uso permanente;
- 43 consumíveis;
- 90 ignorados;
- 219 não classificados.

Os 219 itens não classificados permanecem fora da cobrança até revisão.

## Consequência para a migração

A versão modular usa a lógica V9, mas não deve substituir a produção de uma
vez. A homologação precisa comparar o resultado V8 atual com a saída V9
modular e explicar todas as diferenças, principalmente em Ferramentas.
