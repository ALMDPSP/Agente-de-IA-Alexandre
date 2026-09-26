# V7.1 — Retry automático Gemini

- Mantém a arquitetura da V7.
- Retry automático no chat para HTTP 429 e 503.
- Até 4 tentativas por pergunta.
- Exponential backoff: 1s, 2s e 4s, respeitando `Retry-After` quando enviado pelo Gemini (limitado a 30s).
- Mensagens de status em tempo real no indicador do chat e no balão de pensamento.
- HTTP 429 e 503 preservados pelo backend para o frontend distinguir erros transitórios.
- Demais erros não são repetidos automaticamente.
