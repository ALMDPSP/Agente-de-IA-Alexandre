# Minha Evolução IA — instalação no iPhone (PWA)

## Publicar no Render
1. Substitua os arquivos do seu repositório pelos desta versão, preservando variáveis/segredos do Render.
2. Faça commit e push para a branch conectada ao serviço do Render.
3. Confirme as variáveis `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `GEMINI_API_KEY` e um `GEMINI_MODEL` válido. Não publique senhas no GitHub.
4. Aguarde o deploy concluir e acesse seu endereço **HTTPS** no Safari do iPhone.
5. Faça login normalmente com e-mail e senha; o MFA continua desativado.

## Adicionar à Tela de Início
1. Abra o endereço HTTPS do seu sistema no **Safari** (não em um navegador interno de outro aplicativo).
2. Toque em **Compartilhar** (ícone quadrado com seta para cima).
3. Selecione **Adicionar à Tela de Início** (em versões recentes do iOS, a opção pode estar no menu '…' ou dentro das ações).
4. Confirme o nome **Minha Evolução IA** e toque em **Adicionar**.
5. Abra o ícone verde na Tela de Início e faça login.

## Limitações e observações
- Internet é necessária para login, sincronização, diário e análise das fotos pelo Gemini. Offline exibe somente aviso de falta de conexão.
- Não é necessário pagar a conta Apple Developer nem publicar na App Store.
- HTTPS é necessário em produção para registro de service worker.
- Uma PWA não é um aplicativo nativo, mas pode abrir em tela independente.
- Fotos são processadas com o Gemini, mas não ficam salvas no diário nesta versão.
- O diário do MVP ainda usa armazenamento JSON local: **não confie em dados persistentes no plano gratuito do Render**. Migrar para Neon/PostgreSQL antes de uso real e backups.
- Este PWA não armazena informações de saúde no cache do navegador; não muda o tratamento de dados do servidor.
