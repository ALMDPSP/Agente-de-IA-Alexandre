# Atualização PostgreSQL / Aiven

## Implementado

- Persistência PostgreSQL para projetos.
- Persistência de documentos e chunks extraídos.
- Persistência da conversa com a Agente IA.
- Persistência do histórico de pesquisas.
- Persistência do projeto ativo.
- Exclusão de projetos/documentos refletida diretamente no banco.
- Backup e restauração gravando no PostgreSQL.
- Migração automática dos dados antigos do `localStorage` quando o banco estiver vazio.
- Criação automática das tabelas no primeiro start.
- `DATABASE_URL` adicionada ao `render.yaml`.
- Driver PostgreSQL `psycopg` adicionado às dependências.
- `/health` informa se a variável de banco está configurada.
- Textos da interface atualizados para indicar persistência em banco.

## Deploy

No Render, configure `DATABASE_URL` com a URI do Aiven apontando para o banco desejado e contendo `sslmode=require`. Depois use **Save and deploy**.
