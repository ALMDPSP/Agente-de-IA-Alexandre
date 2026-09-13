# Agente de IA Alexandre — versão sem banco

Central pessoal com login, dashboard responsivo e interface inicial para um Agente de IA.

## Stack

- Python + Flask
- Flask-Login
- HTML + CSS + JavaScript
- Gunicorn
- Render
- GitHub

## Esta versão NÃO usa banco de dados

O login é validado usando variáveis de ambiente configuradas no Render:

- `ADMIN_NAME`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `SECRET_KEY`

O histórico da conversa é salvo no `localStorage` do navegador.

## Recursos

- Login
- Sessão autenticada
- Proteção CSRF
- Dashboard responsivo
- Menu lateral mobile/desktop
- Área de conversa com rolagem
- Histórico local no navegador
- Endpoint inicial `/api/agent`
- Health check `/health`
- Estrutura pronta para Groq → Gemini → Cloudflare AI

## Deploy no Render

Build Command:

```text
pip install -r requirements.txt
```

Start Command:

```text
gunicorn app:app
```

Variáveis:

```text
SECRET_KEY
ADMIN_NAME
ADMIN_EMAIL
ADMIN_PASSWORD
```

O `render.yaml` já está pronto para criar essas configurações.

## Segurança

Nunca coloque chaves de IA, senha administrativa ou `SECRET_KEY` dentro do código.

Não envie o arquivo `.env` para o GitHub.

## Próxima etapa

Conectar o endpoint `/api/agent` ao fallback:

```text
Groq → Gemini → Cloudflare AI
```
