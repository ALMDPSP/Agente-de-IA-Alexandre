"""Alexandre AI Local Agent - monitora C:\\agenteIA e sincroniza automaticamente.

Executa silenciosamente na bandeja do Windows. Sem BAT.
Cria um painel visível ao lado da pasta monitorada para confirmar o status local.
"""
import json
import os
import queue
import socket
import threading
import time
import webbrowser
from html import escape
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
        self.last_success = None
        self.last_error = ''
        self.detected_files = 0
        # Ficam AO LADO da pasta C:\agenteIA, por exemplo em C:\
        self.sidecar_status = self.root.parent / 'Alexandre AI - Status.html'
        self.sidecar_open = self.root.parent / 'Alexandre AI - Abrir.url'

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

    def count_files(self):
        try:
            self.detected_files = sum(
                1 for p in self.root.rglob('*')
                if p.is_file() and p.suffix.lower() in SUPPORTED
            )
        except Exception:
            self.detected_files = 0
        return self.detected_files

    def write_sidecars(self):
        """Cria/atualiza painel e atalho visíveis ao lado da pasta monitorada."""
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self.count_files()
            self.sidecar_open.write_text(
                '[InternetShortcut]\nURL=' + self.base_url + '\n', encoding='utf-8'
            )
            last = (
                time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(self.last_success))
                if self.last_success else 'Ainda não concluída'
            )
            now = time.strftime('%d/%m/%Y %H:%M:%S')
            html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta http-equiv="refresh" content="10">
<title>Alexandre AI - Status</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;background:#090c12;color:#eaf2ff;margin:0;padding:32px}}
.card{{max-width:760px;margin:auto;background:#111722;border:1px solid #28344a;border-radius:18px;padding:26px;box-shadow:0 18px 50px #0008}}
h1{{margin:0 0 6px;font-size:26px}} .ok{{color:#72f1b8}} .muted{{color:#93a4bd}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:22px}}
.box{{background:#0c111a;border:1px solid #202b3e;border-radius:12px;padding:15px}}
b{{display:block;color:#9cb8ff;margin-bottom:5px}} .err{{margin-top:14px;background:#171018;border:1px solid #4a2742;border-radius:12px;padding:15px}}
a{{color:#80b7ff}}
</style></head><body><div class="card">
<h1>Alexandre AI <span class="ok">●</span></h1><div class="muted">Monitor local do conhecimento pessoal</div>
<div class="grid">
<div class="box"><b>Pasta monitorada</b>{escape(str(self.root))}</div>
<div class="box"><b>Status</b>{escape(self.status)}</div>
<div class="box"><b>Arquivos encontrados</b>{self.detected_files}</div>
<div class="box"><b>Pendentes</b>{self.pending}</div>
<div class="box"><b>Última sincronização</b>{last}</div>
<div class="box"><b>Atualizado em</b>{now}</div>
</div><div class="err"><b>Último erro</b>{escape(self.last_error or 'Nenhum')}</div>
<p><a href="{escape(self.base_url)}">Abrir Alexandre AI online</a></p>
<div class="muted">Esta página atualiza automaticamente a cada 10 segundos.</div>
</div></body></html>"""
            self.sidecar_status.write_text(html, encoding='utf-8')
        except Exception as exc:
            log(f'Falha criando painel local: {exc}')

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
        self.write_sidecars()

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
                    self.last_success = time.time()
                    self.last_error = ''
                    log(f'OK {relative}')
                    self.write_sidecars()
                    return
                self.last_error = f'HTTP {r.status_code} ao enviar {relative}'
                log(f'HTTP {r.status_code} em {relative}: {r.text[:300]}')
            except Exception as exc:
                self.last_error = f'Falha ao enviar {relative}: {exc}'
                log(f'Falha {relative} tentativa {attempt + 1}: {exc}')
            self.write_sidecars()
            time.sleep(2 ** attempt)
        self.errors += 1
        self.status = 'erro de sincronização'
        self.write_sidecars()

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
                self.last_success = time.time()
                self.last_error = ''
                log(f'REMOVIDO {relative}')
            else:
                self.errors += 1
                self.last_error = f'Erro removendo {relative}: HTTP {r.status_code}'
                log(f'Erro removendo {relative}: HTTP {r.status_code} {r.text[:300]}')
        except Exception as exc:
            self.errors += 1
            self.last_error = f'Falha removendo {relative}: {exc}'
            log(f'Falha removendo {relative}: {exc}')
        self.write_sidecars()

    def full_sync(self):
        self.root.mkdir(parents=True, exist_ok=True)
        files = [p for p in self.root.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED]
        self.detected_files = len(files)
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
                    self.write_sidecars()

    def heartbeat(self):
        while not self.stop_event.is_set():
            try:
                r = requests.post(
                    f'{self.base_url}/api/sync/heartbeat',
                    headers={**self.headers(), 'Content-Type': 'application/json'},
                    json={
                        'computer': socket.gethostname(), 'folder': str(self.root), 'status': self.status,
                        'pending': self.pending, 'synced': self.synced, 'errors': self.errors,
                        'detectedFiles': self.count_files(),
                    }, timeout=20,
                )
                if r.ok:
                    if self.status == 'iniciando':
                        self.status = 'conectado'
                    self.last_error = ''
                else:
                    self.last_error = f'Heartbeat HTTP {r.status_code}'
            except Exception as exc:
                self.last_error = f'Servidor não respondeu: {exc}'
                log(f'Heartbeat: {exc}')
            self.write_sidecars()
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
    engine.write_sidecars()
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

    def open_status(icon, item):
        engine.write_sidecars()
        os.startfile(str(engine.sidecar_status))

    def sync_now(icon, item):
        threading.Thread(target=engine.full_sync, daemon=True).start()

    def quit_app(icon, item):
        engine.stop_event.set()
        observer.stop()
        observer.join(timeout=3)
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem('Abrir Alexandre AI', open_site, default=True),
        pystray.MenuItem(r'Abrir C:\agenteIA', open_folder),
        pystray.MenuItem('Ver status da pasta', open_status),
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
