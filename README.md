# Dashboard Profissional do Almoxarifado

**Versão:** 2.0.0

**Status:** produção.

## Como funciona

```text
backup Access fechado mais recente
  → scripts/atualizar_dashboard.py
  → regras operacionais validadas
  → data/dashboard-data.js
  → downloads/relatorio_almoxarifado_2026.xlsx
  → commit e push automáticos
  → front-end modular
```

O Python atualiza somente o arquivo de dados e a planilha. O `index.html`, o
CSS e os módulos JavaScript não são reescritos a cada ciclo.

## Instalação da automação de produção

No computador que já executava a V8:

1. Atualize este repositório com `git pull`.
2. Execute `instalar_producao.bat` como administrador.
3. Aguarde a mensagem de instalação concluída.

O pacote externo também oferece `PUBLICAR_E_INSTALAR.bat`: ele publica somente
os caminhos listados em `ARQUIVOS_PUBLICACAO.txt` e inicia o instalador apenas
depois que o envio ao GitHub termina com sucesso.

O instalador:

- preserva o `config.env` e a senha já existentes;
- copia a configuração legada quando necessário;
- faz backup da pasta antiga da automação;
- desativa, sem excluir, a tarefa agendada anterior;
- instala as dependências Python;
- executa uma atualização real de validação;
- cria a tarefa `Atualizar Dashboard Almoxarifado V2` a cada 5 minutos;
- reativa a tarefa anterior automaticamente se a validação falhar.

Para desfazer a troca, execute `restaurar_automacao_anterior.bat`.

## Segurança da publicação

A produção é preparada obrigatoriamente com:

```env
HOMOLOGATION_MODE=false
GIT_PUSH=true
INCLUDE_PERSONAL_DATA=false
ALLOW_PUBLIC_PERSONAL_DATA=false
DIRECT_WHATSAPP_ENABLED=false
```

Nomes e números de retirada recebem identificadores estáveis; observações,
responsável pelo registro e telefones não são publicados. `config.env`, banco
Access, classificação privada, logs, estado e lock permanecem fora do Git.

## Testes

```text
npm install
npm test
npm run check:syntax
python -m unittest discover -s tests -p "test_*.py"
```

O módulo Sacolas usa 90 dias como ponto de reposição: acima de 120 dias é
seguro; de 91 a 120 dias exige atenção; em 90 dias ou menos recomenda compra.

Leia `docs/migracao.md`, `docs/seguranca.md` e
`docs/regras-de-negocio.md` para os detalhes.
