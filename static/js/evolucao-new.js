
const $ = (id) => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n) => Number(n).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
const day = (s) => new Date(s).toLocaleDateString('pt-BR');
let selected = [];

const catalog = [
  ['Arroz branco cozido',128],['Arroz integral cozido',124],['Feijão carioca cozido',76],['Feijão preto cozido',77],
  ['Ovo mexido',170],['Ovo cozido',146],['Peito de frango grelhado',165],['Carne bovina grelhada',230],
  ['Peixe grelhado',130],['Batata cozida',52],['Batata doce cozida',77],['Macarrão cozido',158],['Pão francês',300],
  ['Pão de forma',265],['Banana',89],['Maçã',52],['Laranja',47],['Mamão',43],['Alface',15],['Tomate',18],
  ['Pimentão',25],['Cenoura',35],['Brócolis',35],['Queijo muçarela',300],['Leite integral',61],['Iogurte natural',65],
  ['Azeite',884],['Café com leite',45],['Aveia',394],['Granola',471],['Iogurte proteico',82],['Tapioca pronta',230]
];

const portionsCatalog = [
  { value:'100g', label:'100 g', grams:100 },
  { value:'colher_sopa', label:'1 colher de sopa', grams:25 },
  { value:'colher_servir', label:'1 colher de servir', grams:45 },
  { value:'concha_media', label:'1 concha média', grams:100 },
  { value:'escumadeira', label:'1 escumadeira', grams:90 },
  { value:'fatia', label:'1 fatia', grams:30 },
  { value:'unidade_pequena', label:'1 unidade pequena', grams:60 },
  { value:'unidade_media', label:'1 unidade média', grams:80 },
  { value:'unidade_grande', label:'1 unidade grande', grams:120 },
  { value:'xicara', label:'1 xícara', grams:120 },
  { value:'copo', label:'1 copo', grams:200 },
  { value:'prato_raso', label:'1 prato raso', grams:250 },
  { value:'gramas', label:'Personalizado em gramas', grams:null }
];

function populateLists() {
  const list = $('foodsList');
  catalog.forEach(([name]) => {
    const opt = document.createElement('option');
    opt.value = name;
    list.append(opt);
  });

  const select = $('foodPortion');
  portionsCatalog.forEach((portion) => {
    const opt = document.createElement('option');
    opt.value = portion.value;
    opt.textContent = `${portion.label}${portion.grams ? ` · ${portion.grams} g` : ''}`;
    select.append(opt);
  });
}

function getFoodData(name) {
  const found = catalog.find((x) => x[0].toLowerCase() === name.trim().toLowerCase());
  return found ? { name: found[0], kcal100: found[1] } : { name: name.trim(), kcal100: Number($('foodKcal').value || 0) };
}

function currentPortion() {
  return portionsCatalog.find((x) => x.value === $('foodPortion').value) || portionsCatalog[0];
}

function updateFoodInputs() {
  const food = getFoodData($('foodSearch').value || '');
  if (food.kcal100) $('foodKcal').value = food.kcal100;
  const portion = currentPortion();
  const custom = portion.value === 'gramas';
  $('customGramsWrap').hidden = !custom;
  if (!custom && !$('foodGrams').value) $('foodGrams').value = portion.grams || '';
  updatePortionPreview();
}

function computeCurrentItem() {
  const food = getFoodData($('foodSearch').value || '');
  const portion = currentPortion();
  const portionsCount = Number($('foodPortionsCount').value || 0);
  const kcal100 = Number($('foodKcal').value || 0);
  const gramsPerPortion = portion.value === 'gramas' ? Number($('foodGrams').value || 0) : Number(portion.grams || 0);
  const totalGrams = gramsPerPortion * portionsCount;
  const kcal = totalGrams > 0 && kcal100 >= 0 ? (totalGrams * kcal100 / 100) : 0;
  return {
    name: food.name,
    kcal100,
    portionsCount,
    portionLabel: portion.label,
    gramsPerPortion,
    totalGrams,
    kcal
  };
}

