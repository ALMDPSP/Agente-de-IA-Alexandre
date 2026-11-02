# MVP de diário alimentar
import base64, json, os, re, threading, uuid
from datetime import datetime, timezone
from pathlib import Path
import requests
from flask import jsonify, render_template, request
from flask_login import login_required, current_user

from wellness_storage import read_state, update_state
from ai_providers import analyze
from personal_ai import get_config, generate

MAX_IMG=5*1024*1024

def _user(): return str(current_user.get_id())

def _state(): return read_state(_user())

def _update(mutator): return update_state(_user(), mutator)

def _gemini(parts,prompt):
    key=(os.getenv('GEMINI_API_KEY') or '').strip()
    if not key:raise RuntimeError('Configure GEMINI_API_KEY no Render.')
    model=(os.getenv('GEMINI_MODEL') or 'gemini-2.5-flash').strip()
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    data={'contents':[{'role':'user','parts':[{'text':prompt}]+parts}], 'generationConfig':{'temperature':0.2,'maxOutputTokens':1200}}
    r=requests.post(url,params={'key':key},json=data,timeout=60)
    if not r.ok:raise RuntimeError(f'Gemini indisponível (HTTP {r.status_code}). Verifique o modelo e a chave.')
    d=r.json();return '\n'.join(p.get('text','') for c in d.get('candidates',[]) for p in c.get('content',{}).get('parts',[]) if p.get('text'))

def _json_reply(text):
    text=re.sub(r'^```(?:json)?|```$','',text.strip(),flags=re.I).strip()
    try:return json.loads(text)
    except ValueError:
        start=text.find('{');end=text.rfind('}')
        if start>=0 and end>start:return json.loads(text[start:end+1])
        raise ValueError('A IA não retornou uma análise estruturada. Tente outra foto.')

def register_health_routes(app):
    @app.route('/evolucao')
    @login_required
    def evolucao():return render_template('evolucao.html',user=current_user)

    @app.route('/api/evolucao/estado')
    @login_required
    def evolucao_estado():return jsonify(_state())

    @app.route('/api/evolucao/perfil',methods=['POST'])
    @login_required
    def evolucao_perfil():
        data=request.get_json(silent=True) or {}
        name=str(data.get('name',''))[:70]
        try:
            goal=float(data.get('goal',0));height=float(data.get('height',0))
            if not (25<=goal<=350 and 90<=height<=230):raise ValueError()
        except (ValueError,TypeError):return jsonify(error='Informe altura e meta válidas.'),400
        _update(lambda state: state.update(profile={'name':name,'goal':goal,'height':height}))
        return jsonify(ok=True)

    @app.route('/api/evolucao/peso',methods=['POST'])
    @login_required
    def evolucao_peso():
        data=request.get_json(silent=True) or {}
        try:
            w=float(data.get('weight'))
            if not 25<=w<=350:raise ValueError()
        except (ValueError,TypeError):return jsonify(error='Peso inválido.'),400
        entry={'id':str(uuid.uuid4()),'weight':round(w,1),'at':datetime.now(timezone.utc).isoformat()}
        _update(lambda state: state.setdefault('weights',[]).append(entry));return jsonify(entry),201

    @app.route('/api/evolucao/refeicao',methods=['POST'])
    @login_required
    def evolucao_refeicao():
        f=request.files.get('photo');kind=str(request.form.get('kind','Refeição'))[:35]
        if not f:return jsonify(error='Envie uma foto do prato.'),400
        raw=f.read(MAX_IMG+1)
        if not raw or len(raw)>MAX_IMG:return jsonify(error='A foto deve ter até 5 MB.'),400
        detected=('jpeg' if raw.startswith(bytes.fromhex('ffd8ff')) else 'png' if raw.startswith(bytes.fromhex('89504e470d0a1a0a')) else 'webp' if raw[:4]==b'RIFF' and raw[8:12]==b'WEBP' else None)
        mimetype={'jpeg':'image/jpeg','png':'image/png','webp':'image/webp'}.get(detected)
        if not mimetype:return jsonify(error='Envie imagem JPG, PNG ou WEBP.'),400
        prompt='''Analise a foto como assistente educacional de alimentação, em português brasileiro. Identifique apenas alimentos visíveis, não presuma ingredientes invisíveis. Estime calorias somente como intervalo amplo e com alto grau de incerteza; a foto não permite peso nem calorias exatos. Responda SOMENTE JSON válido com campos: alimentos (lista de strings), calorias_min (inteiro ou null), calorias_max (inteiro ou null), observacoes (string curta), sugestao (string curta). Se não for prato de comida, use alimentos vazio, valores null e explique. Não faça julgamento moral nem dê diagnóstico.'''
        try:
            personal=get_config(_user(),reveal=True)
            image=(mimetype,base64.b64encode(raw).decode('ascii'))
            analysis=generate(personal,[{'role':'user','content':prompt}],image=image) if personal else analyze(prompt,image=image)
            result=_json_reply(analysis['text'])
            foods=result.get('alimentos',[])
            if not isinstance(foods,list):foods=[]
            entry={'id':str(uuid.uuid4()),'kind':kind,'at':datetime.now(timezone.utc).isoformat(),'alimentos':[str(x)[:100] for x in foods[:20]],'calorias_min':result.get('calorias_min'),'calorias_max':result.get('calorias_max'),'observacoes':str(result.get('observacoes',''))[:1000],'sugestao':str(result.get('sugestao',''))[:1000],'provider':analysis['provider']}
            # A imagem não é salva. Armazenamos somente a análise resumida.
            _update(lambda state: state.setdefault('meals',[]).append(entry))
            return jsonify(entry),201
        except (RuntimeError,ValueError,requests.RequestException) as exc:return jsonify(error=str(exc)[:220]),502

    @app.route('/api/evolucao/conversas',methods=['DELETE'])
    @login_required
    def limpar_conversas():
        _update(lambda state: state.update(chat_history=[]))
        return jsonify(ok=True)

    @app.route('/api/evolucao/chat',methods=['POST'])
    @login_required
    def evolucao_chat():
        data=request.get_json(silent=True) or {};q=str(data.get('message','')).strip()[:1400]
        if not q:return jsonify(error='Escreva uma pergunta.'),400
        state=_state();recent=state.get('meals',[])[-12:];profile=state.get('profile',{})
        prompt='''Você é um acompanhante virtual de hábitos alimentares em português do Brasil, acolhedor, prático e sem julgamento. Não se apresente como nutricionista registrado. Não prescreva medicamentos, calorias restritivas ou metas rápidas. Fotos e contagens são estimativas; peça confirmação de porções. Em sinais de transtorno alimentar ou sintomas importantes, incentive avaliação profissional. Contexto resumido: '''+json.dumps({'perfil':profile,'refeicoes':recent},ensure_ascii=False)[:6500]+'\nPergunta: '+q
        try:
            personal=get_config(_user(),reveal=True)
            response=generate(personal,[{'role':'user','content':prompt}]) if personal else analyze(prompt)
            _update(lambda state: (state.setdefault('chat_history',[]).append({'question':q[:1400],'answer':response['text'][:4500],'at':datetime.now(timezone.utc).isoformat(),'provider':response['provider']}), state.__setitem__('chat_history',state['chat_history'][-60:])))
            return jsonify(answer=response['text'][:4500],provider=response['provider'])
        except (RuntimeError,requests.RequestException) as exc:return jsonify(error=str(exc)[:200]),502
