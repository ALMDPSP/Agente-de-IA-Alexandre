# Minha Evolução IA — MVP

Adaptação da base Agente de IA Alexandre. Mantém login com e-mail e senha e adiciona `/evolucao` (aberto após login).

## Funcionalidades
- Foto JPG/PNG/WEBP (até 5 MB) → Gemini Vision → alimentos, intervalo aproximado de calorias e sugestão.
- Diário com texto das análises; imagens **não** são persistidas.
- Registro e gráfico de peso; definição de meta; chat educacional contextual.
- Design responsivo e manifest PWA.

## Execução
Use as variáveis já existentes `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `GEMINI_API_KEY`, `GEMINI_MODEL`. Instale `requirements.txt` e rode `gunicorn app:app`.

## Atenção antes de publicar
O MVP armazena dados em `DATA_DIR/evolucao_ia.json`. **Render Free não oferece armazenamento persistente**: migre para PostgreSQL/Neon ou armazenamento persistente antes de usar de verdade. O projeto antigo ainda contém rotas e código legado; revise permissões, endpoints e retenção de dados antes de oferecer a terceiros. Dados de saúde requerem consentimento e controles adequados à LGPD. A IA não substitui atendimento nutricional; caloria por imagem é estimativa muito imprecisa.

O conteúdo antigo foi mantido no repositório para permitir migração gradual. Os recursos do executável Windows não são necessários para o novo aplicativo web.
