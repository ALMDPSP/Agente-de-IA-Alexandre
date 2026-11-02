# IA automática do sistema

- Usuários entram normalmente com a conta cadastrada. O sistema usa as credenciais configuradas **somente** no Render (`GEMINI_API_KEY` e/ou `OPENAI_API_KEY`). Nenhuma pessoa precisa fornecer chave de API.
- Ter o mesmo e-mail de uma conta ChatGPT/Gemini/Claude não oferece autorização para consumir a assinatura pessoal. Login social/OAuth só pode usar recursos que o provedor efetivamente disponibiliza e autoriza; esta versão **não conecta assinaturas pessoais**.
- A foto é comprimida no navegador e enviada para análise; o backend limita o tamanho e tenta Gemini e, para falhas transitórias, OpenAI se configurado.
- Timeout de conexão com provedores reduzido para 5 s de conexão e 19 s de leitura, buscando evitar o timeout padrão de 30 s do Gunicorn. Em caso de falha o sistema retorna JSON de erro para a interface, sem registrar a foto.
- No Render, configure GEMINI_API_KEY e, se desejar fallback, OPENAI_API_KEY (cobrança separada). O tempo de resposta deve ser testado em produção.
- Não há integração por e-mail com contas pessoais nem login OAuth externo neste pacote.
- Configurações individuais antigas permanecem no banco, mas não são utilizadas no diário; não foram apagadas.
