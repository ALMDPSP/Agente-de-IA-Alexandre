import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("alexandre-ai.db")


def database_url():
    return (os.getenv("DATABASE_URL") or "").strip()


def database_configured():
    return bool(database_url())


@contextmanager
def get_conn():
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL não configurada.")
    conn = psycopg.connect(url, row_factory=dict_row, connect_timeout=12)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    if not database_configured():
        logger.warning("DATABASE_URL ausente; persistência PostgreSQL indisponível.")
        return False

    ddl = """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Planejamento',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_id, updated_at DESC);

    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        owner_id TEXT NOT NULL,
        title TEXT NOT NULL,
        size_bytes BIGINT NOT NULL DEFAULT 0,
        characters INTEGER NOT NULL DEFAULT 0,
        imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id, imported_at DESC);

    CREATE TABLE IF NOT EXISTS document_chunks (
        id BIGSERIAL PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        owner_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        filename TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL,
        UNIQUE(document_id, chunk_index)
    );
    CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id, chunk_index);

    CREATE TABLE IF NOT EXISTS chat_messages (
        id BIGSERIAL PRIMARY KEY,
        owner_id TEXT NOT NULL,
        message_type TEXT NOT NULL CHECK (message_type IN ('user', 'assistant')),
        content TEXT NOT NULL,
        provider TEXT NOT NULL DEFAULT '',
        documents JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_chat_owner ON chat_messages(owner_id, id DESC);

    CREATE TABLE IF NOT EXISTS search_history (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        query TEXT NOT NULL,
        project_id TEXT,
        project_name TEXT NOT NULL DEFAULT 'Conversa geral',
        provider TEXT NOT NULL DEFAULT '',
        used_documents JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_history_owner ON search_history(owner_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS user_settings (
        owner_id TEXT PRIMARY KEY,
        active_project_id TEXT,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
    logger.info("Estrutura PostgreSQL validada/inicializada.")
    return True


def iso(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_state(owner_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM projects WHERE owner_id=%s ORDER BY updated_at DESC, created_at DESC",
                (owner_id,),
            )
            projects_rows = cur.fetchall()

            cur.execute(
                "SELECT * FROM documents WHERE owner_id=%s ORDER BY imported_at DESC",
                (owner_id,),
            )
            document_rows = cur.fetchall()

            cur.execute(
                "SELECT * FROM document_chunks WHERE owner_id=%s ORDER BY document_id, chunk_index",
                (owner_id,),
            )
            chunk_rows = cur.fetchall()

            cur.execute(
                "SELECT * FROM chat_messages WHERE owner_id=%s ORDER BY id ASC LIMIT 500",
                (owner_id,),
            )
            chat_rows = cur.fetchall()

            cur.execute(
                "SELECT * FROM search_history WHERE owner_id=%s ORDER BY created_at DESC LIMIT 500",
                (owner_id,),
            )
            history_rows = cur.fetchall()

            cur.execute("SELECT active_project_id FROM user_settings WHERE owner_id=%s", (owner_id,))
            setting = cur.fetchone()

    docs_by_project = {}
    chunks_by_doc = {}
    for chunk in chunk_rows:
        chunks_by_doc.setdefault(chunk["document_id"], []).append({
            "id": f"chunk_{chunk['chunk_index']}",
            "index": chunk["chunk_index"],
            "filename": chunk["filename"],
            "text": chunk["content"],
        })

    for doc in document_rows:
        docs_by_project.setdefault(doc["project_id"], []).append({
            "id": doc["id"],
            "title": doc["title"],
            "size": doc["size_bytes"],
            "characters": doc["characters"],
            "importedAt": iso(doc["imported_at"]),
            "chunks": chunks_by_doc.get(doc["id"], []),
        })

    projects = [{
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "createdAt": iso(row["created_at"]),
        "updatedAt": iso(row["updated_at"]),
        "documents": docs_by_project.get(row["id"], []),
    } for row in projects_rows]

    chat = [{
        "id": row["id"],
        "text": row["content"],
        "type": row["message_type"],
        "provider": row["provider"],
        "documents": row["documents"] or [],
        "ts": int(row["created_at"].timestamp() * 1000),
    } for row in chat_rows]

    history = [{
        "id": row["id"],
        "query": row["query"],
        "projectId": row["project_id"] or "",
        "projectName": row["project_name"],
        "provider": row["provider"],
        "usedDocuments": row["used_documents"] or [],
        "createdAt": iso(row["created_at"]),
    } for row in history_rows]

    return {
        "projects": projects,
        "chat": chat,
        "searchHistory": history,
        "activeProjectId": (setting or {}).get("active_project_id") or "",
    }


def replace_state(owner_id, payload):
    projects = payload.get("projects") if isinstance(payload, dict) else []
    chat = payload.get("chat") if isinstance(payload, dict) else []
    history = payload.get("searchHistory") if isinstance(payload, dict) else []
    active_project_id = str(payload.get("activeProjectId") or "") if isinstance(payload, dict) else ""

    if not isinstance(projects, list):
        raise ValueError("projects inválido")
    if not isinstance(chat, list):
        chat = []
    if not isinstance(history, list):
        history = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM projects WHERE owner_id=%s", (owner_id,))
            cur.execute("DELETE FROM chat_messages WHERE owner_id=%s", (owner_id,))
            cur.execute("DELETE FROM search_history WHERE owner_id=%s", (owner_id,))

            for project in projects[:200]:
                pid = str(project.get("id") or "").strip()
                name = str(project.get("name") or "").strip()
                if not pid or not name:
                    continue
                cur.execute(
                    """INSERT INTO projects(id, owner_id, name, description, status, created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,COALESCE(%s::timestamptz,NOW()),COALESCE(%s::timestamptz,NOW()))""",
                    (pid, owner_id, name, str(project.get("description") or ""),
                     str(project.get("status") or "Planejamento"), project.get("createdAt"), project.get("updatedAt")),
                )
                for doc in (project.get("documents") or [])[:500]:
                    did = str(doc.get("id") or "").strip()
                    if not did:
                        continue
                    cur.execute(
                        """INSERT INTO documents(id, project_id, owner_id, title, size_bytes, characters, imported_at)
                           VALUES (%s,%s,%s,%s,%s,%s,COALESCE(%s::timestamptz,NOW()))""",
                        (did, pid, owner_id, str(doc.get("title") or "Documento"), int(doc.get("size") or 0),
                         int(doc.get("characters") or 0), doc.get("importedAt")),
                    )
                    for idx, chunk in enumerate((doc.get("chunks") or [])[:180], start=1):
                        chunk_index = int(chunk.get("index") or idx)
                        cur.execute(
                            """INSERT INTO document_chunks(document_id, owner_id, chunk_index, filename, content)
                               VALUES (%s,%s,%s,%s,%s)""",
                            (did, owner_id, chunk_index, str(chunk.get("filename") or doc.get("title") or ""),
                             str(chunk.get("text") or "")[:200000]),
                        )

            for item in chat[-500:]:
                typ = "assistant" if item.get("type") == "assistant" else "user"
                cur.execute(
                    """INSERT INTO chat_messages(owner_id, message_type, content, provider, documents, created_at)
                       VALUES (%s,%s,%s,%s,%s::jsonb,COALESCE(%s::timestamptz,NOW()))""",
                    (owner_id, typ, str(item.get("text") or "")[:50000], str(item.get("provider") or ""),
                     json.dumps(item.get("documents") or []),
                     datetime.fromtimestamp((item.get("ts") or 0)/1000, tz=timezone.utc).isoformat() if item.get("ts") else None),
                )

            for item in history[:500]:
                hid = str(item.get("id") or "").strip()
                if not hid:
                    continue
                cur.execute(
                    """INSERT INTO search_history(id, owner_id, query, project_id, project_name, provider, used_documents, created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,COALESCE(%s::timestamptz,NOW()))""",
                    (hid, owner_id, str(item.get("query") or "")[:20000], item.get("projectId") or None,
                     str(item.get("projectName") or "Conversa geral"), str(item.get("provider") or ""),
                     json.dumps(item.get("usedDocuments") or []), item.get("createdAt")),
                )

            cur.execute(
                """INSERT INTO user_settings(owner_id, active_project_id, updated_at) VALUES (%s,%s,NOW())
                   ON CONFLICT(owner_id) DO UPDATE SET active_project_id=EXCLUDED.active_project_id, updated_at=NOW()""",
                (owner_id, active_project_id or None),
            )


def create_project(owner_id, project):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO projects(id, owner_id, name, description, status)
                   VALUES (%s,%s,%s,%s,%s) RETURNING created_at, updated_at""",
                (project["id"], owner_id, project["name"], project.get("description", ""), project.get("status", "Planejamento")),
            )
            row = cur.fetchone()
    return {**project, "createdAt": iso(row["created_at"]), "updatedAt": iso(row["updated_at"]), "documents": []}


