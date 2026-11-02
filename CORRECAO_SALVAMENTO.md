# Correção do salvamento de dados — Minha Evolução IA

## Corrigido
- Independência das inicializações das tabelas `wellness_accounts`, `wellness_diaries` e `wellness_rate_limits`.
- Recuperação automática da tabela `wellness_diaries` quando ela ainda não existe (primeira leitura ou gravação).
- Resposta JSON 503 informativa quando conexão PostgreSQL falha, com detalhes técnicos somente nos logs.
- Mensagem amigável no navegador quando servidor envia HTML de erro, em vez de JSON.
- `render.yaml` documenta a necessidade de `DATABASE_URL` e variáveis OAuth/IA.

## Configurar no Render
1. Environment → `DATABASE_URL`: conexão PostgreSQL de seu projeto Neon, com SSL exigido pelo provedor.
2. Confirmar que o banco não está suspenso, credenciais estão corretas e o usuário tem permissão para criar tabelas.
3. Verificar `SECRET_KEY` (estável), `ADMIN_EMAIL`, `ADMIN_PASSWORD`.
4. Fazer deploy, abrir Logs e procurar por `Não foi possível inicializar tabela` ou `Falha PostgreSQL`.
5. Testar gravação e recarregamento de **perfil**, **peso**, **refeição**. O envio de foto exige também uma IA válida.
6. Não colocar a string DATABASE_URL, tokens, senhas nem dados pessoais em prints compartilhados.

## Limites
Não foi possível testar contra o Neon real sem conexão e credenciais. Não execute scripts destrutivos ou recrie o banco: o pacote não remove dados existentes. As fotos não são persistidas, apenas o resultado da análise.
