# V3 — Gemini + Conhecimento Local

- PostgreSQL removido integralmente.
- `database.py`, `DATABASE_URL` e `psycopg` removidos.
- Persistência substituída por arquivo JSON local (`storage.py`).
- Groq e Cloudflare removidos; Gemini passa a ser o único provedor.
- Pasta automática `C:\agenteIA` para execução local no Windows.
- Endpoint seguro de sincronização para enviar conhecimento do PC para a versão online.
- Script `sync_local_knowledge.py` e atalho `sincronizar_agenteIA.bat`.
- Painel mostra disponibilidade da pasta local e permite indexação manual.