def update_project(owner_id, project_id, fields):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE projects SET name=%s, description=%s, status=%s, updated_at=NOW()
                   WHERE id=%s AND owner_id=%s RETURNING updated_at""",
                (fields["name"], fields.get("description", ""), fields.get("status", "Planejamento"), project_id, owner_id),
            )
            return cur.fetchone()


def delete_project(owner_id, project_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM projects WHERE id=%s AND owner_id=%s", (project_id, owner_id))
            cur.execute("UPDATE user_settings SET active_project_id=NULL, updated_at=NOW() WHERE owner_id=%s AND active_project_id=%s", (owner_id, project_id))
            return cur.rowcount


def set_active_project(owner_id, project_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if project_id:
                cur.execute("SELECT 1 FROM projects WHERE id=%s AND owner_id=%s", (project_id, owner_id))
                if not cur.fetchone():
                    raise ValueError("Projeto não encontrado.")
            cur.execute(
                """INSERT INTO user_settings(owner_id, active_project_id, updated_at) VALUES (%s,%s,NOW())
                   ON CONFLICT(owner_id) DO UPDATE SET active_project_id=EXCLUDED.active_project_id, updated_at=NOW()""",
                (owner_id, project_id or None),
            )


def insert_document(owner_id, project_id, document):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM projects WHERE id=%s AND owner_id=%s", (project_id, owner_id))
            if not cur.fetchone():
                raise ValueError("Projeto não encontrado.")
            cur.execute(
                """INSERT INTO documents(id, project_id, owner_id, title, size_bytes, characters)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING imported_at""",
                (document["id"], project_id, owner_id, document["title"], document.get("size", 0), document.get("characters", 0)),
            )
            imported = cur.fetchone()["imported_at"]
            for chunk in document.get("chunks", []):
                cur.execute(
                    """INSERT INTO document_chunks(document_id, owner_id, chunk_index, filename, content)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (document["id"], owner_id, int(chunk.get("index") or 0), str(chunk.get("filename") or document["title"]), str(chunk.get("text") or "")),
                )
            cur.execute("UPDATE projects SET updated_at=NOW() WHERE id=%s AND owner_id=%s", (project_id, owner_id))
    document["importedAt"] = iso(imported)
    return document


