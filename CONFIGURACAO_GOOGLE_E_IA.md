# Minha Evolução IA — login Google e fallback Gemini/OpenAI

## Render → Environment

- `ADMIN_EMAIL`: e-mail do administrador já existente
- `ADMIN_PASSWORD`: senha do administrador (não compartilhar)
- `SECRET_KEY`: string longa, secreta e estável (essencial para sessão e OAuth)
- `DATABASE_URL`: conexão PostgreSQL persistente (necessário para usuários)
- `GOOGLE_CLIENT_ID`: client ID do OAuth 2.0 Google
- `GOOGLE_CLIENT_SECRET`: client secret do OAuth 2.0 Google
- `GOOGLE_REDIRECT_URI`: `https://SEU-SERVICO.onrender.com/auth/google/callback`
- `GEMINI_API_KEY`: chave do Gemini (opcional se houver OpenAI)
- `GEMINI_MODEL`: modelo de texto e visão habilitado na sua conta
- `OPENAI_API_KEY`: chave da API OpenAI (opcional se houver Gemini)
- `OPENAI_MODEL`: modelo OpenAI com suporte a imagens (padrão `gpt-4.1-mini`)

No Google Cloud Console, crie uma credencial OAuth tipo **Aplicativo da Web** e inclua exatamente a `GOOGLE_REDIRECT_URI` em **URIs de redirecionamento autorizados**. Configure também a tela de consentimento e os usuários de teste, se o app estiver em modo teste. Não comite segredos no GitHub.

## Como o acesso funciona

- Email/senha continua funcionando.
- Google é opcional, só aparece quando as credenciais estiverem configuradas.
- O primeiro login Google cria conta `pending`. Admin aprova em `/admin/usuarios`.
- Conta bloqueada não entra, inclusive com Google.
- Por segurança, contas já criadas com senha não são vinculadas automaticamente só por ter e-mail igual. A vinculação validada pode ser adicionada depois.
- O administrador de ambiente continua entrando com email/senha, não com Google.

## Fallback de IA

- Gemini é usado primeiro se configurado; senão, usa a OpenAI.
- Se Gemini falhar por timeout, HTTP 429 ou erro temporário de servidor, tenta OpenAI se configurada.
- Erros de autenticação/cota não temporária, bloqueios de conteúdo e requisições inválidas **não** são contornados pelo fallback.
- Fotos não são persistidas no aplicativo; são enviadas ao provedor escolhido. Configure aviso de privacidade e consentimento apropriados antes de aceitar usuários reais.
- Cada API tem sua própria cobrança e limites; assinar ChatGPT não inclui créditos de API.

## Publicação / testes

1. Faça backup do banco; publique o ZIP no repositório e deploy no Render.
2. Configure as variáveis de ambiente e Google Cloud OAuth.
3. Teste Google novo (pendente → aprovação → acesso), bloqueio, senha tradicional e administrador.
4. Teste análise de foto e chat com ambos os provedores; teste fallback simulando erro HTTP 503 em ambiente de homologação.
5. Valide cookies e HTTPS no Safari/PWA do iPhone.
