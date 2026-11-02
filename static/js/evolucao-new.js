
const $ = (id) => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n) => Number(n).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
const day = (s) => new Date(s).toLocaleDateString('pt-BR');
let selected = [];

// Catálogo de referência com energia aproximada por 100 g (alimentos prontos para consumo).
// Um alimento da lista recebe valor definido; somente "Outro" permite entrada manual.
const catalog = [
  // Nome, kcal/100g, categoria, porção habitual (g), nome da porção
  ['Arroz branco cozido',128,'Arroz e massas',100,'100 g'],['Arroz integral cozido',124,'Arroz e massas',100,'100 g'],
  ['Macarrão cozido',158,'Arroz e massas',100,'100 g'],['Tapioca pronta',230,'Arroz e massas',60,'1 unidade média'],
  ['Cuscuz de milho cozido',112,'Arroz e massas',100,'100 g'],['Batata cozida',52,'Arroz e massas',100,'100 g'],
  ['Batata-doce cozida',77,'Arroz e massas',100,'100 g'],['Mandioca cozida',125,'Arroz e massas',100,'100 g'],
  ['Feijão carioca cozido',76,'Feijão e leguminosas',100,'1 concha média'],['Feijão preto cozido',77,'Feijão e leguminosas',100,'1 concha média'],
  ['Lentilha cozida',93,'Feijão e leguminosas',100,'100 g'],['Grão-de-bico cozido',164,'Feijão e leguminosas',100,'100 g'],
  ['Ovo cozido',146,'Ovos e carnes',50,'1 unidade média'],['Ovo mexido sem óleo extra',170,'Ovos e carnes',50,'1 ovo preparado'],
  ['Ovo frito com óleo',196,'Ovos e carnes',50,'1 unidade média'],['Peito de frango grelhado',165,'Ovos e carnes',100,'100 g'],
  ['Frango cozido sem pele',165,'Ovos e carnes',100,'100 g'],['Carne bovina grelhada',230,'Ovos e carnes',100,'100 g'],
  ['Carne moída cozida',212,'Ovos e carnes',100,'100 g'],['Peixe grelhado',130,'Ovos e carnes',100,'100 g'],
  ['Atum em água escorrido',116,'Ovos e carnes',100,'100 g'],['Presunto',145,'Ovos e carnes',30,'1 fatia'],
  ['Pão francês',300,'Pães e cereais',50,'1 unidade'],['Pão de forma',265,'Pães e cereais',25,'1 fatia'],
  ['Pão integral',250,'Pães e cereais',30,'1 fatia'],['Aveia em flocos',394,'Pães e cereais',15,'1 colher de sopa'],
  ['Granola',471,'Pães e cereais',30,'2 colheres de sopa'],['Biscoito água e sal',430,'Pães e cereais',10,'2 unidades'],
  ['Banana',89,'Frutas',80,'1 unidade média sem casca'],['Maçã',52,'Frutas',130,'1 unidade média sem caroço'],
  ['Laranja',47,'Frutas',130,'1 unidade média sem casca'],['Mamão',43,'Frutas',100,'1 fatia'],
  ['Melancia',30,'Frutas',100,'1 fatia pequena'],['Melão',34,'Frutas',100,'1 fatia'],
  ['Morango',32,'Frutas',100,'100 g'],['Uva',69,'Frutas',100,'100 g'],
  ['Abacaxi',50,'Frutas',100,'1 fatia'],['Manga',60,'Frutas',100,'100 g'],
  ['Pera',57,'Frutas',130,'1 unidade média'],['Abacate',160,'Frutas',100,'100 g'],
  ['Alface',15,'Verduras e legumes',30,'1 prato de folhas'],['Tomate',18,'Verduras e legumes',100,'1 unidade pequena'],
  ['Pimentão',25,'Verduras e legumes',50,'1/2 unidade'],['Cenoura cozida',35,'Verduras e legumes',100,'100 g'],
  ['Brócolis cozido',35,'Verduras e legumes',100,'100 g'],['Abobrinha cozida',20,'Verduras e legumes',100,'100 g'],
  ['Pepino',15,'Verduras e legumes',100,'100 g'],['Repolho cru',25,'Verduras e legumes',100,'100 g'],
  ['Beterraba cozida',44,'Verduras e legumes',100,'100 g'],['Couve refogada',90,'Verduras e legumes',100,'100 g'],
  ['Queijo muçarela',300,'Leites e derivados',30,'1 fatia'],['Queijo minas frescal',264,'Leites e derivados',30,'1 fatia'],
  ['Requeijão',250,'Leites e derivados',30,'1 colher de sopa'],['Leite integral',61,'Leites e derivados',200,'1 copo (200 ml)'],
  ['Leite desnatado',35,'Leites e derivados',200,'1 copo (200 ml)'],['Iogurte natural',65,'Leites e derivados',170,'1 pote'],
  ['Iogurte natural desnatado',45,'Leites e derivados',170,'1 pote'],
  ['Azeite',884,'Óleos e complementos',13,'1 colher de sopa'],['Óleo vegetal',884,'Óleos e complementos',13,'1 colher de sopa'],
  ['Manteiga',717,'Óleos e complementos',10,'1 colher de chá cheia'],['Açúcar',387,'Óleos e complementos',5,'1 colher de chá'],
  ['Mel',304,'Óleos e complementos',15,'1 colher de sopa'],['Pasta de amendoim',588,'Óleos e complementos',15,'1 colher de sopa'],
  ['Café sem açúcar',1,'Bebidas',200,'1 xícara grande (200 ml)'],['Suco de laranja natural',45,'Bebidas',200,'1 copo (200 ml)'],
  ['Água',0,'Bebidas',200,'1 copo (200 ml)'],['Água de coco',19,'Bebidas',200,'1 copo (200 ml)']
].map(([name,kcal100,category,grams,label])=>({name,kcal100,category,grams,label}));
const OTHER='Outro alimento (manual)';
const normalize = v => String(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const categories=['Todos',...new Set(catalog.map(f=>f.category))];
let chosenFood=null;
function populateLists(){
 const cat=$('foodCategory');
 categories.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;cat.append(o)});
 populateFoods();
}
function populateFoods(){
 const c=$('foodCategory').value, sel=$('foodSelect');
 sel.innerHTML='';
 const foods=catalog.filter(f=>c==='Todos'||f.category===c).sort((a,b)=>a.name.localeCompare(b.name,'pt-BR'));
 for(const f of foods){const o=document.createElement('option');o.value=f.name;o.textContent=`${f.name} · ${fmt(f.kcal100)} kcal/100 g`;sel.append(o)}
 const other=document.createElement('option');other.value=OTHER;other.textContent='✍ Outro alimento — cadastrar manualmente';sel.append(other);
 updateFoodInputs();
}
function updateFoodInputs(){
 const key=$('foodSelect').value;
 chosenFood=catalog.find(f=>f.name===key)||null;
 const manual=!chosenFood;
 const portion=$('foodPortion');portion.innerHTML='';
 const choices=manual?[[100,'100 g'],[null,'Peso personalizado']]:[[chosenFood.grams,chosenFood.label],[100,'100 g'],[null,'Peso personalizado']];
 choices.forEach(([grams,label],i)=>{const o=document.createElement('option');o.value=grams===null?'custom':String(grams);o.textContent=label+(grams!==null?' ('+grams+' g)':'');portion.append(o)});
 $('customGramsWrap').hidden=!manual;
 $('foodGrams').value=manual?'':chosenFood.grams;
 $('foodKcal').value=manual?'':chosenFood.kcal100;
 // Nome manual em campo independente, apenas quando a opção manual é selecionada.
 $('manualNameWrap').hidden=!manual;
 updatePortionPreview();
}
function currentItem(){
 const manual=!chosenFood, count=Number($('foodPortionsCount').value), p=$('foodPortion');
 const grams=p.value==='custom'?Number($('foodGrams').value):Number(p.value);
 const kcal100=manual?Number($('foodKcal').value):chosenFood.kcal100;
 const name=manual?$('foodManualName').value.trim():chosenFood.name;
 const total=grams*count;
 const kcal=Math.round(total*kcal100)/100;
 return {name,quantity:total,kcal100,portions:count,gramsPerPortion:grams,portionLabel:p.options[p.selectedIndex]?.textContent||'Porção',totalGrams:total,kcal};
}
function updatePortionPreview(){
 const custom=$('foodPortion').value==='custom',manual=!chosenFood;
 $('customGramsWrap').hidden=custom||manual?false:true;
 $('foodGrams').parentElement.hidden=!custom;
 $('foodKcal').parentElement.hidden=!manual;
 const item=currentItem();
 $('portionGrams').textContent=Number.isFinite(item.totalGrams)&&item.totalGrams>0?fmt(item.totalGrams)+' g':'—';
 $('portionKcal').textContent=Number.isFinite(item.kcal)&&item.kcal>=0&&item.totalGrams>0?fmt(item.kcal)+' kcal':'—';
}
async function req(url, opts = {}) {
  opts.headers = { ...opts.headers, 'X-CSRFToken': csrf };
  const r = await fetch(url, opts);
  const raw = await r.text();
  let d;
  try {
    d = JSON.parse(raw);
  } catch {
    throw Error(r.redirected ? 'Sua sessão expirou. Entre novamente.' : 'O servidor respondeu com HTML em vez de JSON. Consulte os logs do Render.');
  }
  if (!r.ok) throw Error(d.error || `Erro HTTP ${r.status}`);
  return d;
}

