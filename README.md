# Agente de IA Alexandre — V4 com MFA

Versão pessoal sem banco de dados, com login futurista, dupla autenticação TOTP e Agente IA com fallback.

## Fluxo de acesso

```text
E-mail + senha
      ↓
MFA / Authenticator
      ↓
Dashboard
      ↓
Agente IA
```

Compatível com:

- Microsoft Authenticator
- Google Authenticator
- Outros aplicativos TOTP compatíveis

## Variáveis do Render

### Login

```text
SECRET_KEY
ADMIN_NAME
ADMIN_EMAIL
ADMIN_PASSWORD
```

### MFA

```text
MFA_ENABLED=true
MFA_SETUP_ENABLED=true
```

`MFA_SETUP_ENABLED=true` deve ser usado somente durante o primeiro pareamento.

## Primeiro pareamento do Authenticator

1. Faça o deploy com:
   - `MFA_ENABLED=true`
   - `MFA_SETUP_ENABLED=true`
2. Acesse o site.
3. Digite e-mail e senha.
4. Na tela MFA, clique em **Configurar QR Code**.
5. Leia o QR Code com Microsoft Authenticator ou Google Authenticator.
6. Digite o código de 6 dígitos.
7. Confirme o acesso ao Dashboard.
8. Volte ao Render e altere:

```text
MFA_SETUP_ENABLED=false
```

9. Salve e faça novo deploy.

A partir daí o QR Code de configuração deixa de ficar disponível.

## Atenção ao SECRET_KEY

A chave TOTP é derivada de `SECRET_KEY`.

**Não altere o `SECRET_KEY` depois de configurar o Authenticator.**

Se alterar, será necessário ativar temporariamente `MFA_SETUP_ENABLED=true` e parear novamente o aplicativo.

## IA

Ordem de fallback:

```text
Groq → Gemini → Cloudflare
```

Variáveis:

```text
GROQ_API_KEY
GROQ_MODEL

GEMINI_API_KEY
GEMINI_MODEL

CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_MODEL
```

## Deploy

Build:

```text
pip install -r requirements.txt
```

Start:

```text
gunicorn app:app
```

## Segurança

- Nunca envie `.env` para o GitHub.
- Nunca coloque API Keys no JavaScript.
- Após configurar MFA, desative `MFA_SETUP_ENABLED`.
- O login MFA tem validade de 5 minutos para concluir a segunda etapa.
- Após 5 códigos MFA incorretos, é necessário iniciar o login novamente.
