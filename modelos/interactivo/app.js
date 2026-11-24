(function () {
  'use strict';
  const D = window.MOD;
  const I = D.int;
  const EST = ['Racarumi', 'Tamshiyacu'];
  const H = D.H_CLAVE;
  const HH = Array.from({ length: 30 }, (_, i) => i + 1);
  const A = D.anticipacion;
  const BANDAS = ['1–3 días', '4–7 días', '8–15 días', '16–30 días'];
  const MOD7 = D.MODELOS.concat(['Chronos-2']);
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const fmt = (x, d = 2) => (x == null || !isFinite(x)) ? '—' : Number(x).toLocaleString('es-PE', { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (x, d = 0) => (x == null || !isFinite(x)) ? '—' : fmt(100 * x, d) + ' %';
  const COMB = 'Combinado por horizonte';
  const oscuro = () => document.documentElement.getAttribute('data-theme') !== 'light';
  const PAL_OSC = { 'Persistencia': '#9aa6ab', 'Climatología': '#d4d64a', 'Tendencia 3 días': '#8796a0', 'Regresión lineal': '#d39a76', 'Random Forest': '#4cc95a',
    'XGBoost': '#f08bd0', 'KNN': '#2fd3e6', 'MLP': '#b18cff', 'LSTM': '#ff9a3c', 'Chronos-2': '#ff4d6d' };
  const PAL_CLA = Object.assign({}, D.COLORES, { 'Chronos-2': '#d02848', 'Tendencia 3 días': '#555f66' });
  const colM = n => n === COMB ? css('--ink-2') : ((oscuro() ? PAL_OSC : PAL_CLA)[n] || css('--accent'));
  const colE = e => css(e === 'Racarumi' ? '--rac' : '--tam');
  const ETQ = { NSE: 'NSE', KGE: 'KGE', MAE: 'MAE (m³/s)', RMSE: 'RMSE (m³/s)', PBIAS: 'PBIAS (%)', hab_pers: 'Habilidad frente a la persistencia', hab_clim: 'Habilidad frente a la climatología' };
  const CFG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'toggleSpikelines'], locale: 'es' };
  const K_HU = 'H cota 95 % (d)', K_PUN = 'H puntual (d)', K_P05 = 'H p05 (d)', K_P95 = 'H p95 (d)', K_CAL = 'NSE ≥ 0.5 hasta (d)';
  const txtHU = v => v == null ? '—' : v >= 30 ? '≥ 30' : String(Math.round(v));
  const rangoH = r => r[K_P05] === r[K_P95] ? txtHU(r[K_P05]) : `${Math.round(r[K_P05])}–${r[K_P95] >= 30 ? '30+' : Math.round(r[K_P95])}`;
  const FCOM = D.estaciones.Racarumi.fechas_comunes;
  const huDe = (e, n, lista = 'hu') => D.estaciones[e][lista].find(r => r.modelo === n) || {};
  const sintesisA = e => A.sintesis.find(r => r['estación'] === e) || {};
  const dotM = n => `<i class="dot" style="background:${colM(n)}"></i>${esc(n)}`;
  const perCorto = p => p.startsWith('con San Regis') ? 'con San Regis' : p.startsWith('común con Requena') ? 'común con Requena' : 'prueba';
  const angosto = () => window.innerWidth < 640;
  const rango = v => { const a = Math.min(...v), b = Math.max(...v); if (Math.round(a) === Math.round(b)) return fmt(a, 0);
    return a < 0 ? `${fmt(a, 0)} a ${b > 0 ? '+' : ''}${fmt(b, 0)}` : `${fmt(a, 0)}–${fmt(b, 0)}`; };

  // ────────────────────────────────────────────────────────── utilidades de gráficos
  function base(extra = {}) {
    const ink = css('--ink-2'), grid = css('--grid');
    const eje = { gridcolor: grid, zerolinecolor: css('--line'), linecolor: css('--line'), tickfont: { color: ink, size: 11, family: css('--f-mono') }, title: { font: { color: ink, size: 12 } }, automargin: true };
    const l = { paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { family: css('--f-body'), color: ink, size: 12 },
      margin: { l: 56, r: 14, t: 26, b: 44 }, hovermode: 'x unified',
      hoverlabel: { bgcolor: css('--solid'), bordercolor: css('--line'), font: { color: css('--ink'), family: css('--f-body') } },
      legend: { orientation: 'h', y: -0.2, x: 0, font: { size: 11 }, bgcolor: 'rgba(0,0,0,0)' }, xaxis: { ...eje }, yaxis: { ...eje } };
    for (const k of Object.keys(extra)) {
      if (/^[xy]axis\d*$/.test(k)) l[k] = { ...eje, ...extra[k], title: { font: { color: ink, size: 12 }, ...(extra[k].title || {}) } };
      else l[k] = extra[k];
    }
    return l;
  }
  function plot(div, data, layout, alto) {
    if (typeof div === 'string') div = $(div);
    if (!div) return;
    layout.height = alto || 340;
    Plotly.react(div, data, layout, CFG);
  }
  const divergente = () => [[0, css('--bad')], [0.5, oscuro() ? '#15232b' : '#f4f7f8'], [1, css('--good')]];
  const fecha0 = s => { const [y, m, d] = s.split('-').map(Number); return Date.UTC(y, m - 1, d); };
  const iso = ms => new Date(ms).toISOString().slice(0, 10);
  const DIA = 86400000;
  function seg(id, opciones, actual, txt = false) {
    return `<div class="seg" id="${id}" role="group">${opciones.map(([v, e]) => `<button type="button" class="${txt ? 'txt' : ''}" data-v="${esc(v)}" aria-pressed="${String(v) === String(actual)}">${esc(e)}</button>`).join('')}</div>`;
  }
  function onSeg(root, id, fn) {
    const g = $('#' + id, root);
    g.addEventListener('click', ev => {
      const b = ev.target.closest('button'); if (!b) return;
      $$('button', g).forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      fn(b.dataset.v);
    });
  }
  function tabla(id, filas, cols, opciones = {}) {
    const el = typeof id === 'string' ? $(id) : id;
    if (!el) return;
    el.innerHTML = `<table class="t"><thead><tr>${cols.map(([k, t]) => `<th>${esc(t)}</th>`).join('')}</tr></thead><tbody>${filas.map(r => {
      const cls = opciones.marca && opciones.marca(r) ? 'mejor' : '';
      return `<tr class="${cls}">${cols.map(([k, , f, c]) => { const v = r[k];
        if (f) return `<td class="${c || 'n'}" data-s="${esc(v ?? '')}">${f(v, r)}</td>`;
        if (typeof v === 'number') return `<td class="n" data-s="${v}">${fmt(v, Math.abs(v) >= 100 ? 0 : 3)}</td>`;
        return `<td class="${c || ''}">${esc(v ?? '—')}</td>`; }).join('')}</tr>`; }).join('')}</tbody></table>`;
    ordenable($('table', el));
    $$('td', el).forEach(td => { if (td.innerHTML.includes('class="dot"') || td.innerHTML.includes('class="chip')) td.classList.remove('n'); });
  }
  function ordenable(t) {
    $$('thead th', t).forEach((th, j) => th.addEventListener('click', () => {
      const tb = $('tbody', t), filas = $$('tr', tb), asc = th.dataset.o !== 'asc';
      $$('thead th', t).forEach(x => delete x.dataset.o); th.dataset.o = asc ? 'asc' : 'desc';
      filas.sort((a, b) => { const x = a.children[j].dataset.s ?? a.children[j].textContent, y = b.children[j].dataset.s ?? b.children[j].textContent;
        const nx = parseFloat(x), ny = parseFloat(y); const r = (isFinite(nx) && isFinite(ny)) ? nx - ny : x.localeCompare(y, 'es'); return asc ? r : -r; });
      filas.forEach(f => tb.appendChild(f));
    }));
  }
  // Lecturas: frases cortas (textos.js), plegadas por defecto y separadas por tema.
  const ul = k => { const a = Array.isArray(k) ? k : (k || []); return a.length ? `<ul class="puntos">${a.map(x => `<li>${x}</li>`).join('')}</ul>` : ''; };
  const conclusiones = (a, titulo = 'Conclusiones') => `<div class="glass panel conc mt"><header><h2>${esc(titulo)}</h2></header><div class="cuerpo"><ul class="claves">${a.map(x => `<li>${x}</li>`).join('')}</ul></div></div>`;
  const LECT = {};
  let nLect = 0;
  function lectura(items, titulo = 'Interpretación', abierto = false) {
    items = items.filter(([, h]) => h && h.trim());
    if (!items.length) return '';
    const id = 'lc' + (++nLect); LECT[id] = items;
    return `<details class="lectura" id="${id}" ${abierto ? 'open' : ''}><summary>${esc(titulo)}</summary>
      ${items.length > 1 ? `<div class="lect-tabs" role="tablist">${items.map(([t], i) => `<button type="button" role="tab" data-i="${i}" aria-selected="${i === 0}">${esc(t)}</button>`).join('')}</div>` : ''}
      <div class="lect-body prosa">${items[0][1]}</div></details>`;
  }
  document.addEventListener('click', ev => {
    const b = ev.target.closest('.lect-tabs button'); if (!b) return;
    const d = b.closest('details.lectura'), items = LECT[d.id];
    $$('.lect-tabs button', d).forEach(x => x.setAttribute('aria-selected', String(x === b)));
    const body = $('.lect-body', d); body.innerHTML = items[+b.dataset.i][1]; body.scrollTop = 0;
  });
  // Subtítulos largos → ayuda contextual junto al título (menos texto a la vista).
  function compactar(root) {
    $$('.panel>header', root).forEach(h => {
      const sub = $(':scope>.sub', h), h2 = $(':scope>h2', h);
      if (!sub || !h2 || sub.textContent.trim().length < 95) return;
      const tit = document.createElement('div'); tit.className = 'tit';
      h.insertBefore(tit, h2); tit.appendChild(h2);
      const tip = document.createElement('span'); tip.className = 'tip';
      tip.innerHTML = `<button type="button" aria-label="Cómo leer este gráfico">i</button><div class="pop" role="tooltip">${sub.innerHTML}</div>`;
      tit.appendChild(tip); sub.remove();
    });
  }
  document.addEventListener('click', ev => {
    const t = ev.target.closest('.tip');
    $$('.tip.abierto').forEach(x => { if (x !== t) x.classList.remove('abierto'); });
    if (t && ev.target.closest('.tip>button')) t.classList.toggle('abierto');
  });
  const kpi = (l, v, s, k) => `<div class="kpi" ${k ? `style="--k:${k}"` : ''}><div class="l">${l}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
  const hero = (eyebrow, titulo, lead, corta, c) => `<div class="hero" style="--c:var(${c || '--accent'})"><div><span class="eyebrow">${eyebrow}</span><h1>${titulo}</h1>${lead ? `<p class="lead">${lead}</p>` : ''}</div>
    ${corta ? `<div class="resp-corta"><span class="et">En corto</span><div>${corta}</div></div>` : ''}</div>`;

  // Mapa de calor de G (mismo modelo, prueba): filas = modelos, columnas = bandas de horizonte.
  function calorG(div, filas, modelos, alto) {
    const z = modelos.map(m => BANDAS.map(b => { const r = filas.find(x => x.mod === m && x.b === b); return r ? 100 * r.G : null; }));
    const cd = modelos.map(m => BANDAS.map(b => { const r = filas.find(x => x.mod === m && x.b === b); return r ? [fmt(100 * r.lo, 0), fmt(100 * r.hi, 0), r.l > 0 ? 'reduce el error' : r.l < 0 ? 'aumenta el error' : 'sin diferencia demostrada'] : ['', '', 'no evaluado']; }));
    const txt = modelos.map(m => BANDAS.map(b => { const r = filas.find(x => x.mod === m && x.b === b); if (!r) return '';
      return (r.G > 0 ? '+' : '') + fmt(100 * r.G, 0) + ' %' + (r.l > 0 ? ' ▲' : r.l < 0 ? ' ▼' : ''); }));
    const mx = Math.max(10, ...z.flat().filter(v => v != null).map(Math.abs));
    plot(div, [{ type: 'heatmap', z, x: BANDAS, y: modelos, text: txt, texttemplate: '%{text}', customdata: cd, zmid: 0, zmin: -mx, zmax: mx,
      colorscale: divergente(), xgap: 3, ygap: 3, showscale: false, textfont: { family: css('--f-mono'), size: 12, color: css('--ink') },
      hovertemplate: '<b>%{y}</b> · %{x}<br>G = %{z:.1f} %<br>IC 90 %: %{customdata[0]} a %{customdata[1]} %<br>%{customdata[2]}<extra></extra>' }],
    base({ hovermode: 'closest', margin: { l: 130, r: 10, t: 10, b: 36 }, xaxis: { side: 'bottom', showgrid: false, tickfont: { size: angosto() ? 9 : 11 } }, yaxis: { autorange: 'reversed', showgrid: false } }), alto || Math.max(260, 46 * modelos.length + 60));
  }

  // ────────────────────────────────────────────────────────── capítulos y navegación
  const CAPS = [
    { id: 'sintesis', n: '00', t: 'Visión general', s: 'Respuestas P1–P6', g: 'Inicio', c: '--accent', f: vSintesis },
    { id: 'resumen', n: 'P1', t: 'Horizonte útil', s: 'Seis modelos · dos ríos', g: 'Base · solo caudal local', c: '--accent', f: vResumen },
    { id: 'Racarumi', n: '01', t: 'Racarumi', s: 'Chancay-Lambayeque', c: '--rac', f: () => vEstacion('Racarumi') },
    { id: 'Tamshiyacu', n: '02', t: 'Tamshiyacu', s: 'Ucayali–Amazonas', c: '--tam', f: () => vEstacion('Tamshiyacu') },
    { id: 'anticipacion', n: 'P2', t: 'Avisos de crecidas', s: 'Nuevos cruces del P95', c: '--bad', f: vAnticipacion },
    { id: 'arriba', n: 'P3', t: 'Aguas arriba', s: 'San Regis · Requena · Cirato', g: 'Más información', c: '--c3', f: vArriba },
    { id: 'lluvia', n: 'P4', t: 'Lluvia-escorrentía', s: 'PISCOp e índices antecedentes', c: '--c4', f: vLluvia },
    { id: 'chronos', n: 'P5', t: 'Chronos-2', s: 'Modelo fundacional', c: '--c5', f: vChronos },
    { id: 'integrado', n: 'P6', t: 'Selección final', s: 'Comparación integrada', g: 'Integración', c: '--c6', f: vIntegrado },
    { id: 'metodo', n: 'M', t: 'Método', s: 'Cómo se obtuvieron', c: '--ink-3', f: vMetodo }];
  const capDe = id => CAPS.find(c => c.id === id);
  let vista = 'sintesis';
  $('#caps').innerHTML = CAPS.map(c => `${c.g ? `<div class="grupo">${esc(c.g)}</div>` : ''}<button type="button" class="cap" data-v="${c.id}" style="--c:var(${c.c})"><span class="num">${c.n}</span><span>${esc(c.t)}<small>${esc(c.s)}</small></span></button>`).join('');
  $('#caps').addEventListener('click', ev => { const b = ev.target.closest('button.cap'); if (b) { ir(b.dataset.v); document.body.classList.remove('nav-abierta'); } });
  function ir(v, desplazar = true) {
    if (!capDe(v)) v = 'sintesis';
    vista = v; nLect = 0; for (const k in LECT) delete LECT[k];
    if (mapaActivo) { mapaActivo.remove(); mapaActivo = null; } document.body.classList.remove('mapa-completo');
    const c = capDe(v), i = CAPS.indexOf(c);
    $$('#caps button.cap').forEach(b => b.setAttribute('aria-current', String(b.dataset.v === v)));
    $('#migas').innerHTML = `<span class="num" style="--c:var(${c.c})">${c.n}</span><b>${esc(c.t)}</b><span class="sr"> · </span><span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(c.s)}</span>`;
    $('#migas').style.setProperty('--c', `var(${c.c})`);
    try { history.replaceState(null, '', '#' + v); } catch (e) { /* vista previa */ }
    c.f();
    const app = $('#app'), ant = CAPS[i - 1], sig = CAPS[i + 1];
    $('.vista', app).insertAdjacentHTML('beforeend', `<nav class="pasos">${ant ? `<button type="button" data-ir="${ant.id}">← Anterior<b>${esc(ant.n + ' · ' + ant.t)}</b></button>` : '<span></span>'}${sig ? `<button type="button" class="sig" data-ir="${sig.id}">Siguiente →<b>${esc(sig.n + ' · ' + sig.t)}</b></button>` : ''}</nav>`);
    compactar(app);
    document.title = `${c.t} · MAYU`;
    if (desplazar) window.scrollTo(0, 0);
  }
  document.addEventListener('click', ev => { const a = ev.target.closest('.indice a'); if (!a) return; ev.preventDefault(); const t = $(a.getAttribute('href')); if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  document.addEventListener('click', ev => { const b = ev.target.closest('[data-ir]'); if (b && !b.closest('.cap')) ir(b.dataset.ir); });
  // tema
  function aplicaTema(t) {
    document.documentElement.setAttribute('data-theme', t);
    $('#tema-t').textContent = t === 'dark' ? 'Tema claro' : 'Tema oscuro';
  }
  let temaG = 'dark'; try { temaG = localStorage.getItem('cda-mod-tema-v2') || 'dark'; } catch (e) { /* sin almacenamiento */ }
  aplicaTema(temaG);
  const cambiaTema = () => { const t = oscuro() ? 'light' : 'dark'; try { localStorage.setItem('cda-mod-tema-v2', t); } catch (e) { /* */ } aplicaTema(t); ir(vista, false); };
  $('#tema').addEventListener('click', cambiaTema);
  // cajón del glosario y menú móvil
  const abreGlos = abrir => { document.body.classList.toggle('cajon-abierto', abrir); $('#cajon').setAttribute('aria-hidden', String(!abrir)); if (abrir) $('#cerrar').focus(); };
  $('#glos').addEventListener('click', () => abreGlos(true));
  $('#cerrar').addEventListener('click', () => abreGlos(false));
  $('#velo').addEventListener('click', () => { abreGlos(false); document.body.classList.remove('nav-abierta'); });
  $('#menu').addEventListener('click', () => document.body.classList.toggle('nav-abierta'));
  document.addEventListener('keydown', ev => {
    if (ev.altKey || ev.ctrlKey || ev.metaKey || /INPUT|SELECT|TEXTAREA/.test(ev.target.tagName)) return;
    const i = CAPS.findIndex(c => c.id === vista);
    if (ev.key === 'ArrowRight' && CAPS[i + 1]) ir(CAPS[i + 1].id);
    else if (ev.key === 'ArrowLeft' && CAPS[i - 1]) ir(CAPS[i - 1].id);
    else if (ev.key === 'g' || ev.key === 'G') abreGlos(!document.body.classList.contains('cajon-abierto'));
    else if (ev.key === 't' || ev.key === 'T') cambiaTema();
    else if (ev.key === 'm' || ev.key === 'M') { ev.preventDefault(); MAYU.abre(!document.body.classList.contains('bot-abierto')); }
    else if (ev.key === 'Escape') { abreGlos(false); MAYU.abre(false); document.body.classList.remove('nav-abierta'); }
  });
  const GLOS = [
    ['NSE', 'Eficiencia de Nash-Sutcliffe: 1 es perfecto; 0 equivale a pronosticar la media observada; negativo es peor que eso.'],
    ['NSE medio', 'Promedio del NSE de los 30 horizontes. Es el criterio de selección (en validación, bloque 2012–2015).'],
    ['KGE · PBIAS', 'KGE combina correlación, sesgo y variabilidad (1 es perfecto). PBIAS: sesgo porcentual; negativo = subestima.'],
    ['Persistencia', 'Referencia ingenua: el caudal de mañana (y de los próximos 30 días) es el de hoy.'],
    ['Climatología', 'Referencia: el caudal típico de ese día del año, con los datos que también vio el modelo.'],
    ['H (horizonte útil)', 'Mayor horizonte consecutivo desde 1 día con NSE > 0 que supera a persistencia y climatología.'],
    ['H cota 95 %', 'Cifra de las conclusiones: el menor entre H puntual y el percentil 5 de H en un bootstrap por bloques de un mes. «≥ 30» = no se encontró el límite.'],
    ['G', 'Ganancia de una entrada con el mismo modelo: G = 1 − MSE(con)/MSE(sin). G = +30 % significa 30 % menos error cuadrático.'],
    ['IC 90 % · equivalente · inconcluso', 'Intervalo por bootstrap de meses. Equivalente: el IC cabe en ±0.01 de NSE. Inconcluso: el IC es demasiado ancho para decidir (no es equivalencia).'],
    ['P95', 'Percentil 95 del caudal de entrenamiento: umbral de «caudal alto» y de cruce para los avisos.'],
    ['POD · FAR · CSI', 'Aciertos sobre cruces (POD), falsas alarmas sobre avisos (FAR) y su combinación (CSI). Criterio de utilidad: POD ≥ 0.5 con FAR ≤ 0.5.'],
    ['Anticipación real', 'Fecha del cruce − fecha de emisión del primer aviso correcto. Solo cuentan avisos emitidos antes del cruce.'],
    ['Q · P · IA · SR · RQ', 'Entradas: caudal local (Q), lluvia de la cuenca (P), índices de lluvia antecedente (IA), San Regis (SR) y Requena (RQ). «(t−1)»: la fuente externa llega con un día de retraso.'],
    ['Mismo día · un día de retraso', 'Escenarios de disponibilidad: la fuente externa se conoce el mismo día de la emisión (supuesto, no demostrado para PISCOp) o un día después.'],
    ['Validación · prueba', 'Entrenamiento hasta 2008; validación 2009–2015 (2009–2011 corrige el sesgo; 2012–2015 selecciona); prueba desde 2016. La prueba no decide nada.'],
    ['Chronos-2', 'Modelo fundacional de series de tiempo (120 M de parámetros) usado con sus pesos publicados, sin ajuste local (zero-shot).']];
  $('#glosario').innerHTML = `<dl>${GLOS.map(([t, d]) => `<dt>${esc(t)}</dt><dd>${esc(d)}</dd>`).join('')}</dl>`;

  // ────────────────────────────────────────────────────────── mapa de estaciones y cuencas (Leaflet)
  let mapaActivo = null;
  function crearMapa(el) {
    const M = I.mapa, E = M.estaciones;
    if (typeof L === 'undefined' || !el) return;
    const map = L.map(el, { preferCanvas: true, minZoom: 4, maxZoom: 12, zoomSnap: 0.25, wheelPxPerZoomLevel: 90 });
    map.attributionControl.setPrefix(false); map.attributionControl.addAttribution('CAMELS-PE v1.0.1');
    const R = L.canvas({ padding: 0.4, tolerance: 6 });
    const BASES = { relieve: { t: 'Relieve', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', at: 'Mapa base © Esri, HERE, Garmin, USGS, NASA' },
      satelite: { t: 'Satélite', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', at: 'Imagen © Esri, Maxar, Earthstar Geographics' },
      vector: { t: 'Sin fondo', url: null } };
    let baseSel = 'relieve', base = null, capas = [], ctrl = null, aviso = null, sel = null, polis = {}, marcas = {};
    try { baseSel = localStorage.getItem('cda-mod-mapa') || 'relieve'; } catch (e) { /* */ }
    const ORD = { eda: 0, arriba: 1, objetivo: 2 };
    const colE_ = n => { const r = E[n].rol; return r === 'objetivo' ? colE(n) : r === 'arriba' ? css('--c3') : css('--ink-4'); };
    const H_ = n => huDe(n, D.estaciones[n].mejor)[K_HU];
    const papel = n => { const r = E[n].rol;
      if (r === 'objetivo') return `Estación pronosticada. Horizonte útil de la magnitud: <b>${txtHU(H_(n))} días</b> (${esc(D.estaciones[n].mejor)}, solo caudal).`;
      if (n === 'Cirato') return 'Aguas arriba de Racarumi. Exploratoria: solo 13 meses con fechas confiables; sin mejora demostrada.';
      if (n === 'San Regis') return 'Aguas arriba de Tamshiyacu (Marañón). Anticipa 1 día y reduce el error 33–45 % a 1–3 días.';
      if (n === 'Requena') return 'Aguas arriba de Tamshiyacu (Ucayali). Sin desfase positivo ni reducción demostrada del error.';
      return 'Analizada en la exploración inicial; no se eligió para modelar.'; };
    const destino = n => E[n].rol === 'objetivo' ? n : E[n].rol === 'arriba' ? 'arriba' : null;
    const etqRol = n => ({ objetivo: 'Estación pronosticada', arriba: 'Estación aguas arriba', eda: 'Estación analizada' }[E[n].rol]);
    const estilo = n => { const r = E[n].rol, c = colE_(n), on = sel === n;
      return { color: c, weight: on ? 3.2 : r === 'objetivo' ? 2.2 : r === 'arriba' ? 1.6 : 1, dashArray: r === 'objetivo' || on ? null : '5 4', fillColor: c,
        fillOpacity: on ? 0.3 : r === 'objetivo' ? 0.14 : r === 'arriba' ? 0.1 : 0.04, opacity: r === 'eda' && !on ? 0.7 : 1 }; };
    function ficha(n) {
      const f = $('#ficha'); if (!f) return;
      if (!n) { f.innerHTML = f.dataset.leyenda; return; }
      const m = E[n], d = destino(n);
      f.innerHTML = `<div class="ficha-est"><span class="eyebrow" style="color:${colE_(n)}">${etqRol(n)}</span><h3>${esc(n)}</h3>
        <div class="meta">${esc(m.cuenca)} · vertiente ${esc(m.vertiente)} · ${esc(m.id)}<br>${fmt(m.area, 0)} km² · ${fmt(m.elev, 0)} m s. n. m. · registro ${esc(String(m.inicio).slice(0, 4))}–${esc(String(m.fin).slice(0, 4))}</div>
        <p>${papel(n)}</p><div class="acc">${d ? `<button class="btn" type="button" data-ir="${d}">Abrir capítulo →</button>` : ''}<button class="btn" type="button" id="ficha-x">Ver todas</button></div></div>`;
      $('#ficha-x').addEventListener('click', () => marcar(null, true));
    }
    function marcar(n, mover) {
      sel = n;
      Object.keys(polis).forEach(k => polis[k].setStyle(estilo(k)));
      Object.keys(marcas).forEach(k => marcas[k].setStyle({ radius: k === n ? 12 : E[k].rol === 'objetivo' ? 9 : E[k].rol === 'arriba' ? 6.5 : 5, weight: k === n ? 3 : 2 }));
      if (n && polis[n]) polis[n].bringToFront();
      Object.keys(marcas).sort((a, b) => ORD[E[a].rol] - ORD[E[b].rol]).forEach(k => marcas[k].bringToFront());
      if (n && marcas[n]) marcas[n].bringToFront();
      ficha(n);
      if (mover) { if (n && polis[n]) map.flyToBounds(polis[n].getBounds(), { padding: [30, 30], maxZoom: 9, duration: 0.6 }); else encuadre(true); }
    }
    function pinta() {
      capas.forEach(l => l.remove()); capas = []; polis = {}; marcas = {};
      const fondo = !!base, sat = baseSel === 'satelite';
      capas.push(L.geoJSON(M.camels, { renderer: R, interactive: false, style: { color: fondo ? (sat ? '#ffffff' : '#5b6670') : css('--line'), weight: 0.6, opacity: fondo ? 0.5 : 1, fill: !fondo, fillColor: css('--glass-2'), fillOpacity: fondo ? 0 : 0.6 } }).addTo(map));
      const feats = M.cuencas.features.filter(f => E[f.properties.nombre]).sort((a, b) => E[b.properties.nombre].area - E[a.properties.nombre].area);
      capas.push(L.geoJSON({ type: 'FeatureCollection', features: feats }, { renderer: R, style: f => estilo(f.properties.nombre),
        onEachFeature: (f, l) => { const n = f.properties.nombre; polis[n] = l;
          l.bindTooltip(`<b>Cuenca hasta ${esc(n)}</b><br>${esc(E[n].cuenca)} · ${fmt(E[n].area, 0)} km²`, { sticky: true, className: 'tt' });
          l.on('mouseover', () => { if (sel !== n) l.setStyle({ weight: estilo(n).weight + 1.2, fillOpacity: estilo(n).fillOpacity + 0.08 }); });
          l.on('mouseout', () => l.setStyle(estilo(n)));
          l.on('click', ev => { L.DomEvent.stopPropagation(ev); marcar(n, false); }); } }).addTo(map));
      const g = L.layerGroup().addTo(map); capas.push(g);
      Object.keys(E).sort((a, b) => ORD[E[a].rol] - ORD[E[b].rol]).forEach(n => {
        const m = E[n], r = m.rol;
        const k = L.circleMarker([m.lat, m.lon], { renderer: R, radius: r === 'objetivo' ? 9 : r === 'arriba' ? 6.5 : 5, color: '#ffffff', weight: 2, fillColor: colE_(n), fillOpacity: 1 });
        k.bindTooltip(`<b>${esc(n)}</b> · ${esc(m.cuenca)}<br>${etqRol(n)} · ${fmt(m.area, 0)} km²<br><span style="color:var(--ink-3)">Clic para ver la ficha</span>`, { direction: 'top', offset: [0, -10], className: 'tt' });
        k.on('click', ev => { L.DomEvent.stopPropagation(ev); marcar(n, true); }); k.addTo(g); marcas[n] = k;
        if (r === 'objetivo') L.tooltip({ permanent: true, direction: n === 'Racarumi' ? 'left' : 'right', offset: [n === 'Racarumi' ? -12 : 12, 0], className: 'etq', interactive: false })
          .setLatLng([m.lat, m.lon]).setContent(`${esc(n)} · ${txtHU(H_(n))} d`).addTo(g);
      });
      if (sel) marcar(sel, false);
    }
    function ponerBase(k, guardar = false) {
      if (base) { base.remove(); base = null; }
      baseSel = k; if (guardar) try { localStorage.setItem('cda-mod-mapa', k); } catch (e) { /* */ }
      if (BASES[k].url) { let ok = 0, err = 0;
        base = L.tileLayer(BASES[k].url, { maxZoom: 18, attribution: BASES[k].at });
        base.on('tileload', () => { ok++; if (aviso) aviso.hidden = true; });
        base.on('tileerror', () => { err++; if (err >= 4 && ok === 0 && baseSel === k) { if (aviso) { aviso.hidden = false; setTimeout(() => { aviso.hidden = true; }, 7000); } ponerBase('vector'); } });
        base.addTo(map); }
      if (ctrl) ctrl.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.b === baseSel)));
      pinta();
    }
    const Bases = L.Control.extend({ options: { position: 'topright' }, onAdd: () => {
      const d = L.DomUtil.create('div', 'base-ctrl');
      d.innerHTML = `<div class="seg" role="group" aria-label="Mapa base">${Object.entries(BASES).map(([k, v]) => `<button type="button" class="txt" data-b="${k}" aria-pressed="${k === baseSel}">${v.t}</button>`).join('')}</div><div class="base-aviso" hidden>El mapa base necesita internet; se muestra el mapa vectorial.</div>`;
      L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
      d.addEventListener('click', e => { const b = e.target.closest('button[data-b]'); if (b) ponerBase(b.dataset.b, true); });
      ctrl = d; aviso = d.querySelector('.base-aviso'); return d; } });
    new Bases().addTo(map);
    const Vista = L.Control.extend({ options: { position: 'topleft' }, onAdd: () => {
      const d = L.DomUtil.create('div', 'mapa-ctrl');
      d.innerHTML = `<button type="button" data-a="ini" title="Volver a la vista inicial" aria-label="Volver a la vista inicial"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/></svg></button>
        <button type="button" data-a="full" title="Pantalla completa" aria-label="Pantalla completa"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg></button>`;
      L.DomEvent.disableClickPropagation(d);
      d.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return;
        if (b.dataset.a === 'ini') marcar(null, true);
        else { const c = el.closest('.mapa'); document.body.classList.toggle('mapa-completo', c.classList.toggle('completo')); setTimeout(() => map.invalidateSize(), 60); } });
      return d; } });
    new Vista().addTo(map);
    map.on('click', () => marcar(null, false));
    document.addEventListener('keydown', function salir(ev) { if (!document.body.contains(el)) { document.removeEventListener('keydown', salir); return; }
      if (ev.key === 'Escape' && el.closest('.mapa').classList.contains('completo')) { el.closest('.mapa').classList.remove('completo'); document.body.classList.remove('mapa-completo'); setTimeout(() => map.invalidateSize(), 60); } });
    ponerBase(baseSel);
    function encuadre(suave) { map.invalidateSize(); const b = [[-18.4, -81.4], [0.1, -68.6]]; if (suave) map.flyToBounds(b, { padding: [8, 8], duration: 0.6 }); else map.fitBounds(b, { padding: [8, 8] }); }
    encuadre(); setTimeout(() => encuadre(), 60);
    mapaActivo = map;
    mapaActivo.marcar = n => marcar(n, true);
  }

  // ────────────────────────────────────────────────────────── 00 · VISIÓN GENERAL
  function vSintesis() {
    const S = I.sintesis, R = D.estaciones.Racarumi, T = D.estaciones.Tamshiyacu;
    const huR = huDe('Racarumi', R.mejor)[K_HU], huT = huDe('Tamshiyacu', T.mejor)[K_HU];
    const aR = sintesisA('Racarumi'), aT = sintesisA('Tamshiyacu');
    const gr = (ef, est, ent, b) => ef.filter(r => r.est === est && r.ent === ent && r.b === b).map(r => 100 * r.G);
    const gSR = gr(I.arriba.efecto, 'Tamshiyacu', 'SR', '1–3 días'), gP = gr(I.lluvia.efecto, 'Racarumi', 'P', '1–3 días');
    const gPt1 = gr(I.lluvia.efecto, 'Racarumi', 'P con latencia 1 d', '1–3 días');
    const smR = I.integrado.sel_mag.find(r => r['estación'] === 'Racarumi' && r.escenario === 'mismo día') || {};
    const frT = I.chronos.frente.filter(r => r['estación'] === 'Tamshiyacu'), peorT = frT.filter(r => r.clase === 'peor').length;
    const avR = I.integrado.sel_avisos;
    const tarjetas = [
      { p: 'P1', c: '--accent', ir: 'resumen', q: '¿Hasta cuántos días se estima bien la magnitud del caudal?', big: `${txtHU(huR)} d <span class="sep">/</span> ${txtHU(huT)} d`, sm: 'Racarumi / Tamshiyacu',
        d: 'Solo con el caudal local. La diferencia entre ríos es mucho mayor que entre modelos.', ch: ['ok', 'respondida'] },
      { p: 'P2', c: '--bad', ir: 'anticipacion', q: '¿Con cuánta anticipación se avisa un nuevo cruce del P95?', big: `${fmt(aR['anticipación útil (d)'], 0)} d <span class="sep">/</span> ${fmt(aT['anticipación útil (d)'], 0)} d`, sm: 'anticipación útil',
        d: `Racarumi: ${fmt(aR.aciertos, 0)} de ${fmt(aR['cruces evaluables'], 0)} cruces con FAR ${fmt(aR.FAR, 2)}. Tamshiyacu: ${fmt(aT.aciertos, 0)} de ${fmt(aT['cruces evaluables'], 0)}, muy pocos eventos.`, ch: ['med', 'parcial'] },
      { p: 'P3', c: '--c3', ir: 'arriba', q: '¿Aportan las estaciones aguas arriba?', big: `${rango(gSR)} %`, sm: 'menos error a 1–3 d con San Regis',
        d: 'Con los seis modelos. Requena no reduce el error y Cirato no se demuestra; el horizonte útil casi no cambia.', ch: ['ok', 'San Regis sí'] },
      { p: 'P4', c: '--c4', ir: 'lluvia', q: '¿Aporta la lluvia de la cuenca?', big: `${rango(gP)} %`, sm: 'menos error a 1–3 d en Racarumi',
        d: `Solo si la lluvia del mismo día está disponible; con un día de retraso: ${rango(gPt1)} %. En Tamshiyacu complementa a San Regis.`, ch: ['med', 'condicional'] },
      { p: 'P5', c: '--c5', ir: 'chronos', q: '¿Sirve un modelo fundacional sin ajuste local?', big: `${fmt(smR['NSE medio validación (2012–2015)'], 3)} → ${fmt(smR['NSE medio prueba'], 3)}`, sm: 'NSE medio validación → prueba (Racarumi)',
        d: `Chronos-2 gana en validación y se selecciona, pero no se sostiene en la prueba. En Tamshiyacu es peor que lo seleccionado en ${peorT} de ${frT.length} comparaciones.`, ch: ['med', 'no se sostiene'] },
      { p: 'P6', c: '--c6', ir: 'integrado', q: '¿Qué configuración final se elige?', big: '<span style="font-size:1.45rem">Q · Chronos-2 <span class="sep">/</span> Q · KNN</span>', sm: '',
        d: `Elegidas en validación entre 21–84 candidatos. Ninguna coincide con la mejor de la prueba; los avisos (${avR.map(r => esc(r['seleccionada en validación'])).join(', ')}) no cumplen.`, ch: ['no', 'avisos no cumplen'] }];
    const NB = [['01', 'Racarumi', 'Racarumi', '--rac'], ['02', 'Tamshiyacu', 'Tamshiyacu', '--tam'], ['03', 'Comparación', 'resumen', '--accent'], ['04', 'Avisos', 'anticipacion', '--bad'],
      ['05', 'Aguas arriba', 'arriba', '--c3'], ['06', 'Lluvia', 'lluvia', '--c4'], ['07', 'Chronos-2', 'chronos', '--c5'], ['08', 'Integración', 'integrado', '--c6'], ['09', 'Síntesis', 'sintesis', '--accent']];
    $('#app').innerHTML = `<section class="vista">
      ${hero('Proyecto Integrador · Ciencia de Datos Ambientales · UTEC', '¿Cuánto aviso nos da un río?',
        'Pronóstico diario del caudal a 1–30 días en dos ríos opuestos del Perú: cuánto se puede anticipar la <b>magnitud</b> y con cuánta anticipación se avisa una <b>crecida</b>, con seis modelos, Chronos-2, caudal aguas arriba y lluvia.',
        `Seleccionar en validación y evaluar en una prueba que no decide nada: <b>el río importa más que el modelo</b>, la información extra ayuda sobre todo en la primera semana y en Racarumi ningún sistema de avisos elegido de antemano cumple el criterio (Tamshiyacu tiene solo 3 crecidas en la prueba).`)}
      <div class="mapa-bloque">
        <div class="glass panel mapa"><div id="mapa" role="region" aria-label="Mapa de estaciones y cuencas"></div></div>
        <div class="mapa-lado">
          <button class="est" data-ir="Racarumi" style="--c:var(--rac)"><div class="valor">${txtHU(huR)}<small> d</small></div><h3>Racarumi</h3><p>Chancay-Lambayeque · Pacífico · ${fmt(R.area, 0)} km² · respuesta rápida: el pico llega 1 día después de la lluvia</p></button>
          <button class="est" data-ir="Tamshiyacu" style="--c:var(--tam)"><div class="valor">${txtHU(huT)}<small> d</small></div><h3>Tamshiyacu</h3><p>Ucayali–Amazonas · ${fmt(T.area, 0)} km² · respuesta lenta: la señal de la lluvia tarda ~6 días en llegar</p></button>
          <div class="glass" id="ficha"><div class="leyenda"><div><i style="background:var(--rac)"></i><i style="background:var(--tam);margin-left:-6px"></i>Estaciones pronosticadas (horizonte útil)</div>
            <div><i style="background:var(--c3)"></i>Aguas arriba: San Regis, Requena (P3) y Cirato</div>
            <div><i style="background:var(--ink-4)"></i>Otras estaciones analizadas, no modeladas</div>
            <div><i class="sq" style="background:transparent;border:1.5px dashed var(--ink-3);box-shadow:none"></i>Cuenca hasta cada estación (CAMELS-PE)</div>
            <span class="nota" style="margin:2px 0 0">Clic en una estación o cuenca para ver su ficha; la rueda del ratón acerca y aleja.</span></div></div>
        </div>
      </div>
      <div class="respuestas mt">${tarjetas.map(t => `<button class="rc" data-ir="${t.ir}" style="--c:var(${t.c})">
        <span class="tag">${t.p}<span class="chip ${t.ch[0]}">${t.ch[1]}</span></span><h3>${t.q}</h3>
        <div class="big">${t.big}${t.sm ? `<small>${t.sm}</small>` : ''}</div><p>${t.d}</p><span class="ir">Ver evidencia →</span></button>`).join('')}</div>
      <div class="g-2 mt">
        <div class="glass panel"><header><h2>Lo elegido frente a lo mejor de la prueba</h2>
          <span class="sub">NSE medio de los 30 horizontes. Anillo: la configuración seleccionada, en validación (2012–2015). Punto: la misma en la prueba. Estrella: la mejor observada en la prueba, que no se usó para elegir. La distancia entre punto y estrella es el costo de elegir sin mirar la prueba.</span></header>
          <div class="cuerpo"><div id="s-sel" class="fig"></div></div></div>
        <div class="glass panel"><header><h2>¿Qué aporta cada fuente de información?</h2><div class="ctrl">${seg('s-est', EST.map(e => [e, e]), 'Tamshiyacu', true)}${seg('s-ori', [['05', 'Aguas arriba'], ['06', 'Lluvia'], ['08', 'Combinaciones']], '05', true)}</div>
          <span class="sub">Cuántos modelos reducen el error al agregar cada fuente (mismo modelo, mismas emisiones de prueba) y la mediana de G entre ellos. Verde: menos error; rojo: más error.</span></header>
          <div class="cuerpo"><div id="s-fuentes" class="fig"></div></div></div>
      </div>
      <div class="glass panel mt"><header><h2>Recorrido del estudio</h2><span class="sub">Etapas del estudio. Haga clic para ir a cada parte.</span></header>
        <div class="cuerpo"><div class="tuberia">${NB.map(([n, t, v, c], i) => `${i ? '<span class="fl">→</span>' : ''}<button data-ir="${v}" style="--c:var(${c})"><b>${i + 1}</b>${t}</button>`).join('')}</div>
        ${lectura([['Respuestas', ul(TX.s_respuestas)], ['Mensaje principal', ul(TX.s_mensaje)], ['Magnitud', ul(TX.s_magnitud)], ['Avisos', ul(TX.s_avisos)], ['Límites', ul(TX.limites)]], 'Síntesis', true)}</div></div>
    </section>`;
    // dumbbell
    const filas = I.integrado.sel_mag.map(r => {
      const m = /\(([\d.]+)\)\s*$/.exec(r['mejor NSE medio en la prueba (no se elige con él)'] || ''), mej = m ? +m[1] : null;
      return { y: `${r['estación']}${r['estación'] === 'Tamshiyacu' ? (r['periodo de prueba'].startsWith('común') ? ' (RQ)' : ' (SR)') : ''} · ${r.escenario === 'mismo día' ? 'mismo día' : 'retraso'}`, est: r['estación'], sel: r['seleccionada en validación'], val: r['NSE medio validación (2012–2015)'], pru: r['NSE medio prueba'],
        mej, mejN: (r['mejor NSE medio en la prueba (no se elige con él)'] || '').replace(/\s*\([\d.]+\)\s*$/, '') };
    }).reverse();
    const ys = filas.map(f => f.y);
    plot('#s-sel', [
      ...filas.map(f => ({ x: [f.pru, f.mej], y: [f.y, f.y], mode: 'lines', line: { color: css('--line'), width: 6 }, hoverinfo: 'skip', showlegend: false })),
      { x: filas.map(f => f.val), y: ys, mode: 'markers', name: 'Seleccionada · validación', marker: { symbol: 'circle-open', size: 14, color: css('--ink-3'), line: { width: 2 } }, customdata: filas.map(f => f.sel), hovertemplate: '%{customdata}<br>validación: %{x:.3f}<extra></extra>' },
      { x: filas.map(f => f.pru), y: ys, mode: 'markers+text', name: 'Seleccionada · prueba', marker: { size: 13, color: filas.map(f => colE(f.est)), line: { width: 1.5, color: css('--solid') } },
        text: filas.map(f => f.sel), textposition: 'bottom center', textfont: { size: 10, color: css('--ink-2') }, customdata: filas.map(f => f.sel), hovertemplate: '%{customdata}<br>prueba: %{x:.3f}<extra></extra>' },
      { x: filas.map(f => f.mej), y: ys, mode: 'markers', name: 'Mejor en la prueba', marker: { symbol: 'star', size: 16, color: css('--good'), line: { width: 1, color: css('--solid') } }, customdata: filas.map(f => f.mejN), hovertemplate: '%{customdata}<br>prueba: %{x:.3f}<extra></extra>' }],
    base({ hovermode: 'closest', margin: { l: 10, r: 14, t: 10, b: 40 }, xaxis: { title: { text: 'NSE medio (30 horizontes)' }, zeroline: false }, yaxis: { automargin: true, tickfont: { size: 11 } }, legend: { orientation: 'h', y: -0.16 } }), 420);
    // fuentes
    let sEst = 'Tamshiyacu', sOri = '05';
    const fuentes = () => {
      const fs = S.fuentes.filter(f => f.est === sEst && f.origen.startsWith(sOri) && f.v.every(Boolean));
      if (!fs.length) { $('#s-fuentes').innerHTML = `<p class="nota" style="padding:40px 0;text-align:center">Sin comparaciones de esta fuente para ${esc(sEst)}.</p>`; return; }
      Plotly.purge($('#s-fuentes'));
      const y = fs.map(f => f.ent);
      const z = fs.map(f => f.v.map(v => Math.max(-45, Math.min(45, v[3]))));
      const txt = fs.map(f => f.v.map(v => `${v[0]}/${v[0] + v[1] + v[2]}`));
      const cd = fs.map(f => f.v.map(v => [v[0], v[1], v[2], fmt(v[3], 0)]));
      plot('#s-fuentes', [{ type: 'heatmap', z, x: S.bandas, y, text: txt, texttemplate: '%{text}', customdata: cd, zmid: 0, zmin: -45, zmax: 45, colorscale: divergente(), showscale: false, xgap: 2, ygap: 2,
        textfont: { family: css('--f-mono'), size: 11, color: css('--ink') },
        hovertemplate: '<b>%{y}</b> · %{x}<br>reducen el error: %{customdata[0]} · sin diferencia: %{customdata[1]} · lo aumentan: %{customdata[2]}<br>mediana G: %{customdata[3]} %<extra></extra>' }],
      base({ hovermode: 'closest', margin: { l: 10, r: 10, t: 10, b: 36 }, xaxis: { showgrid: false, tickangle: angosto() ? -35 : 0, tickfont: { size: angosto() ? 9 : 11 } }, yaxis: { autorange: 'reversed', showgrid: false, tickfont: { size: angosto() ? 9 : 10.5, family: css('--f-mono') } } }), Math.max(330, 26 * fs.length + 60));
    };
    onSeg($('#app'), 's-est', v => { sEst = v; fuentes(); }); onSeg($('#app'), 's-ori', v => { sOri = v; fuentes(); }); fuentes();
    $('#ficha').dataset.leyenda = $('#ficha').innerHTML;
    crearMapa($('#mapa'));
  }

  // ────────────────────────────────────────────────────────── P1 · RESUMEN (base, solo caudal)
  function vResumen() {
    const app = $('#app');
    const tarjeta = e => {
      const S = D.estaciones[e], mj = S.mejor, hc = huDe(e, mj, 'hu_c'), hf = huDe(e, mj);
      return `<button class="est" data-ir="${e}" style="--c:var(${e === 'Racarumi' ? '--rac' : '--tam'})"><div class="valor">${txtHU(hc[K_HU])}<small> d</small></div>
        <h3>${esc(e)} · ${esc(mj)}</h3><p>Horizonte útil en fechas comunes (cota 95 %; incertidumbre ${rangoH(hc)} d). En toda la prueba: <b>${txtHU(hf[K_HU])} d</b>. NSE ≥ 0.5 hasta ${txtHU(hc[K_CAL])} d.</p></button>`;
    };
    const T = D.textos_comp;
    app.innerHTML = `<section class="vista">
      ${hero('P1 · Solo caudal local', '¿Con cuántos días de anticipación se puede pronosticar el caudal?',
        'Seis modelos y su combinado pronostican el caudal diario de 1 a 30 días con <b>solo los caudales antecedentes</b> de cada estación y el calendario.',
        `Racarumi <b>${txtHU(huDe('Racarumi', D.estaciones.Racarumi.mejor, 'hu_c')[K_HU])} d</b> y Tamshiyacu <b>${txtHU(huDe('Tamshiyacu', D.estaciones.Tamshiyacu.mejor, 'hu_c')[K_HU])} d</b> en las ${fmt(FCOM.n, 0)} fechas comunes. El río explica casi toda la diferencia; el modelo, poca.`)}
      <div class="duo">${EST.map(tarjeta).join('')}</div>
      <div class="rejilla mt">
        <div class="glass panel"><header><h2>Cómo cae el pronóstico con el horizonte</h2>
          <div class="ctrl">${seg('r-met', [['NSE', 'NSE'], ['hab_pers', 'vs persistencia'], ['hab_clim', 'vs climatología']], 'NSE', true)}${seg('r-per', [['c', 'fechas comunes'], ['f', 'prueba completa']], 'c', true)}</div>
          <span class="sub">Modelo seleccionado de cada estación (regla de selección en validación). Fechas comunes: ${fmt(FCOM.n, 0)} emisiones idénticas en las dos estaciones (${esc(FCOM.inicio)} a ${esc(FCOM.fin)}). Discontinuas: persistencia; punteadas: climatología. Banda: IC 95 % marginal.</span></header>
          <div class="cuerpo"><div id="r-curva" class="fig"></div></div></div>
        <div class="g-2">
          <div class="glass panel"><header><h2>¿Importa el modelo?</h2><div class="ctrl"><label>Horizonte <input type="range" id="r-h" min="1" max="30" value="7"><b class="n" id="r-hv">7 d</b></label></div>
            <span class="sub">NSE de los seis modelos y el combinado en las fechas comunes; discontinua: persistencia, punteada: climatología.</span></header>
            <div class="cuerpo"><div id="r-mod" class="fig"></div></div></div>
          <div class="glass panel"><header><h2>¿Se repite en otros periodos?</h2>
            <span class="sub">H cota 95 % del modelo seleccionado en cuatro orígenes; en cada uno, preparación e hiperparámetros se eligieron con su propio pasado. Bigote: hasta el p95 del bootstrap.</span></header>
            <div class="cuerpo"><div id="r-est" class="fig"></div></div></div>
        </div>
        <div class="g-2">
          <div class="glass panel"><header><h2>Sensibilidad a la longitud de la historia</h2>${seg('r-memh', [['1', 'h = 1'], ['7', 'h = 7'], ['15', 'h = 15']], '1')}
            <span class="sub">XGBoost con L días de historia; ✕: L = 30 sin calendario. Mide información predictiva, no la memoria física del río.</span></header>
            <div class="cuerpo"><div id="r-mem" class="fig"></div></div></div>
          <div class="glass panel"><header><h2>Interpretación</h2></header>
            <div class="cuerpo">${lectura([['Entre ríos', ul(TX.p1_rios)], ['Crecidas', ul(TX.p1_crecidas)], ['Estabilidad', ul(TX.p1_estabilidad)], ['Selección', ul(TX.p1_seleccion)], ['Historia', ul(TX.p1_historia)]], 'Interpretación', true)}</div></div>
        </div>
        <div class="glass panel"><header><h2>Tabla comparativa de los seis modelos</h2><span class="sub">Fechas comunes. Ordene haciendo clic en las columnas. El criterio de selección es el NSE medio del bloque de selección (2012–2015) con la regla de equivalencia; la prueba solo confirma.</span></header>
          <div class="cuerpo"><div class="tw" id="r-tabla"></div>${lectura([['Lectura de la tabla', ul(TX.p1_tabla)], ['Qué aporta cada familia', ul(TX.p1_familias) + '<div class="tw" id="r-pares"></div>']])}</div></div>
        ${conclusiones(TX.p1_conclusiones)}
      </div></section>`;
    let met = 'NSE', per = 'c';
    const curva = () => {
      const tr = [];
      for (const e of EST) {
        const S = D.estaciones[e], mj = S.mejor, c = colE(e), M = per === 'c' ? S.met_c[mj] : S.met[mj], R = per === 'c' ? S.ref_c : S.ref;
        tr.push({ x: HH, y: M[met], name: `${e} · ${mj}`, line: { color: c, width: 3 }, hovertemplate: '%{y:.3f}' });
        if (met === 'NSE') {
          tr.push({ x: HH, y: R.pers, name: `${e} · persistencia`, line: { color: c, width: 1.4, dash: 'dash' }, hovertemplate: '%{y:.3f}' });
          tr.push({ x: HH, y: R.clim, name: `${e} · climatología`, line: { color: c, width: 1.4, dash: 'dot' }, hovertemplate: '%{y:.3f}' });
        } else if (per === 'f') {
          const k = met === 'hab_pers' ? 'pers' : 'clim', ic = S.met[mj].ic;
          tr.push({ x: HH.concat([...HH].reverse()), y: ic[k + '_sup'].concat([...ic[k + '_inf']].reverse()), fill: 'toself', fillcolor: c + '33', line: { width: 0 }, hoverinfo: 'skip', name: `${e} · IC 95 % marginal` });
        }
      }
      const sh = met === 'NSE' ? [{ type: 'line', x0: 0.5, x1: 30.5, y0: 0.5, y1: 0.5, line: { color: css('--ink-3'), width: 1, dash: 'dashdot' } }]
        : [{ type: 'line', x0: 0.5, x1: 30.5, y0: 0, y1: 0, line: { color: css('--ink-3'), width: 1 } }];
      const ann = [];
      for (const e of EST) {
        const hu = huDe(e, D.estaciones[e].mejor, per === 'c' ? 'hu_c' : 'hu')[K_HU];
        if (hu < 30) sh.push({ type: 'line', x0: hu + 0.5, x1: hu + 0.5, yref: 'paper', y0: 0, y1: 1, line: { color: colE(e), width: 1.4, dash: 'dashdot' } });
        ann.push({ x: hu < 30 ? hu + 0.7 : 29.8, xanchor: hu < 30 ? 'left' : 'right', yref: 'paper', y: e === 'Racarumi' ? 0.06 : 0.97, text: `<b>${e}</b>: H ${txtHU(hu)} d`, showarrow: false, font: { color: colE(e), size: 12 }, bgcolor: css('--solid'), borderpad: 3 });
      }
      plot('#r-curva', tr, base({ xaxis: { title: { text: 'Horizonte de pronóstico (días)' }, range: [0.5, 30.5], dtick: 5 }, yaxis: { title: { text: ETQ[met] } }, shapes: sh, annotations: ann }), 400);
    };
    onSeg(app, 'r-met', v => { met = v; curva(); }); onSeg(app, 'r-per', v => { per = v; curva(); }); curva();
    const modBar = h => {
      $('#r-hv').textContent = h + ' d';
      const tr = EST.map((e, i) => { const S = D.estaciones[e]; return { type: 'bar', x: S.modelos.map(n => n === COMB ? 'Combinado' : n), y: S.modelos.map(n => S.met_c[n].NSE[h - 1]), name: e, marker: { color: S.modelos.map(colM) },
        xaxis: i ? 'x2' : 'x', yaxis: i ? 'y2' : 'y', text: S.modelos.map(n => fmt(S.met_c[n].NSE[h - 1], 3)), textposition: 'outside', cliponaxis: false, textfont: { family: css('--f-mono'), size: 10 }, hovertemplate: '%{x}: NSE %{y:.3f}<extra>' + e + '</extra>', showlegend: false }; });
      const rng = i => { const S = D.estaciones[EST[i]], v = S.modelos.map(n => S.met_c[n].NSE[h - 1]).concat([S.ref_c.pers[h - 1], S.ref_c.clim[h - 1]]); const lo = Math.min(...v), hi = Math.max(...v); const pad = Math.max(0.02, (hi - lo) * 0.25); return [Math.max(-1, lo - pad), Math.min(1.02, hi + pad)]; };
      const ref = i => { const S = D.estaciones[EST[i]], xr = i ? 'x2' : 'x', yr = i ? 'y2' : 'y'; return [
        { type: 'line', xref: xr + ' domain', x0: 0, x1: 1, yref: yr, y0: S.ref_c.pers[h - 1], y1: S.ref_c.pers[h - 1], line: { color: colM('Persistencia'), dash: 'dash', width: 1.4 } },
        { type: 'line', xref: xr + ' domain', x0: 0, x1: 1, yref: yr, y0: S.ref_c.clim[h - 1], y1: S.ref_c.clim[h - 1], line: { color: colM('Climatología'), dash: 'dot', width: 1.6 } }]; };
      plot('#r-mod', tr, base({ grid: { rows: 1, columns: 2, pattern: 'independent' }, hovermode: 'closest', margin: { l: 50, r: 10, t: 34, b: 90 },
        xaxis: { tickangle: -35 }, xaxis2: { tickangle: -35 }, yaxis: { title: { text: 'NSE' }, range: rng(0) }, yaxis2: { range: rng(1) }, shapes: ref(0).concat(ref(1)),
        annotations: [{ text: '<b>Racarumi</b>', xref: 'x domain', yref: 'paper', x: 0.5, y: 1.08, showarrow: false, font: { color: colE('Racarumi') } },
          { text: '<b>Tamshiyacu</b>', xref: 'x2 domain', yref: 'paper', x: 0.5, y: 1.08, showarrow: false, font: { color: colE('Tamshiyacu') } }] }), 370);
    };
    $('#r-h').addEventListener('input', ev => modBar(+ev.target.value)); modBar(7);
    const tr = EST.map(e => { const S = D.estaciones[e], s = S.estabilidad.filter(r => r.modelo === S.mejor);
      return { type: 'bar', x: s.map(r => 'prueba ' + r.prueba), y: s.map(r => r[K_HU]), name: `${e} · ${S.mejor}`, marker: { color: colE(e) },
        error_y: { type: 'data', symmetric: false, array: s.map(r => Math.max(0, r[K_P95] - r[K_HU])), arrayminus: s.map(() => 0), color: css('--ink-3'), thickness: 1.2, width: 3 },
        text: s.map(r => txtHU(r[K_HU])), textposition: 'outside', cliponaxis: false, hovertemplate: '%{x}: H cota %{text} d<extra>' + e + '</extra>' }; });
    plot('#r-est', tr, base({ barmode: 'group', hovermode: 'closest', yaxis: { title: { text: 'H cota 95 % (días)' }, range: [0, 34] }, legend: { orientation: 'h', y: -0.18 } }), 370);
    const mem = h => {
      const Ls = ['1', '3', '7', '15', '30', '60'];
      plot('#r-mem', EST.map(e => ({ x: Ls.map(Number), y: Ls.map(L => D.estaciones[e].memoria[L].hab_pers[h - 1]), name: e, mode: 'lines+markers', line: { color: colE(e), width: 2.4 }, marker: { size: 8 }, hovertemplate: 'L = %{x} d: %{y:.3f}' }))
        .concat(EST.map(e => ({ x: [30], y: [D.estaciones[e].memoria['30 sin calendario'].hab_pers[h - 1]], name: `${e}: sin calendario`, mode: 'markers', marker: { symbol: 'x', size: 11, color: colE(e), line: { width: 2 } }, hovertemplate: 'L = 30 sin calendario: %{y:.3f}' }))),
        base({ hovermode: 'closest', xaxis: { type: 'log', title: { text: 'Días de historia que ve el modelo (L)' }, tickvals: [1, 3, 7, 15, 30, 60] }, yaxis: { title: { text: 'Habilidad frente a la persistencia' } } }), 360);
    };
    onSeg(app, 'r-memh', v => mem(+v)); mem(1);
    const cols = [['estación', 'Estación'], ['modelo', 'Modelo', (v, r) => dotM(v) + (D.estaciones[r['estación']].mejor === v ? ' <span class="chip ok">seleccionado</span>' : ''), 'izq'],
      ['NSE medio selección', 'NSE selección'], ['NSE h=1', 'NSE 1 d'], ['NSE h=7', 'NSE 7 d'], ['NSE h=30', 'NSE 30 d'], ['MAE h=7 (m³/s)', 'MAE 7 d'],
      ['H cota 95 % (d)', 'H cota', v => txtHU(v)], ['H puntual (d)', 'H puntual', v => txtHU(v)], ['H p05–p95 (d)', 'H p05–p95'], ['NSE ≥ 0.5 hasta (d)', 'NSE≥0.5 (d)', v => txtHU(v)],
      ['H cota, prueba completa (d)', 'H cota completa', v => txtHU(v)], ['CSI diario h=3', 'CSI diario 3 d']];
    tabla('#r-tabla', D.comparativa, cols, { marca: r => D.estaciones[r['estación']].mejor === r.modelo });
    const pares = () => tabla('#r-pares', D.pares, [['estación', 'Estación'], ['comparación', 'Comparación'], ['Δ NSE medio selección', 'Δ NSE selección'], ['Δ NSE h=1', 'Δ NSE 1 d'],
      ['Δ NSE h=7', 'Δ NSE 7 d'], ['Δ NSE h=30', 'Δ NSE 30 d'], ['Δ H puntual (d)', 'Δ H puntual (d)', v => fmt(v, 0)]]);
    app.addEventListener('click', ev => { if (ev.target.closest('.lect-tabs button')) setTimeout(() => { if ($('#r-pares') && !$('#r-pares').innerHTML) pares(); }, 0); });
  }

  // ────────────────────────────────────────────────────────── ESTACIÓN (01 · 02)
  function vEstacion(e) {
    const S = D.estaciones[e], app = $('#app'), mj = S.mejor, colorE = e === 'Racarumi' ? '--rac' : '--tam';
    const dec = e === 'Tamshiyacu' ? 0 : 1, U = 'm³/s';
    const hf = huDe(e, mj), X = TX[e];
    const secs = [['s-exp', 'Explorador'], ['s-hor', 'Desempeño'], ['s-crec', 'Crecidas'], ['s-ev', 'Eventos'], ['s-est', 'Estabilidad'], ['s-mem', 'Historia y variables'], ['s-conc', 'Conclusiones']];
    const opM = (sel, extra = []) => extra.concat(S.modelos).map(n => `<option ${n === sel ? 'selected' : ''}>${esc(n)}</option>`).join('');
    app.innerHTML = `<section class="vista" style="--c:var(${colorE})">
      ${hero(`${esc(S.cuenca)} · vertiente ${S.vertiente === 'Pacífico' ? 'del Pacífico' : 'amazónica'} · ${fmt(S.area, 0)} km² · registro ${esc(S.periodo)}`, esc(e), '', `Modelo seleccionado: <b>${esc(mj)}</b>. Horizonte útil <b>${txtHU(hf[K_HU])} d</b> en toda la prueba (rango bootstrap ${rangoH(hf)} d); NSE ≥ 0.5 hasta ${txtHU(hf[K_CAL])} d.`, colorE)}
      <div class="kpis">
        ${kpi('Horizonte útil', txtHU(hf[K_HU]) + ' d', `${esc(mj)} · cota 95 %`, css(colorE))}
        ${kpi('Incertidumbre', rangoH(hf) + ' d', `H puntual ${txtHU(hf[K_PUN])} d · p05–p95`)}
        ${kpi('NSE ≥ 0.5', txtHU(hf[K_CAL]) + ' d', 'calidad suficiente')}
        ${kpi('P95 (entrenamiento)', fmt(S.P95, dec), U)}
        ${kpi('Muestras de prueba', fmt(S.pred.h['1'].d.length, 0), 'emisiones con 30 caudales futuros')}
      </div>
      <nav class="indice mt" style="--c:var(${colorE})">${secs.map(([id, t]) => `<a href="#${id}">${t}</a>`).join('')}</nav>

      <div class="glass panel sec" id="s-exp"><header><h2>Explorador de pronósticos</h2>
        <div class="ctrl"><label>Modelo <select id="e-mod">${opM(mj, ['Persistencia', 'Climatología'])}</select></label>
          ${seg('e-h', H.map(h => [h, h + ' d']), 3)}
          <label><input type="checkbox" id="e-pers"> persistencia</label>
          <label>Ir a <select id="e-ev"><option value="">todo el periodo de prueba</option>${S.eventos.map((v, i) => `<option value="${i}">crecida ${v.fecha} (${fmt(v.pico, 0)} ${U})</option>`).join('')}</select></label></div>
        <span class="sub">Línea clara: caudal observado. En color: lo pronosticado para cada día, emitido <b id="e-hl">3</b> días antes. Use la barra inferior o arrastre para hacer zoom.</span></header>
        <div class="cuerpo"><div id="e-graf" class="fig"></div><div class="cifras" id="e-cif"></div></div></div>

      <div class="g-2 mt">
        <div class="glass panel sec" id="s-hor"><header><h2>Desempeño por horizonte</h2>
          <div class="ctrl"><select id="h-met">${Object.entries(ETQ).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
            <label>Banda IC <select id="h-ic">${opM(mj)}</select></label></div>
          <span class="sub">Seis modelos y el combinado en prueba (2016–fin). Clic en la leyenda para ocultar curvas. Banda: IC 95 % marginal por horizonte.</span></header>
          <div class="cuerpo"><div id="h-graf" class="fig"></div>
            ${lectura([['Prueba', ul(X.prueba)], ['Selección', ul(X.seleccion) + '<div class="tw" id="h-sel"></div>'], ['Ajuste y semillas', ul(X.ajuste) + '<div class="tw" id="h-pres"></div><div class="tw" id="h-sem"></div>']])}</div></div>
        <div class="glass panel"><header><h2>Horizontes por modelo</h2>
          <span class="sub">H cota 95 % (cifra de las conclusiones); H puntual con su rango bootstrap p05–p95; NSE ≥ 0.5 (complementario). Una barra en 30 significa «30 o más».</span></header>
          <div class="cuerpo"><div id="hu-graf" class="fig"></div>${lectura([['Horizonte útil', ul(X.horizonte)], ['Fechas comunes', ul(X.comun) + '<div class="tw" id="hu-bloq"></div>']])}</div></div>
      </div>

      <div class="glass panel sec mt" id="s-crec"><header><h2>Caudales elevados (sobre el P95 = ${fmt(S.P95, dec)} ${U})</h2>
        <div class="ctrl"><label>Modelo <select id="c-mod">${opM(mj)}</select></label>${seg('c-modo', [['rel', 'error relativo'], ['abs', 'error absoluto']], 'rel', true)}</div>
        <span class="sub">(a) Error en días altos y ordinarios; (b) detección diaria de días sobre el P95 (no distingue avisos de eventos nuevos: ver P2); (c) observado frente a pronosticado en el horizonte elegido en el explorador.</span></header>
        <div class="cuerpo"><div class="g-3"><div id="c-err" class="fig"></div><div id="c-det" class="fig"></div><div id="c-disp" class="fig"></div></div>
          ${lectura([['Caudales altos', ul(X.crecidas)], ['Mayores crecidas', ul(X.picos)]])}</div></div>

      <div class="glass panel sec mt" id="s-ev"><header><h2>Errores por evento (${esc(mj)})</h2>${seg('ev-h', [['1', '1 d'], ['3', '3 d'], ['7', '7 d']], '1')}
        <span class="sub">Todos los eventos de la prueba. Errores firmados (negativo = subestimación): pronóstico para el día del pico emitido h días antes y máximo pronosticado en la ventana del evento extendida h + 3 días, con su desfase (positivo = tarde).</span></header>
        <div class="cuerpo"><div class="cifras" id="ev-res" style="border:0;margin:0 0 8px;padding:0"></div><div class="tw" id="ev-tabla" style="max-height:380px"></div>${lectura([['Eventos', ul(X.eventos)]])}</div></div>

      <div class="g-2 mt">
        <div class="glass panel sec" id="s-est"><header><h2>Estabilidad con varios orígenes</h2>
          <span class="sub">En cada origen, ε, escalones, P95, climatología, hiperparámetros, épocas y semillas se eligieron con su propio pasado. Barra: H cota 95 %; bigote: hasta p95.</span></header>
          <div class="cuerpo"><div id="est-graf" class="fig"></div>${lectura([['Estabilidad', ul(X.estabilidad)], ['Registros con escalones', ul(X.sensibilidad) + '<div class="tw" id="sens-tabla"></div>']])}</div></div>
        <div class="glass panel sec" id="s-mem"><header><h2>Historia y variables</h2>${seg('m-vista', [['mem', 'historia (L)'], ['imp', 'qué usa el modelo']], 'mem', true)}
          <span class="sub">Historia: XGBoost con L días (mismas muestras de prueba); punteada: L = 30 sin calendario. Variables: aumento del error (%) al desordenar cada grupo en la prueba (XGBoost); mide uso, no causalidad.</span></header>
          <div class="cuerpo"><div id="m-graf" class="fig"></div>${lectura([['Historia', ul(X.memoria)], ['Variables', ul(X.importancia)]])}</div></div>
      </div>
      <div class="sec" id="s-conc">${conclusiones(X.conclusiones, `Conclusiones · ${e}`)}</div>
    </section>`;

    const t0p = fecha0(S.pred.t0), t0s = fecha0(S.serie.t0);
    const xs = S.serie.q.map((_, i) => iso(t0s + i * DIA));
    const obsEn = ms => { const k = Math.round((ms - t0s) / DIA); return (k >= 0 && k < S.serie.q.length) ? S.serie.q[k] : null; };
    const cache = {};
    const serieH = h => cache[h] || (cache[h] = (() => { const P = S.pred.h[h]; const ms = P.d.map(d => t0p + d * DIA);
      const x = [], idx = []; for (let i = 0; i < ms.length; i++) { if (i && ms[i] - ms[i - 1] > DIA) { x.push(null); idx.push(-1); } x.push(iso(ms[i])); idx.push(i); }
      return { x, idx, ms }; })());
    const valores = (h, n) => { const s = serieH(h), v = S.pred.h[h].mod[n]; return s.idx.map(i => i < 0 ? null : v[i]); };

    let hSel = 3, rango = null;
    const exp = () => {
      const n = $('#e-mod').value, s = serieH(hSel);
      $('#e-hl').textContent = hSel;
      const tr = [{ x: xs, y: S.serie.q, name: 'Observado', line: { color: css('--ink'), width: 1.6 }, hovertemplate: '%{y:,.' + dec + 'f} ' + U }];
      if ($('#e-pers').checked && n !== 'Persistencia') tr.push({ x: s.x, y: valores(hSel, 'Persistencia'), name: `Persistencia (h = ${hSel} d)`, line: { color: colM('Persistencia'), width: 1.2, dash: 'dash' }, hovertemplate: '%{y:,.' + dec + 'f} ' + U });
      tr.push({ x: s.x, y: valores(hSel, n), name: `${n} (h = ${hSel} d)`, line: { color: colM(n), width: 1.8 }, hovertemplate: '%{y:,.' + dec + 'f} ' + U });
      plot('#e-graf', tr, base({ xaxis: { type: 'date', rangeslider: { visible: true, thickness: 0.08, bgcolor: css('--glass-2') }, range: rango || undefined },
        yaxis: { title: { text: 'Caudal (' + U + ')' }, tickformat: ',.0f' }, legend: { orientation: 'h', y: 1.1, x: 0 }, margin: { l: 64, r: 14, t: 30, b: 30 },
        shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: S.P95, y1: S.P95, line: { color: css('--bad'), dash: 'dot', width: 1.2 } }],
        annotations: [{ xref: 'paper', x: 0.005, y: S.P95, yanchor: 'bottom', xanchor: 'left', text: 'P95', showarrow: false, font: { size: 10, color: css('--bad') } }] }), 440);
      const nm = S.met[n], i = hSel - 1;
      $('#e-cif').innerHTML = nm ? `<span>A ${hSel} días — NSE <b>${fmt(nm.NSE[i], 3)}</b></span><span>KGE <b>${fmt(nm.KGE[i], 3)}</b></span><span>RMSE <b>${fmt(nm.RMSE[i], dec)} ${U}</b></span><span>PBIAS <b>${fmt(nm.PBIAS[i], 1)} %</b></span><span>habilidad vs persistencia <b>${fmt(nm.hab_pers[i], 3)}</b></span><span>vs climatología <b>${fmt(nm.hab_clim[i], 3)}</b></span>`
        : `<span>A ${hSel} días — NSE de la ${n.toLowerCase()} <b>${fmt(n === 'Persistencia' ? S.ref.pers[i] : S.ref.clim[i], 3)}</b></span>`;
    };
    $('#e-mod').addEventListener('change', exp); $('#e-pers').addEventListener('change', exp);
    onSeg(app, 'e-h', v => { hSel = +v; exp(); disp(); });
    $('#e-ev').addEventListener('change', ev => { const v = ev.target.value; if (v === '') rango = null; else { const p = fecha0(S.eventos[+v].fecha); rango = [iso(p - 50 * DIA), iso(p + 35 * DIA)]; } exp(); });
    exp();

    const hor = () => {
      const met = $('#h-met').value, nic = $('#h-ic').value, tr = [];
      if (met === 'NSE') { tr.push({ x: HH, y: S.ref.pers, name: 'Persistencia', line: { color: colM('Persistencia'), dash: 'dash', width: 2 }, hovertemplate: '%{y:.3f}' });
        tr.push({ x: HH, y: S.ref.clim, name: 'Climatología', line: { color: colM('Climatología'), dash: 'dot', width: 2.2 }, hovertemplate: '%{y:.3f}' }); }
      if (met === 'hab_pers' || met === 'hab_clim') { const k = met === 'hab_pers' ? 'pers' : 'clim', ic = S.met[nic].ic;
        tr.push({ x: HH.concat([...HH].reverse()), y: ic[k + '_sup'].concat([...ic[k + '_inf']].reverse()), fill: 'toself', fillcolor: colM(nic) + '30', line: { width: 0 }, hoverinfo: 'skip', name: `IC 95 % ${nic}` }); }
      for (const n of S.modelos) tr.push({ x: HH, y: S.met[n][met], name: n, line: { color: colM(n), width: n === mj ? 3.2 : 1.6, dash: n === COMB ? 'dot' : 'solid' }, hovertemplate: '%{y:.3f}' });
      const sh = (met === 'hab_pers' || met === 'hab_clim' || met === 'PBIAS') ? [{ type: 'line', x0: 0.5, x1: 30.5, y0: 0, y1: 0, line: { color: css('--ink-3'), width: 1 } }]
        : met === 'NSE' ? [{ type: 'line', x0: 0.5, x1: 30.5, y0: 0.5, y1: 0.5, line: { color: css('--ink-3'), width: 1, dash: 'dashdot' } }] : [];
      plot('#h-graf', tr, base({ xaxis: { title: { text: 'Horizonte (días)' }, dtick: 5, range: [0.5, 30.5] }, yaxis: { title: { text: ETQ[met] } }, shapes: sh }), 410);
    };
    $('#h-met').addEventListener('change', hor); $('#h-ic').addEventListener('change', hor); hor();

    const tablasLect = () => {
      tabla('#h-pres', S.presupuesto, [['modelo', 'Modelo', v => dotM(v), 'izq'], ['combinaciones', 'Combinaciones', v => fmt(v, 0)], ['segundos', 'Segundos', v => fmt(v, 0)], ['NSE_sel_mejor', 'NSE selección, mejor'], ['NSE_sel_peor', 'NSE selección, peor']]);
      tabla('#h-sel', S.seleccion, [['modelo', 'Modelo', (v, r) => dotM(v) + (r.seleccionado ? ' <span class="chip ok">seleccionado</span>' : ''), 'izq'], ['NSE medio selección', 'NSE medio'],
        ['diferencia con el mejor', 'Diferencia'], ['IC90 inferior', 'IC 90 % inf.'], ['IC90 superior', 'IC 90 % sup.'], ['clase', 'Clase']], { marca: r => r.seleccionado });
      tabla('#h-sem', S.semillas, [['modelo', 'Modelo', v => dotM(v), 'izq'], ['semilla', 'Semilla'], ['H puntual (d)', 'H puntual', v => txtHU(v)], ['NSE h=1', 'NSE 1 d'], ['NSE h=7', 'NSE 7 d'], ['NSE h=30', 'NSE 30 d']]);
      tabla('#hu-bloq', S.bloques, [['bloque', 'Bloque bootstrap'], [K_HU, 'H cota', v => txtHU(v)], [K_P05, 'p05', v => txtHU(v)], ['H mediana (d)', 'Mediana', v => txtHU(v)], [K_P95, 'p95', v => txtHU(v)], ['P(H ≥ 30)', 'P(H ≥ 30)']]);
      if ($('#sens-tabla')) {
        if (S.sens_resumen.length) tabla('#sens-tabla', S.sens_resumen, [['indicador', 'Indicador'], ['solo años sin escalones', 'Solo años sin escalones'], ['controles: mínimo', 'Controles: mín.'],
          ['p25', 'p25'], ['mediana', 'Mediana'], ['p75', 'p75'], ['máximo', 'Máx.'], ['controles ≤ variante restringida (%)', 'Controles ≤ variante (%)', v => fmt(v, 0)]]);
        else $('#sens-tabla').innerHTML = '';
      }
    };
    app.addEventListener('click', ev => { if (ev.target.closest('.lect-tabs button')) setTimeout(tablasLect, 0); });
    const claves = [[K_HU, 'H cota 95 %', css('--accent')], [K_PUN, 'H puntual', css('--ink-3')], [K_CAL, 'NSE ≥ 0.5', css('--good')]];
    const trHU = claves.map(([k, t, c], j) => ({ type: 'bar', orientation: 'h', y: S.hu.map(r => r.modelo === COMB ? 'Combinado' : r.modelo), x: S.hu.map(r => r[k]), name: t, marker: { color: c },
      text: S.hu.map(r => txtHU(r[k])), textposition: 'outside', cliponaxis: false, textfont: { family: css('--f-mono'), size: 10 }, hovertemplate: '%{y}: %{text} d<extra>' + t + '</extra>',
      error_x: j === 1 ? { type: 'data', symmetric: false, array: S.hu.map(r => Math.max(0, r[K_P95] - r[k])), arrayminus: S.hu.map(r => Math.max(0, r[k] - r[K_P05])), color: css('--ink-2'), thickness: 1.2, width: 3 } : undefined }));
    plot('#hu-graf', trHU, base({ barmode: 'group', bargap: 0.25, hovermode: 'closest', xaxis: { title: { text: 'Días' }, range: [0, 34] }, yaxis: { autorange: 'reversed' }, margin: { l: 120, r: 20, t: 10, b: 40 }, legend: { orientation: 'h', y: -0.14 } }), 410);

    let modoErr = 'rel';
    const crec = () => {
      const n = $('#c-mod').value, c = S.crec[n], p = S.crec['Persistencia'], ka = modoErr === 'rel' ? 'error_rel_altos' : 'MAE_altos', ko = modoErr === 'rel' ? 'error_rel_ordinarios' : 'MAE_ordinarios';
      const un = modoErr === 'rel' ? '%' : U, fm = modoErr === 'rel' ? '%{y:.1f} %' : '%{y:,.0f} ' + U;
      plot('#c-err', [
        { x: HH, y: c[ka], name: `${n}: > P95`, line: { color: colM(n), width: 2.6 }, hovertemplate: fm },
        { x: HH, y: c[ko], name: `${n}: ordinarios`, line: { color: colM(n), width: 1.3, dash: 'dot' }, hovertemplate: fm },
        { x: HH, y: p[ka], name: 'Persistencia: > P95', line: { color: colM('Persistencia'), width: 2, dash: 'dash' }, hovertemplate: fm },
        { x: HH, y: p[ko], name: 'Persistencia: ordinarios', line: { color: colM('Persistencia'), width: 1, dash: 'dot' }, hovertemplate: fm }],
      base({ title: { text: modoErr === 'rel' ? '(a) Error relativo mediano' : '(a) Error absoluto medio', font: { size: 13 }, x: 0.01 }, xaxis: { title: { text: 'Horizonte (días)' }, dtick: 5 }, yaxis: { title: { text: un }, tickformat: modoErr === 'rel' ? '' : ',.0f' }, margin: { l: 56, r: 10, t: 40, b: 44 }, legend: { orientation: 'h', y: -0.3 } }), 360);
      plot('#c-det', [
        { x: HH, y: c.CSI, name: `CSI ${n}`, line: { color: colM(n), width: 2.6 }, hovertemplate: '%{y:.2f}' },
        { x: HH, y: c.POD, name: 'POD', line: { color: css('--good'), width: 1.4 }, hovertemplate: '%{y:.2f}' },
        { x: HH, y: c.FAR, name: 'FAR', line: { color: css('--bad'), width: 1.4 }, hovertemplate: '%{y:.2f}' },
        { x: HH, y: p.CSI, name: 'CSI persistencia', line: { color: colM('Persistencia'), width: 2, dash: 'dash' }, hovertemplate: '%{y:.2f}' }],
      base({ title: { text: '(b) Detección diaria sobre el P95', font: { size: 13 }, x: 0.01 }, xaxis: { title: { text: 'Horizonte (días)' }, dtick: 5 }, yaxis: { range: [0, 1.02] }, margin: { l: 44, r: 10, t: 40, b: 44 }, legend: { orientation: 'h', y: -0.3 } }), 360);
      disp();
    };
    const disp = () => {
      const n = $('#c-mod').value, s = serieH(hSel), v = S.pred.h[hSel].mod[n];
      const o = s.ms.map(obsEn), alto = o.map(x => x != null && x > S.P95);
      const tr = [false, true].map(a => ({ type: 'scattergl', mode: 'markers', x: o.filter((_, i) => alto[i] === a), y: v.filter((_, i) => alto[i] === a),
        name: a ? 'días > P95' : 'ordinarios', marker: { size: a ? 6 : 4, color: a ? css('--bad') : colM(n), opacity: a ? 0.85 : 0.35 }, hovertemplate: 'obs %{x:,.' + dec + 'f} · pron %{y:,.' + dec + 'f}<extra></extra>' }));
      const val = o.filter(x => x != null).concat(v.filter(x => x != null));
      const mx = Math.max(...val) * 1.03, mn = e === 'Tamshiyacu' ? Math.min(...val) * 0.95 : 0;
      tr.push({ x: [mn, mx], y: [mn, mx], mode: 'lines', line: { color: css('--ink-3'), dash: 'dash', width: 1 }, name: '1:1', hoverinfo: 'skip' });
      plot('#c-disp', tr, base({ title: { text: `(c) ${n}, ${hSel} d`, font: { size: 13 }, x: 0.01 }, hovermode: 'closest', xaxis: { title: { text: 'Observado (' + U + ')' }, range: [mn, mx], tickformat: ',.0f' }, yaxis: { title: { text: 'Pronosticado (' + U + ')' }, range: [mn, mx], tickformat: ',.0f' }, margin: { l: 60, r: 10, t: 40, b: 44 }, legend: { orientation: 'h', y: -0.3 },
        shapes: [{ type: 'line', x0: S.P95, x1: S.P95, yref: 'paper', y0: 0, y1: 1, line: { color: css('--bad'), dash: 'dot', width: 1 } }, { type: 'line', y0: S.P95, y1: S.P95, xref: 'paper', x0: 0, x1: 1, line: { color: css('--bad'), dash: 'dot', width: 1 } }] }), 360);
    };
    $('#c-mod').addEventListener('change', crec); onSeg(app, 'c-modo', v => { modoErr = v; crec(); }); crec();

    const evT = h => { const r = S.eventos_res.find(x => (x.h ?? x['Unnamed: 0']) === h) || {};
      $('#ev-res').innerHTML = `<span>A ${h} d · <b>${fmt(r['eventos con pronóstico'], 0)}</b> eventos con pronóstico</span><span>error firmado mediano en el pico <b>${fmt(r['error firmado mediano (m³/s)'], dec)} ${U}</b> (<b>${fmt(r['error relativo firmado mediano (%)'], 1)} %</b>)</span><span>subestimados <b>${fmt(r['eventos subestimados en el pico'], 0)}</b></span><span>error del máximo <b>${fmt(r['error relativo mediano del máximo (%)'], 1)} %</b></span><span>desfase mediano del máximo <b>${fmt(r['desfase mediano (d)'], 0)} d</b> (p25–p75 ${fmt(r['desfase p25 (d)'], 0)}–${fmt(r['desfase p75 (d)'], 0)})</span>`;
      tabla('#ev-tabla', S.eventos_pron.filter(r => r.h === h), [['inicio', 'Inicio'], ['pico obs (m³/s)', 'Pico obs.'], ['pronóstico para el pico', 'Pron. para el pico'],
        ['error firmado en el pico (m³/s)', 'Error firmado'], ['error relativo firmado en el pico (%)', 'Error rel. (%)', v => fmt(v, 1)], ['máximo pronosticado', 'Máx. pronosticado'],
        ['error relativo firmado del máximo (%)', 'Error rel. máx. (%)', v => fmt(v, 1)], ['desfase del máximo (d)', 'Desfase (d)', v => fmt(v, 0)]]); };
    onSeg(app, 'ev-h', v => evT(+v)); evT(1);

    const cortes = [...new Set(S.estabilidad.map(r => r.prueba))];
    const mods = [...new Set(S.estabilidad.map(r => r.modelo))];
    const fe = (c, n) => S.estabilidad.find(r => r.prueba === c && r.modelo === n) || {};
    plot('#est-graf', mods.map(n => ({ type: 'bar', x: cortes.map(c => 'prueba ' + c), y: cortes.map(c => fe(c, n)[K_HU]),
      error_y: { type: 'data', symmetric: false, array: cortes.map(c => Math.max(0, (fe(c, n)[K_P95] ?? 0) - (fe(c, n)[K_HU] ?? 0))), arrayminus: cortes.map(() => 0), color: css('--ink-3'), thickness: 1, width: 2 },
      name: n, marker: { color: colM(n) }, text: cortes.map(c => txtHU(fe(c, n)[K_HU])), textposition: 'outside', cliponaxis: false, textfont: { size: 10 } })),
    base({ barmode: 'group', hovermode: 'closest', yaxis: { title: { text: 'H cota 95 % (días)' }, range: [0, 34] } }), 360);

    const memG = () => {
      const Ls = ['1', '3', '7', '15', '30', '60', '30 sin calendario'], pal = ['#440154', '#3b528b', '#21918c', '#27ad81', '#5ec962', '#bddf26', '#ff6b6b'];
      plot('#m-graf', Ls.map((L, i) => ({ x: HH, y: S.memoria[L].hab_pers, name: `L = ${L}`, line: { color: oscuro() && i < 2 ? ['#7b5cd6', '#5b7fd6'][i] : pal[i], width: L === '1' || L === '3' ? 2.6 : 1.6, dash: i === 6 ? 'dot' : 'solid' }, hovertemplate: '%{y:.3f}' })),
        base({ xaxis: { title: { text: 'Horizonte (días)' }, dtick: 5 }, yaxis: { title: { text: 'Habilidad frente a la persistencia' } } }), 360);
    };
    const impG = () => {
      const z = S.imp.v.map(r => r.map(x => Math.log10(Math.max(x, 0) + 1)));
      plot('#m-graf', [{ type: 'heatmap', z, x: S.imp.h.map(h => h.replace('h=', '') + ' d'), y: S.imp.grupos, text: S.imp.v.map(r => r.map(x => fmt(x, 0) + ' %')), texttemplate: '%{text}',
        hovertemplate: '%{y}<br>horizonte %{x}: +%{text}<extra></extra>', colorscale: 'Viridis', showscale: false, xgap: 2, ygap: 2 }],
      base({ hovermode: 'closest', xaxis: { title: { text: 'Horizonte' } }, yaxis: { autorange: 'reversed' }, margin: { l: 180, r: 10, t: 10, b: 44 } }), 360);
    };
    onSeg(app, 'm-vista', v => v === 'mem' ? memG() : impG()); memG();
  }

  // ────────────────────────────────────────────────────────── P2 · ANTICIPACIÓN
  function vAnticipacion() {
    const app = $('#app'), T = A.textos;
    const avisa = e => sintesisA(e)['modelo (avisos)'];
    const tarjeta = e => { const s = sintesisA(e), ok = s['anticipación útil (d)'] > 0;
      return `<div class="glass panel" style="--c:var(${e === 'Racarumi' ? '--rac' : '--tam'})"><header><h2 style="color:var(--c)">${esc(e)}</h2><span class="chip ${ok ? (s['cruces evaluables'] < 10 ? 'med' : 'ok') : 'no'}">${ok ? (s['cruces evaluables'] < 10 ? 'exploratorio' : 'cumple') : 'no cumple el criterio'}</span></header>
        <div class="cuerpo"><div class="kpis k4">${kpi('Anticipación útil', fmt(s['anticipación útil (d)'], 0) + ' d', `avisos con ${esc(s['modelo (avisos)'])}`, css(e === 'Racarumi' ? '--rac' : '--tam'))}
          ${kpi('Aciertos', `${fmt(s.aciertos, 0)}/${fmt(s['cruces evaluables'], 0)}`, `POD ${fmt(s.POD, 2)}`)}${kpi('Falsas alarmas', fmt(s['falsas alarmas'], 0), `FAR ${fmt(s.FAR, 2)}`)}
          ${kpi('CSI', fmt(s.CSI, 2), `referencia: ${esc(s['referencia con mayor CSI en prueba (descriptiva, no seleccionada)'] || '')} ${fmt(s['CSI de esa referencia'], 2)}`)}</div>
          <p class="nota">Magnitud: ${esc(s['modelo (magnitud)'])}, H cota ${txtHU(s['H cota 95 % magnitud (d)'])} d. Anticipación mediana de los aciertos: ${fmt(s['anticipación real mediana entre los aciertos (d)'], 0)} d. Carácter: ${esc(s['carácter'])}.</p></div></div>`; };
    app.innerHTML = `<section class="vista" style="--c:var(--bad)">
      ${hero('P2 · Solo caudal local · verificación por eventos', '¿Con cuántos días reales de anticipación se puede avisar un nuevo cruce del P95?',
        'Solo cuentan avisos emitidos <b>antes</b> del cruce, desde días en que el río llevaba 7 días bajo el umbral. Detecciones, omisiones y falsas alarmas se cuentan en eventos y episodios.',
        'Estimar bien la magnitud no basta para avisar: <b>Racarumi no alcanza el criterio</b> (POD ≥ 0.5 con FAR ≤ 0.5) y Tamshiyacu solo tiene 3 cruces en la prueba.', '--bad')}
      <div class="g-2">${EST.map(tarjeta).join('')}</div>
      <div class="g-2 mt">
        <div class="glass panel"><header><h2>Diagrama de desempeño</h2><div class="ctrl">${seg('d-est', EST.map(e => [e, e]), 'Racarumi', true)}<label>Modelo <select id="d-mod"></select></label></div>
          <span class="sub">Detección (POD) frente a tasa de éxito (1 − FAR) de los días en que el pronóstico a h días supera el P95. Puntos: un horizonte cada uno (color = h). Curvas: CSI constante; rectas punteadas: sesgo (avisos por crecida). Lo ideal es la esquina superior derecha. Estrellas: sistemas de aviso por evento (base y selección final).</span></header>
          <div class="cuerpo"><div id="d-graf" class="fig"></div></div></div>
        <div class="glass panel"><header><h2>Los avisos temporada por temporada</h2><div class="ctrl">${seg('t-est', EST.map(e => [e, e]), 'Racarumi', true)}</div>
          <span class="sub">Lo que habría visto un operador en cada temporada de lluvias de la prueba con el sistema de avisos base (solo caudal). Triángulos: avisos emitidos (verde: acierto; gris: falsa alarma). Círculos sobre el P95: crecidas nuevas (relleno: avisada a tiempo; vacío: omitida).</span></header>
          <div class="cuerpo"><div class="ctrl" style="margin-bottom:6px"><div class="seg" id="t-anio"></div></div><div id="t-graf" class="fig"></div><div class="cifras" id="t-cif"></div></div></div>
      </div>
      <div class="rejilla mt">
        <div class="glass panel"><header><h2>Detección según la anticipación real exigida</h2>
          <div class="ctrl">${seg('a-est', EST.map(e => [e, e]), 'Racarumi', true)}<label>Modelo <select id="a-mod"></select></label>${seg('a-reg', [['calibrada', 'regla calibrada'], ['fija (u = P95, h_max = 30)', 'regla fija']], 'calibrada', true)}</div>
          <span class="sub">POD(A): cruces avisados con al menos A días reales de anticipación, entre los cruces con emisiones elegibles los A días previos. CSI(A) incluye las falsas alarmas del sistema (no dependen de A). Discontinuas: tendencia de 3 días.</span></header>
          <div class="cuerpo"><div class="g-2"><div id="a-curva" class="fig"></div><div id="a-n" class="fig"></div></div><div class="cifras" id="a-cif"></div>
            ${lectura([['Prueba', ul(TX.p2_prueba)]])}</div></div>
        <div class="glass panel"><header><h2>Candidatos y catálogo de cruces</h2>${seg('a-est3', EST.map(e => [e, e]), 'Racarumi', true)}${seg('a-tab', [['cand', 'todos los candidatos'], ['ev', 'catálogo de cruces']], 'cand', true)}
          <span class="sub">Candidatos: regla calibrada en validación (f × P95 y h_max), conteos de eventos y episodios; días de aviso por año como carga del sistema. Catálogo: error de fecha = primer día con pronóstico sobre el P95 − día del cruce (positivo = tarde).</span></header>
          <div class="cuerpo"><div class="tw" id="a-todos"></div>${lectura([['Eventos de la prueba', ul(TX.p2_eventos_prueba)]])}</div></div>
        <div class="g-2">
          <div class="glass panel"><header><h2>Cruces disponibles y calibración</h2></header><div class="cuerpo"><div class="tw" id="a-cruces"></div>${lectura([['Eventos', ul(TX.p2_eventos)], ['Calibración', ul(TX.p2_calibracion)]])}</div></div>
          <div class="glass panel"><header><h2>Sensibilidad y fechas comunes</h2></header><div class="cuerpo"><div class="tw" id="a-sens"></div><div class="tw mt" id="a-comun"></div>${lectura([['Sensibilidad', ul(TX.p2_sensibilidad)], ['Fechas comunes', ul(TX.p2_comun)], ['Límites', ul(TX.p2_limites)]])}</div></div>
        </div>
        ${conclusiones(TX.p2_conclusiones)}
      </div></section>`;
    tabla('#a-cruces', A.cruces, [['estación', 'Estación'], ['bloque', 'Bloque'], ['cruces identificados', 'Identificados', v => fmt(v, 0)], ['nuevos cruces elegibles', 'Elegibles', v => fmt(v, 0)],
      ['evaluables (emisión elegible el día previo)', 'Evaluables', v => fmt(v, 0)], ['evaluables con ≥ 7 días de emisiones elegibles', 'Evaluables a 7 d', v => fmt(v, 0)]]);
    tabla('#a-sens', A.sensibilidad, [['estación', 'Estación'], ['variante', 'Variante'], ['evaluables', 'Cruces', v => fmt(v, 0)], ['aciertos', 'Aciertos', v => fmt(v, 0)], ['falsas_alarmas', 'FA', v => fmt(v, 0)],
      ['POD', 'POD'], ['FAR', 'FAR'], ['CSI', 'CSI'], ['anticipacion_util', 'Antic. útil', v => fmt(v, 0)]]);
    tabla('#a-comun', A.comun, [['estación', 'Estación'], ['modelo', 'Modelo'], ['emisiones', 'Emisiones', v => fmt(v, 0)], ['evaluables', 'Cruces', v => fmt(v, 0)], ['aciertos', 'Aciertos', v => fmt(v, 0)],
      ['falsas_alarmas', 'FA', v => fmt(v, 0)], ['POD', 'POD'], ['FAR', 'FAR'], ['CSI', 'CSI'], ['anticipacion_util', 'Antic. útil', v => fmt(v, 0)]]);
    let est = 'Racarumi', regla = 'calibrada';
    const fila = (e, n, rg) => A.resumen.find(r => r['estación'] === e && r.modelo === n && r.regla === rg) || {};
    const opciones = () => { const mods = Object.keys(A.por_A[est]); const mj = avisa(est);
      $('#a-mod').innerHTML = mods.map(n => `<option ${n === mj ? 'selected' : ''}>${esc(n)}</option>`).join(''); };
    const dibuja = () => {
      const n = $('#a-mod').value, r = A.por_A[est][n][regla], tref = A.por_A[est]['Tendencia 3 días'][regla], K = r.POD.map((_, i) => i + 1), f = fila(est, n, regla);
      plot('#a-curva', [
        { x: K, y: r.POD, name: 'POD(A)', line: { color: css('--good'), width: 2.6 }, hovertemplate: '%{y:.2f}' },
        { x: K, y: r.CSI, name: 'CSI(A)', line: { color: colM(n), width: 2.6 }, hovertemplate: '%{y:.2f}' },
        { x: K, y: tref.POD, name: 'POD tendencia 3 d', line: { color: css('--good'), width: 1.2, dash: 'dash' }, hovertemplate: '%{y:.2f}' },
        { x: K, y: tref.CSI, name: 'CSI tendencia 3 d', line: { color: colM('Tendencia 3 días'), width: 1.2, dash: 'dash' }, hovertemplate: '%{y:.2f}' }],
      base({ title: { text: `${est} · ${n} · regla ${regla === 'calibrada' ? 'calibrada' : 'fija'}`, font: { size: 13 }, x: 0.01 }, xaxis: { title: { text: 'Anticipación real exigida A (días)' }, dtick: 5 }, yaxis: { range: [-0.02, 1.02] }, margin: { l: 44, r: 10, t: 40, b: 44 },
        shapes: [{ type: 'line', x0: 0.5, x1: 30.5, y0: 0.5, y1: 0.5, line: { color: css('--ink-3'), dash: 'dashdot', width: 1 } }] }), 370);
      plot('#a-n', [
        { type: 'bar', x: K, y: r.aciertos, name: 'Avisados con ≥ A días', marker: { color: css('--good') } },
        { type: 'bar', x: K, y: r.evaluables.map((v, i) => v - r.aciertos[i]), name: 'No avisados', marker: { color: css('--warn') } }],
      base({ title: { text: `Cruces evaluables a cada A · falsas alarmas: ${fmt(f.falsas_alarmas, 0)}`, font: { size: 13 }, x: 0.01 }, barmode: 'stack', xaxis: { title: { text: 'Anticipación real exigida A (días)' }, dtick: 5 }, yaxis: { title: { text: 'Cruces' } }, margin: { l: 50, r: 10, t: 40, b: 44 } }), 370);
      $('#a-cif').innerHTML = `<span>u = <b>${fmt(f.f, 2)} × P95</b>, h_max <b>${fmt(f.hmax, 0)} d</b></span><span>aciertos <b>${fmt(f.aciertos, 0)}</b> de ${fmt(f.evaluables, 0)}</span><span>falsas alarmas <b>${fmt(f.falsas_alarmas, 0)}</b></span><span>POD <b>${fmt(f.POD, 2)}</b> · FAR <b>${fmt(f.FAR, 2)}</b> · CSI <b>${fmt(f.CSI, 2)}</b></span><span>anticipación mediana <b>${fmt(f.anticipacion_mediana, 0)} d</b></span><span>días con aviso por año <b>${fmt(f.dias_aviso_anio, 0)}</b></span>`;
    };
    onSeg(app, 'a-est', v => { est = v; opciones(); dibuja(); });
    onSeg(app, 'a-reg', v => { regla = v; dibuja(); });
    $('#a-mod').addEventListener('change', dibuja);
    opciones(); dibuja();
    let e3 = 'Racarumi', vt = 'cand';
    const abajo = () => {
      if (vt === 'cand') tabla('#a-todos', A.resumen.filter(r => r['estación'] === e3 && r.regla === 'calibrada'), [['modelo', 'Modelo', (v, r) => dotM(v) + (r['modelo para avisos'] ? ' <span class="chip ok">avisos</span>' : ''), 'izq'],
        ['f', 'f'], ['hmax', 'h_max', v => fmt(v, 0)], ['evaluables', 'Cruces', v => fmt(v, 0)], ['aciertos', 'Aciertos', v => fmt(v, 0)], ['omisiones', 'Omisiones', v => fmt(v, 0)],
        ['falsas_alarmas', 'FA', v => fmt(v, 0)], ['POD', 'POD'], ['FAR', 'FAR'], ['CSI', 'CSI'], ['anticipacion_util', 'Antic. útil', v => fmt(v, 0)],
        ['anticipacion_mediana', 'Antic. mediana', v => fmt(v, 0)], ['dias_aviso_anio', 'Días aviso/año', v => fmt(v, 0)], ['falsas_alarmas_anio', 'FA/año', v => fmt(v, 1)], ['cobertura', 'Cobertura', v => fmt(100 * v, 0) + ' %']],
      { marca: r => r['modelo para avisos'] });
      else tabla('#a-todos', A.por_evento.filter(r => r['estación'] === e3), [['fecha', 'Cruce', v => esc(String(v).slice(0, 10))], ['elegible', 'Elegible', v => v ? 'sí' : 'no'],
        ['motivo', 'Motivo'], ['evaluable', 'Evaluable', v => v ? 'sí' : 'no'], ['detectado', 'Detectado', v => v ? '<span class="chip ok">sí</span>' : 'no'], ['anticipacion_real', 'Anticipación real (d)', v => fmt(v, 0)],
        ['error_fecha_umbral', 'Error fecha (d)', v => fmt(v, 0)], ['error_fecha_A1', 'Error 1 d antes', v => fmt(v, 0)], ['error_fecha_A3', 'Error 3 d antes', v => fmt(v, 0)],
        ['error_fecha_A7', 'Error 7 d antes', v => fmt(v, 0)], ['pico 15 d (m³/s)', 'Pico 15 d', v => fmt(v, e3 === 'Tamshiyacu' ? 0 : 1)]]);
    };
    onSeg(app, 'a-est3', v => { e3 = v; abajo(); }); onSeg(app, 'a-tab', v => { vt = v; abajo(); }); abajo();
    // ── Diagrama de desempeño: pronóstico diario sobre el P95 (trayectoria por h) y sistemas de aviso por evento
    let dEst = 'Racarumi';
    const opcD = () => { const S = D.estaciones[dEst]; $('#d-mod').innerHTML = S.modelos.filter(n => S.crec[n]).map(n => `<option ${n === S.mejor ? 'selected' : ''}>${esc(n)}</option>`).join(''); };
    const desempeno = () => {
      const S = D.estaciones[dEst], n = $('#d-mod').value, c = S.crec[n], N = 60, tr = [];
      const xs = Array.from({ length: N }, (_, i) => 0.01 + i * 0.99 / (N - 1));
      const z = xs.map(p => xs.map(s => 1 / (1 / s + 1 / p - 1)));
      const gris = oscuro() ? [[0, 'rgba(255,255,255,0)'], [1, 'rgba(160,205,225,0.30)']] : [[0, 'rgba(15,32,40,0)'], [1, 'rgba(15,32,40,0.22)']];
      tr.push({ type: 'contour', x: xs, y: xs, z, colorscale: gris, showscale: false, hoverinfo: 'skip', contours: { start: 0.1, end: 0.9, size: 0.1, coloring: 'fill', showlabels: true, labelfont: { size: 9, color: css('--ink-3') } }, line: { color: css('--ink-4'), width: 0.8 } });
      const ann = [];
      for (const b of [0.5, 1, 2, 4]) { const x1 = Math.min(1, 1 / b);
        tr.push({ x: [0, x1], y: [0, b * x1], mode: 'lines', line: { color: css('--ink-3'), width: 0.9, dash: 'dot' }, hoverinfo: 'skip', showlegend: false });
        ann.push(b >= 1 ? { x: 1 / b, y: 1.035, text: `sesgo ${fmt(b, 0)}`, showarrow: false, font: { size: 9, color: css('--ink-3') } } : { x: 1.03, y: b, xanchor: 'left', text: 'sesgo 0.5', showarrow: false, font: { size: 9, color: css('--ink-3') } }); }
      const ok = HH.map((h, i) => c.FAR[i] != null && c.POD[i] != null);
      const hx = HH.filter((_, i) => ok[i]);
      tr.push({ x: hx.map(h => 1 - c.FAR[h - 1]), y: hx.map(h => c.POD[h - 1]), mode: 'lines+markers', name: `${n}, pronóstico diario`, line: { color: css('--ink-3'), width: 1 },
        marker: { size: 8, color: hx, colorscale: [[0, '#f0f921'], [0.25, '#f89540'], [0.5, '#cc4778'], [0.75, '#7e03a8'], [1, '#0d0887']], cmin: 1, cmax: 30, line: { width: 0.6, color: css('--solid') }, colorbar: { title: { text: 'h (d)', font: { size: 11, color: css('--ink-2') } }, thickness: 10, len: 0.8, tickfont: { size: 10, color: css('--ink-2') }, x: 1.02 } },
        customdata: hx.map(h => [h, c.CSI[h - 1]]), hovertemplate: 'h = %{customdata[0]} d<br>POD %{y:.2f} · 1 − FAR %{x:.2f}<br>CSI %{customdata[1]:.2f}<extra></extra>' });
      [1, 3, 7, 15, 30].filter(h => ok[h - 1]).forEach(h => ann.push({ x: 1 - c.FAR[h - 1], y: c.POD[h - 1], text: `h=${h}`, showarrow: false, xshift: 18, yshift: 8, font: { size: 9.5, color: css('--ink-2') } }));
      const est = dEst === 'Racarumi' ? I.sintesis.avisos.map(r => ({ t: `${r['configuración']} (${r.cuaderno === 4 ? 'base' : /avisos \(mismo/.test(r.papel) ? 'final, mismo día' : /avisos \(un d/.test(r.papel) ? 'final, retraso' : 'candidato'})`, x: 1 - r['FAR (global)'], y: r.POD, csi: r.CSI, m: r['configuración'].split(' · ')[1], d: `${r.aciertos}/${r['N_1 (cruces evaluables)']} cruces, ${r['falsas alarmas']} falsas alarmas` }))
        : [{ t: `Q · ${sintesisA('Tamshiyacu')['modelo (avisos)']} (base)`, x: 1 - sintesisA('Tamshiyacu').FAR, y: sintesisA('Tamshiyacu').POD, csi: sintesisA('Tamshiyacu').CSI, m: sintesisA('Tamshiyacu')['modelo (avisos)'], d: `${sintesisA('Tamshiyacu').aciertos}/${sintesisA('Tamshiyacu')['cruces evaluables']} cruces · exploratorio` }];
      est.forEach(s => tr.push({ x: [s.x], y: [s.y], mode: 'markers', name: `${s.t} · CSI ${fmt(s.csi, 2)}`, marker: { symbol: 'star', size: 19, color: colM(s.m), line: { width: 1.2, color: oscuro() ? '#ffffff' : '#0f2028' } },
        hovertemplate: `<b>${esc(s.t)}</b><br>POD %{y:.2f} · 1 − FAR %{x:.2f}<br>CSI ${fmt(s.csi, 2)} · ${esc(s.d)}<extra>aviso por evento</extra>` }));
      plot('#d-graf', tr, base({ hovermode: 'closest', xaxis: { title: { text: 'Tasa de éxito (1 − FAR)' }, range: [0, 1.08], dtick: 0.2, zeroline: false }, yaxis: { title: { text: 'Detección (POD)' }, range: [0, 1.08], dtick: 0.2, zeroline: false, scaleanchor: 'x' },
        annotations: ann, legend: { orientation: 'h', y: -0.16, font: { size: 10.5 } }, margin: { l: 56, r: 30, t: 20, b: 50 } }), 560);
    };
    onSeg(app, 'd-est', v => { dEst = v; opcD(); desempeno(); }); $('#d-mod').addEventListener('change', desempeno); opcD(); desempeno();

    // ── Avisos temporada por temporada
    let tEst = 'Racarumi', tAnio = 2017;
    const anios = e => e === 'Racarumi' ? [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023] : [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
    const ventana = (e, y) => { const a = y === 2016 ? '2016-01-01' : e === 'Racarumi' ? `${y - 1}-12-15` : `${y - 1}-11-01`; const b = e === 'Racarumi' ? `${y}-05-31` : `${y}-07-31`; return [a, b]; };
    const segAnios = () => { $('#t-anio').outerHTML = seg('t-anio', anios(tEst).map(y => [y, y]), tAnio); onSeg(app, 't-anio', v => { tAnio = +v; temporada(); }); };
    const temporada = () => {
      const S = D.estaciones[tEst], [a, b] = ventana(tEst, tAnio), t0 = fecha0(S.serie.t0), dec = tEst === 'Tamshiyacu' ? 0 : 1, U = 'm³/s';
      const x = [], y = [];
      S.serie.q.forEach((v, i) => { const d = iso(t0 + i * DIA); if (d >= a && d <= b) { x.push(d); y.push(v); } });
      const qObs = d => { const k = Math.round((fecha0(d) - t0) / DIA); return S.serie.q[k]; };
      const vals = y.filter(v => v != null), top = Math.max(S.P95, ...vals) * 1.1, bajo = tEst === 'Tamshiyacu' ? Math.min(...vals) * 0.92 : 0;
      const av = I.avisos.filter(r => r.est === tEst && r.e >= a && r.e <= b);
      const cr = A.por_evento.filter(r => r['estación'] === tEst && r.elegible && String(r.fecha).slice(0, 10) >= a && String(r.fecha).slice(0, 10) <= b);
      const col = colE(tEst), tr = [
        { x, y, name: 'Caudal observado', mode: 'lines', line: { color: col, width: 1.8 }, fill: tEst === 'Racarumi' ? 'tozeroy' : 'none', fillcolor: col + '26', hovertemplate: '%{x|%d %b %Y}: %{y:,.' + dec + 'f} ' + U + '<extra></extra>' }];
      for (const [okv, nom, c] of [[true, 'Aviso correcto (emisión)', css('--good')], [false, 'Falsa alarma (emisión)', css('--ink-3')]]) {
        const u = av.filter(r => r.ok === okv);
        tr.push({ x: u.map(r => r.e), y: u.map(() => top * 0.985), mode: 'markers', name: nom, marker: { symbol: 'triangle-down', size: 12, color: c, line: { width: 1, color: css('--solid') } },
          customdata: u.map(r => [r.t, r.h]), hovertemplate: `${nom}<br>emitido %{x|%d %b}; anuncia el cruce para %{customdata[0]} (h = %{customdata[1]} d)<extra></extra>` });
      }
      for (const [det, nom] of [[true, 'Crecida avisada a tiempo'], [false, 'Crecida omitida']]) {
        const u = cr.filter(r => !!r.detectado === det);
        tr.push({ x: u.map(r => String(r.fecha).slice(0, 10)), y: u.map(() => S.P95), mode: 'markers', name: nom, marker: { size: 12, color: det ? css('--bad') : 'rgba(0,0,0,0)', line: { width: 2.2, color: css('--bad') } },
          customdata: u.map(r => [r.anticipacion_real, fmt(r['pico 15 d (m³/s)'], dec)]), hovertemplate: `${nom}<br>cruce del P95 el %{x|%d %b %Y}<br>${det ? 'anticipación real %{customdata[0]} d · ' : ''}pico en 15 d: %{customdata[1]} ${U}<extra></extra>` });
      }
      plot('#t-graf', tr, base({ hovermode: 'closest', xaxis: { type: 'date', range: [a, b], tickformat: '%b' }, yaxis: { title: { text: 'Caudal (' + U + ')' }, range: [bajo, top * 1.02], tickformat: ',.0f' },
        legend: { orientation: 'h', y: -0.14, font: { size: 10.5 } }, margin: { l: 62, r: 14, t: 16, b: 40 },
        shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: S.P95, y1: S.P95, line: { color: css('--ink-2'), dash: 'dash', width: 1.2 } }],
        annotations: [{ xref: 'paper', x: 0.005, y: S.P95, yanchor: 'bottom', xanchor: 'left', text: `P95 = ${fmt(S.P95, dec)} ${U}`, showarrow: false, font: { size: 10, color: css('--ink-2') } }] }), 470);
      const ok = av.filter(r => r.ok).length, det = cr.filter(r => r.detectado).length;
      $('#t-cif').innerHTML = `<span>${tEst} · temporada <b>${tAnio}</b> (${a} a ${b})</span><span>crecidas (nuevos cruces) <b>${cr.length}</b> · avisadas a tiempo <b>${det}</b></span><span>avisos emitidos <b>${av.length}</b>: correctos <b>${ok}</b> · falsas alarmas <b>${av.length - ok}</b></span><span>modelo de avisos: <b>${esc(sintesisA(tEst)['modelo (avisos)'])}</b> (sistema base, solo caudal)</span>`;
    };
    const conEventos = e => { let mj = anios(e)[0], k = -1; anios(e).forEach(y => { const [a, b] = ventana(e, y); const n = A.por_evento.filter(r => r['estación'] === e && r.elegible && String(r.fecha).slice(0, 10) >= a && String(r.fecha).slice(0, 10) <= b).length + I.avisos.filter(r => r.est === e && r.e >= a && r.e <= b).length / 100; if (n > k) { k = n; mj = y; } }); return mj; };
    onSeg(app, 't-est', v => { tEst = v; tAnio = v === 'Racarumi' ? 2017 : conEventos(v); segAnios(); temporada(); }); segAnios(); temporada();

  }

  // ────────────────────────────────────────────────────────── P3 · AGUAS ARRIBA (05)
  function vArriba() {
    const X = I.arriba, ef = X.efecto, T = X.textos, app = $('#app');
    const ents = [...new Set(ef.map(r => r.ent))];
    const tr = (est, pref) => X.transito.find(r => r['estación'] === est && r.preblanqueo.startsWith(pref)) || {};
    const sr = tr('San Regis', 'AR de 1998'), rq = tr('Requena', 'AR de 1998');
    const fsr = X.fisica.find(r => r.tramo.startsWith('San Regis')) || {};
    const g = (ent, b) => ef.filter(r => r.ent === ent && r.b === b).map(r => 100 * r.G);
    const red = (ent, b) => ef.filter(r => r.ent === ent && r.b === b && r.l > 0).length;
    app.innerHTML = `<section class="vista" style="--c:var(--c3)">
      ${hero('P3 · Tamshiyacu con San Regis (Marañón) y Requena (Ucayali) · Racarumi con Cirato', '¿Mejora el pronóstico si se agrega el caudal de las estaciones aguas arriba?',
        'Los seis modelos, con y sin cada estación. G compara cada modelo consigo mismo en las mismas fechas de prueba.',
        `<b>San Regis sí</b>: ${rango(g('SR', '1–3 días'))} % menos error a 1–3 días con los seis modelos (${rango(g('SR', '4–7 días'))} % a 4–7). <b>Requena no</b> reduce el error. El horizonte útil casi no cambia.`, '--c3')}
      <div class="kpis">
        ${kpi('Desfase San Regis', fmt(sr['desfase del máximo (d)'], 0) + ' día', `r preblanqueada ${fmt(sr['r máximo'], 2)} (k = 1)`, css('--c3'))}
        ${kpi('Celeridad implícita', esc(fsr['celeridad si tarda 1 día (m/s)'] || '—') + ' m/s', `${fmt(fsr['distancia en línea recta (km)'], 0)} km en línea recta · plausible`)}
        ${kpi('San Regis, 1–3 d', `${red('SR', '1–3 días')}/6`, 'modelos con menos error (IC > 0)', css('--good'))}
        ${kpi('Con 1 día de retraso', rango(g('SR con latencia 1 d', '1–3 días')) + ' %', 'menos error a 1–3 d')}
        ${kpi('Desfase Requena', fmt(rq['desfase del máximo (d)'], 0) + ' día', 'no positivo: no anticipa', css('--bad'))}
      </div>
      <div class="g-2-1 mt">
        <div class="glass panel"><header><h2>Ganancia por modelo y horizonte</h2><div class="ctrl"><label>Entrada <select id="u-ent">${ents.map(e => `<option ${e === 'SR' ? 'selected' : ''}>${esc(e)}</option>`).join('')}</select></label></div>
          <span class="sub">G = 1 − MSE(con)/MSE(sin) con el mismo modelo, en las mismas emisiones de prueba. ▲: reduce el error (IC 90 % > 0); ▼: lo aumenta (IC < 0); sin marca: sin diferencia demostrada. Pase el cursor para ver el IC.</span></header>
          <div class="cuerpo"><div id="u-calor" class="fig"></div><p class="nota" id="u-per"></p></div></div>
        <div class="glass panel"><header><h2>¿Cuándo llega la señal?</h2><span class="sub">Correlación cruzada preblanqueada (AR de 1998–2008) entre las variaciones diarias de cada estación en t − k y las de Tamshiyacu en t. Un pico en k = 1 significa que la estación anticipa un día.</span></header>
          <div class="cuerpo"><div id="u-ccf" class="fig"></div><div class="tw" id="u-fis"></div></div></div>
      </div>
      <div class="glass panel mt"><header><h2>Configuración seleccionada en validación (magnitud)</h2><span class="sub">Regla: mayor NSE medio en 2012–2015 y, entre el mayor y sus equivalentes (IC dentro de ±0.01), la más simple. La selección final con lluvia y Chronos-2 está en P6.</span></header>
        <div class="cuerpo"><div class="tw" id="u-sel"></div>
        ${lectura([['Prueba', ul(TX.p3_prueba)], ['Desfase', ul(TX.p3_desfase)], ['Validación', ul(TX.p3_validacion)], ['Crecidas', ul(TX.p3_crecidas)], ['Avisos', ul(TX.p3_cruces)], ['Cirato', ul(TX.p3_cirato)]])}</div></div>
      ${conclusiones(TX.p3_conclusiones)}
    </section>`;
    const calor = ent => { const f = ef.filter(r => r.ent === ent); calorG('#u-calor', f, D.MODELOS); $('#u-per').textContent = `Prueba ${f[0] ? f[0].per : ''} · ${f[0] ? 'Tamshiyacu' : ''}.`; };
    $('#u-ent').addEventListener('change', ev => calor(ev.target.value)); calor('SR');
    const ks = [['r a k = −1', '−1'], ['r a k = 0', '0'], ['r a k = 1', '1'], ['r a k = 2', '2']];
    plot('#u-ccf', [['San Regis', sr, css('--c3')], ['Requena', rq, css('--ink-3')]].map(([n, r, c]) => ({ type: 'bar', name: n, x: ks.map(k => 'k = ' + k[1]), y: ks.map(k => r[k[0]]), marker: { color: c },
      text: ks.map(k => fmt(r[k[0]], 2)), textposition: 'outside', cliponaxis: false, textfont: { family: css('--f-mono'), size: 10 }, hovertemplate: n + ' %{x}: r = %{y:.3f}<extra></extra>' })),
    base({ barmode: 'group', hovermode: 'closest', yaxis: { title: { text: 'r preblanqueada' } }, xaxis: { title: { text: 'Desfase (días que la estación va adelante)' } }, legend: { orientation: 'h', y: -0.28 }, margin: { l: 50, r: 10, t: 20, b: 50 } }), 290);
    tabla('#u-fis', X.fisica, [['tramo', 'Tramo'], ['distancia en línea recta (km)', 'Línea recta (km)', v => fmt(v, 0)], ['cauce supuesto (km, sinuosidad 1.3–2.0)', 'Cauce (km)'], ['celeridad si tarda 1 día (m/s)', 'Celeridad 1 d (m/s)'], ['tiempo con celeridad 1–3 m/s (h)', 'Tránsito 1–3 m/s (h)']]);
    tabla('#u-sel', X.seleccion, [['periodo de prueba', 'Periodo'], ['escenario', 'Escenario'], ['seleccionada (la más simple entre el mayor y sus equivalentes)', 'Seleccionada', v => `<b>${esc(v)}</b>`, 'izq'],
      ['NSE medio de la seleccionada', 'NSE medio'], ['mayor NSE medio', 'Mayor', null, 'izq'], ['NSE medio del mayor', 'NSE del mayor'], ['equivalentes al mayor (IC dentro de ±0.01)', 'Equivalentes', v => fmt(v, 0)], ['inconclusas (IC demasiado ancho; no es equivalencia)', 'Inconclusas', v => fmt(v, 0)], ['candidatos', 'Candidatos', v => fmt(v, 0)]]);
  }

  // ────────────────────────────────────────────────────────── P4 · LLUVIA (06)
  function vLluvia() {
    const X = I.lluvia, ef = X.efecto, T = X.textos, app = $('#app');
    const bal = e => X.balance.find(r => r['estación'] === e) || {};
    const ccf = e => X.ccf.find(r => r['estación'] === e && r.preblanqueo === 'AR de entrenamiento') || {};
    const g = (e, ent, b) => ef.filter(r => r.est === e && r.ent === ent && r.b === b).map(r => 100 * r.G);
    const idR = X.idealizado.filter(r => r['estación'] === 'Racarumi' && r.modelo === 'XGBoost' && /futura/.test(r['comparación']) && /Solo caudal/.test(r['comparación'])).map(r => 100 * r.G);
    app.innerHTML = `<section class="vista" style="--c:var(--c4)">
      ${hero('P4 · Lluvia media de la cuenca (PISCOp v2.1) e índices antecedentes', '¿Cuánto aporta la lluvia al pronóstico del caudal?',
        'Seis modelos con Q, Q+P, Q+P+IA, sus versiones con un día de retraso y un control. La lluvia futura perfecta es un escenario idealizado aparte que no compite.',
        `En <b>Racarumi</b> la lluvia del mismo día reduce el error ${rango(g('Racarumi', 'P', '1–3 días'))} % a 1–3 días, pero con un día de retraso casi nada. En <b>Tamshiyacu</b> la señal tarda ~${fmt(ccf('Tamshiyacu')['desfase del máximo (d)'], 0)} días y la lluvia ayuda sobre todo de la segunda a la cuarta semana (salvo con KNN).`, '--c4')}
      <div class="kpis">
        ${kpi('Desfase Racarumi', fmt(ccf('Racarumi')['desfase del máximo (d)'], 0) + ' día', `r preblanqueada ${fmt(ccf('Racarumi')['r máximo'], 2)}`, css('--rac'))}
        ${kpi('Desfase Tamshiyacu', fmt(ccf('Tamshiyacu')['desfase del máximo (d)'], 0) + ' días', `r preblanqueada ${fmt(ccf('Tamshiyacu')['r máximo'], 2)}`, css('--tam'))}
        ${kpi('Escorrentía Q/P', `${fmt(bal('Racarumi')['Q/P medio'], 2)} · ${fmt(bal('Tamshiyacu')['Q/P medio'], 2)}`, 'Racarumi · Tamshiyacu (coherente con CAMELS-PE)')}
        ${kpi('Lluvia hasta t−1', rango(g('Racarumi', 'P con latencia 1 d', '1–3 días')) + ' %', 'Racarumi, menos error a 1–3 d')}
        ${kpi('Lluvia futura perfecta', rango(idR) + ' %', 'Racarumi, XGBoost · idealizado', css('--good'))}
      </div>
      <div class="g-2-1 mt">
        <div class="glass panel"><header><h2>Ganancia por modelo y horizonte</h2><div class="ctrl">${seg('l-est', EST.map(e => [e, e]), 'Racarumi', true)}<label>Entrada <select id="l-ent"></select></label></div>
          <span class="sub">G = 1 − MSE(con)/MSE(sin) con el mismo modelo, en las mismas emisiones de prueba. ▲ reduce el error (IC 90 % > 0); ▼ lo aumenta. «P»: lluvia observada hasta t (disponibilidad supuesta); «con latencia 1 d»: hasta t − 1.</span></header>
          <div class="cuerpo"><div id="l-calor" class="fig"></div></div></div>
        <div class="glass panel"><header><h2>¿Cuándo responde el río a la lluvia?</h2><span class="sub">Correlación cruzada preblanqueada entre la lluvia de la cuenca en t − k y la variación diaria del caudal en t (AR del entrenamiento).</span></header>
          <div class="cuerpo"><div id="l-ccf" class="fig"></div></div></div>
      </div>
      <div class="glass panel mt"><header><h2>Lo que daría conocer la lluvia futura (escenario idealizado)</h2><div class="ctrl">${seg('l-est2', EST.map(e => [e, e]), 'Racarumi', true)}${seg('l-mod', [['XGBoost', 'XGBoost'], ['Regresión lineal', 'Regresión lineal']], 'XGBoost', true)}</div>
        <span class="sub">G frente a solo caudal con la lluvia observada hasta t y con la lluvia futura observada (como si el pronóstico de lluvia fuera perfecto). Bigotes: IC 90 %. Es una cota optimista: no compite en la selección.</span></header>
        <div class="cuerpo"><div id="l-ideal" class="fig"></div>
        ${lectura([['Prueba', ul(TX.p4_prueba)], ['Balance y respuesta', ul(TX.p4_balance)], ['Crecidas', ul(TX.p4_crecidas)], ['Avisos', ul(TX.p4_avisos)], ['Lluvia futura', ul(TX.p4_idealizado)]])}</div></div>
      ${conclusiones(TX.p4_conclusiones)}
    </section>`;
    let est = 'Racarumi';
    const opciones = () => { const ents = [...new Set(ef.filter(r => r.est === est).map(r => r.ent))]; $('#l-ent').innerHTML = ents.map(e => `<option ${e === 'P' ? 'selected' : ''}>${esc(e)}</option>`).join(''); };
    const calor = () => calorG('#l-calor', ef.filter(r => r.est === est && r.ent === $('#l-ent').value), D.MODELOS);
    onSeg(app, 'l-est', v => { est = v; opciones(); calor(); }); $('#l-ent').addEventListener('change', calor); opciones(); calor();
    const ks = ['r a k = -1', 'r a k = 0', 'r a k = 1', 'r a k = 2', 'r a k = 3', 'r a k = 7'];
    plot('#l-ccf', EST.map(e => { const r = ccf(e); return { x: ks.map(k => +k.split('= ')[1]), y: ks.map(k => r[k]), name: e, mode: 'lines+markers', line: { color: colE(e), width: 2.4 }, marker: { size: 8 }, hovertemplate: e + ' k = %{x}: r = %{y:.3f}<extra></extra>' }; }),
      base({ hovermode: 'closest', xaxis: { title: { text: 'Desfase k (días)' }, tickvals: [-1, 0, 1, 2, 3, 7] }, yaxis: { title: { text: 'r preblanqueada' } }, legend: { orientation: 'h', y: -0.25 }, margin: { l: 50, r: 10, t: 16, b: 50 } }), 330);
    let e2 = 'Racarumi', m2 = 'XGBoost';
    const ideal = () => {
      const rs = X.idealizado.filter(r => r['estación'] === e2 && r.modelo === m2);
      const comps = [...new Set(rs.map(r => r['comparación']))];
      const corto = c => { const t = c.replace(/ \(disponibilidad supuesta\)| \(escenario idealizado\)/g, '');
        return /futura.*frente a \+ lluvia/.test(t) ? 'lluvia futura frente a lluvia hasta t' : /futura/.test(t) ? 'lluvia futura frente a solo caudal' : 'lluvia hasta t frente a solo caudal'; };
      const cols = [css('--c4'), css('--good'), css('--ink-3')];
      plot('#l-ideal', comps.map((c, i) => { const f = BANDAS.map(b => rs.find(r => r['comparación'] === c && r.banda === b) || {});
        return { type: 'bar', name: corto(c), x: BANDAS, y: f.map(r => 100 * r.G), marker: { color: cols[i % 3] },
          error_y: { type: 'data', symmetric: false, array: f.map(r => 100 * (r['IC90 superior'] - r.G)), arrayminus: f.map(r => 100 * (r.G - r['IC90 inferior'])), color: css('--ink-2'), thickness: 1.2, width: 3 },
          text: f.map(r => (r.G > 0 ? '+' : '') + fmt(100 * r.G, 0) + ' %'), textposition: f.map(r => Math.abs(r.G) > 0.12 ? 'inside' : 'outside'), insidetextanchor: 'middle', cliponaxis: false, textfont: { family: css('--f-mono'), size: 10.5, color: css('--ink') }, hovertemplate: '%{x}: G = %{y:.1f} %<extra>' + esc(corto(c)) + '</extra>' }; }),
      base({ barmode: 'group', hovermode: 'closest', yaxis: { title: { text: 'G (% menos error)' }, zeroline: true }, legend: { orientation: 'h', y: -0.2 }, margin: { l: 56, r: 10, t: 24, b: 50 } }), 360);
    };
    onSeg(app, 'l-est2', v => { e2 = v; ideal(); }); onSeg(app, 'l-mod', v => { m2 = v; ideal(); }); ideal();
  }

  // ────────────────────────────────────────────────────────── P5 · CHRONOS-2 (07)
  function vChronos() {
    const X = I.chronos, T = X.textos, app = $('#app');
    const ctx = e => X.contexto.find(r => r['estación'] === e && r.seleccionado) || {};
    const cond = (e, b) => X.condiciones.find(r => r['estación'] === e && r['información'] === 'solo caudal' && r.banda === b) || {};
    const prob1 = e => X.probabilistico.find(r => r['estación'] === e && r.variante === 'Solo caudal' && r.h === 1) || {};
    const frT = X.frente.filter(r => r['estación'] === 'Tamshiyacu');
    app.innerHTML = `<section class="vista" style="--c:var(--c5)">
      ${hero('P5 · Chronos-2 (120 M de parámetros) · pesos publicados, sin ajuste local', '¿Sirve un modelo fundacional sin entrenar con estos ríos?',
        'Solo se eligen en validación el contexto (512, 1 024 o 2 048 días) y el pronóstico puntual. Además de un valor, Chronos-2 entrega una distribución: aquí se evalúa también su banda P10–P90.',
        `Bandas bien calibradas en conjunto (~${pct(cond('Racarumi', '1–3 días')['cobertura (todos)'])} en Racarumi para un 80 % nominal), pero <b>los caudales altos quedan fuera</b> (${pct(cond('Racarumi', '1–3 días')['cobertura (pares con Q > P95)'])}). Como pronóstico puntual queda por debajo de los mejores modelos entrenados en la prueba.`, '--c5')}
      <div class="kpis">
        ${kpi('Contexto Racarumi', esc((ctx('Racarumi').candidato || '—').split(' · ')[0]), `${esc((ctx('Racarumi').candidato || '').split(' · ')[1] || '')} · NSE validación ${fmt(ctx('Racarumi')['NSE medio selección'], 3)}`, css('--rac'))}
        ${kpi('Contexto Tamshiyacu', esc((ctx('Tamshiyacu').candidato || '—').split(' · ')[0]), `${esc((ctx('Tamshiyacu').candidato || '').split(' · ')[1] || '')} · los escalones impidieron distinguir`, css('--tam'))}
        ${kpi('Cobertura P10–P90', pct(cond('Racarumi', '1–3 días')['cobertura (todos)']), 'Racarumi, 1–3 d · nominal 80 %')}
        ${kpi('En días > P95', pct(cond('Racarumi', '1–3 días')['cobertura (pares con Q > P95)']), `sobre el P90: ${pct(cond('Racarumi', '1–3 días')['sobre P90 (pares con Q > P95)'])}`, css('--bad'))}
        ${kpi('CRPSS a 1 día', fmt(prob1('Racarumi')['CRPSS frente a la persistencia'], 2), 'Racarumi, frente a la persistencia', css('--good'))}
        ${kpi('Tamshiyacu vs seleccionada', `${frT.filter(r => r.clase === 'peor').length}/${frT.length}`, 'configuraciones peores (IC < 0)', css('--bad'))}
      </div>
      <div class="glass panel mt"><header><h2>Bandas de pronóstico P10–P90 en la prueba</h2>
        <div class="ctrl">${seg('c-est', EST.map(e => [e, e]), 'Racarumi', true)}${seg('c-h', X.H.map(h => [h, h + ' d']), 1)}<label>Ir a <select id="c-ev"></select></label></div>
        <span class="sub">Chronos-2 con solo caudal (configuración «Q»): banda P10–P90 y pronóstico puntual (media) para cada día, emitidos h días antes; línea clara: observado. La cobertura se calcula aquí, en todas las emisiones de prueba del horizonte elegido.</span></header>
        <div class="cuerpo"><div id="c-banda" class="fig"></div><div class="cifras" id="c-cif"></div></div></div>
      <div class="g-2 mt">
        <div class="glass panel"><header><h2>Cobertura por horizonte</h2>${seg('c-est2', EST.map(e => [e, e]), 'Racarumi', true)}<span class="sub">Fracción de observados dentro de la banda P10–P90 (ideal 80 %): en todos los días y solo en los días sobre el P95.</span></header>
          <div class="cuerpo"><div id="c-cob" class="fig"></div></div></div>
        <div class="glass panel"><header><h2>Elección del contexto</h2>${seg('c-est3', EST.map(e => [e, e]), 'Racarumi', true)}<span class="sub">NSE medio en el bloque de selección (2012–2015) de cada contexto y pronóstico puntual. Resaltado: el elegido.</span></header>
          <div class="cuerpo"><div id="c-ctx" class="fig"></div></div></div>
      </div>
      <div class="glass panel mt"><header><h2>Configuraciones de Chronos-2 frente a lo seleccionado</h2>${seg('c-est4', EST.map(e => [e, e]), 'Tamshiyacu', true)}<span class="sub">ΔNSE medio de prueba de cada configuración de Chronos-2 frente a la configuración seleccionada en validación para su periodo y escenario (IC 90 %). Mezcla algoritmo, entradas y representación.</span></header>
          <div class="cuerpo"><div id="c-fre" class="fig"></div></div></div>
      <div class="glass panel mt"><header><h2>Interpretación</h2></header><div class="cuerpo">
        ${lectura([['Bandas', ul(TX.p5_probabilistico)], ['Contexto', ul(TX.p5_contexto)], ['Sensibilidad', ul(TX.p5_sensibilidad)], ['Lluvia futura', ul(TX.p5_idealizado)]], 'Interpretación', true)}</div></div>
      ${conclusiones(TX.p5_conclusiones)}
    </section>`;
    let est = 'Racarumi', h = 1, rangoX = null;
    const evs = () => { const S = D.estaciones[est]; $('#c-ev').innerHTML = `<option value="">todo el periodo de prueba</option>${S.eventos.map((v, i) => `<option value="${i}">crecida ${v.fecha}</option>`).join('')}`; };
    const banda = () => {
      const S = D.estaciones[est], B = X.bandas[est], P = B.h[h], t0b = fecha0(B.t0), t0s = fecha0(S.serie.t0), U = 'm³/s', dec = est === 'Tamshiyacu' ? 0 : 1;
      const ms = P.d.map(d => t0b + d * DIA), x = [], ix = [];
      for (let i = 0; i < ms.length; i++) { if (i && ms[i] - ms[i - 1] > DIA) { x.push(null); ix.push(-1); } x.push(iso(ms[i])); ix.push(i); }
      const sel = a => ix.map(i => i < 0 ? null : a[i]);
      const obs = ms.map(m => { const k = Math.round((m - t0s) / DIA); return k >= 0 && k < S.serie.q.length ? S.serie.q[k] : null; });
      let n = 0, den = 0, na = 0, dena = 0;
      obs.forEach((o, i) => { if (o == null || P.lo[i] == null) return; const d = o >= P.lo[i] && o <= P.hi[i]; den++; n += d; if (o > S.P95) { dena++; na += d; } });
      const xs = S.serie.q.map((_, i) => iso(t0s + i * DIA)), c = css('--c5');
      const tramos = []; let ini = 0;
      for (let i = 1; i <= ms.length; i++) if (i === ms.length || ms[i] - ms[i - 1] > DIA) { tramos.push([ini, i]); ini = i; }
      const poligonos = tramos.map(([a, b], j) => { const xx = [], yy = [];
        for (let i = a; i < b; i++) { xx.push(iso(ms[i])); yy.push(P.hi[i]); }
        for (let i = b - 1; i >= a; i--) { xx.push(iso(ms[i])); yy.push(P.lo[i]); }
        return { x: xx, y: yy, mode: 'lines', fill: 'toself', fillcolor: c + '40', line: { width: 0 }, hoverinfo: 'skip', name: 'Banda P10–P90', legendgroup: 'banda', showlegend: j === 0 }; });
      plot('#c-banda', [
        ...poligonos,
        { x: xs, y: S.serie.q, name: 'Observado', line: { color: css('--ink'), width: 1.5 }, hovertemplate: '%{y:,.' + dec + 'f} ' + U },
        { x, y: sel(P.p), name: `Chronos-2 (h = ${h} d)`, line: { color: c, width: 1.6 }, hovertemplate: '%{y:,.' + dec + 'f} ' + U }],
      base({ xaxis: { type: 'date', rangeslider: { visible: true, thickness: 0.08, bgcolor: css('--glass-2') }, range: rangoX || [iso(ms[0]), iso(ms[ms.length - 1])] }, yaxis: { title: { text: 'Caudal (' + U + ')' }, tickformat: ',.0f' },
        legend: { orientation: 'h', y: 1.1, x: 0 }, margin: { l: 64, r: 14, t: 30, b: 30 },
        shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: S.P95, y1: S.P95, line: { color: css('--bad'), dash: 'dot', width: 1.2 } }] }), 430);
      $('#c-cif').innerHTML = `<span>${est} · h = <b>${h} d</b></span><span>cobertura P10–P90 <b>${pct(n / den, 1)}</b> de ${fmt(den, 0)} días</span><span>en días > P95 <b>${pct(dena ? na / dena : null, 1)}</b> de ${fmt(dena, 0)}</span><span>nominal <b>80 %</b></span>`;
    };
    onSeg(app, 'c-est', v => { est = v; rangoX = null; evs(); banda(); }); onSeg(app, 'c-h', v => { h = +v; banda(); });
    $('#c-ev').addEventListener('change', ev => { const v = ev.target.value, S = D.estaciones[est]; if (v === '') rangoX = null; else { const p = fecha0(S.eventos[+v].fecha); rangoX = [iso(p - 50 * DIA), iso(p + 35 * DIA)]; } banda(); });
    evs(); banda();
    const cob = e => { const rs = X.probabilistico.filter(r => r['estación'] === e && r.variante === 'Solo caudal').sort((a, b) => a.h - b.h), x = rs.map(r => r.h);
      plot('#c-cob', [{ x, y: rs.map(r => 100 * r['P10–P90']), name: 'todos los días', mode: 'lines+markers', line: { color: css('--c5'), width: 2.4 }, hovertemplate: '%{y:.0f} %' },
        { x, y: rs.map(r => 100 * r['P10–P90 en días > P95']), name: 'días > P95', mode: 'lines+markers', line: { color: css('--bad'), width: 2, dash: 'dot' }, hovertemplate: '%{y:.0f} %' }],
      base({ xaxis: { title: { text: 'Horizonte (días)' }, type: 'log', tickvals: x }, yaxis: { title: { text: 'Cobertura (%)' }, range: [0, 100] }, legend: { orientation: 'h', y: -0.3 }, margin: { l: 50, r: 10, t: 14, b: 50 },
        shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 80, y1: 80, line: { color: css('--ink-3'), dash: 'dashdot', width: 1 } }] }), 320); };
    onSeg(app, 'c-est2', cob); cob('Racarumi');
    const ctxG = e => { const rs = X.contexto.filter(r => r['estación'] === e);
      plot('#c-ctx', [{ type: 'bar', orientation: 'h', y: rs.map(r => r.candidato), x: rs.map(r => r['NSE medio selección']), marker: { color: rs.map(r => r.seleccionado ? css('--c5') : css('--ink-4')) },
        text: rs.map(r => fmt(r['NSE medio selección'], 3) + ' · ' + r.clase), textposition: 'auto', insidetextanchor: 'end', textfont: { size: 10, family: css('--f-mono'), color: css('--ink') }, hovertemplate: '%{y}: %{x:.3f}<extra></extra>' }],
      base({ hovermode: 'closest', xaxis: { title: { text: 'NSE medio (2012–2015)' }, range: [Math.min(...rs.map(r => r['NSE medio selección'])) - 0.05, Math.max(...rs.map(r => r['NSE medio selección'])) + 0.01] }, yaxis: { autorange: 'reversed', tickfont: { family: css('--f-mono'), size: 10 } }, margin: { l: 110, r: 10, t: 14, b: 44 } }), 320); };
    onSeg(app, 'c-est3', ctxG); ctxG('Racarumi');
    const freG = e => { const rs = X.frente.filter(r => r['estación'] === e).sort((a, b) => a['ΔNSE medio'] - b['ΔNSE medio']);
      const cc = { mejora: css('--good'), peor: css('--bad'), inconcluso: css('--warn'), equivalente: css('--ink-3') };
      plot('#c-fre', [{ type: 'scatter', mode: 'markers', x: rs.map(r => `${r['configuración'].replace(' · Chronos-2', '')}${r.escenario === 'mismo día' ? '' : ' ·r'}${r['periodo de prueba'].startsWith('común') ? ' ·RQ' : ''}`), y: rs.map(r => r['ΔNSE medio']),
        error_y: { type: 'data', symmetric: false, array: rs.map(r => r['IC90 superior'] - r['ΔNSE medio']), arrayminus: rs.map(r => r['ΔNSE medio'] - r['IC90 inferior']), color: css('--ink-3'), thickness: 1.2, width: 0 },
        marker: { size: 9, color: rs.map(r => cc[r.clase] || css('--ink-2')), line: { width: 1, color: css('--solid') } }, customdata: rs.map(r => [r.referencia, r.clase, r['periodo de prueba'], r.escenario, r['configuración']]),
        hovertemplate: '<b>%{customdata[4]}</b> · %{customdata[3]}<br>ΔNSE %{y:.3f} frente a %{customdata[0]}<br>%{customdata[1]} · %{customdata[2]}<extra></extra>' }],
      base({ hovermode: 'closest', yaxis: { title: { text: 'ΔNSE medio (prueba)' }, zeroline: true, zerolinecolor: css('--ink-3') }, xaxis: { showticklabels: false, title: { text: 'Configuraciones de Chronos-2, de peor a mejor (pase el cursor para ver cada una)' } }, margin: { l: 56, r: 10, t: 24, b: 40 },
        annotations: [{ xref: 'paper', yref: 'paper', x: 1, y: 1.02, xanchor: 'right', showarrow: false, font: { size: 10, color: css('--ink-3') }, text: `<span style="color:${cc.mejora}">● mejora</span>  <span style="color:${cc.peor}">● peor</span>  <span style="color:${cc.inconcluso}">● inconcluso</span>  ·  «·r»: un día de retraso  ·  «·RQ»: periodo común con Requena` }] }), 380);
    };
    onSeg(app, 'c-est4', freG); freG('Tamshiyacu');
  }

  // ────────────────────────────────────────────────────────── P6 · SELECCIÓN FINAL (08)
  function vIntegrado() {
    const X = I.integrado, T = X.textos, app = $('#app');
    const PERS = [['Racarumi|prueba 2016-01 a 2023-08', 'Racarumi'], ['Tamshiyacu|con San Regis (prueba 2016-01 a 2025-12)', 'Tamshiyacu · con San Regis'], ['Tamshiyacu|común con Requena (prueba 2016-01 a 2020-03)', 'Tamshiyacu · común con Requena']];
    const grupos = [];
    for (const r of X.sel_mag) {
      const g = grupos.find(x => x['estación'] === r['estación'] && x['periodo de prueba'] === r['periodo de prueba'] && x['seleccionada en validación'] === r['seleccionada en validación'] && x['NSE medio prueba'] === r['NSE medio prueba']);
      if (g) g.escenario = 'ambos escenarios'; else grupos.push({ ...r });
    }
    const card = r => { const est = r['estación'], cumpleMej = r['mejor en prueba frente al seleccionado'] || '';
      return `<div class="glass panel" style="--c:var(${est === 'Racarumi' ? '--rac' : '--tam'})"><div class="cuerpo" style="padding-top:14px">
        <div class="eyebrow">${esc(est)} · ${esc(perCorto(r['periodo de prueba']))} · ${esc(r.escenario)}</div>
        <h3 style="font-size:1.3rem;font-weight:780;font-stretch:84%;margin:4px 0 6px">${esc(r['seleccionada en validación'])}</h3>
        <div class="cifras" style="border:0;margin:0;padding:0"><span>validación <b>${fmt(r['NSE medio validación (2012–2015)'], 3)}</b></span><span>prueba <b>${fmt(r['NSE medio prueba'], 3)}</b></span><span>H <b>${txtHU(r['H cota 95 % (d)'])} d</b></span></div>
        <p class="nota">Mejor en prueba: <b style="color:var(--ink)">${esc(r['mejor NSE medio en la prueba (no se elige con él)'])}</b> · Δ ${esc(cumpleMej)}. ${fmt(r['equivalentes al mayor en validación (incluido el mayor)'], 0)} equivalentes y ${fmt(r['inconclusos en validación'], 0)} inconclusos de ${fmt(r.candidatos, 0)}.</p></div></div>`; };
    app.innerHTML = `<section class="vista" style="--c:var(--c6)">
      ${hero('P6 · Comparación integrada y selección final', '¿Qué configuración se elige y cómo le va en la prueba?',
        'Seis modelos y Chronos-2 con todas las combinaciones de entradas de cada cuenca, con las fuentes hasta t y hasta t − 1. Se elige en validación (2012–2015), por cuenca, periodo y escenario; la prueba no cambia nada.',
        `<b>Racarumi: Q · Chronos-2</b> (no se sostiene en la prueba). <b>Tamshiyacu: Q · KNN</b> (Q+SR · KNN en el periodo con Requena, mismo día). Ninguna coincide con la mejor de la prueba; los avisos elegidos no cumplen el criterio. ${X.verificaciones.correctas}/${X.verificaciones.total} verificaciones correctas.`, '--c6')}
      <div class="g-2" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">${grupos.map(card).join('')}</div>
      <div class="g-2-1 mt">
        <div class="glass panel"><header><h2>Validación frente a prueba: todos los candidatos</h2>
          <div class="ctrl">${seg('i-per', PERS.map(([v, t]) => [v, t]), PERS[0][0], true)}${seg('i-esc', [['mismo', 'mismo día'], ['retraso', 'un día de retraso'], ['todos', 'todos']], 'mismo', true)}</div>
          <span class="sub">Cada punto es una configuración (entradas × modelo). Color: modelo; forma: fuentes (● solo caudal, ◆ lluvia, ■ aguas arriba, ▲ ambas; hueca: con un día de retraso). Anillo grande: la seleccionada; estrella: la mejor de la prueba. Haga clic en un punto para ver su detalle.</span></header>
          <div class="cuerpo"><div id="i-disp" class="fig"></div></div></div>
        <div class="glass panel"><header><h2>Detalle de la configuración</h2></header><div class="cuerpo"><div class="detalle" id="i-det"></div></div></div>
      </div>
      <div class="g-2 mt">
        <div class="glass panel"><header><h2>Tamshiyacu: cada fuente con cada familia</h2><div class="ctrl">${seg('i-cper', [['2016-01 a 2025-12', 'con San Regis'], ['2016-01 a 2020-03', 'con Requena']], '2016-01 a 2025-12', true)}${seg('i-band', BANDAS.map(b => [b, b.replace(' días', ' d')]), '1–3 días', true)}</div>
          <span class="sub">G (% menos error) de agregar una fuente, con la misma familia y las mismas emisiones de prueba (combinaciones del 08). ▲ reduce el error (IC 90 % > 0); ▼ lo aumenta. Las filas con Requena usan la prueba común 2016-01 a 2020-03.</span></header>
          <div class="cuerpo"><div id="i-comb" class="fig"></div></div></div>
        <div class="glass panel"><header><h2>Avisos en Racarumi: diagrama de desempeño</h2>
          <span class="sub">Cada punto es un sistema de avisos evaluado en la prueba (32 cruces). Eje x: razón de éxito (1 − FAR); eje y: POD. Curvas: CSI constante. Zona sombreada: criterio de utilidad (POD ≥ 0.5 con FAR ≤ 0.5). Ninguno entra con anticipación útil ≥ 1 día.</span></header>
          <div class="cuerpo"><div id="i-avisos" class="fig"></div><div class="tw" id="i-selav"></div></div></div>
      </div>
      <div class="glass panel mt"><header><h2>Interpretación y verificación</h2></header><div class="cuerpo">
        <div class="tuberia" style="margin-bottom:6px">${X.verificaciones.grupos.map(g => `<span class="chip ok">✓ ${esc(g.grupo)} · ${g.n}</span>`).join('')}</div>
        ${lectura([['Prueba', ul(TX.p6_prueba)], ['Validación', ul(TX.p6_validacion)], ['Avisos', ul(TX.p6_avisos)]])}</div></div>
      ${conclusiones(TX.p6_conclusiones)}
    </section>`;
    let per = PERS[0][0], esc_ = 'mismo', actual = null;
    const fuentes = c => { const p = /\+P/.test(c), a = /SR|RQ/.test(c); return p && a ? 'triangle-up' : p ? 'diamond' : a ? 'square' : 'circle'; };
    const retr = c => /t−1/.test(c);
    const escenarioTxt = () => esc_ === 'mismo' ? 'mismo día' : 'un día de retraso';
    const filtra = () => { const [est, pp] = per.split('|'); return X.candidatos.filter(r => r.est === est && r.per === pp && (esc_ === 'todos' || (esc_ === 'mismo' ? !retr(r.c) : (retr(r.c) || r.c === 'Q')))); };
    const esSel = r => r.sel && (esc_ === 'todos' ? true : r.sel.includes(`${r.per} · ${escenarioTxt()}`));
    const detalle = r => {
      if (!r) return;
      actual = r;
      const nh = ['1 d', '3 d', '7 d', '15 d', '30 d'], mx = 1;
      const hp = (() => { try { const o = JSON.parse(r.hp || '{}'); const k = Object.entries(o); return k.length ? k.map(([a, b]) => `${a} = ${Array.isArray(b) ? b.join('×') : b}`).join(' · ') : 'sin hiperparámetros (o fijados por el método)'; } catch (e) { return String(r.hp); } })();
      $('#i-det').innerHTML = `<div class="eyebrow" style="color:${colM(r.mod)}">${esc(r.mod)}${esSel(r) ? ' · <span class="chip ok">seleccionada</span>' : ''}</div>
        <h3>${esc(r.c)} · ${esc(r.mod)}</h3><div class="meta">${esc(r.disp)}<br>${esc(r.est)} · ${esc(r.per)} · ${fmt(r.n, 0)} emisiones</div>
        <div class="kpis" style="grid-template-columns:repeat(3,minmax(0,1fr))">${kpi('Validación', fmt(r.val, 3), 'NSE medio 2012–15')}${kpi('Prueba', fmt(r.pru, 3), 'NSE medio', colM(r.mod))}${kpi('H cota', txtHU(r.H) + ' d', r.Hr ? 'p05–p95 ' + esc(r.Hr) : '')}</div>
        <div><div class="barras">${r.h.map((v, i) => `<div><b>${fmt(v, 2)}</b><i style="--k:${colM(r.mod)};height:${Math.max(2, 100 * Math.max(0, v) / mx)}%"></i></div>`).join('')}</div><div class="ejes">${nh.map(x => `<span>${x}</span>`).join('')}</div><p class="nota">NSE de prueba por horizonte.</p></div>
        <p class="nota"><b style="color:var(--ink-2)">Hiperparámetros:</b> ${esc(hp)}</p>`;
    };
    const disp = () => {
      const rs = filtra(), sel = rs.filter(esSel), mej = rs.reduce((a, b) => (b.pru > (a ? a.pru : -9) ? b : a), null);
      const tr = D.MODELOS.concat(['Chronos-2']).map(m => { const f = rs.filter(r => r.mod === m); return { type: 'scatter', mode: 'markers', name: m, x: f.map(r => r.val), y: f.map(r => r.pru),
        marker: { size: 11, color: colM(m), symbol: f.map(r => fuentes(r.c) + (retr(r.c) ? '-open' : '')), line: { width: f.map(r => retr(r.c) ? 2 : 1), color: f.map(r => retr(r.c) ? colM(m) : css('--solid')) }, opacity: 0.92 },
        customdata: f.map(r => rs.indexOf(r)), text: f.map(r => `${r.c} · ${r.mod}`), hovertemplate: '<b>%{text}</b><br>validación %{x:.3f} · prueba %{y:.3f}<extra></extra>' }; });
      const v = rs.map(r => r.val).concat(rs.map(r => r.pru)), lo = Math.min(...v) - 0.01, hi = Math.max(...v) + 0.01;
      tr.unshift({ x: [lo, hi], y: [lo, hi], mode: 'lines', line: { color: css('--ink-4'), dash: 'dot', width: 1 }, hoverinfo: 'skip', showlegend: false });
      tr.push({ x: sel.map(r => r.val), y: sel.map(r => r.pru), mode: 'markers', name: 'seleccionada', marker: { size: 26, symbol: 'circle-open', color: css('--accent'), line: { width: 2.5 } }, hoverinfo: 'skip' });
      if (mej) tr.push({ x: [mej.val], y: [mej.pru], mode: 'markers', name: 'mejor en prueba', marker: { size: 20, symbol: 'star', color: css('--good'), line: { width: 1, color: css('--solid') } }, hoverinfo: 'skip' });
      const ann = sel.slice(0, 2).map(r => ({ x: r.val, y: r.pru, text: `<b>${esc(r.c)} · ${esc(r.mod)}</b>`, showarrow: true, arrowcolor: css('--accent'), ax: -60, ay: -36, font: { color: css('--accent'), size: 11 }, bgcolor: css('--solid'), borderpad: 3 }));
      if (mej && !sel.includes(mej)) ann.push({ x: mej.val, y: mej.pru, text: `mejor en prueba: ${esc(mej.c)} · ${esc(mej.mod)}`, showarrow: true, arrowcolor: css('--good'), ax: 40, ay: -30, font: { color: css('--good'), size: 11 }, bgcolor: css('--solid'), borderpad: 3 });
      const div = $('#i-disp');
      plot(div, tr, base({ hovermode: 'closest', xaxis: { title: { text: 'NSE medio en validación (2012–2015) → elige' }, range: [lo, hi] }, yaxis: { title: { text: 'NSE medio en la prueba → confirma' }, range: [lo, hi] }, annotations: ann, legend: { orientation: 'h', y: -0.18 }, margin: { l: 60, r: 14, t: 16, b: 50 } }), 480);
      div.removeAllListeners && div.removeAllListeners('plotly_click');
      div.on('plotly_click', ev => { const p = ev.points[0]; if (p && p.customdata != null) detalle(rs[p.customdata]); });
      detalle(sel[0] || mej);
    };
    onSeg(app, 'i-per', v => { per = v; disp(); }); onSeg(app, 'i-esc', v => { esc_ = v; disp(); }); disp();
    let cPer = '2016-01 a 2025-12', cBan = '1–3 días';
    const comb = () => { const f = X.combinaciones.filter(r => r.b === cBan && r.per === cPer), ents = [...new Set(f.map(r => r.ent))];
      const z = ents.map(e => MOD7.map(m => { const r = f.find(x => x.ent === e && x.mod === m); return r ? 100 * r.G : null; }));
      const tx = ents.map(e => MOD7.map(m => { const r = f.find(x => x.ent === e && x.mod === m); return r ? (r.G > 0 ? '+' : '') + fmt(100 * r.G, 0) + (r.l > 0 ? '▲' : r.l < 0 ? '▼' : '') : ''; }));
      const cd = ents.map(e => MOD7.map(m => { const r = f.find(x => x.ent === e && x.mod === m); return r ? [fmt(100 * r.lo, 0), fmt(100 * r.hi, 0), r.per] : ['', '', '']; }));
      plot('#i-comb', [{ type: 'heatmap', z: z.map(r => r.map(v => v == null ? null : Math.max(-60, Math.min(60, v)))), x: MOD7.map(m => ({ 'Regresión lineal': 'Lineal', 'Random Forest': 'RF', 'XGBoost': 'XGB', 'Chronos-2': 'Chronos' }[m] || m)), y: ents, text: tx, texttemplate: '%{text}', customdata: cd,
        zmid: 0, zmin: -60, zmax: 60, colorscale: divergente(), showscale: false, xgap: 2, ygap: 2, textfont: { family: css('--f-mono'), size: 10, color: css('--ink') },
        hovertemplate: '<b>%{y}</b> · %{x}<br>G = %{text} %<br>IC 90 %: %{customdata[0]} a %{customdata[1]} %<br>prueba %{customdata[2]}<extra></extra>' }],
      base({ hovermode: 'closest', margin: { l: 10, r: 10, t: 10, b: 40 }, xaxis: { showgrid: false, side: 'top', tickangle: angosto() ? -45 : 0, tickfont: { size: angosto() ? 9 : 11 } }, yaxis: { autorange: 'reversed', showgrid: false, tickfont: { size: 10.5, family: css('--f-mono') } } }), Math.max(380, 26 * ents.length + 80)); };
    onSeg(app, 'i-band', v => { cBan = v; comb(); }); onSeg(app, 'i-cper', v => { cPer = v; comb(); }); comb();
    // diagrama de desempeño
    const av = I.sintesis.avisos, grid = [];
    for (const c of [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]) { const xs = [], ys = []; for (let s = c + 0.001; s <= 1.0001; s += 0.01) { const p = 1 / (1 / c - 1 / s + 1); if (p > 0 && p <= 1) { xs.push(s); ys.push(p); } }
      grid.push({ x: xs, y: ys, mode: 'lines', line: { color: css('--ink-4'), width: 1, dash: 'dot' }, hoverinfo: 'skip', showlegend: false }); }
    const lbl = [0.2, 0.4, 0.6].map(c => ({ x: 0.97, y: 1 / (1 / c - 1 / 0.97 + 1), text: 'CSI ' + c, showarrow: false, font: { size: 9, color: css('--ink-3') }, xanchor: 'right' }));
    plot('#i-avisos', grid.concat([{ type: 'scatter', mode: 'markers+text', x: av.map(r => 1 - r['FAR (global)']), y: av.map(r => r.POD), text: av.map(r => r['configuración']), textposition: av.map(r => ({ 'Q · Tendencia 3 días': 'top center', 'Q+P · KNN': 'top right', 'Q · Random Forest': 'top left', 'Q · MLP': 'middle right', 'Q · Chronos-2': 'bottom center' }[r['configuración']] || 'top center')), textfont: { size: 10, color: css('--ink-2') },
      marker: { size: 13, color: av.map(r => r.cuaderno === 4 ? css('--ink-3') : css('--c6')), line: { width: 1.5, color: css('--solid') } }, customdata: av.map(r => [r.aciertos, r['N_1 (cruces evaluables)'], r['falsas alarmas'], r.CSI, r['papel']]),
      hovertemplate: '<b>%{text}</b><br>POD %{y:.2f} · FAR %{customdata[2]} falsas alarmas<br>aciertos %{customdata[0]}/%{customdata[1]} · CSI %{customdata[3]:.2f}<br>%{customdata[4]}<extra></extra>', showlegend: false }]),
    base({ hovermode: 'closest', xaxis: { title: { text: 'Razón de éxito (1 − FAR)' }, range: [0, 1] }, yaxis: { title: { text: 'POD' }, range: [0, 1] }, annotations: lbl, margin: { l: 50, r: 10, t: 14, b: 44 },
      shapes: [{ type: 'rect', x0: 0.5, x1: 1, y0: 0.5, y1: 1, fillcolor: css('--good') + '1f', line: { color: css('--good'), width: 1, dash: 'dot' } }] }), 360);
    tabla('#i-selav', X.sel_avisos, [['escenario', 'Escenario'], ['seleccionada en validación', 'Seleccionada', v => `<b>${esc(v)}</b>`, 'izq'], ['CSI 2012–2015 (regla de 2009–2011)', 'CSI validación'], ['prueba: aciertos / evaluables', 'Prueba'], ['FAR (IC90)', 'FAR (IC 90 %)'], ['CSI (IC90)', 'CSI (IC 90 %)'],
      ['cumple: anticipación útil ≥ 1 día', 'Cumple', v => v ? '<span class="chip ok">sí</span>' : '<span class="chip no">no</span>']]);
  }

  // ────────────────────────────────────────────────────────── MÉTODO
  function vMetodo() {
    const filaP = e => { const S = D.estaciones[e]; return S.modelos.filter(n => S.parametros[n]).map(n => `<tr><td>${esc(e)}</td><td>${dotM(n)}</td><td class="izq">${esc(JSON.stringify(S.parametros[n]).replace(/[{}"]/g, '').replace(/,/g, ', ').replace(/:/g, ' = ') || '—')}</td><td class="n">${fmt(S.nse_val[n], 3)}</td></tr>`).join(''); };
    const div = e => D.estaciones[e].division.map(r => `<tr><td>${esc(e)}</td><td>${esc(r.bloque)}</td><td>${esc(r['periodo de emisión'])}</td><td class="n">${fmt(r.muestras, 0)}</td><td class="n">${fmt(r['Q medio (m³/s)'], 1)}</td><td class="n">${fmt(r['días > P95 en t (%)'], 1)}</td></tr>`).join('');
    $('#app').innerHTML = `<section class="vista" style="--c:var(--ink-3)">
      ${hero('Método', 'Cómo se obtuvieron los resultados', 'El mismo procedimiento para las dos estaciones, los siete modelos y todas las fuentes de información.', '', '--ink-3')}
      <div class="met">
        <div class="glass"><h3>Datos</h3><p>CAMELS-PE v1.0.1 (SENAMHI): caudal diario observado y lluvia PISCOp v2.1. Los vacíos cortos (≤ 3 días) se rellenan solo en las entradas; los caudales a pronosticar nunca se inventan.</p></div>
        <div class="glass"><h3>Modelos</h3><p>Regresión lineal, Random Forest, XGBoost, KNN, MLP y LSTM, más Chronos-2 sin entrenar. Las redes se promedian con ${D.SEMILLAS.length} semillas.</p></div>
        <div class="glass"><h3>Periodos</h3><p>Entrenamiento hasta 2008. Validación 2009–2015: 2009–2011 corrige el sesgo y 2012–2015 elige. Prueba desde 2016: solo confirma.</p></div>
        <div class="glass"><h3>Cómo se elige</h3><p>Gana el mayor NSE medio de los 30 horizontes en 2012–2015. Si otro queda a menos de 0.01, se prefiere el más simple.</p></div>
        <div class="glass"><h3>Horizonte útil</h3><p>Último día seguido en que el pronóstico supera a la persistencia y a la climatología (cota 95 % por remuestreo de meses). «30» significa «30 o más».</p></div>
        <div class="glass"><h3>Avisos</h3><p>Solo cuentan los avisos emitidos antes de una crecida nueva (7 días bajo el P95). Útil si detecta al menos la mitad con no más de la mitad de falsas alarmas.</p></div>
      </div>
      <div class="g-2 mt">
        <div class="glass panel"><header><h2>Controles de calidad</h2></header><div class="cuerpo">${ul(TX.controles)}<div class="tuberia" style="margin-top:8px">${I.integrado.verificaciones.grupos.map(g => `<span class="chip ok">✓ ${esc(g.grupo)} · ${g.n}</span>`).join('')}</div></div></div>
        <div class="glass panel"><header><h2>Límites</h2></header><div class="cuerpo">${ul(TX.limites)}</div></div>
      </div>
      <div class="g-2 mt">
        <div class="glass panel"><header><h2>División temporal</h2></header>
          <div class="cuerpo tw"><table class="t"><thead><tr><th>Estación</th><th>Bloque</th><th>Periodo de emisión</th><th>Muestras</th><th>Q medio (m³/s)</th><th>Días &gt; P95 (%)</th></tr></thead><tbody>${div('Racarumi')}${div('Tamshiyacu')}</tbody></table></div></div>
        <div class="glass panel"><header><h2>Hiperparámetros elegidos (solo caudal)</h2></header>
          <div class="cuerpo tw"><table class="t"><thead><tr><th>Estación</th><th>Modelo</th><th class="izq">Hiperparámetros</th><th>NSE medio selección</th></tr></thead><tbody>${filaP('Racarumi')}${filaP('Tamshiyacu')}</tbody></table></div></div>
      </div>
    </section>`;
  }

  // ────────────────────────────────────────────────────────── MAYU · asistente local (sin internet, sin modelo de lenguaje)
  const MAYU = (() => {
    const N = s => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[¿?¡!.,;:()]/g, ' ').replace(/\s+/g, ' ').trim();
    const tiene = (t, ...p) => p.some(x => new RegExp('(^|\\s)' + x + '(\\s|$)').test(t));
    const algo = (t, re) => re.test(t);
    const ESTS = [[/racarumi|chancay|lambayeque|pacifico|costa/, 'Racarumi'], [/tamshiyacu|amazon|ucayali|selva|iquitos/, 'Tamshiyacu']];
    const MODS = [[/regresion lineal|lineal/, 'Regresión lineal'], [/random forest|\brf\b|bosque/, 'Random Forest'], [/xgboost|\bxgb\b/, 'XGBoost'], [/\bknn\b|vecinos/, 'KNN'],
      [/\bmlp\b|perceptron/, 'MLP'], [/\blstm\b/, 'LSTM'], [/combinado/, COMB], [/chronos|fundacional/, 'Chronos-2'], [/persistencia/, 'Persistencia'], [/climatologia/, 'Climatología']];
    const METS = [[/\bnse\b|nash/, 'NSE'], [/\bkge\b|kling/, 'KGE'], [/rmse/, 'RMSE'], [/\bmae\b|error absoluto/, 'MAE'], [/pbias|sesgo/, 'PBIAS']];
    const busca = (t, L_) => { for (const [re, v] of L_) if (re.test(t)) return v; return null; };
    const horiz = t => { const m = /\b(\d{1,2})\s*(d|dia|dias)\b/.exec(t) || /\ba\s+(\d{1,2})\b/.exec(t) || /\bh\s*=?\s*(\d{1,2})\b/.exec(t); const h = m ? +m[1] : null; return h >= 1 && h <= 30 ? h : null; };
    const GL = [[/\bnse\b|nash/, 0], [/nse medio/, 1], [/\bkge\b|pbias/, 2], [/persistencia/, 3], [/climatologia/, 4], [/h cota|cota 95/, 6], [/horizonte util|que es h\b/, 5], [/\bganancia\b|que es g\b|\bg\b =/, 7],
      [/equivalente|inconcluso|ic 90|intervalo/, 8], [/\bp95\b|umbral/, 9], [/\bpod\b|\bfar\b|\bcsi\b|falsa alarma/, 10], [/anticipacion real/, 11], [/\bsr\b|\brq\b|\bia\b|notacion|q\+p/, 12],
      [/mismo dia|retraso|t-1|t−1/, 13], [/validacion|prueba|entrenamiento/, 14], [/chronos/, 15]];
    const CAP = [[/mapa|cuenca|ubicacion|donde/, 'sintesis'], [/vision general|inicio|resumen general|portada/, 'sintesis'], [/horizonte util|p1\b/, 'resumen'], [/racarumi/, 'Racarumi'], [/tamshiyacu/, 'Tamshiyacu'],
      [/aviso|alerta|crecida|p2\b|temporada|desempeno/, 'anticipacion'], [/aguas arriba|san regis|requena|cirato|p3\b/, 'arriba'], [/lluvia|precipitacion|piscop|p4\b/, 'lluvia'],
      [/chronos|fundacional|p5\b/, 'chronos'], [/seleccion|integrad|p6\b|final/, 'integrado'], [/metodo|revision|protocolo|reproducir/, 'metodo']];
    const ver = (id, t) => ({ t: t || `Ver ${capDe(id).n} · ${capDe(id).t}`, ir: id });
    const S_ = e => D.estaciones[e];
    // respuestas por tema (con los datos de la página)
    const R = {
      hola: () => ({ h: '¡Hola! Soy <b>MAYU</b> («río» en quechua). Respondo con los resultados de este estudio: horizontes útiles, avisos, modelos, aguas arriba, lluvia y Chronos-2. También te llevo a cualquier capítulo.', a: [] }),
      p1: () => { const r = huDe('Racarumi', S_('Racarumi').mejor), t = huDe('Tamshiyacu', S_('Tamshiyacu').mejor);
        return { h: `Con solo el caudal local, la magnitud se estima bien hasta <b>${txtHU(r[K_HU])} días en Racarumi</b> (${esc(S_('Racarumi').mejor)}) y <b>${txtHU(t[K_HU])} días en Tamshiyacu</b> (${esc(S_('Tamshiyacu').mejor)}), con la cota 95 % del bootstrap. La diferencia entre ríos (${fmt(S_('Racarumi').area, 0)} frente a ${fmt(S_('Tamshiyacu').area, 0)} km²) pesa mucho más que la elección del modelo.`, a: [ver('resumen')] }; },
      p2: () => { const r = sintesisA('Racarumi'), t = sintesisA('Tamshiyacu');
        return { h: `Para avisar un <b>nuevo cruce del P95</b>: en Racarumi el mejor sistema (${esc(r['modelo (avisos)'])}) acierta ${fmt(r.aciertos, 0)} de ${fmt(r['cruces evaluables'], 0)} cruces con FAR ${fmt(r.FAR, 2)}, así que <b>no alcanza el criterio</b> (POD ≥ 0.5 con FAR ≤ 0.5): anticipación útil 0 días. En Tamshiyacu, ${fmt(t.aciertos, 0)} de ${fmt(t['cruces evaluables'], 0)} con ${fmt(t['anticipación útil (d)'], 0)} días, pero son tan pocos eventos que es exploratorio.`, a: [ver('anticipacion'), ver('anticipacion', 'Ver avisos por temporada')] }; },
      p3: () => ({ h: 'De las estaciones aguas arriba, <b>San Regis</b> (Marañón) sí ayuda a Tamshiyacu: va 1 día adelante y reduce el error 33–45 % a 1–3 días con los seis modelos (18–25 % a 4–7 días). <b>Requena</b> no tiene desfase positivo ni reduce el error, y <b>Cirato</b> (Racarumi) es exploratoria. El horizonte útil casi no cambia.', a: [ver('arriba')] }),
      p4: () => ({ h: 'La <b>lluvia</b> del mismo día reduce el error de Racarumi un 12–27 % a 1–3 días, pero con un día de retraso casi no aporta. En Tamshiyacu la señal tarda ~6 días y la lluvia complementa a San Regis de la segunda a la cuarta semana. Conocer la lluvia futura (escenario idealizado) bajaría el error 62–69 % en Racarumi.', a: [ver('lluvia')] }),
      p5: () => { const r = I.integrado.sel_mag.find(x => x['estación'] === 'Racarumi') || {}, ft = I.chronos.frente.filter(x => x['estación'] === 'Tamshiyacu');
        return { h: `<b>Chronos-2</b> se usó sin ajuste local. En Racarumi ganó en validación (NSE medio ${fmt(r['NSE medio validación (2012–2015)'], 3)}) y fue seleccionado, pero en la prueba bajó a ${fmt(r['NSE medio prueba'], 3)}. En Tamshiyacu sus configuraciones son peores que la seleccionada en ${ft.filter(x => x.clase === 'peor').length} de ${ft.length} comparaciones. Sus bandas P10–P90 cubren ~79 % en conjunto, pero fallan en los caudales altos.`, a: [ver('chronos')] }; },
      p6: () => ({ h: `La selección final (hecha en validación) es <b>Q · Chronos-2</b> en Racarumi y <b>Q · KNN</b> en Tamshiyacu (Q+SR · KNN en el periodo común con Requena, mismo día). Ninguna coincide con la mejor de la prueba y los sistemas de avisos elegidos no cumplen el criterio. Se verificaron ${I.integrado.verificaciones.correctas} de ${I.integrado.verificaciones.total} comprobaciones.`, a: [ver('integrado')] }),
      limites: () => ({ h: 'Límites principales: pocos eventos (Racarumi 32 cruces en la prueba; Tamshiyacu 3), la disponibilidad de la lluvia del mismo día no está demostrada, el periodo de prueba ya se había consultado en versiones anteriores y las familias de modelos reciben las mismas fuentes con representaciones distintas. Es una <b>comparación académica</b>, no un sistema operativo de alerta.', a: [ver('metodo')] }),
      equipo: () => ({ h: 'Proyecto Integrador del curso Ciencia de Datos Ambientales (UTEC). Equipo: <b>Luis Angel Cupe Espinoza, Yely Lanasca Justiniano, Lia Kim Alcantara Tineo, Mayra Madelyn Marzano Mejia y María Fernanda Torres Carbajal</b>.', a: [] }),
      datos: () => ({ h: 'Única fuente: <b>CAMELS-PE v1.0.1</b> (SENAMHI): caudal observado diario depurado y lluvia PISCOp v2.1. Entrenamiento hasta 2008, validación 2009–2015 y prueba desde 2016.', a: [ver('metodo')] }),
      metodo: () => ({ h: 'Se elige en validación (2012–2015) el candidato de mayor NSE medio o el más simple entre sus equivalentes (IC 90 % dentro de ±0.01); la prueba solo confirma. El horizonte útil es el mayor h consecutivo con NSE > 0 que supera a persistencia y climatología, con cota 95 % por bootstrap.', a: [ver('metodo')] }),
      porque: () => ({ h: `Tamshiyacu drena ~${fmt(S_('Tamshiyacu').area, 0)} km²: su caudal integra la lluvia de toda la cuenca y cambia despacio (la señal de la lluvia tarda ~6 días), así que el caudal de hoy ya dice mucho del de las próximas semanas. Racarumi (${fmt(S_('Racarumi').area, 0)} km²) responde al día siguiente de la lluvia, y sin conocer la lluvia futura el pronóstico pierde calidad en pocos días.`, a: [ver('lluvia'), ver('resumen')] }),
      mayu: () => ({ h: '<b>MAYU</b> significa «río» en quechua. Soy un asistente local: busco en los resultados que trae esta página (no uso internet ni un modelo de lenguaje). Prueba con: «NSE de LSTM en Racarumi a 3 días», «¿qué es el CSI?» o «llévame a la lluvia».', a: [] })
    };
    function mejor(e) {
      const S = S_(e), f = I.integrado.sel_mag.filter(r => r['estación'] === e);
      return { h: `<b>${e}</b>: con solo caudal se selecciona <b>${esc(S.mejor)}</b> (horizonte útil ${txtHU(huDe(e, S.mejor)[K_HU])} d). En la selección final: ${[...new Set(f.map(r => `<b>${esc(r['seleccionada en validación'])}</b> (${esc(perCorto(r['periodo de prueba']) === 'prueba' ? r['periodo de prueba'] : perCorto(r['periodo de prueba']))})`))].join('; ')}. La mejor en la prueba, que no se usa para elegir, fue ${esc((f[0] || {})['mejor NSE medio en la prueba (no se elige con él)'] || '—')}.`, a: [ver(e), ver('integrado')] };
    }
    function metrica(e, m, met, h) {
      const S = S_(e);
      if (m === 'Chronos-2') { const c = I.integrado.candidatos.find(r => r.est === e && r.c === 'Q' && r.mod === 'Chronos-2');
        if (!c) return null; return { h: `<b>Chronos-2 (solo caudal) en ${e}</b>, prueba: NSE medio ${fmt(c.pru, 3)}; NSE a 1/3/7/15/30 días: ${c.h.map(v => fmt(v, 2)).join(' / ')}; horizonte útil ${txtHU(c.H)} d.`, a: [ver('chronos')] }; }
      if (m === 'Persistencia' || m === 'Climatología') { const v = m === 'Persistencia' ? S.ref.pers : S.ref.clim, hh = h || 7;
        return { h: `<b>${m}</b> en ${e}: NSE ${fmt(v[hh - 1], 3)} a ${hh} días (a 1 día ${fmt(v[0], 3)}; a 30 días ${fmt(v[29], 3)}). Es una referencia, no un modelo entrenado.`, a: [ver(e)] }; }
      const M = S.met[m]; if (!M) return null;
      if (h) { const k = met || 'NSE', u = k === 'RMSE' || k === 'MAE' ? ' m³/s' : k === 'PBIAS' ? ' %' : '';
        const otros = [['NSE', 3], ['KGE', 3]].filter(([x]) => x !== k).map(([x, d]) => `${x} ${fmt(M[x][h - 1], d)}`).concat([`habilidad frente a la persistencia ${fmt(M.hab_pers[h - 1], 3)}`]);
        return { h: `<b>${esc(m)} en ${e}</b>, a <b>${h} días</b> (prueba): ${k} = <b>${fmt(M[k][h - 1], k === 'RMSE' || k === 'MAE' ? 1 : 3)}${u}</b>. Además: ${otros.join(', ')}.`, a: [ver(e)] }; }
      const hu = huDe(e, m);
      return { h: `<b>${esc(m)} en ${e}</b> (prueba): horizonte útil ${txtHU(hu[K_HU])} d (cota 95 %); NSE a 1 / 7 / 30 días: ${fmt(M.NSE[0], 3)} / ${fmt(M.NSE[6], 3)} / ${fmt(M.NSE[29], 3)}.${m === S.mejor ? ' Es el modelo seleccionado en validación.' : ''}`, a: [ver(e)] };
    }
    function responde(q) {
      const t = N(q);
      if (!t) return R.mayu();
      const e = busca(t, ESTS), m = busca(t, MODS), met = busca(t, METS), h = horiz(t);
      // navegación explícita
      if (algo(t, /^(ir|ve|vamos|abre|abrir|muestra|muestrame|llevame|lleva|ensename|quiero ver|ver)\b/)) {
        const c = busca(t, CAP); if (c) { ir(c); if (c === 'sintesis' && /mapa|cuenca|donde/.test(t)) setTimeout(() => { const el = $('#mapa'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, 300);
          return { h: `Listo, abrí <b>${capDe(c).n} · ${esc(capDe(c).t)}</b>.`, a: [] }; } }
      if (algo(t, /^(hola|buenas|buenos|hey|que tal|saludos)/)) return R.hola();
      if (algo(t, /^ayuda$|^help$|mayu|quien eres|que eres|como funcionas|que puedes hacer/)) return R.mayu();
      // definiciones
      if (algo(t, /que es|que son|que significa|significado|define|definicion|explica|que mide|como se calcula/)) {
        for (const [re, i] of GL) if (re.test(t)) return { h: `<b>${esc(GLOS[i][0])}</b>: ${esc(GLOS[i][1])}`, a: [{ t: 'Abrir glosario', fn: () => abreGlos(true) }] }; }
      // métricas puntuales
      if (m && (e || m === 'Chronos-2')) { const r = metrica(e || 'Racarumi', m, met, h); if (r) return r; }
      if (algo(t, /mejor modelo|que modelo|modelo seleccionado|modelo elegido|cual modelo|gano/)) return e ? mejor(e) : { h: mejor('Racarumi').h + '<br><br>' + mejor('Tamshiyacu').h, a: [ver('integrado')] };
      if (algo(t, /por que|porque|diferencia entre|explica la diferencia/) && (e || /rio|cuenca/.test(t))) return R.porque();
      if (algo(t, /san regis|requena|cirato|aguas arriba/)) return R.p3();
      if (algo(t, /lluvia|precipitacion|piscop|llueve/)) return R.p4();
      if (algo(t, /chronos|fundacional|transformer|zero shot/)) return R.p5();
      if (algo(t, /aviso|alerta|crecida|cruce|inundacion|desborde|temporada/)) return R.p2();
      if (algo(t, /seleccion final|configuracion final|integrad|08\b|p6/)) return R.p6();
      if (algo(t, /horizonte|cuantos dias|anticipacion|cuanto aviso|magnitud|pronostic/)) return R.p1();
      if (algo(t, /limite|limitacion|confiable|sirve para alertar|operativo/)) return R.limites();
      if (algo(t, /equipo|integrante|autor|quien hizo|quienes/)) return R.equipo();
      if (algo(t, /dato|camels|fuente|senamhi/)) return R.datos();
      if (algo(t, /metodo|protocolo|validacion|bootstrap|como se eligio/)) return R.metodo();
      const c = busca(t, CAP); if (c) return { h: `Eso está en <b>${capDe(c).n} · ${esc(capDe(c).t)}</b>.`, a: [ver(c, 'Abrir ' + capDe(c).t)] };
      return { h: 'No encontré eso en los resultados de esta página. Puedo responder sobre horizontes útiles, avisos de crecidas, aguas arriba, lluvia, Chronos-2, la selección final, métricas de un modelo (p. ej. «NSE de KNN en Tamshiyacu a 15 días») o definiciones.', a: [] };
    }
    const SUG = ['¿Cuántos días de aviso hay?', 'Mejor modelo en Racarumi', 'NSE de XGBoost en Tamshiyacu a 7 días', '¿Qué es el CSI?', '¿Ayuda la lluvia?', '¿Qué aporta San Regis?', '¿Sirve Chronos-2?', '¿Por qué Tamshiyacu da más aviso?', 'Llévame al mapa', 'Limitaciones'];
    const caja = $('#bot-msgs');
    function pinta(cls, html, acciones) {
      const d = document.createElement('div'); d.className = 'msg ' + cls; d.innerHTML = html;
      if (acciones && acciones.length) { const a = document.createElement('div'); a.className = 'acc';
        acciones.forEach(x => { const b = document.createElement('button'); b.type = 'button'; b.textContent = x.t;
          b.addEventListener('click', () => { if (x.ir) ir(x.ir); if (x.fn) x.fn(); if (innerWidth < 640) abre(false); }); a.appendChild(b); }); d.appendChild(a); }
      caja.appendChild(d); caja.scrollTop = caja.scrollHeight; return d;
    }
    function pregunta(q) {
      if (!q.trim()) return;
      pinta('yo', esc(q));
      const e = pinta('el escribe', '<i></i><i></i><i></i>');
      setTimeout(() => { e.remove(); let r; try { r = responde(q); } catch (err) { r = { h: 'Tuve un problema al buscar eso; prueba con otra pregunta.', a: [] }; } pinta('el', r.h, r.a); }, 380);
    }
    $('#bot-sug').innerHTML = SUG.map(s => `<button type="button">${esc(s)}</button>`).join('');
    $('#bot-sug').addEventListener('click', ev => { const b = ev.target.closest('button'); if (b) pregunta(b.textContent); });
    $('#bot-f').addEventListener('submit', ev => { ev.preventDefault(); const i = $('#bot-in'); pregunta(i.value); i.value = ''; });
    let saludo = false;
    function abre(si) {
      document.body.classList.toggle('bot-abierto', si); $('#bot').setAttribute('aria-hidden', String(!si));
      if (si && !saludo) { saludo = true; pinta('el', R.hola().h + ' ¿Qué quieres saber?'); }
      if (si) setTimeout(() => $('#bot-in').focus(), 150);
    }
    $('#bot-btn').addEventListener('click', () => abre(!document.body.classList.contains('bot-abierto')));
    setTimeout(() => { const b = $('#bot-btn .burbuja'); if (b) b.remove(); }, 9000);
    $('#bot-x').addEventListener('click', () => abre(false));
    return { abre, responde };
  })();

  let ini = 'sintesis';
  try { const h = decodeURIComponent(location.hash.slice(1)); if (capDe(h)) ini = h; } catch (e) { /* sin hash */ }
  ir(ini);
  window.addEventListener('hashchange', () => { const h = decodeURIComponent(location.hash.slice(1)); if (capDe(h) && h !== vista) ir(h); });
})();
