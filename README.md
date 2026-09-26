# Alexandre AI — Gemini + Conhecimento Local

Agente pessoal em Flask com login/MFA, chat dinâmico, base de conhecimento por arquivos e **Gemini como único provedor de IA**.

## O que mudou nesta versão

- **Sem PostgreSQL**: não existe `DATABASE_URL` e não é necessário banco externo.
- **Somente Gemini**: Groq e Cloudflare foram removidos.
- **Conhecimento local automático**: quando executado no Windows, o agente pode ler `C:\agenteIA` diretamente.
- **Sincronização para a rede**: `sync_local_knowledge.py` envia os arquivos de `C:\agenteIA` para a aplicação online usando `SYNC_TOKEN`.
- **Persistência em arquivos**: projetos, trechos extraídos, histórico e conversa ficam em `data/state_admin.json` (ou no diretório definido por `DATA_DIR`).
- **Chat dinâmico**: mostra quando está pensando, consultando conhecimento e gerando a resposta.

## Executar no Windows

1. Instale Python 3.11+.
2. Crie a pasta `C:\agenteIA`.
3. Coloque seus PDF, DOCX, XLSX, TXT, MD, CSV, JSON, XML, HTML ou LOG nessa pasta.
4. Instale as dependências:

   `pip install -r requirements.txt`

5. Configure as variáveis:

   - `ADMIN_EMAIL`
   - `ADMIN_PASSWORD`
   - `SECRET_KEY`
   - `GEMINI_API_KEY`
   - opcional: `GEMINI_MODEL`
   - opcional: `LOCAL_KNOWLEDGE_DIR` (padrão no Windows: `C:\agenteIA`)

6. Execute:

   `python app.py`

No painel, use **Ler C:\agenteIA agora** para indexar a pasta.

## Sincronizar C:\agenteIA com a versão online

Na versão online configure `SYNC_TOKEN`. No seu Windows configure o mesmo token e a URL pública:

- `AGENT_URL=https://seu-servico.onrender.com`
- `SYNC_TOKEN=seu-token-secreto`

Depois execute `sincronizar_agenteIA.bat` ou:

`python sync_local_knowledge.py`

O script percorre `C:\agenteIA` e envia os arquivos compatíveis para o projeto **Conhecimento Local**.

## Importante sobre Render

O Render não consegue acessar o disco `C:\` do seu computador diretamente. O acesso automático a `C:\agenteIA` funciona quando a aplicação está rodando no próprio PC. Para a versão online, use o sincronizador incluído.

No plano sem disco persistente, os arquivos locais do serviço podem ser apagados quando a instância for recriada/reimplantada. Como a fonte principal continua sendo `C:\agenteIA`, basta executar a sincronização novamente. Para persistência contínua no servidor, configure um volume/disco persistente e aponte `DATA_DIR` para ele.
