# V7 — Gerenciamento de usuários

- Adicionada exclusão permanente de usuário com digitação do e-mail como confirmação, exclusiva para admin.
- Remove registro em wellness_accounts e wellness_diaries na mesma transação.
- Usuários excluídos perdem a sessão no próximo request.
- Status online usa heartbeat do diário a cada 60s e janela de 3min.
- Último login é gravado no PostgreSQL para contas comuns. Horários exibidos em UTC.
- O usuário admin do ambiente não pode ser excluído.
- A exclusão é irreversível; realizar backup antes.
