"""Limites de tentativa compartilhados entre instâncias via PostgreSQL."""
import hashlib
from wellness_storage import connect


def init_limits():
    with connect() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS wellness_rate_limits (
            key_hash TEXT PRIMARY KEY, hits INTEGER NOT NULL DEFAULT 0,
            window_start TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )''')


def allow_attempt(action, ip, identity='', limit=10, minutes=15):
    # Fingerprint avoids storing raw email/IP in the rate-limit table.
    raw = '|'.join((action, ip or '', identity.lower().strip()))
    fingerprint = hashlib.sha256(raw.encode()).hexdigest()
    with connect() as conn:
        row = conn.execute('''INSERT INTO wellness_rate_limits(key_hash,hits,window_start)
          VALUES (%s,1,NOW())
          ON CONFLICT(key_hash) DO UPDATE SET
             hits=CASE WHEN wellness_rate_limits.window_start < NOW() - (%s * INTERVAL '1 minute') THEN 1
                       ELSE wellness_rate_limits.hits + 1 END,
             window_start=CASE WHEN wellness_rate_limits.window_start < NOW() - (%s * INTERVAL '1 minute')
                               THEN NOW() ELSE wellness_rate_limits.window_start END
          RETURNING hits''', (fingerprint, minutes, minutes)).fetchone()
    return row['hits'] <= limit
