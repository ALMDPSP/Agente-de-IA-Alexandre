# V7.2 — Pasta pessoal visível e configuração sem BAT

- Novo `configurar_agente_local.pyw`: configuração gráfica por duplo clique, sem BAT e sem terminal.
- O agente é copiado para `%LOCALAPPDATA%\AlexandreAI`, evitando depender da pasta extraída do ZIP.
- Inicialização automática no Windows via registro do usuário.
- Monitoramento automático e recursivo de `C:\agenteIA`.
- Cria ao lado da pasta monitorada:
  - `Alexandre AI - Status.html`: mostra pasta detectada, arquivos encontrados, pendências, última sincronização e último erro.
  - `Alexandre AI - Abrir.url`: abre o agente online.
- Menu da bandeja ganhou `Ver status da pasta`.
- Heartbeat agora informa também a quantidade de arquivos detectados localmente.
- Mantido Gemini com retry automático para 429/503, busca global e sincronização automática.
