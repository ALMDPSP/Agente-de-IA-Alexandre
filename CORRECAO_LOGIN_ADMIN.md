# Correção do login do administrador

Defina no Render, em Environment:

- `ADMIN_EMAIL=alexandre.martins@dpsp.com.br`
- `ADMIN_PASSWORD` = sua senha de administrador (não publique no GitHub)
- `SECRET_KEY` = chave forte, permanente
- `DATABASE_URL` = conexão Neon válida (obrigatória para painel, peso e refeições)

Após salvar as variáveis, execute novo deploy e entre em `/login` com o e-mail e a senha configurados. O administrador não precisa se cadastrar nem ser aprovado no painel. As contas criadas via `/cadastro` são contas comuns.

A versão anterior dependia do PostgreSQL até para conferir o rate limit do login. Esta versão permite validar o administrador por variáveis de ambiente se esse serviço estiver indisponível, com limitação local conservadora de até 10 tentativas por IP+e-mail em 15 minutos por processo. Para ambiente de múltiplas instâncias, adicione proteção externa, pois o limite local não é compartilhado. Se o PostgreSQL estiver indisponível, recursos que dependem dele continuarão indisponíveis mesmo após o login.

Se aparecer *E-mail ou senha inválidos*, confirme as variáveis exatamente no serviço Render correto (e não em outro projeto). Se aparecer *Login temporariamente indisponível*, verifique a conexão PostgreSQL e os logs. Não compartilhe `ADMIN_PASSWORD`, `DATABASE_URL` nem `SECRET_KEY`.
