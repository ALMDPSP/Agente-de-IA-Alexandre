# Alexandre AI — V6 Central Pessoal

Esta versão transforma o projeto em uma central pessoal funcional, ainda sem banco de dados.

## Recursos

### Segurança
- Login por e-mail e senha
- MFA TOTP com Microsoft Authenticator / Google Authenticator
- Sessão protegida
- Limite de tentativas MFA

### Agente IA
- Groq → Gemini → Cloudflare
- Histórico de conversa local
- Projeto ativo enviado como contexto
- Fontes do projeto usadas como conhecimento privado

### Projetos pessoais
- Criar
- Editar
- Excluir
- Definir projeto ativo
- Status do projeto
- Fontes vinculadas ao projeto

### Arquivos locais
Formatos suportados:
- PDF
- DOCX
- XLSX / XLSM
- TXT
- Markdown
- CSV
- JSON
- XML
- HTML
- LOG

O arquivo é processado em memória. O original não é persistido no Render.

### Microsoft
Integração OAuth com Microsoft Graph:
- OneNote
- OneDrive

Permissões delegadas:
- User.Read
- Notes.Read
- Files.Read

### Histórico
- Registro das perguntas feitas ao agente
- Pesquisa no histórico
- Reutilização da pergunta
- Exclusão individual
- Botão "Limpar histórico"

### Backup
- Exportar projetos, fontes e histórico em JSON
- Restaurar backup em outro navegador/computador

---

# Importante: sem banco de dados

Projetos, fontes importadas e histórico ficam no `localStorage` do navegador.

O Render Free tem filesystem efêmero, portanto o aplicativo não tenta guardar uploads no disco do servidor.

Use a função **Backup e restauração** para proteger seus dados locais.

A autenticação Microsoft é armazenada em sessão do servidor. Se o serviço do Render reiniciar ou ficar inativo e for recriado, talvez seja necessário clicar novamente em **Conectar Microsoft**.

---

# Configurar Microsoft Graph

Você precisa criar um App Registration na Microsoft.

## 1. Criar o aplicativo

Acesse o Microsoft Entra Admin Center / App registrations e crie um novo registro.

Para conta pessoal Microsoft, escolha um tipo de conta que permita:
- contas organizacionais
- contas pessoais Microsoft

## 2. Redirect URI

Tipo: Web

Use exatamente:

```text
https://SEU-SERVICO.onrender.com/microsoft/callback
```

Exemplo:

```text
https://agente-ia-alexandre.onrender.com/microsoft/callback
```

## 3. API permissions

Microsoft Graph — Delegated permissions:

```text
User.Read
Notes.Read
Files.Read
```

## 4. Client secret

Crie um Client Secret e salve o **Value** imediatamente.

Nunca coloque esse segredo no GitHub.

## 5. Render → Environment

Adicione:

```text
MS_CLIENT_ID=<Application (client) ID>
MS_CLIENT_SECRET=<secret Value>
MS_TENANT=common
MS_REDIRECT_URI=https://SEU-SERVICO.onrender.com/microsoft/callback
```

Depois salve e faça novo deploy.

---

# Variáveis completas

```text
SECRET_KEY
ADMIN_NAME
ADMIN_EMAIL
ADMIN_PASSWORD

MFA_ENABLED
MFA_SETUP_ENABLED

GROQ_API_KEY
GROQ_MODEL

GEMINI_API_KEY
GEMINI_MODEL

CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_MODEL

MS_CLIENT_ID
MS_CLIENT_SECRET
MS_TENANT
MS_REDIRECT_URI
```

---

# Deploy Render

Build:

```text
pip install -r requirements.txt
```

Start:

```text
gunicorn app:app
```
