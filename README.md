# Alexandre AI

Central pessoal com login, dashboard responsivo e interface inicial para um Agente de IA.

## Stack

- Python + Flask
- PostgreSQL / Neon
- Flask-Login
- SQLAlchemy
- HTML + CSS + JavaScript
- Gunicorn
- Render
- GitHub

## Recursos desta versão

- Login com senha armazenada por hash
- Sessão autenticada
- Proteção CSRF
- Dashboard responsivo
- Menu lateral mobile/desktop
- Card de projetos, tarefas, documentos e memória
- Área de conversa com rolagem
- Endpoint inicial `/api/agent`
- Health check `/health`
- Estrutura pronta para Groq → Gemini → Cloudflare AI
- Blueprint `render.yaml`

## Rodar localmente

### 1. Criar ambiente virtual

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar dependências

```powershell
pip install -r requirements.txt
```

### 3. Criar `.env`

Copie `.env.example` para `.env`.

Para um teste local sem Neon, você pode remover `DATABASE_URL` do `.env`.
Nesse caso o projeto usa SQLite apenas localmente.

Defina:

```env
SECRET_KEY=uma-chave-grande
ADMIN_NAME=Alexandre
ADMIN_EMAIL=seu-email
ADMIN_PASSWORD=sua-senha
```

### 4. Executar

```powershell
python app.py
```

Acesse:

`http://127.0.0.1:5000`

## Subir para o GitHub

No diretório do projeto:

```powershell
git init
git add .
git commit -m "Primeira versão Alexandre AI"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/alexandre-ai.git
git push -u origin main
```

> Nunca envie o arquivo `.env` para o GitHub.

## Configurar Neon

Use a connection string PostgreSQL fornecida pelo Neon como `DATABASE_URL`.

Exemplo:

```text
postgresql://usuario:senha@host/database?sslmode=require
```

O projeto cria a tabela `users` automaticamente no primeiro start.

## Deploy no Render

### Opção A — usando `render.yaml`

1. Envie este projeto ao GitHub.
2. No Render, crie um Blueprint a partir do repositório.
3. Configure as variáveis solicitadas:
   - `DATABASE_URL`
   - `ADMIN_EMAIL`
   - `ADMIN_PASSWORD`
4. O `SECRET_KEY` será gerado pelo Render.
5. Faça o deploy.

### Opção B — Web Service manual

- Runtime: Python
- Build Command:

```text
pip install -r requirements.txt
```

- Start Command:

```text
gunicorn app:app
```

Variáveis:

```text
DATABASE_URL
SECRET_KEY
ADMIN_NAME
ADMIN_EMAIL
ADMIN_PASSWORD
```

## Segurança

- Não coloque chaves de IA no JavaScript/frontend.
- Groq, Gemini e Cloudflare devem ser configurados como variáveis de ambiente no Render.
- Nunca versione `.env`.
- Em produção, utilize sempre o PostgreSQL/Neon; o SQLite local é apenas para desenvolvimento.

## Próxima etapa

Conectar o `/api/agent` ao roteador:

```text
Usuário
   ↓
Flask
   ↓
Agent Router
   ├── Groq
   ├── Gemini
   └── Cloudflare AI
```

Depois disso, adicionar tools/function calling para:

- Projetos
- Tarefas
- Documentos
- Anotações
- Memória/Conhecimento
