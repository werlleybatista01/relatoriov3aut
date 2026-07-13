# Changelog

## 2.0.0 — Produção

- Front-end modular promovido para produção no lugar do `index.html` monolítico V8.
- Atualização automática preservada a cada 5 minutos, agora alterando apenas dados e planilha.
- Adicionado instalador que reaproveita a configuração local, faz backup e troca as tarefas com rollback.
- Corrigido o Git para versionar os artefatos públicos gerados pela automação.
- Publicação configurada sem nomes, telefones, observações ou outros dados pessoais.
- Incorporada a regra beta.6: 90 dias é ponto de reposição e a faixa segura começa acima de 120 dias.
- Corrigida a passagem do caminho do repositório ao PowerShell quando `%~dp0` termina com barra invertida.
- Adicionada restauração automática do `index.html` modular depois que a tarefa V8 é pausada.

## 2.0.0-beta.6 — Ponto de reposição e semáforo de decisão

- Corrigida a regra de compra: 90 dias agora é o ponto de reposição, não uma situação segura.
- Acima de 120 dias: situação segura em verde.
- De 91 a 120 dias: atenção em amarelo.
- Em 90 dias ou menos: providenciar compra em vermelho.
- Faixas críticas abaixo de 60 e 30 dias permanecem vermelhas, com texto de urgência crescente.
- Removida da decisão principal a regra inadequada baseada em prazo fixo de 14 dias.
- Cartão de estoque, status e recomendação agora usam cor integral conforme a decisão.
- Tela de estoque passou a chamar 90 dias de ponto de reposição e explicar que não é o estoque final desejado após a compra.

## 2.0.0-beta.5 — Visão geral executiva de Sacolas

- Removidos os filtros de período, ano e tipo da Visão geral.
- A Visão geral agora sempre abre com o período operacional atual e sem filtros ocultos.
- Estoque atual foi transformado em um painel destacado ao lado dos insights.
- Insights importantes e decisão recomendada foram agrupados na coluna executiva.
- Os cartões superiores ficaram restritos a consumo, cobertura, esgotamento e tendência.
- Mantidos filtros completos nas áreas Estoque, Sazonalidade, Colaboradores, Comparações e Relatórios.
- Ajustada a responsividade da coluna executiva para computador, tablet e celular.

## 2.0.0-beta.4 — Sacolas com navegação analítica

- Transformada a página Sacolas em miniaplicativo com navegação lateral interna.
- Visão geral simplificada para decisão: estoque, consumo, cobertura, esgotamento, tendência, gráfico principal e recomendação.
- Criadas áreas separadas de Estoque, Sazonalidade, Colaboradores, Comparações e Relatórios.
- Comparação mensal usa o mesmo número de dias para evitar distorção de mês incompleto.
- Adicionado simulador de entrada sem alterar o estoque real.
- Adicionado download CSV das linhas filtradas na área Relatórios.
- Barra lateral vira navegação horizontal compacta em telas menores.
- Mantidas as regras matemáticas auditáveis, a pseudonimização e as travas de homologação.

## 2.0.0-beta.3 — Dashboard inteligente de Sacolas

- Remodelação exclusiva da página Sacolas inspirada em painel executivo de decisão.
- Filtros por data, 2025, 2026, período geral, colaborador, produto e setor opcional.
- Indicadores de estoque, consumo do último mês filtrado, média diária, cobertura em dias, status de compra e tendência.
- Projeção mensal por média móvel, tendência linear e cálculo auditável de meta de 90 dias.
- Ranking de colaboradores, participação por setor ou tipo, mapa de dias/horários e insights por regras.
- Recomendação arredondada para pacotes fechados e fórmula exibida na interface.
- Comportamento seguro quando setor ou horário não estão disponíveis no Access.
- Mantidas as correções visuais anteriores do módulo Ferramentas.

## 2.0.0-beta.2 — 13/07/2026

- Sincronizada a biblioteca de regras com o arquivo V9 realmente enviado.
- Confirmado que o script ativo e o estado operacional ainda são V8.
- Registrado que o `index.html` da pasta `automacao` está desatualizado.
- Criado diagnóstico seguro do ambiente legado.
- Adicionadas travas de homologação e publicação.
- Adicionada pseudonimização de dados pessoais por padrão.
- Telefones continuam fora do payload quando WhatsApp direto está desligado.
- Corrigida a tela de Ferramentas para não exibir “sem telefone” quando a
  integração direta está desativada.
- Estado e lock da versão modular receberam nomes próprios.
- Instalador do Agendador bloqueado na beta.
- Adicionados testes de segurança, diagnóstico e configuração.
- Criado suplemento privado separado para classificação operacional.

## 2.0.0-beta.1 — 11/07/2026

- Primeira divisão entre HTML, CSS, ES Modules, dados, serviços e domínios.
- Novo atualizador gera somente dados e planilha.
- Adicionados testes, lint, formatação e documentação inicial.
