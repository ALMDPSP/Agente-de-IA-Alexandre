import os
import sys
if os.name != 'nt':
    raise SystemExit('Execute no Windows.')
import winreg
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE) as key:
        winreg.DeleteValue(key, 'AlexandreAI')
    print('Inicialização automática removida. Feche o ícone Alexandre AI na bandeja caso esteja em execução.')
except FileNotFoundError:
    print('O Agente Local não estava registrado na inicialização automática.')