def delete_document(owner_id, document_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id=%s AND owner_id=%s RETURNING project_id", (document_id, owner_id))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE projects SET updated_at=NOW() WHERE id=%s AND owner_id=%s", (row["project_id"], owner_id))
            return bool(row)


def add_chat_message(owner_id, item):
    typ = "assistant" if item.get("type") == "assistant" else "user"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO chat_messages(owner_id, message_type, content, provider, documents)
                   VALUES (%s,%s,%s,%s,%s::jsonb) RETURNING id, created_at""",
                (owner_id, typ, str(item.get("text") or "")[:50000], str(item.get("provider") or ""), json.dumps(item.get("documents") or [])),
            )
            return cur.fetchone()


def clear_chat(owner_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_messages WHERE owner_id=%s", (owner_id,))


def add_history(owner_id, item):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO search_history(id, owner_id, query, project_id, project_name, provider, used_documents)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (item["id"], owner_id, item["query"], item.get("projectId") or None, item.get("projectName") or "Conversa geral",
                 item.get("provider") or "", json.dumps(item.get("usedDocuments") or [])),
            )


def delete_history(owner_id, history_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if history_id:
                cur.execute("DELETE FROM search_history WHERE id=%s AND owner_id=%s", (history_id, owner_id))
            else:
                cur.execute("DELETE FROM search_history WHERE owner_id=%s", (owner_id,))
