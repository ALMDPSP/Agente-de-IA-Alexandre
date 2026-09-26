"""Sincroniza C:\\agenteIA com a versão online do Agente IA Alexandre.

Configure antes de executar:
  AGENT_URL=https://seu-servico.onrender.com
  SYNC_TOKEN=um-token-forte-igual-ao-configurado-no-servidor
Opcional:
  LOCAL_KNOWLEDGE_DIR=C:\\agenteIA
  SYNC_PROJECT_NAME=Conhecimento Local
"""
import os
import sys
from pathlib import Path

import requests

SUPPORTED = {'.pdf', '.docx', '.xlsx', '.xlsm', '.txt', '.md', '.csv', '.json', '.log', '.xml', '.html', '.htm'}


def main():
    folder = Path(os.getenv('LOCAL_KNOWLEDGE_DIR', r'C:\agenteIA'))
    base_url = (os.getenv('AGENT_URL') or '').strip().rstrip('/')
    token = (os.getenv('SYNC_TOKEN') or '').strip()
    project_name = (os.getenv('SYNC_PROJECT_NAME') or 'Conhecimento Local').strip()

    if not base_url:
        print('ERRO: defina AGENT_URL com o endereço da versão online.')
        return 2
    if not token:
        print('ERRO: defina SYNC_TOKEN.')
        return 2
    if not folder.exists() or not folder.is_dir():
        print(f'ERRO: pasta não encontrada: {folder}')
        return 2

    files = [p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED]
    if not files:
        print(f'Nenhum arquivo compatível encontrado em {folder}.')
        return 0

    print(f'Sincronizando {len(files)} arquivo(s) de {folder} para {base_url}...')
    ok = 0
    failures = []
    endpoint = f'{base_url}/api/sync/local-file'

    for index, path in enumerate(files, start=1):
        relative = path.relative_to(folder).as_posix()
        print(f'[{index}/{len(files)}] {relative}')
        try:
            with path.open('rb') as handle:
                response = requests.post(
                    endpoint,
                    headers={'X-Sync-Token': token},
                    data={
                        'relativePath': relative,
                        'sourceMtime': str(path.stat().st_mtime),
                        'projectName': project_name,
                    },
                    files={'file': (relative, handle)},
                    timeout=120,
                )
            if response.ok:
                ok += 1
            else:
                try:
                    detail = response.json().get('error') or response.text[:200]
                except Exception:
                    detail = response.text[:200]
                failures.append(f'{relative}: HTTP {response.status_code} - {detail}')
        except Exception as exc:
            failures.append(f'{relative}: {exc}')

    print(f'Concluído: {ok}/{len(files)} arquivo(s) sincronizados.')
    if failures:
        print('\nFalhas:')
        for item in failures:
            print(f' - {item}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
