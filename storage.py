import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.RLock()


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _data_dir():
    configured = (os.getenv('DATA_DIR') or '').strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parent / 'data'


def _state_path(owner_id):
    safe = ''.join(ch for ch in str(owner_id) if ch.isalnum() or ch in ('-', '_')) or 'admin'
    return _data_dir() / f'state_{safe}.json'


def storage_configured():
    return True


def init_storage():
    _data_dir().mkdir(parents=True, exist_ok=True)
    return True


def _default_state():
    return {
        'projects': [],
        'chat': [],
        'searchHistory': [],
        'activeProjectId': '',
    }


def _load(owner_id):
    path = _state_path(owner_id)
    if not path.exists():
        return _default_state()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return _default_state()
    except Exception:
        return _default_state()
    base = _default_state()
    base.update({k: data.get(k, base[k]) for k in base})
    return base


def _save(owner_id, state):
    init_storage()
    path = _state_path(owner_id)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def load_state(owner_id):
    with _LOCK:
        return deepcopy(_load(owner_id))


def replace_state(owner_id, payload):
    if not isinstance(payload, dict):
        raise ValueError('Backup inválido.')
    state = _default_state()
    state['projects'] = payload.get('projects') if isinstance(payload.get('projects'), list) else []
    state['chat'] = payload.get('chat') if isinstance(payload.get('chat'), list) else []
    state['searchHistory'] = payload.get('searchHistory') if isinstance(payload.get('searchHistory'), list) else []
    state['activeProjectId'] = str(payload.get('activeProjectId') or '')
    state['chat'] = state['chat'][-500:]
    state['searchHistory'] = state['searchHistory'][:500]
    with _LOCK:
        _save(owner_id, state)


def create_project(owner_id, project):
    with _LOCK:
        state = _load(owner_id)
        now = _now_iso()
        item = {**project, 'createdAt': now, 'updatedAt': now, 'documents': []}
        state['projects'].insert(0, item)
        _save(owner_id, state)
        return deepcopy(item)


def update_project(owner_id, project_id, fields):
    with _LOCK:
        state = _load(owner_id)
        for project in state['projects']:
            if project.get('id') == project_id:
                project.update(fields)
                project['updatedAt'] = _now_iso()
                _save(owner_id, state)
                return {'updated_at': datetime.now(timezone.utc)}
        return None


def delete_project(owner_id, project_id):
    with _LOCK:
        state = _load(owner_id)
        before = len(state['projects'])
        state['projects'] = [p for p in state['projects'] if p.get('id') != project_id]
        if state.get('activeProjectId') == project_id:
            state['activeProjectId'] = ''
        _save(owner_id, state)
        return before - len(state['projects'])


def set_active_project(owner_id, project_id):
    with _LOCK:
        state = _load(owner_id)
        if project_id and not any(p.get('id') == project_id for p in state['projects']):
            raise ValueError('Projeto não encontrado.')
        state['activeProjectId'] = project_id or ''
        _save(owner_id, state)


def insert_document(owner_id, project_id, document):
    with _LOCK:
        state = _load(owner_id)
        for project in state['projects']:
            if project.get('id') == project_id:
                doc = deepcopy(document)
                doc['importedAt'] = doc.get('importedAt') or _now_iso()
                project.setdefault('documents', []).insert(0, doc)
                project['updatedAt'] = _now_iso()
                _save(owner_id, state)
                return deepcopy(doc)
        raise ValueError('Projeto não encontrado.')


def delete_document(owner_id, document_id):
    with _LOCK:
        state = _load(owner_id)
        found = False
        for project in state['projects']:
            docs = project.get('documents') or []
            new_docs = [d for d in docs if d.get('id') != document_id]
            if len(new_docs) != len(docs):
                found = True
                project['documents'] = new_docs
                project['updatedAt'] = _now_iso()
        if found:
            _save(owner_id, state)
        return found



def delete_document_by_source(owner_id, source_path):
    source_path = str(source_path or '').replace('\\', '/').strip()
    if not source_path:
        return 0
    with _LOCK:
        state = _load(owner_id)
        removed = 0
        for project in state['projects']:
            docs = project.get('documents') or []
            new_docs = []
            for doc in docs:
                current = str(doc.get('sourcePath') or '').replace('\\', '/').strip()
                if current == source_path:
                    removed += 1
                else:
                    new_docs.append(doc)
            if len(new_docs) != len(docs):
                project['documents'] = new_docs
                project['updatedAt'] = _now_iso()
        if removed:
            _save(owner_id, state)
        return removed

def add_chat_message(owner_id, item):
    with _LOCK:
        state = _load(owner_id)
        entry = deepcopy(item)
        entry['id'] = entry.get('id') or f"chat_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        entry['ts'] = entry.get('ts') or int(datetime.now(timezone.utc).timestamp() * 1000)
        entry['type'] = 'assistant' if entry.get('type') == 'assistant' else 'user'
        state['chat'].append(entry)
        state['chat'] = state['chat'][-500:]
        _save(owner_id, state)
        return {'id': entry['id'], 'created_at': datetime.now(timezone.utc)}


def clear_chat(owner_id):
    with _LOCK:
        state = _load(owner_id)
        state['chat'] = []
        _save(owner_id, state)


def add_history(owner_id, item):
    with _LOCK:
        state = _load(owner_id)
        entry = deepcopy(item)
        entry['createdAt'] = entry.get('createdAt') or _now_iso()
        state['searchHistory'].insert(0, entry)
        state['searchHistory'] = state['searchHistory'][:500]
        _save(owner_id, state)


def delete_history(owner_id, history_id=None):
    with _LOCK:
        state = _load(owner_id)
        if history_id:
            state['searchHistory'] = [h for h in state['searchHistory'] if h.get('id') != history_id]
        else:
            state['searchHistory'] = []
        _save(owner_id, state)
