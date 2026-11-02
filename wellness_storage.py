"""Persistência transacional e isolada por conta para dados de bem-estar."""
import json
import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def connect():
    url = os.getenv('DATABASE_URL', '').strip()
    if not url:
        raise RuntimeError('DATABASE_URL não configurada. Configure PostgreSQL (Neon) no Render.')
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)


def init_wellness():
    with connect() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS wellness_diaries (
            user_id TEXT PRIMARY KEY,
            state JSONB NOT NULL DEFAULT '{"meals":[],"weights":[],"profile":{}}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )''')


def read_state(user_id):
    with connect() as conn:
        row = conn.execute('SELECT state FROM wellness_diaries WHERE user_id = %s', (str(user_id),)).fetchone()
    return row['state'] if row else {'meals': [], 'weights': [], 'profile': {}}


def update_state(user_id, mutate):
    """Row lock prevents lost updates when multiple devices write simultaneously."""
    with connect() as conn:
        conn.execute('''INSERT INTO wellness_diaries(user_id) VALUES (%s)
             ON CONFLICT (user_id) DO NOTHING''', (str(user_id),))
        row = conn.execute('SELECT state FROM wellness_diaries WHERE user_id = %s FOR UPDATE', (str(user_id),)).fetchone()
        state = row['state']
        mutate(state)
        conn.execute('''UPDATE wellness_diaries SET state=%s, updated_at=NOW()
                        WHERE user_id=%s''', (Jsonb(state), str(user_id)))
    return state
