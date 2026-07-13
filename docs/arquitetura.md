# Arquitetura

## Princípios aplicados

1. **Responsabilidade única**: cada módulo possui uma função clara.
2. **Dependência explícita**: módulos recebem seletores, serviços e componentes.
3. **Sem funções globais**: ações usam `data-action` e delegação de eventos.
4. **Dados fora do HTML**: o Python gera `data/dashboard-data.js`.
5. **Main mínimo**: `src/main.js` apenas inicializa.
6. **Contrato versionado**: o payload usa `schemaVersion: 2`.
7. **Testabilidade**: formatadores, seletores e módulos podem ser testados isoladamente.

## Fluxo de dados

O frontend não conhece Access, tabelas nem caminhos locais. Ele consome apenas:

```js
{
  schemaVersion: 2,
  metadata: {},
  features: {},
  withdrawals: [],
  stock: [],
  openTools: []
}
```

## Decisão sobre página única

O dashboard permanece como uma aplicação de página única porque os módulos compartilham dados, navegação e componentes. Isso não significa concentrar tudo em um arquivo.

## Compatibilidade

`scripts/legacy/atualizar_index_github_v9.py` preserva a lógica validada de:

- seleção segura do backup;
- estabilidade do arquivo;
- leitura das cinco tabelas;
- classificação por código;
- devoluções e exclusões;
- botinas por modelo e tamanho;
- conversão de sacolas;
- proteção contra regressão.

O novo `scripts/atualizar_dashboard.py` usa essa lógica, mas gera somente dados e planilha.
