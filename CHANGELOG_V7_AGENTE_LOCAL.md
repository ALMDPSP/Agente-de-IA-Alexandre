# V7 — Agente Local Automático

- Remove a necessidade de executar BAT para sincronização.
- Novo `agente_local.pyw`: roda na bandeja do Windows e monitora `C:\agenteIA` em tempo real.
- Sincronização automática ao criar, alterar, mover ou excluir arquivos suportados.
- Sincronização completa automática ao iniciar o Windows.
- Heartbeat para o painel identificar se o Agente Local está online.
- Novo endpoint de remoção sincronizada para refletir exclusões locais na base online.
- Instalador único `instalar_agente_local.py`, que configura credenciais e inicialização no Windows.
- Projetos continuam apenas como organização; o chat pesquisa toda a base globalmente.
