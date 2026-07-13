# Relatório de validação da versão 2.0 beta

Data: 11/07/2026

## Verificações concluídas

- `index.html` sem `<style>` embutido.
- `index.html` sem JavaScript embutido.
- nenhum `onclick`, `oninput` ou `onchange` inline.
- ES Modules com `import` e `export`.
- `main.js` sem regra de negócio.
- módulos separados por responsabilidade.
- dados separados em contrato versionado.
- sintaxe JavaScript validada com `node --check`.
- sintaxe Python validada com `py_compile`.
- 7 testes JavaScript aprovados.
- 2 testes Python aprovados.
- massa de teste sintética, sem dados reais.
- senha e token não incluídos.

## Pendente

- teste com cópia fechada do banco real;
- comparação visual completa;
- teste no Windows com Agendador;
- teste de Git em branch de homologação;
- validação de todos os produtos classificados;
- decisão sobre hospedagem autenticada.
