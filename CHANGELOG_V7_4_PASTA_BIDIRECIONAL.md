# V7.4 — Pasta pessoal bidirecional

- Agente Local Windows reforçado para validar leitura e gravação em `C:\agenteIA`.
- Criação automática das pastas `Documentos`, `Trabalho`, `Projetos`, `Manuais` e `Anotacoes`.
- Projetos criados no site agora geram automaticamente `C:\agenteIA\Projetos\<Nome>\projeto.json` no PC conectado.
- Renomear projeto no site renomeia a pasta local quando possível.
- Excluir projeto no site preserva os arquivos movendo a pasta para `Projetos\_Arquivados`.
- Arquivos locais passam a ser classificados conforme a pasta de origem; a busca do chat continua global.
- Nova fila segura de comandos Render → Agente Local, autenticada pelo `SYNC_TOKEN`.
- Status passa a informar se o agente realmente possui acesso de leitura/gravação à pasta e quantos arquivos detectou.
- Atualização do Agente Local encerra automaticamente uma instalação anterior para evitar duas instâncias concorrentes.
- Identidade visual do agente local usa o ícone Alexandre AI e cria atalhos no Desktop/Menu Iniciar com esse ícone.
