"""Alexandre AI Local Agent - monitora C:\\agenteIA e sincroniza automaticamente.

Executa silenciosamente na bandeja do Windows. Use instalar_agente_local.py uma única vez.
"""
import json
import os
import queue
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import requests
from PIL import Image, ImageDraw
import pystray
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

APP_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "AlexandreAI"
CONFIG_FILE = APP_DIR / "agent_config.json"
LOG_FILE = APP_DIR / "agent_local.log"
SUPPORTED = {'.pdf', '.docx', '.xlsx', '.xlsm', '.txt', '.md', '.csv', '.json', '.log', '.xml', '.html', '.htm'}
DEBOUNCE_SECONDS = 2.0
HEARTBEAT_SECONDS = 60


def log(message):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        with LOG_FILE.open('a', encoding='utf-8') as fh:
            fh.write(f'[{stamp}] {message}\n')
    except Exception:
        pass


def load_config():
    if not CONFIG_FILE.exists():
        raise RuntimeError(f'Configuração não encontrada: {CONFIG_FILE}')
    cfg = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    cfg['agent_url'] = str(cfg.get('agent_url') or '').rstrip('/')
    cfg['folder'] = str(cfg.get('folder') or r'C:\agenteIA')
    cfg['sync_token'] = str(cfg.get('sync_token') or '')
    if not cfg['agent_url'] or not cfg['sync_token']:
        raise RuntimeError('URL ou token de sincronização ausente.')
    return cfg


class SyncEngine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = Path(cfg['folder'])
        self.base_url = cfg['agent_url']
        self.token = cfg['sync_token']
        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.last_queued = {}
        self.synced = 0
        self.errors = 0
        self.pending = 0
        self.status = 'iniciando'
        self.icon = None

    def headers(self):
        return {'X-Sync-Token': self.token}

    def relative(self, path):
        try:
            return Path(path).resolve().relative_to(self.root.resolve()).as_posix()
        except Exception:
            return Path(path).name

    def supported(self, path):
        p = Path(path)
        return p.is_file() and p.suffix.lower() in SUPPORTED

    def queue_sync(self, path):
        p = Path(path)
        if p.suffix.lower() not in SUPPORTED:
            return
        key = str(p)
        now = time.time()
        if now - self.last_queued.get(key, 0) < DEBOUNCE_SECONDS:
            return
        self.last_queued[key] = now
        self.q.put(('sync', key))
        self.update_pending()

    def queue_delete(self, path):
        p = Path(path)
        if p.suffix.lower() not in SUPPORTED:
            return
        self.q.put(('delete', str(p)))
        self.update_pending()

    def update_pending(self):
        self.pending = self.q.qsize()
        if self.icon:
            self.icon.title = self.tooltip()

    def tooltip(self):
        return f'Alexandre AI - {self.status} | pendentes: {self.pending}'[:120]

    def upload(self, path):
        p = Path(path)
        if not p.exists() or not p.is_file() or p.suffix.lower() not in SUPPORTED:
            return
        relative = self.relative(p)
        endpoint = f'{self.base_url}/api/sync/local-file'
        for attempt in range(3):
            try:
                with p.open('rb') as handle:
                    r = requests.post(
                        endpoint,
                        headers=self.headers(),
                        data={'relativePath': relative, 'sourceMtime': str(p.stat().st_mtime), 'projectName': 'Conhecimento Local'},
                        files={'file': (relative, handle)},
                        timeout=180,
                    )
                if r.ok:
                    self.synced += 1
                    self.status = 'sincronizado'
                    log(f'OK {relative}')
                    return
                log(f'HTTP {r.status_code} em {relative}: {r.text[:300]}')
            except Exception as exc:
                log(f'Falha {relative} tentativa {attempt + 1}: {exc}')
            time.sleep(2 ** attempt)
        self.errors += 1
        self.status = 'erro de sincronização'

    def delete_remote(self, path):
        relative = self.relative(path)
        try:
            r = requests.post(
                f'{self.base_url}/api/sync/delete',
                headers={**self.headers(), 'Content-Type': 'application/json'},
                json={'relativePath': relative}, timeout=30,
            )
            if r.ok:
                self.status = 'sincronizado'
                log(f'REMOVIDO {relative}')
            else:
                self.errors += 1
                log(f'Erro removendo {relative}: HTTP {r.status_code} {r.text[:300]}')
        except Exception as exc:
            self.errors += 1
            log(f'Falha removendo {relative}: {exc}')

    def full_sync(self):
        self.root.mkdir(parents=True, exist_ok=True)
        files = [p for p in self.root.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED]
        self.status = f'sincronizando {len(files)} arquivo(s)'
        for p in files:
            self.q.put(('sync', str(p)))
        self.update_pending()
        log(f'Sincronização completa enfileirada: {len(files)} arquivo(s)')

    def worker(self):
        while not self.stop_event.is_set():
            try:
                action, path = self.q.get(timeout=1)
            except queue.Empty:
                continue
            self.status = 'sincronizando'
            self.update_pending()
            try:
                if action == 'sync':
                    self.upload(path)
                elif action == 'delete':
                    self.delete_remote(path)
            finally:
                self.q.task_done()
                self.update_pending()
                if self.q.empty() and self.status != 'erro de sincronização':
                    self.status = 'sincronizado'

    def heartbeat(self):
        while not self.stop_event.is_set():
            try:
                requests.post(
                    f'{self.base_url}/api/sync/heartbeat',
                    headers={**self.headers(), 'Content-Type': 'application/json'},
                    json={
                        'computer': socket.gethostname(), 'folder': str(self.root), 'status': self.status,
                        'pending': self.pending, 'synced': self.synced, 'errors': self.errors,
                    }, timeout=20,
                )
            except Exception as exc:
                log(f'Heartbeat: {exc}')
            self.stop_event.wait(HEARTBEAT_SECONDS)


