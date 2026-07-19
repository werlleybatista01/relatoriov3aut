# MVP Funil CLT

Página mobile-first de pré-qualificação para campanha de Meta Ads de crédito consignado CLT.

## Como configurar o WhatsApp

Abra `script.js` e troque:

```js
whatsappNumber: "5599999999999"
```

Use o formato com codigo do pais e DDD, sem espacos. Exemplo:

```js
whatsappNumber: "5511999999999"
```

## Eventos preparados para tracking

O arquivo `script.js` já dispara eventos em `window.dataLayer` e também chama `fbq("trackCustom")` caso o Meta Pixel seja instalado depois.

Eventos:

- `ViewContent`
- `StartQuiz`
- `Question1`
- `Question2`
- `Question3`
- `QualifiedLead`
- `DisqualifiedLead`
- `WhatsAppClick`

## Regra aplicada no MVP

O lead só chega ao botão de WhatsApp como qualificado quando informa que:

- trabalha com carteira assinada;
- está há pelo menos 6 meses no emprego atual.

Quem marca menos de 6 meses recebe uma tela informando que, neste momento, o crédito CLT pode não estar disponível.

## Publicar no GitHub Pages

1. Crie um repositorio no GitHub.
2. Envie `index.html`, `styles.css`, `script.js` e `README.md`.
3. Vá em `Settings > Pages`.
4. Em `Build and deployment`, selecione `Deploy from a branch`.
5. Escolha a branch `main` e a pasta `/root`.
6. Salve e aguarde o link do GitHub Pages.
