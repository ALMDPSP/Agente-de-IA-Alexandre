"""Instalador único do Agente Local Alexandre AI para Windows.
Não usa arquivo BAT. Configura dependências, pasta, credenciais e inicialização automática.
"""
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

if os.name != 'nt':
    print('Este instalador deve ser executado no Windows.')
    raise SystemExit(1)

APP_DIR = Path(os.getenv('LOCALAPPDATA', Path.home())) / 'AlexandreAI'
CONFIG_FILE = APP_DIR / 'agent_config.json'
SCRIPT_DIR = Path(__file__).resolve().parent
AGENT_SCRIPT = SCRIPT_DIR / 'agente_local.pyw'
REQ_FILE = SCRIPT_DIR / 'requirements-local.txt'

print('=' * 64)
print(' ALEXANDRE AI - INSTALAÇÃO DO AGENTE LOCAL')
print('=' * 64)
print('Este processo é executado apenas uma vez. Depois, o agente inicia')
print('automaticamente com o Windows e monitora C:\\agenteIA.')
print()

url = input('URL do Alexandre AI [https://agente-de-ia-alexandre.onrender.com]: ').strip() or 'https://agente-de-ia-alexandre.onrender.com'
folder = input(r'Pasta de conhecimento [C:\agenteIA]: ').strip() or r'C:\agenteIA'
token = getpass.getpass('SYNC_TOKEN configurado no Render: ').strip()
if not token:
    print('ERRO: SYNC_TOKEN é obrigatório.')
    raise SystemExit(2)

print('\nInstalando componentes do monitor local...')
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', str(REQ_FILE)])

APP_DIR.mkdir(parents=True, exist_ok=True)
Path(folder).mkdir(parents=True, exist_ok=True)
CONFIG_FILE.write_text(json.dumps({
    'agent_url': url.rstrip('/'),
    'folder': folder,
    'sync_token': token,
}, ensure_ascii=False, indent=2), encoding='utf-8')

import winreg
pythonw = Path(sys.executable).with_name('pythonw.exe')
command = f'"{pythonw}" "{AGENT_SCRIPT}"'
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE) as key:
    winreg.SetValueEx(key, 'AlexandreAI', 0, winreg.REG_SZ, command)

subprocess.Popen([str(pythonw), str(AGENT_SCRIPT)], creationflags=0x00000008)
print('\nInstalação concluída.')
print(f'Pasta monitorada: {folder}')
print('O ícone Alexandre AI ficará na bandeja do Windows.')
print('A partir de agora, basta colocar arquivos na pasta monitorada.')
input('\nPressione Enter para fechar...')
