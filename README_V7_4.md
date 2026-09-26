# Alexandre AI V7.4

## Estrutura local

Na primeira execução do `AlexandreAI.exe`, após informar URL, pasta e `SYNC_TOKEN`, o agente garante esta estrutura:

```
C:\agenteIA
├── Documentos
├── Trabalho
├── Projetos
│   └── _Arquivados
├── Manuais
└── Anotacoes
```

O agente testa leitura e gravação na pasta. O resultado aparece em `C:\Alexandre AI - Status.html` e também no painel online.

## Projetos

Ao criar um projeto no site, o agente local recebe a instrução e cria:

```
C:\agenteIA\Projetos\Nome do Projeto\projeto.json
```

O arquivo contém os dados básicos do projeto e passa a fazer parte da base sincronizada. Renomeações são refletidas na pasta local. Ao excluir um projeto no site, a pasta local é preservada em `_Arquivados`.

## Organização do conhecimento

- `Documentos\...` → categoria Documentos
- `Trabalho\...` → categoria Trabalho
- `Manuais\...` → categoria Manuais
- `Anotacoes\...` → categoria Anotacoes
- `Projetos\Nome\...` → projeto Nome

O chat continua pesquisando toda a base automaticamente, independentemente da categoria.

## Windows

Não requer Python nem BAT. O executável é Windows x64 standalone. Na instalação ele cria atalhos **Alexandre AI** no Desktop e Menu Iniciar usando o ícone oficial do agente.
