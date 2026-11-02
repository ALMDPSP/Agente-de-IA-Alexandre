# Configuração de IA por usuário

- Nova tela `/configurar-ia` para escolha de provedor, modelo e chave individual.
- Provedores: Gemini, OpenAI, Claude, Groq, OpenRouter, DeepSeek, Mistral e xAI.
- Configurações persistentes no PostgreSQL (`user_ai_settings`) com chave cifrada usando Fernet e chave derivada de `AI_CREDENTIALS_KEY`, ou `SECRET_KEY` como fallback. **Não altere essas variáveis sem planejar migração das credenciais.**
- A mesma configuração alimenta o chat principal, o chat de evolução e as fotos das refeições.
- Quem não configurar utiliza a IA padrão já configurada no Render.
- Todas as rotas exigem login, CSRF nos POST/DELETE e evitam expor as chaves pela API.
- Assinaturas de apps não dão acesso automático à API: cada pessoa precisa de credencial API, com eventuais custos.
- Alguns modelos não aceitam imagens; escolha um multimodal para fotos.
- Após deploy, confirme que a tabela foi criada, configure a chave, teste o chat e o envio de fotos.
- Configure `AI_CREDENTIALS_KEY` com 32+ caracteres aleatórios para separar criptografia das credenciais da sessão Flask (opcional, mas recomendável).
