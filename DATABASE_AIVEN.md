# PostgreSQL no Aiven + Render

Esta versão usa PostgreSQL como persistência principal. O `localStorage` é usado somente uma vez para migrar automaticamente dados de uma versão antiga, quando o banco ainda estiver vazio. Depois da migração, as chaves antigas são removidas do navegador.

## 1. Aiven

Crie um serviço PostgreSQL e um banco para a aplicação. Na URI fornecida pelo Aiven, troque o banco final pelo banco criado para a aplicação. Mantenha `sslmode=require`.

Formato:

```text
postgres://avnadmin:SENHA@HOST:PORTA/BANCO?sslmode=require
```

## 2. Render

No serviço Web do Render, abra **Environment** e crie/edite:

```text
DATABASE_URL=postgres://avnadmin:SENHA@HOST:PORTA/BANCO?sslmode=require
```

Salve usando **Save and deploy**.

## 3. Inicialização automática

No primeiro start com `DATABASE_URL` configurada, `database.py` cria automaticamente as tabelas:

- `projects`
- `documents`
- `document_chunks`
- `chat_messages`
- `search_history`
- `user_settings`

Não é necessário executar SQL manualmente.

## 4. O que passa a persistir

- projetos e status;
- documentos e trechos extraídos;
- projeto ativo;
- conversa da agente;
- histórico de pesquisas;
- metadados de provedor/modelo e arquivos consultados.

## 5. Verificação

A rota `/health` retorna:

```json
{
  "status": "ok",
  "database": "configured"
}
```

Se aparecer `"database": "missing"`, a variável `DATABASE_URL` não está configurada no ambiente.
