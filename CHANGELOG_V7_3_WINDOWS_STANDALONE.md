# V7.3 — Agente Local Windows Standalone

- Substitui o monitor local em Python por `AlexandreAI.exe` standalone para Windows x64.
- Não requer Python, BAT ou Prompt de Comando no computador do usuário.
- Na primeira execução, abre uma tela de configuração no navegador local.
- Configura URL do agente, `SYNC_TOKEN` e pasta pessoal (padrão `C:\agenteIA`).
- Copia o executável para `%LOCALAPPDATA%\AlexandreAI\AlexandreAI.exe` e registra inicialização automática do usuário.
- Monitora a pasta a cada 10 segundos e sincroniza novos arquivos, alterações e exclusões.
- Envia heartbeat ao Render para o dashboard exibir o estado do agente local.
- Cria `C:\Alexandre AI - Status.html` e `C:\Alexandre AI - Abrir.url`.
- O painel local fica disponível em `http://127.0.0.1:8765/status` e permite forçar sincronização.
- Mantém a busca global, Gemini e retry automático para 429/503 da V7.1/V7.2.
