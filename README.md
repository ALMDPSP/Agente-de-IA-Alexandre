# Agente de IA Alexandre — V3

Site pessoal sem banco de dados, com login, dashboard e Agente IA usando fallback automático.

## Arquitetura

```text
Usuário
  ↓
Flask no Render
  ↓
Groq
  ↓ falhou/limite
Gemini
  ↓ falhou/limite
Cloudflare Workers AI
```

## Stack

- Python + Flask
- Flask-Login
- OpenAI Python SDK como cliente compatível
- HTML + CSS + JavaScript
- Gunicorn
- Render
- GitHub
- Sem banco de dados

## Variáveis obrigatórias do login

```text
SECRET_KEY
ADMIN_NAME
ADMIN_EMAIL
ADMIN_PASSWORD
```

## Variáveis da IA

Configure pelo menos um provedor.

### Groq

```text
GROQ_API_KEY
GROQ_MODEL=openai/gpt-oss-20b
```

### Gemini

```text
GEMINI_API_KEY
GEMINI_MODEL=gemini-3.8-flash
```

### Cloudflare Workers AI

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_MODEL=@cf/google/gemma-4-26b-a4b-it
```

## Ordem de fallback

A ordem é fixa no backend:

1. Groq
2. Gemini
3. Cloudflare

Se uma credencial não estiver configurada, aquele provedor é ignorado.

## Histórico

O histórico fica no `localStorage` do navegador e não em um banco.
Somente as últimas mensagens são enviadas ao backend como contexto.

## Deploy no Render

Build:

```text
pip install -r requirements.txt
```

Start:

```text
gunicorn app:app
```

Depois de adicionar/alterar variáveis no Render, faça um novo deploy.

## Segurança

Nunca coloque API keys diretamente no GitHub ou no JavaScript.
As chaves devem ficar somente em `Environment` no Render.
