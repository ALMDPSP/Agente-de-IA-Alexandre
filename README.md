# Alexandre AI — V7.3

Agente pessoal com Gemini, busca global sobre a base sincronizada e monitor local Windows sem Python.

## Servidor / Render

O backend continua publicado normalmente no Render. Configure pelo menos:

- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-3.8-flash`
- `SYNC_TOKEN` com um valor forte e privado

O `SYNC_TOKEN` será usado apenas para autenticar o agente local.

## Agente local Windows — sem Python

O arquivo abaixo é um executável standalone x64:

`AlexandreAI.exe`

Ele não requer Python, BAT ou Prompt de Comando.

### Primeira execução

1. No Windows, dê dois cliques em `AlexandreAI.exe`.
2. O navegador abrirá a página local de configuração.
3. Confirme a URL do site (por padrão `https://agente-de-ia-alexandre.onrender.com`).
4. Confirme a pasta `C:\agenteIA`.
5. Informe o mesmo `SYNC_TOKEN` configurado no Render.
6. Clique em **Conectar pasta e ativar sincronização**.

O agente então:

- cria `C:\agenteIA` se ela ainda não existir;
- instala uma cópia em `%LOCALAPPDATA%\AlexandreAI\AlexandreAI.exe`;
- registra a inicialização automática com o Windows para o usuário atual;
- faz uma sincronização completa inicial;
- verifica alterações automaticamente a cada 10 segundos.

### Status visível

O agente cria:

- `C:\Alexandre AI - Status.html`
- `C:\Alexandre AI - Abrir.url`

Também há um painel local em:

`http://127.0.0.1:8765/status`

Nele é possível ver a pasta detectada, quantidade de arquivos, última sincronização, erro atual e executar **Sincronizar agora**.

## Tipos de arquivos monitorados

PDF, DOCX, XLSX, XLS, TXT, CSV, JSON, Markdown, HTML, XML e LOG.

## Fluxo

`C:\agenteIA` → `AlexandreAI.exe` → Render → base pessoal → busca global → Gemini.
