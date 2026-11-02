# Cadastro e controle de usuários

Configure `DATABASE_URL` com PostgreSQL persistente no Render/Neon. As contas ficam no banco `wellness_accounts` e as senhas são armazenadas como hash, não em texto puro. `ADMIN_EMAIL` e `ADMIN_PASSWORD` permanecem como credenciais do administrador principal (em variáveis secretas). `SECRET_KEY` deve ser forte e constante.

Visitantes usam `/cadastro`. Contas novas ficam `pending`, sem acesso. O administrador entra pelo login existente e abre `/admin/usuarios` para aprovar ou bloquear. Alterações de status são protegidas por login administrativo e CSRF.

ATENÇÃO: o diário alimentar atual usa arquivo JSON local (`DATA_DIR/evolucao_ia.json`), que NÃO é persistente no Render sem disco, nem é um armazenamento de produção multiusuário. Os dados são separados pelo ID da conta, mas devem ser migrados para banco antes do uso real por múltiplos usuários.

Para aplicações públicas, adicionar antes de divulgação: proteção contra brute-force/rate limit, confirmação de e-mail, recuperação de senha e política de privacidade/LGPD.
