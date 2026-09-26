"""Configuração gráfica do Agente Local Alexandre AI para Windows.
Sem BAT e sem terminal. Executar uma única vez com duplo clique.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

if os.name != 'nt':
    raise SystemExit('Este configurador deve ser executado no Windows.')

APP_DIR = Path(os.getenv('LOCALAPPDATA', Path.home())) / 'AlexandreAI'
CONFIG_FILE = APP_DIR / 'agent_config.json'
SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_AGENT = SCRIPT_DIR / 'agente_local.pyw'
REQ_FILE = SCRIPT_DIR / 'requirements-local.txt'
INSTALLED_AGENT = APP_DIR / 'agente_local.pyw'
DEFAULT_URL = 'https://agente-de-ia-alexandre.onrender.com'
DEFAULT_FOLDER = r'C:\agenteIA'


def register_startup(agent_path: Path):
    import winreg
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    command = f'"{pythonw}" "{agent_path}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, 'AlexandreAI', 0, winreg.REG_SZ, command)
    return pythonw


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Alexandre AI - Conectar pasta pessoal')
        self.geometry('680x520')
        self.minsize(680, 520)
        self.configure(bg='#0a0e15')

        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('TLabel', background='#0a0e15', foreground='#eaf2ff', font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI Semibold', 20), foreground='#ffffff')
        style.configure('Sub.TLabel', foreground='#9aabc3')
        style.configure('TButton', font=('Segoe UI Semibold', 10), padding=8)

        frame = ttk.Frame(self, padding=24)
        frame.pack(fill='both', expand=True)
        frame.configure(style='TFrame')
        style.configure('TFrame', background='#0a0e15')

        ttk.Label(frame, text='Alexandre AI', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='Conecte C:\\agenteIA ao seu agente online. Depois disso, a sincronização será automática.', style='Sub.TLabel').pack(anchor='w', pady=(2, 20))

        form = ttk.Frame(frame)
        form.pack(fill='x')

        ttk.Label(form, text='URL do agente').grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.url = tk.StringVar(value=DEFAULT_URL)
        tk.Entry(form, textvariable=self.url, bg='#111722', fg='#eaf2ff', insertbackground='white', relief='flat', font=('Segoe UI', 10)).grid(row=1, column=0, columnspan=2, sticky='ew', ipady=9)

        ttk.Label(form, text='Pasta pessoal').grid(row=2, column=0, sticky='w', pady=(16, 5))
        self.folder = tk.StringVar(value=DEFAULT_FOLDER)
        tk.Entry(form, textvariable=self.folder, bg='#111722', fg='#eaf2ff', insertbackground='white', relief='flat', font=('Segoe UI', 10)).grid(row=3, column=0, sticky='ew', ipady=9)
        ttk.Button(form, text='Escolher...', command=self.pick_folder).grid(row=3, column=1, padx=(8, 0), sticky='ew')

        ttk.Label(form, text='SYNC_TOKEN do Render').grid(row=4, column=0, sticky='w', pady=(16, 5))
        self.token = tk.StringVar()
        tk.Entry(form, textvariable=self.token, show='•', bg='#111722', fg='#eaf2ff', insertbackground='white', relief='flat', font=('Segoe UI', 10)).grid(row=5, column=0, columnspan=2, sticky='ew', ipady=9)
        form.columnconfigure(0, weight=1)

        self.status = tk.StringVar(value='Pronto para configurar.')
        ttk.Label(frame, textvariable=self.status, style='Sub.TLabel').pack(anchor='w', pady=(18, 8))
        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.pack(fill='x')

        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=(20, 0))
        self.install_btn = ttk.Button(btns, text='Conectar pasta e ativar sincronização', command=self.install)
        self.install_btn.pack(side='left')
        ttk.Button(btns, text='Abrir C:\\agenteIA', command=self.open_folder).pack(side='left', padx=8)
        ttk.Button(btns, text='Fechar', command=self.destroy).pack(side='right')

        note = (
            'Depois da configuração, o Alexandre AI inicia junto com o Windows. '
            'Ao lado da pasta C:\\agenteIA serão criados “Alexandre AI - Status.html” '
            'e “Alexandre AI - Abrir.url”. Nenhum BAT será necessário.'
        )
        ttk.Label(frame, text=note, wraplength=620, style='Sub.TLabel').pack(anchor='w', pady=(22, 0))

    def pick_folder(self):
        selected = filedialog.askdirectory(initialdir='C:\\' if Path('C:\\').exists() else str(Path.home()))
        if selected:
            self.folder.set(selected)

    def open_folder(self):
        p = Path(self.folder.get().strip() or DEFAULT_FOLDER)
        p.mkdir(parents=True, exist_ok=True)
        os.startfile(str(p))

    def install(self):
        url = self.url.get().strip().rstrip('/')
        folder = self.folder.get().strip() or DEFAULT_FOLDER
        token = self.token.get().strip()
        if not url.startswith('http'):
            messagebox.showerror('Alexandre AI', 'Informe uma URL válida do agente.')
            return
        if not token:
            messagebox.showerror('Alexandre AI', 'Informe o SYNC_TOKEN configurado no Render.')
            return
        self.install_btn.configure(state='disabled')
        self.progress.start(10)
        self.status.set('Configurando o agente local...')
        threading.Thread(target=self._install_worker, args=(url, folder, token), daemon=True).start()

    def _install_worker(self, url, folder, token):
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            Path(folder).mkdir(parents=True, exist_ok=True)
            self.after(0, lambda: self.status.set('Instalando componentes necessários...'))
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--user', '-r', str(REQ_FILE)], creationflags=0x08000000)

            shutil.copy2(SOURCE_AGENT, INSTALLED_AGENT)
            CONFIG_FILE.write_text(json.dumps({
                'agent_url': url,
                'folder': folder,
                'sync_token': token,
            }, ensure_ascii=False, indent=2), encoding='utf-8')

            pythonw = register_startup(INSTALLED_AGENT)
            self.after(0, lambda: self.status.set('Iniciando monitor automático...'))
            subprocess.Popen([str(pythonw), str(INSTALLED_AGENT)], creationflags=0x08000000)

            self.after(0, self._done)
        except Exception as exc:
            self.after(0, lambda e=exc: self._failed(e))

    def _done(self):
        self.progress.stop()
        self.install_btn.configure(state='normal')
        self.status.set('Conectado. O monitor já está acompanhando sua pasta.')
        messagebox.showinfo(
            'Alexandre AI',
            'Configuração concluída.\n\n'
            'A sincronização agora é automática.\n'
            'Veja “Alexandre AI - Status.html” ao lado da pasta agenteIA para confirmar o funcionamento.'
        )

    def _failed(self, exc):
        self.progress.stop()
        self.install_btn.configure(state='normal')
        self.status.set('Não foi possível concluir a configuração.')
        messagebox.showerror('Alexandre AI', f'Erro: {exc}')


if __name__ == '__main__':
    App().mainloop()