function toast(msg, error = false) {
  const n = $('notice');
  n.hidden = false;
  n.textContent = msg;
  n.style.background = error ? '#fff0eb' : '#e8f6ed';
  n.style.color = error ? '#ae3b2d' : '#216f4e';
  n.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function renderSelected() {
  const total = selected.reduce((a, x) => a + x.kcal, 0);
  $('mealTotal').textContent = `${fmt(total)} kcal`;
  $('selectedFoods').innerHTML = selected.length ? selected.map((x, i) => `
    <div class="food-item">
      <div>
        <b>${esc(x.name)}</b>
        <span class="portion-tag">${esc(fmt(x.portions))} × ${esc(x.portionLabel)}</span>
        <small>${fmt(x.totalGrams)} g · ${fmt(x.kcal)} kcal</small>
      </div>
      <button class="remove-food" data-remove="${i}" type="button" aria-label="Remover alimento">✕</button>
    </div>
  `).join('') : '<p class="empty">Seu prato ainda está vazio.</p>';
  document.querySelectorAll('[data-remove]').forEach((b) => b.addEventListener('click', () => {
    selected.splice(Number(b.dataset.remove), 1);
    renderSelected();
  }));
}

function draw(ws) {
  const cv = $('weightChart');
  const c = cv.getContext('2d');
  c.clearRect(0, 0, 800, 210);
  if (!ws.length) {
    c.fillStyle = '#799186';
    c.font = '18px system-ui';
    c.fillText('Registre seu peso para ver a evolução.', 28, 100);
    return;
  }
  const values = ws.map((x) => Number(x.weight));
  const min = Math.min(...values) - 2;
  const max = Math.max(...values) + 2;
  c.strokeStyle = '#d9e8df';
  c.beginPath();
  c.moveTo(40, 15); c.lineTo(40, 180); c.lineTo(785, 180); c.stroke();
  c.strokeStyle = '#188356';
  c.lineWidth = 3;
  c.beginPath();
  values.forEach((n, i) => {
    const x = 55 + i * 712 / Math.max(1, values.length - 1);
    const y = 173 - (n - min) / (max - min) * 150;
    i ? c.lineTo(x, y) : c.moveTo(x, y);
  });
  c.stroke();
  c.fillStyle = '#346650';
  c.font = '13px system-ui';
  c.fillText(`${fmt(values[0])} kg`, 55, 203);
  c.fillText(`${fmt(values.at(-1))} kg`, 680, 203);
}

function renderMeals(ms) {
  $('meals').innerHTML = ms.slice().reverse().slice(0, 30).map((x) => {
    const foods = Array.isArray(x.alimentos) ? x.alimentos.join(', ') : '';
    const obs = x.observacoes ? `<p class="meal-note">${esc(x.observacoes)}</p>` : '';
    const kcal = x.calorias_min != null ? `<p class="meal-kcal">${esc(x.calorias_min)}${x.calorias_max != null && x.calorias_max !== x.calorias_min ? '–' + esc(x.calorias_max) : ''} kcal</p>` : '<p>Calorias não estimadas</p>';
    return `<div class="entry"><strong>${esc(x.kind)}</strong> <small>${day(x.at)} · ${x.source === 'manual' ? 'Manual' : 'IA'}</small><p>${esc(foods)}</p>${kcal}${obs}</div>`;
  }).join('') || '<p class="empty">Nenhuma refeição ainda.</p>';
}

async function refresh() {
  const d = await req('/api/evolucao/estado');
  const ws = d.weights || [];
  const ms = d.meals || [];
  const p = d.profile || {};
  $('weightStat').textContent = ws.length ? `${fmt(ws.at(-1).weight)} kg` : '—';
  $('goalStat').textContent = p.goal ? `${fmt(p.goal)} kg` : '—';
  $('mealStat').textContent = ms.length;
  const today = new Date().toLocaleDateString('en-CA');
  const todays = ms.filter((x) => new Date(x.at).toLocaleDateString('en-CA') === today);
  const known = todays.filter((x) => x.calorias_min != null && x.calorias_max != null);
  $('todayStat').textContent = known.length ? `${fmt(known.reduce((a, x) => a + (Number(x.calorias_min) + Number(x.calorias_max)) / 2, 0))} kcal` : '—';
  $('profileForm').elements.namedItem('name').value = p.name || '';
  $('profileForm').elements.namedItem('height').value = p.height || '';
  $('profileForm').elements.namedItem('goal').value = p.goal || '';
  draw(ws);
  $('weightHistory').textContent = ws.length ? `${ws.length} registros • último em ${day(ws.at(-1).at)}` : 'Sem registros ainda.';
  renderMeals(ms);
}

function bindEvents() {
  $('foodCategory').addEventListener('change',populateFoods);
  $('foodSelect').addEventListener('change',updateFoodInputs);
  $('foodPortion').addEventListener('change',updatePortionPreview);
  $('foodPortionsCount').addEventListener('input',updatePortionPreview);
  $('foodGrams').addEventListener('input',updatePortionPreview);
  $('foodKcal').addEventListener('input',updatePortionPreview);
  $('foodManualName').addEventListener('input',updatePortionPreview);
  $('addFood').addEventListener('click',()=>{
    const item=currentItem();
    if(!item.name||item.name.length>90||!Number.isFinite(item.quantity)||item.quantity<=0||item.quantity>5000||!Number.isFinite(item.kcal100)||item.kcal100<0||item.kcal100>950||(!chosenFood&&item.kcal100===0)||!Number.isFinite(item.portions)||item.portions<=0||item.portions>50){toast('Selecione um alimento e informe uma porção e calorias válidas.',true);return}
    if(selected.length>=20){toast('Máximo de 20 alimentos por refeição.',true);return}
    selected.push(item);renderSelected();
    $('foodPortionsCount').value='1';
    updatePortionPreview();
  });

  $('manualForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selected.length) {
      toast('Adicione pelo menos um alimento.', true);
      return;
    }
    const b = $('manualSave');
    b.disabled = true;
    try {
      await req('/api/evolucao/refeicao/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kind: $('manualKind').value,
          items: selected.map((x) => ({
            name: x.name,
            quantity: x.quantity,
            kcal100: x.kcal100,
            portions: x.portions,
            grams_per_portion: x.gramsPerPortion,
            portion_label: x.portionLabel
          })),
          notes: $('mealNotes').value
        })
      });
      selected = [];
      renderSelected();
      $('mealNotes').value = '';
      $('manualResult').textContent = 'Refeição salva!';
      await refresh();
      toast('Refeição adicionada ao seu diário.');
    } catch (err) {
      $('manualResult').textContent = err.message;
      toast(err.message, true);
    } finally {
      b.disabled = false;
    }
  });

  $('weightForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await req('/api/evolucao/peso', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weight: e.target.elements.namedItem('weight').value })
      });
      e.target.reset();
      await refresh();
      toast('Peso registrado com sucesso.');
    } catch (err) {
      toast(err.message, true);
    }
  });

  $('profileForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      await req('/api/evolucao/perfil', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: f.elements.namedItem('name').value,
          height: f.elements.namedItem('height').value,
          goal: f.elements.namedItem('goal').value
        })
      });
      $('profileMsg').textContent = 'Objetivo salvo!';
      await refresh();
    } catch (err) {
      $('profileMsg').textContent = err.message;
      toast(err.message, true);
    }
  });


}

populateLists();
bindEvents();
refresh().catch(err=>toast('Não foi possível carregar o diário: '+err.message,true));
