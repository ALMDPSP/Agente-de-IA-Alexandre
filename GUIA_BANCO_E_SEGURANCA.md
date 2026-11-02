# Minha Evolução IA — PostgreSQL e segurança (versão multiusuário)

## Render + Neon

1. Criar o PostgreSQL Neon e copiar a conexão criptografada (SSL) para o segredo `DATABASE_URL` no Render. NÃO colocar URL ou senha no GitHub. No Neon usar `sslmode=require` quando aplicável.
2. Configurar `SECRET_KEY` aleatória e permanente, `ADMIN_EMAIL`, `ADMIN_PASSWORD` (senha forte), `GEMINI_API_KEY`, `GEMINI_MODEL`. Manter HTTPS.
3. Fazer deploy. O app cria automaticamente as tabelas `wellness_accounts`, `wellness_diaries` e `wellness_rate_limits`. O usuário administrador é o definido por `ADMIN_EMAIL` + `ADMIN_PASSWORD`.
4. Cadastro em `/cadastro`: novo usuário aguarda aprovação. O administrador abre `/admin/usuarios` para ativar ou bloquear; o link aparece no painel de evolução apenas para o admin.
5. Os diários são salvos como JSONB indexados pelo `user_id` e cada acesso exige sessão. Gravações concorrentes usam transação com bloqueio de linha.
6. Fotos são enviadas ao Gemini para análise e não são armazenadas no banco. Só o resumo da análise é guardado. Informe isso aos participantes antes do uso e publique uma política de privacidade conforme a LGPD.

## Migração de dados antigos

A versão anterior guardava os dados em `DATA_DIR/evolucao_ia.json` **no disco da instância Render**. O novo app não lê esse arquivo. Para preservar dados anteriores, exporte-o antes de atualizar o deploy e migre-o de forma controlada. Caso não exista backup ou disco persistente, os registros locais antigos podem já ter sido apagados pelo Render. Não existe migração automática para evitar que um arquivo de origem incerta sobrescreva dados atuais.

## Checklist antes de abrir ao público

- Verificar instalação PWA via Safari no iPhone, login/registro, bloqueio e aprovação.
- Testar dois usuários diferentes e confirmar que nenhum vê refeições ou pesos de outro.
- Implementar confirmação de e-mail, recuperação de senha e consentimento explícito para tratamento de dados pessoais de saúde, além de política de privacidade, solicitação de exclusão/exportação e retenção.
- Testar limites de requisição e autenticação em produção; monitorar logs sem expor dados pessoais e realizar backups regulares do Neon.
- Limites de tentativas atuais: 25 acessos/15min por IP, 10 tentativas/15min por e-mail e 5 cadastros/hora por IP (em todas as instâncias que compartilham o banco). Essas medidas não substituem proteção adicional na borda.
- Usuários comuns não acessam as antigas rotas do agente pessoal; somente admin mantém essas rotas por compatibilidade. O recomendado é desativá-las em uma futura versão dedicada à saúde.
