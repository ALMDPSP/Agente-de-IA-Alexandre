# Agente de IA Alexandre — Chat Dinâmico + Arquivos Locais

## Chat
- Indicador visual do estado do agente: pronto, pensando, consultando conhecimento e gerando resposta.
- Cronômetro de processamento durante a resposta.
- Bolha animada "Pensando" dentro da conversa.
- Bloqueio de envio duplicado enquanto a IA processa.
- Animação progressiva da resposta.
- Chat maior, mais limpo e com melhor destaque visual.
- Composer com estado de carregamento e foco visual aprimorado.

## Arquivos locais
- Seleção de múltiplos arquivos da máquina.
- Seleção de pasta local inteira via `webkitdirectory` (Chrome/Edge e navegadores compatíveis).
- Arrastar e soltar arquivos no painel de conhecimento.
- Filtro de extensões compatíveis.
- Remoção individual de arquivos antes da importação.
- Progresso arquivo a arquivo durante a leitura/importação.
- Mantido limite de 15 MB por arquivo.

## Segurança / arquitetura
- O navegador não acessa o disco automaticamente: Alexandre precisa selecionar os arquivos/pasta.
- O conteúdo selecionado continua sendo processado pelo backend e persistido no PostgreSQL do projeto.
- Login, MFA, projetos, histórico, backup e provedores de IA foram preservados.