function updatePortionPreview() {
  const item = computeCurrentItem();
  $('portionGrams').textContent = item.totalGrams > 0 ? `${fmt(item.totalGrams)} g` : '—';
  $('portionKcal').textContent = item.kcal > 0 ? `${fmt(item.kcal)} kcal` : '—';
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

function bindTabs() {
  document.querySelectorAll('[data-tab]').forEach((btn) => btn.addEventListener('click', () => {
    document.querySelectorAll('[data-tab]').forEach((b) => {
      b.classList.toggle('active', b === btn);
      b.setAttribute('aria-selected', String(b === btn));
    });
    $('manualPanel').hidden = btn.dataset.tab !== 'manual';
    $('photoPanel').hidden = btn.dataset.tab !== 'photo';
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
  $('foodSearch').addEventListener('change', updateFoodInputs);
  $('foodPortion').addEventListener('change', updateFoodInputs);
  $('foodPortionsCount').addEventListener('input', updatePortionPreview);
  $('foodGrams').addEventListener('input', updatePortionPreview);
  $('foodKcal').addEventListener('input', updatePortionPreview);

  $('addFood').addEventListener('click', () => {
    const item = computeCurrentItem();
    if (!item.name || item.name.length > 90 || !Number.isFinite(item.kcal100) || item.kcal100 < 0 || item.kcal100 > 950 || !Number.isFinite(item.portionsCount) || item.portionsCount <= 0 || item.portionsCount > 50 || !Number.isFinite(item.gramsPerPortion) || item.gramsPerPortion <= 0 || item.totalGrams > 5000) {
      toast('Informe alimento, porção, quantidade e calorias válidas.', true);
      return;
    }
    if (selected.length >= 20) {
      toast('Máximo de 20 alimentos por refeição.', true);
      return;
    }
    selected.push({
      name: item.name,
      quantity: item.totalGrams,
      kcal100: item.kcal100,
      portions: item.portionsCount,
      gramsPerPortion: item.gramsPerPortion,
      portionLabel: item.portionLabel,
      totalGrams: item.totalGrams,
      kcal: item.kcal
    });
    $('foodSearch').value = '';
    $('foodPortionsCount').value = '1';
    $('foodPortion').value = '100g';
    $('foodGrams').value = '';
    updateFoodInputs();
    renderSelected();
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

  $('photo').addEventListener('change', (e) => {
    const f = e.target.files[0];
    if (f) {
      $('preview').src = URL.createObjectURL(f);
      $('preview').hidden = false;
    }
  });

  $('mealForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const b = $('mealBtn');
    b.disabled = true;
    $('mealResult').textContent = 'Analisando foto...';
    try {
      const d = await req('/api/evolucao/refeicao', { method: 'POST', body: new FormData(e.target) });
      $('mealResult').textContent = `Identificado: ${(d.alimentos || []).join(', ')} • ${d.calorias_min ?? '—'} a ${d.calorias_max ?? '—'} kcal. ${d.sugestao || ''}`;
      await refresh();
    } catch (err) {
      $('mealResult').textContent = `${err.message} Você também pode preencher manualmente.`;
    } finally {
      b.disabled = false;
    }
  });

  $('chatForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const b = $('chatBtn');
    b.disabled = true;
    $('chatAnswer').textContent = 'Consultando IA...';
    try {
      const d = await req('/api/evolucao/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: e.target.elements.namedItem('message').value })
      });
      $('chatAnswer').textContent = d.answer;
    } catch (err) {
      $('chatAnswer').textContent = `${err.message} Consulte GEMINI_API_KEY e OPENAI_API_KEY no Render.`;
    } finally {
      b.disabled = false;
    }
  });
}

function checkAIStatus() {
  req('/api/evolucao/ia/status').then((d) => {
    const el = $('aiStatus');
    el.textContent = d.configured ? `✓ Provedor(es) configurado(s): ${d.providers.join(' e ')}. Conexão ainda não testada.` : '⚠ IA sem chave configurada no Render. Use registro manual.';
    el.classList.toggle('unavailable', !d.configured);
  }).catch(() => {
    $('aiStatus').textContent = 'Não foi possível verificar a configuração da IA.';
  });
}

populateLists();
updateFoodInputs();
bindTabs();
bindEvents();
checkAIStatus();
refresh().catch((err) => toast(`Não foi possível carregar o diário: ${err.message}`, true));
