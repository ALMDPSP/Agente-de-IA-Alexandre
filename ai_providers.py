"""Automatic Gemini -> OpenAI fallback for wellness tasks. No secrets in client-side code."""
import logging
import os
import requests

log = logging.getLogger('wellness.ai')

class ProviderError(RuntimeError):
    def __init__(self, provider, status=None, retryable=False):
        super().__init__(f'{provider} indisponível (HTTP {status or "conexão"}).')
        self.retryable = retryable


def _post(url, *, headers=None, params=None, payload=None):
    try:
        response = requests.post(url, headers=headers, params=params, json=payload, timeout=(5, 19))
    except (requests.Timeout, requests.ConnectionError) as exc:
        raise ProviderError('Provedor IA', retryable=True) from exc
    if not response.ok:
        raise ProviderError('Provedor IA', status=response.status_code,
                            retryable=response.status_code in (408, 429, 500, 502, 503, 504))
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError('Provedor IA', retryable=True) from exc


def _gemini(prompt, image=None):
    key = os.getenv('GEMINI_API_KEY', '').strip()
    model = (os.getenv('GEMINI_MODEL') or 'gemini-2.5-flash').strip()
    parts = [{'text': prompt}]
    if image:
        mime, content = image
        parts.append({'inline_data': {'mime_type': mime, 'data': content}})
    data = _post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                 params={'key': key}, payload={'contents': [{'parts': parts}],
                                               'generationConfig': {'temperature': 0.2, 'maxOutputTokens': 1600}})
    text = '\n'.join(part.get('text', '') for candidate in data.get('candidates', [])
                     for part in candidate.get('content', {}).get('parts', []) if part.get('text'))
    if not text.strip():
        raise ProviderError('Gemini', retryable=False)
    return {'text': text, 'provider': 'Gemini', 'model': model}


def _openai(prompt, image=None):
    key = os.getenv('OPENAI_API_KEY', '').strip()
    model = (os.getenv('OPENAI_MODEL') or 'gpt-4.1-mini').strip()
    content = [{'type': 'text', 'text': prompt}]
    if image:
        mime, encoded = image
        content.append({'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{encoded}', 'detail': 'auto'}})
    data = _post('https://api.openai.com/v1/chat/completions',
                 headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                 payload={'model': model, 'messages': [{'role': 'user', 'content': content}],
                          'temperature': 0.2, 'max_tokens': 1600})
    choices = data.get('choices') or []
    result = (choices[0].get('message', {}).get('content') or '') if choices else ''
    if not isinstance(result, str) or not result.strip():
        raise ProviderError('OpenAI', retryable=False)
    return {'text': result, 'provider': 'OpenAI', 'model': model}


def analyze(prompt, image=None):
    providers = []
    if os.getenv('GEMINI_API_KEY', '').strip():
        providers.append(_gemini)
    if os.getenv('OPENAI_API_KEY', '').strip():
        providers.append(_openai)
    if not providers:
        raise RuntimeError('Configure GEMINI_API_KEY e/ou OPENAI_API_KEY no Render.')
    for i, provider in enumerate(providers):
        try:
            return provider(prompt, image)
        except ProviderError as exc:
            log.warning('Falha de provedor %s (retryable=%s)', provider.__name__, exc.retryable)
            if not exc.retryable or i == len(providers) - 1:
                raise RuntimeError('O serviço de inteligência artificial não pôde concluir a análise.') from exc
    raise RuntimeError('Nenhum provedor disponível.')
