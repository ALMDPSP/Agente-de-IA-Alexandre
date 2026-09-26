# V4 - Leitura visual de PDFs

- Corrige leitura de PDFs escaneados, diplomas e certificados.
- Mantém extração local com pypdf para PDFs que possuem texto pesquisável.
- Quando o PDF possui pouco ou nenhum texto extraível, usa somente o Gemini para leitura visual.
- A transcrição visual é indexada normalmente na base de conhecimento local.
- Não adiciona PostgreSQL, Groq ou Cloudflare.