class Handler(FileSystemEventHandler):
    def __init__(self, engine):
        self.engine = engine

    def on_created(self, event):
        if not event.is_directory:
            self.engine.queue_sync(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.engine.queue_sync(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.engine.queue_delete(event.src_path)
            self.engine.queue_sync(event.dest_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self.engine.queue_delete(event.src_path)


def tray_image():
    img = Image.new('RGB', (64, 64), 'black')
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((7, 7, 57, 57), radius=12, outline='white', width=3)
    d.line((18, 46, 32, 17, 46, 46), fill='white', width=5)
    d.ellipse((28, 35, 36, 43), fill='white')
    return img


def main():
    try:
        cfg = load_config()
    except Exception as exc:
        log(f'Erro de configuração: {exc}')
        return

    engine = SyncEngine(cfg)
    engine.root.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=engine.worker, daemon=True).start()
    threading.Thread(target=engine.heartbeat, daemon=True).start()

    observer = Observer()
    observer.schedule(Handler(engine), str(engine.root), recursive=True)
    observer.start()
    engine.full_sync()

    def open_site(icon, item):
        webbrowser.open(engine.base_url)

    def open_folder(icon, item):
        os.startfile(str(engine.root))

    def sync_now(icon, item):
        threading.Thread(target=engine.full_sync, daemon=True).start()

    def quit_app(icon, item):
        engine.stop_event.set()
        observer.stop()
        observer.join(timeout=3)
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem('Abrir Alexandre AI', open_site, default=True),
        pystray.MenuItem('Abrir C:\\agenteIA', open_folder),
        pystray.MenuItem('Sincronizar agora', sync_now),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Sair', quit_app),
    )
    icon = pystray.Icon('AlexandreAI', tray_image(), engine.tooltip(), menu)
    engine.icon = icon
    log('Agente Local iniciado.')
    icon.run()


if __name__ == '__main__':
    main()
