# MVP Funil CLT

Pagina mobile-first de pre-qualificacao para campanha de Meta Ads de credito consignado CLT.

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

O arquivo `script.js` ja dispara eventos em `window.dataLayer` e tambem chama `fbq("trackCustom")` caso o Meta Pixel seja instalado depois.

Eventos:

- `ViewContent`
- `StartQuiz`
- `Question1`
- `Question2`
- `Question3`
- `QualifiedLead`
- `WhatsAppClick`

## Publicar no GitHub Pages

1. Crie um repositorio no GitHub.
2. Envie `index.html`, `styles.css`, `script.js` e `README.md`.
3. Va em `Settings > Pages`.
4. Em `Build and deployment`, selecione `Deploy from a branch`.
5. Escolha a branch `main` e a pasta `/root`.
6. Salve e aguarde o link do GitHub Pages.
