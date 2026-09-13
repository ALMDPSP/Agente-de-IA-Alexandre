# Alexandre AI — V7 Arquivos Inteligentes

Versão focada em projetos pessoais e arquivos locais, sem integração Microsoft e sem banco de dados.

## O que mudou

A integração OneNote / OneDrive foi removida.

Agora o conhecimento do agente vem de arquivos enviados pelo próprio usuário.

## Funcionamento

```text
Arquivo
  ↓
Extração de texto
  ↓
Divisão em trechos
  ↓
Armazenamento no navegador
  ↓
Pergunta
  ↓
Busca dos trechos mais relevantes
  ↓
Groq → Gemini → Cloudflare
  ↓
Resposta contextualizada
```

## Tipos de arquivo

- PDF
- DOCX
- XLSX / XLSM
- TXT
- Markdown
- CSV
- JSON
- XML
- HTML
- LOG

Limite atual por upload: 15 MB.

## Projetos

Cada projeto pode ter:

- Nome
- Descrição
- Status
- Vários documentos
- Centenas de trechos indexados

Ao selecionar um projeto como ativo, o agente busca automaticamente os trechos mais relevantes para cada pergunta.

## Busca inteligente

A versão V7 não envia todos os documentos para a IA.

Ela:

1. transforma a pergunta em palavras relevantes;
2. pesquisa essas palavras nos trechos indexados;
3. atribui uma pontuação a cada trecho;
4. seleciona os melhores resultados;
5. envia somente esses trechos ao modelo.

Isso economiza contexto e melhora a precisão.

## Histórico

Inclui:

- histórico das perguntas;
- busca;
- reutilização;
- exclusão individual;
- botão Limpar histórico.

## Backup

Exporta em JSON:

- projetos;
- descrições;
- documentos extraídos;
- chunks/trechos;
- conversa;
- histórico.

Assim você pode restaurar tudo em outro navegador.

## Importante

O sistema não usa banco de dados.

Os conteúdos extraídos dos arquivos ficam no `localStorage` do navegador.

Arquivos muito grandes ou uma quantidade muito alta de documentos podem atingir o limite de armazenamento do navegador. Se isso acontecer, a evolução recomendada é usar IndexedDB ou um banco vetorial.

## Render

Build:

```text
pip install -r requirements.txt
```

Start:

```text
gunicorn app:app
```


## V8 — Auth futurista

- Tela de login padronizada com MFA e setup
- Visual muito mais futurista e profissional
- Mesma linguagem visual entre login, verificação MFA e pareamento
- Indicador de progresso das etapas de acesso
- Cartões, hologramas, radar e componentes premium


## V9 — Dark Matrix Auth

- telas de Login, MFA e Setup MFA ainda mais dark
- nova paleta em tons de preto, verde neon e cyber
- animação de fundo estilo matriz com canvas
- layout padronizado entre todas as telas de autenticação


## V10 — Site Dark Unificado

- todo o site no mesmo estilo dark
- login, MFA, setup e dashboard com a mesma linguagem visual
- animação tipo matrix também no dashboard
- topo da página com ícone visual do Alexandre AI
- melhorias de responsividade para celular
- cards, menus e áreas internas no mesmo padrão cyber dark


## V11 — Dashboard fixo + App Icon + Mobile

- sidebar fixa no desktop
- topbar fixa no desktop e celular
- tabulação/alinhamento do menu lateral aprimorados
- ícone Alexandre AI no topo
- favicon na aba do navegador
- apple-touch-icon para iPhone/iPad
- manifest com ícones 192x192 e 512x512 para Android
- mesmo ícone usado no site e quando adicionado à tela inicial
- navegação inferior específica para celular
- scroll offsets ajustados para o header fixo
