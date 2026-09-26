# V6 - Correções de Gemini e sincronização global

- Gemini alterado para API nativa `generateContent`, sem camada OpenAI compatível.
- Modelo padrão atualizado para `gemini-3.8-flash`.
- Erros de API/CSRF/sessão agora retornam JSON legível ao chat.
- Frontend não tenta mais interpretar HTML como JSON.
- Busca de conhecimento movida para o servidor e feita em toda a base, sem projeto ativo.
- `/api/agent` retorna os arquivos e trechos realmente usados na resposta.
- Status da base é atualizado automaticamente no chat.
- Sincronizador de `C:\agenteIA` ficou interativo e mais simples de executar no Windows.
- Removido texto de fallback entre provedores; o sistema usa somente Gemini.
