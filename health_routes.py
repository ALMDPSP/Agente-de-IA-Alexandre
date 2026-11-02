# MVP de diário alimentar
import base64, json, os, re, threading, uuid
from datetime import datetime, timezone, date, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
from flask import jsonify, render_template, request, current_app
from flask_login import login_required, current_user

from wellness_storage import read_state, update_state
import psycopg
from ai_providers import analyze

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
    @app.errorhandler(psycopg.Error)
    def database_failure(exc):
        current_app.logger.exception('Falha PostgreSQL ao acessar dados do aplicativo')
        return jsonify(error='Não foi possível acessar o banco de dados. Confira DATABASE_URL, conexão Neon e permissões no Render.'), 503

    @app.errorhandler(RuntimeError)
    def wellness_configuration_failure(exc):
        # Não revelar URLs, tokens ou outros segredos na resposta.
        if request.path.startswith('/api/evolucao/'):
            current_app.logger.exception('Falha de configuração no diário')
            return jsonify(error='Armazenamento indisponível. Verifique DATABASE_URL no Render e os logs do serviço.'), 503
        raise exc

    @app.route('/evolucao')
    @login_required
    def evolucao():return render_template('evolucao.html',user=current_user)

    @app.route('/api/evolucao/estado')
    @login_required
    def evolucao_estado():return jsonify(_state())

    @app.route('/api/evolucao/resumo-mensal')
    @login_required
    def evolucao_resumo_mensal():
        from calendar import monthrange
        tz = ZoneInfo('America/Sao_Paulo')
        today = datetime.now(tz).date()
        month = request.args.get('mes', today.strftime('%Y-%m'))
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
            return jsonify(error='Informe mês válido: AAAA-MM.'), 400
        year, mm = map(int, month.split('-'))
        if not 2020 <= year <= 2100: return jsonify(error='Ano inválido.'), 400
        state = _state()
        days = {f'{month}-{n:02d}': {'kcal': 0, 'refeicoes': 0} for n in range(1, monthrange(year, mm)[1]+1)}
        for meal in state.get('meals', []):
            try:
                dt = datetime.fromisoformat(str(meal['at']).replace('Z','+00:00'))
                if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
                key = dt.astimezone(tz).date().isoformat()
                if key not in days: continue
                a, b = meal.get('calorias_min'), meal.get('calorias_max')
                if a is None or b is None: continue
                kcal=(float(a)+float(b))/2
                if not 0 <= kcal <= 15000:continue
                days[key]['kcal'] += kcal
                days[key]['refeicoes'] += 1
            except (KeyError,ValueError,TypeError,OverflowError): continue
        total = round(sum(v['kcal'] for v in days.values()))
        tracked = sum(v['refeicoes']>0 for v in days.values())
        last = today.isoformat() if month == today.strftime('%Y-%m') else max(days)
        before_today = [k for k in days if k<=last]
        maintenance = (state.get('profile') or {}).get('maintenance_kcal')
        try:
            maintenance=float(maintenance)
            if not 1000<=maintenance<=6000: maintenance=None
        except (ValueError,TypeError): maintenance=None
        # A projeção é só ilustrativa, apenas com os dias registrados e gasto informado.
        deficit = sum(maintenance - days[k]['kcal'] for k in before_today if days[k]['refeicoes']>0) if maintenance else None
        projection = round(max(0,deficit)/7700,2) if deficit is not None else None
        return jsonify(mes=month, hoje=today.isoformat(), total_kcal=total, dias_registrados=tracked,
            manutencao_kcal=maintenance, deficit_estimado_kcal=round(deficit) if deficit is not None else None,
            perda_teorica_kg=projection, dias=[dict(data=k,kcal=round(v['kcal']),refeicoes=v['refeicoes']) for k,v in days.items()])

    @app.route('/api/evolucao/perfil',methods=['POST'])
    @login_required
    def evolucao_perfil():
        data=request.get_json(silent=True) or {}
        name=str(data.get('name',''))[:70]
        try:
            goal=float(data.get('goal',0));height=float(data.get('height',0))
            if not (25<=goal<=350 and 90<=height<=230):raise ValueError()
        except (ValueError,TypeError):return jsonify(error='Informe altura e meta válidas.'),400
        maintenance = data.get('maintenance_kcal')
        if maintenance not in (None, ''):
            try:
                maintenance=float(maintenance)
                if not 1000 <= maintenance <= 6000: raise ValueError()
            except (TypeError,ValueError): return jsonify(error='Gasto diário estimado deve ficar entre 1000 e 6000 kcal.'),400
        else: maintenance = None
        _update(lambda state: state.update(profile={'name':name,'goal':goal,'height':height,'maintenance_kcal':maintenance}))
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
            analysis=analyze(prompt, image=(mimetype,base64.b64encode(raw).decode('ascii')))
            result=_json_reply(analysis['text'])
            foods=result.get('alimentos',[])
            if not isinstance(foods,list):foods=[]
            entry={'id':str(uuid.uuid4()),'kind':kind,'at':datetime.now(timezone.utc).isoformat(),'alimentos':[str(x)[:100] for x in foods[:20]],'calorias_min':result.get('calorias_min'),'calorias_max':result.get('calorias_max'),'observacoes':str(result.get('observacoes',''))[:1000],'sugestao':str(result.get('sugestao',''))[:1000],'provider':analysis['provider']}
            # A imagem não é salva. Armazenamos somente a análise resumida.
            _update(lambda state: state.setdefault('meals',[]).append(entry))
            return jsonify(entry),201
        except (RuntimeError,ValueError,requests.RequestException) as exc:return jsonify(error=str(exc)[:220]),502

    @app.route('/api/evolucao/ia/status')
    @login_required
    def evolucao_ia_status():
        # Exibe somente disponibilidade de configuração, nunca segredos.
        providers=[p for p,key in [('Gemini','GEMINI_API_KEY'),('OpenAI','OPENAI_API_KEY')] if os.getenv(key,'').strip()]
        return jsonify(configured=bool(providers),providers=providers)

    @app.route('/api/evolucao/refeicao/manual',methods=['POST'])
    @login_required
    def evolucao_refeicao_manual():
        data=request.get_json(silent=True) or {}
        kind=str(data.get('kind','Refeição')).strip()[:35]
        allowed={'Café da manhã','Almoço','Lanche','Jantar','Ceia'}
        if kind not in allowed:return jsonify(error='Selecione uma refeição válida.'),400
        foods=data.get('items',[])
        if not isinstance(foods,list) or not 1<=len(foods)<=20:
            return jsonify(error='Adicione de 1 a 20 alimentos.'),400
        clean=[]
        total=0.0
        for item in foods:
            if not isinstance(item,dict):return jsonify(error='Alimento inválido.'),400
            name=str(item.get('name','')).strip()[:90]
            portion_label=str(item.get('portion_label','')).strip()[:70]
            try:
                quantity=float(item.get('quantity'))
                kcal100=float(item.get('kcal100'))
                portions=float(item.get('portions',1) or 1)
                grams_per_portion=float(item.get('grams_per_portion',quantity) or quantity)
            except (ValueError,TypeError):return jsonify(error='Confira as quantidades e calorias dos alimentos.'),400
            if not name or not 0<quantity<=5000 or not 0<=kcal100<=950:
                return jsonify(error='Informe alimento, quantidade em gramas e kcal por 100 g válidas.'),400
            if not 0<portions<=50 or not 0<grams_per_portion<=5000:
                return jsonify(error='Informe uma porção válida para o alimento.'),400
            kcal=round(quantity*kcal100/100,1)
            clean.append({
                'name':name,
                'quantity_g':round(quantity,1),
                'kcal_100g':round(kcal100,1),
                'kcal':kcal,
                'portion_label':portion_label,
                'portions':round(portions,2),
                'grams_per_portion':round(grams_per_portion,1)
            })
            total+=kcal
        if total>15000:return jsonify(error='Calorias totais fora do intervalo permitido. Revise o registro.'),400
        notes=str(data.get('notes','')).strip()[:600]
        def _display_food(x):
            if x.get('portion_label'):
                q=f"{x['portions']:g} x {x['portion_label']}"
                return f"{x['name']} ({q} · {x['quantity_g']:g} g)"
            return f"{x['name']} ({x['quantity_g']:g} g)"
        entry={'id':str(uuid.uuid4()),'kind':kind,'at':datetime.now(timezone.utc).isoformat(),
               'alimentos':[_display_food(x) for x in clean],
               'items':clean,'calorias_min':round(total),'calorias_max':round(total),
               'observacoes':notes,'sugestao':'Valor aproximado calculado com os dados informados pelo usuário.',
               'provider':'manual','source':'manual'}
        _update(lambda state: state.setdefault('meals',[]).append(entry))
        return jsonify(entry),201

    @app.route('/api/evolucao/chat',methods=['POST'])
    @login_required
    def evolucao_chat():
        data=request.get_json(silent=True) or {};q=str(data.get('message','')).strip()[:1400]
        if not q:return jsonify(error='Escreva uma pergunta.'),400
        state=_state();recent=state.get('meals',[])[-12:];profile=state.get('profile',{})
        prompt='''Você é um acompanhante virtual de hábitos alimentares em português do Brasil, acolhedor, prático e sem julgamento. Não se apresente como nutricionista registrado. Não prescreva medicamentos, calorias restritivas ou metas rápidas. Fotos e contagens são estimativas; peça confirmação de porções. Em sinais de transtorno alimentar ou sintomas importantes, incentive avaliação profissional. Contexto resumido: '''+json.dumps({'perfil':profile,'refeicoes':recent},ensure_ascii=False)[:6500]+'\nPergunta: '+q
        try:
            response=analyze(prompt)
            return jsonify(answer=response['text'][:4500],provider=response['provider'])
        except (RuntimeError,requests.RequestException) as exc:return jsonify(error=str(exc)[:200]),502
