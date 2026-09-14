# Alexandre AI — Agente de IA pessoal

Aplicação Flask com autenticação, MFA, fallback entre provedores de IA, base de conhecimento por projeto e persistência PostgreSQL.

## Arquitetura

- **Frontend:** HTML/CSS/JavaScript responsivo.
- **Backend:** Flask + Gunicorn.
- **IA:** fallback Groq → Gemini → Cloudflare conforme as chaves configuradas.
- **Banco:** PostgreSQL, preparado para Aiven.
- **Hospedagem:** preparado para Render.
- **Segurança:** login, MFA TOTP, CSRF, cookies HttpOnly/SameSite e conexão PostgreSQL via SSL.

## Persistência PostgreSQL

Projetos, documentos, chunks, conversa, histórico e projeto ativo são armazenados no PostgreSQL. O navegador não é mais a fonte de persistência.

Para usuários vindos da versão antiga, existe uma migração automática: se o banco estiver vazio e houver dados antigos no `localStorage`, eles são enviados uma única vez ao PostgreSQL e as chaves antigas são removidas do navegador.

## Variáveis obrigatórias

```text
SECRET_KEY
ADMIN_EMAIL
ADMIN_PASSWORD
DATABASE_URL
```

Para MFA:

```text
MFA_ENABLED=true
MFA_SETUP_ENABLED=false
```

Configure pelo menos um provedor de IA:

```text
GROQ_API_KEY
GEMINI_API_KEY
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
```

## DATABASE_URL do Aiven

Use o formato:

```text
postgres://avnadmin:SENHA@HOST:PORTA/BANCO?sslmode=require
```

Nunca grave a senha diretamente no repositório. No Render, configure a URL em **Environment → DATABASE_URL**.

## Deploy no Render

O `render.yaml` já está preparado. O build instala as dependências e o serviço inicia com:

```text
gunicorn app:app
```

Ao iniciar, a aplicação cria automaticamente as tabelas necessárias se `DATABASE_URL` estiver configurada.

Mais detalhes: consulte `DATABASE_AIVEN.md`.

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
python app.py
```

## Backup

A tela de backup continua disponível. O arquivo JSON exportado agora representa os dados persistidos no PostgreSQL e pode ser restaurado pela própria interface.
