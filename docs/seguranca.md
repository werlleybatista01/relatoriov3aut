# Segurança

## Melhorias aplicadas

- Remoção de senha do JavaScript.
- WhatsApp direto desativado por padrão.
- Telefone removido do payload público quando o envio direto está desativado.
- Configuração real fora do repositório.
- Banco, logs, lock, estado e classificação ignorados pelo Git.
- Nenhum arquivo `.env` real incluído.

## Risco restante

O GitHub Pages é público. Qualquer dado presente em `dashboard-data.js` pode ser lido por quem acessar o repositório ou o site.

Esta instalação foi ajustada para permitir nomes reais de colaboradores no
dashboard publicado. Para reduzir risco, os telefones continuam bloqueados
quando `DIRECT_WHATSAPP_ENABLED=false`.

Para uma implantação profissional com nomes e retiradas individuais, prefira:

- repositório privado com hospedagem autenticada; ou
- backend protegido; ou
- dashboard público apenas com dados agregados.

## WhatsApp

A solução recomendada é:

```text
Frontend sem telefone
    ↓
n8n autenticado
    ↓
consulta controlada
    ↓
WAHA
```

Não colocar tokens, telefones ou segredos no navegador.
