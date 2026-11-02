# Configuração individual de provedores IA
import base64
import hashlib
import os
import re
import requests
from cryptography.fernet import Fernet, InvalidToken
from wellness_storage import connect

PROVIDERS = {
 'gemini': ('Gemini', None, 'gemini-2.5-flash'),
 'openai': ('OpenAI', 'https://api.openai.com/v1/chat/completions', 'gpt-4.1-mini'),
 'anthropic': ('Claude (Anthropic)', 'https://api.anthropic.com/v1/messages', 'claude-sonnet-4-5'),
 'groq': ('Groq', 'https://api.groq.com/openai/v1/chat/completions', 'llama-3.3-70b-versatile'),
 'openrouter': ('OpenRouter', 'https://openrouter.ai/api/v1/chat/completions', 'openai/gpt-4.1-mini'),
 'deepseek': ('DeepSeek', 'https://api.deepseek.com/chat/completions', 'deepseek-chat'),
 'mistral': ('Mistral', 'https://api.mistral.ai/v1/chat/completions', 'mistral-small-latest'),
 'xai': ('Grok (xAI)', 'https://api.x.ai/v1/chat/completions', 'grok-3-mini'),
}

def _cipher():
 secret = os.getenv('AI_CREDENTIALS_KEY') or os.getenv('SECRET_KEY', '')
 if len(secret) < 32 or secret == 'dev-change-me':
  raise RuntimeError('Configure uma SECRET_KEY forte e estável no Render para proteger as credenciais.')
 return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('ai-credentials-v1:' + secret).encode()).digest()))

def init_personal_ai():
 with connect() as conn:
  conn.execute('''CREATE TABLE IF NOT EXISTS user_ai_settings (
     user_id TEXT PRIMARY KEY, provider TEXT NOT NULL,
     model TEXT NOT NULL, encrypted_key TEXT NOT NULL,
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')

def get_config(user_id, reveal=False):
 with connect() as conn:
  row=conn.execute('SELECT provider,model,encrypted_key FROM user_ai_settings WHERE user_id=%s',(str(user_id),)).fetchone()
 if not row: return None
 result={'provider':row['provider'],'model':row['model'],'configured':True}
 if reveal:
  try: result['api_key']=_cipher().decrypt(row['encrypted_key'].encode()).decode()
  except InvalidToken as exc: raise RuntimeError('Chave de IA não pode ser recuperada. Verifique AI_CREDENTIALS_KEY/SECRET_KEY.') from exc
 return result

def save_config(user_id, provider, model, key):
 if provider not in PROVIDERS: raise ValueError('Provedor não suportado.')
 model=(model or PROVIDERS[provider][2]).strip()
 if not re.fullmatch(r'[a-zA-Z0-9._:/-]{2,120}',model): raise ValueError('Nome do modelo inválido.')
 key=(key or '').strip()
 if key and (len(key)<10 or len(key)>1000): raise ValueError('A chave API informada parece inválida.')
 if not key:
  old=get_config(user_id,reveal=True)
  if not old or old['provider']!=provider: raise ValueError('Informe a chave de API do provedor selecionado.')
  key=old['api_key']
 token=_cipher().encrypt(key.encode()).decode()
 with connect() as conn:
  conn.execute('''INSERT INTO user_ai_settings(user_id,provider,model,encrypted_key)
    VALUES(%s,%s,%s,%s) ON CONFLICT(user_id) DO UPDATE SET
    provider=EXCLUDED.provider,model=EXCLUDED.model,encrypted_key=EXCLUDED.encrypted_key,updated_at=NOW()''',
    (str(user_id),provider,model,token))

def delete_config(user_id):
 with connect() as conn: conn.execute('DELETE FROM user_ai_settings WHERE user_id=%s',(str(user_id),))

def _request(url, *, headers=None, params=None, payload=None):
 try: r=requests.post(url,headers=headers,params=params,json=payload,timeout=(10,40))
 except requests.RequestException as exc: raise RuntimeError('Falha de conexão ou tempo excedido no provedor de IA.') from exc
 if not r.ok: raise RuntimeError(f'O provedor de IA retornou HTTP {r.status_code}. Confira a chave, modelo e saldo/cota.')
 try: return r.json()
 except ValueError as exc: raise RuntimeError('O provedor retornou uma resposta inválida.') from exc

def generate(config, messages, image=None):
 provider=config['provider'];model=config['model'];key=config['api_key']
 if provider not in PROVIDERS:raise RuntimeError('Provedor inválido.')
 system='\n\n'.join(str(m.get('content','')) for m in messages if m.get('role')=='system')
 conversation=[m for m in messages if m.get('role') in ('user','assistant')]
 if not conversation: raise RuntimeError('Mensagem vazia.')
 if provider=='gemini':
  contents=[]
  for m in conversation:
   parts=[{'text':str(m.get('content',''))}]
   if image and m is conversation[-1]:parts.append({'inline_data':{'mime_type':image[0],'data':image[1]}})
   contents.append({'role':'model' if m['role']=='assistant' else 'user','parts':parts})
  payload={'contents':contents,'generationConfig':{'temperature':0.3,'maxOutputTokens':1800}}
  if system:payload['systemInstruction']={'parts':[{'text':system}]}
  data=_request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',params={'key':key},payload=payload)
  result='\n'.join(x.get('text','') for c in data.get('candidates',[]) for x in c.get('content',{}).get('parts',[]) if x.get('text'))
 elif provider=='anthropic':
  msgs=[]
  for m in conversation:
   content=[{'type':'text','text':str(m.get('content',''))}]
   if image and m is conversation[-1]:content.append({'type':'image','source':{'type':'base64','media_type':image[0],'data':image[1]}})
   msgs.append({'role':m['role'],'content':content})
  data=_request(PROVIDERS[provider][1],headers={'x-api-key':key,'anthropic-version':'2023-06-01'},payload={'model':model,'system':system,'messages':msgs,'max_tokens':1800})
  result='\n'.join(x.get('text','') for x in data.get('content',[]) if x.get('type')=='text')
 else:
  msgs=[]
  if system:msgs.append({'role':'system','content':system})
  for m in conversation:
   content=str(m.get('content',''))
   if image and m is conversation[-1]:content=[{'type':'text','text':content},{'type':'image_url','image_url':{'url':f'data:{image[0]};base64,{image[1]}'}}]
   msgs.append({'role':m['role'],'content':content})
  data=_request(PROVIDERS[provider][1],headers={'Authorization':'Bearer '+key},payload={'model':model,'messages':msgs,'max_tokens':1800})
  result=((data.get('choices') or [{}])[0].get('message') or {}).get('content','')
 if not isinstance(result,str) or not result.strip():raise RuntimeError('A IA retornou uma resposta vazia.')
 return {'reply':result.strip(),'text':result.strip(),'provider':PROVIDERS[provider][0],'model':model}
