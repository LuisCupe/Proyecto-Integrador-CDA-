(function () {
  'use strict';
  const D = window.MOD;
  const EST = ['Racarumi', 'Tamshiyacu'];
  const H = D.H_CLAVE;
  const HH = Array.from({ length: 30 }, (_, i) => i + 1);
  const A = D.anticipacion;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const fmt = (x, d = 2) => (x == null || !isFinite(x)) ? '—' : Number(x).toLocaleString('es-PE', { minimumFractionDigits: d, maximumFractionDigits: d });
  const COMB = 'Combinado por horizonte';
  const colM = n => (n === COMB ? css('--ink') : (D.COLORES[n] || css('--accent')));
  const colE = e => css(e === 'Racarumi' ? '--rac' : '--tam');
  const ETQ = { NSE: 'NSE', KGE: 'KGE', MAE: 'MAE (m³/s)', RMSE: 'RMSE (m³/s)', PBIAS: 'PBIAS (%)', hab_pers: 'Habilidad frente a la persistencia', hab_clim: 'Habilidad frente a la climatología' };
  const CFG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'], locale: 'es' };
  const K_HU = 'H cota 95 % (d)', K_PUN = 'H puntual (d)', K_P05 = 'H p05 (d)', K_P95 = 'H p95 (d)', K_CAL = 'NSE ≥ 0.5 hasta (d)';
  const rangoH = r => r[K_P05] === r[K_P95] ? txtHU(r[K_P05]) : `${Math.round(r[K_P05])}–${r[K_P95] >= 30 ? '30+' : Math.round(r[K_P95])}`;
  const FCOM = D.estaciones.Racarumi.fechas_comunes;

  // ---------------------------------------------------------------- utilidades
  function base(extra = {}) {
    const ink = css('--ink-2'), grid = css('--grid');
    const eje = { gridcolor: grid, zerolinecolor: css('--line'), linecolor: css('--line'), tickfont: { color: ink, size: 11 }, title: { font: { color: ink, size: 12 } }, automargin: true };
    const l = { paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { family: css('--f-body'), color: ink, size: 12 },
      margin: { l: 56, r: 14, t: 26, b: 44 }, hovermode: 'x unified', hoverlabel: { bgcolor: css('--surface'), bordercolor: css('--line'), font: { color: css('--ink') } },
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
  const huDe = (e, n, lista = 'hu') => D.estaciones[e][lista].find(r => r.modelo === n) || {};
  const txtHU = v => v == null ? '—' : v >= 30 ? '≥ 30' : String(Math.round(v));
  function sintesis(e) { return A.sintesis.find(r => r['estación'] === e) || {}; }
  function tabla(id, filas, cols, opciones = {}) {
    const el = typeof id === 'string' ? $(id) : id;
    el.innerHTML = `<table class="t"><thead><tr>${cols.map(([k, t]) => `<th>${esc(t)}</th>`).join('')}</tr></thead><tbody>${filas.map(r => {
      const cls = opciones.marca && opciones.marca(r) ? 'mejor' : '';
      return `<tr class="${cls}">${cols.map(([k, , f]) => { const v = r[k];
        if (f) return `<td class="n" data-s="${v ?? ''}">${f(v, r)}</td>`;
        if (typeof v === 'number') return `<td class="n" data-s="${v}">${fmt(v, Math.abs(v) >= 100 ? 0 : 3)}</td>`;
        return `<td>${esc(v ?? '—')}</td>`; }).join('')}</tr>`; }).join('')}</tbody></table>`;
    ordenable($('table', el));
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
  const dotM = n => `<i class="dot" style="background:${colM(n)}"></i>${esc(n)}`;

  // ---------------------------------------------------------------- pestañas
  const VISTAS = [['resumen', 'Resumen y comparación', '--accent', 'sq'], ['Racarumi', 'Racarumi · Chancay-Lambayeque', '--rac'],
    ['Tamshiyacu', 'Tamshiyacu · Ucayali–Amazonas', '--tam'], ['anticipacion', 'Anticipación de crecidas', '--bad', 'sq'], ['metodo', 'Método', '--ink-3', 'sq']];
  let vista = 'resumen';
  const render = { resumen: vResumen, Racarumi: () => vEstacion('Racarumi'), Tamshiyacu: () => vEstacion('Tamshiyacu'), anticipacion: vAnticipacion, metodo: vMetodo };
  $('#pest').innerHTML = VISTAS.map(([id, t, c, cls]) => `<button role="tab" data-v="${id}" style="--c:var(${c})" aria-selected="${id === vista}"><i class="pt ${cls || ''}"></i>${esc(t)}</button>`).join('');
  $('#pest').addEventListener('click', ev => { const b = ev.target.closest('button'); if (b) ir(b.dataset.v); });
  function ir(v) {
    vista = v;
    $$('#pest button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.v === v)));
    try { history.replaceState(null, '', '#' + v); } catch (e) { /* vista previa */ }
    render[v](); window.scrollTo(0, 0);
  }
  const temaBtn = $('#tema');
  function aplicaTema(t) {
    if (t) document.documentElement.setAttribute('data-theme', t); else document.documentElement.removeAttribute('data-theme');
    const oscuro = t ? t === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    temaBtn.textContent = oscuro ? 'Tema claro' : 'Tema oscuro';
  }
  let temaGuardado = null; try { temaGuardado = localStorage.getItem('cda-mod-tema'); } catch (e) { /* sin almacenamiento */ }
  aplicaTema(temaGuardado);
  temaBtn.addEventListener('click', () => {
    const t = temaBtn.textContent === 'Tema claro' ? 'light' : 'dark';
    try { localStorage.setItem('cda-mod-tema', t); } catch (e) { /* sin almacenamiento */ }
    aplicaTema(t); render[vista]();
  });

  // ---------------------------------------------------------------- RESUMEN
  function vResumen() {
    const app = $('#app');
    const tarjeta = e => {
      const S = D.estaciones[e], mj = S.mejor, hc = huDe(e, mj, 'hu_c'), hf = huDe(e, mj), si = sintesis(e);
      return `<button class="card" data-ir="${e}" style="--c:var(${e === 'Racarumi' ? '--rac' : '--tam'})">
        <div class="t"><h2>${esc(e)}</h2><span class="cu">${esc(S.cuenca)} · vertiente ${S.vertiente === 'Pacífico' ? 'del Pacífico' : 'amazónica'} · ${fmt(S.area, 0)} km²</span></div>
        <div class="dos">
          <div class="big"><b>${txtHU(hc[K_HU])} d</b><span>horizonte útil para estimar la <b>magnitud</b> del caudal, cota 95 % (${esc(mj)}, fechas comunes)</span></div>
          <div class="big alt"><b>${si['anticipación útil (d)'] > 0 ? fmt(si['anticipación útil (d)'], 0) + ' d' : '0 d'}</b><span>anticipación útil para avisar un <b>nuevo cruce</b> del P95${si['anticipación útil (d)'] > 0 ? '' : ': no alcanza el criterio (POD ≥ 0.5 con FAR ≤ 0.5)'} (${esc(si['modelo (avisos)'] || '')}; ${fmt(si['aciertos'], 0)} de ${fmt(si['cruces evaluables'], 0)} cruces, FAR ${fmt(si['FAR'], 2)}${si['cruces evaluables'] < 10 ? '; exploratorio' : ''})</span></div>
        </div>
        <div class="kpis">
          <div class="kpi"><div class="l">Incertidumbre</div><div class="v">${rangoH(hc)} d</div><div class="s">H en el bootstrap, p05–p95</div></div>
          <div class="kpi"><div class="l">NSE ≥ 0.5</div><div class="v">${txtHU(hc[K_CAL])} d</div><div class="s">calidad suficiente</div></div>
          <div class="kpi"><div class="l">Prueba completa</div><div class="v">${txtHU(hf[K_HU])} d</div><div class="s">H cota 95 %</div></div>
          <div class="kpi"><div class="l">Avisos de cruces</div><div class="v">CSI ${fmt(si['CSI'], 2)}</div><div class="s">eventos; ref. ${esc(si['mejor referencia'] || '')} ${fmt(si['CSI mejor referencia'], 2)}</div></div>
        </div></button>`;
    };
    app.innerHTML = `<section class="vista">
      <div class="cab"><span class="eyebrow">Proyecto Integrador · Ciencia de Datos Ambientales · modelos base con caudal local (cuadernos 01–04)</span>
        <h1>¿Con cuántos días de anticipación se puede pronosticar el caudal?</h1>
        <p>Seis modelos (regresión lineal, Random Forest, XGBoost, KNN, MLP y LSTM) y su combinado por horizonte pronostican el caudal diario de 1 a 30 días usando <b>solo los caudales antecedentes</b> de cada estación y el calendario. Se responden dos preguntas distintas: hasta qué día se estima bien la <b>magnitud</b> del caudal (horizonte útil) y con cuánta anticipación se puede <b>avisar un cruce nuevo</b> del P95. Resultados válidos para estas dos estaciones y este experimento; haga clic en una tarjeta para ver el detalle.</p></div>
      <div class="resp">${EST.map(tarjeta).join('')}</div>
      <div class="pila" style="margin-top:14px">
        <div class="panel"><header><h2>Cómo cae el pronóstico con el horizonte</h2>
          <div class="ctrl">${seg('r-met', [['NSE', 'NSE'], ['hab_pers', 'vs persistencia'], ['hab_clim', 'vs climatología']], 'NSE', true)}${seg('r-per', [['c', 'fechas comunes'], ['f', 'prueba completa']], 'c', true)}</div>
          <span class="sub">Modelo seleccionado de cada estación (regla de selección en validación). Fechas comunes: ${fmt(FCOM.n, 0)} emisiones idénticas en las dos estaciones (${esc(FCOM.inicio)} a ${esc(FCOM.fin)}). Discontinuas: persistencia; punteadas: climatología. Banda: IC 95 % marginal.</span></header>
          <div class="cuerpo"><div id="r-curva" class="fig"></div></div></div>
        <div class="g-2">
          <div class="panel"><header><h2>¿Importa el modelo?</h2><div class="ctrl"><label>Horizonte <input type="range" id="r-h" min="1" max="30" value="7"><b class="n" id="r-hv">7 d</b></label></div>
            <span class="sub">NSE de los seis modelos y el combinado en las fechas comunes, en el horizonte elegido; discontinua: persistencia, punteada: climatología.</span></header>
            <div class="cuerpo"><div id="r-mod" class="fig"></div></div></div>
          <div class="panel"><header><h2>¿Se repite en otros periodos?</h2>
            <span class="sub">H cota 95 % del modelo seleccionado en cuatro orígenes; en cada uno, preparación e hiperparámetros se eligieron con su propio pasado.</span></header>
            <div class="cuerpo"><div id="r-est" class="fig"></div></div></div>
        </div>
        <div class="g-2">
          <div class="panel"><header><h2>H3 · Horizonte útil entre cuencas</h2></header><div class="cuerpo prosa">${D.textos_comp.h3 || ''}</div></div>
          <div class="panel"><header><h2>H4 · Horizontes largos y crecidas</h2></header><div class="cuerpo prosa">${D.textos_comp.h4 || ''}</div></div>
        </div>
        <div class="g-2">
          <div class="panel"><header><h2>Sensibilidad a la longitud de la historia</h2>${seg('r-memh', [['1', 'h = 1'], ['7', 'h = 7'], ['15', 'h = 15']], '1')}
            <span class="sub">XGBoost con L días de historia; ✕: L = 30 sin calendario. Mide información predictiva, no la memoria física del río.</span></header>
            <div class="cuerpo"><div id="r-mem" class="fig"></div><details class="lect"><summary>Lectura</summary><div class="prosa">${D.textos_comp.memoria || ''}</div></details></div></div>
          <div class="panel"><header><h2>Estabilidad</h2></header><div class="cuerpo prosa">${D.textos_comp.estabilidad || ''}</div></div>
        </div>
        <div class="panel"><header><h2>Tabla comparativa de los seis modelos (3.6)</h2><span class="sub">Fechas comunes. Ordene haciendo clic en las columnas. El criterio de selección es el NSE medio del bloque de selección (2012–2015) con la regla de equivalencia; la prueba solo confirma.</span></header>
          <div class="cuerpo"><div class="tw" id="r-tabla"></div><details class="lect"><summary>Lectura de la tabla</summary><div class="prosa">${D.textos_comp.tabla || ''}</div></details>
            <details class="lect"><summary>Qué aporta cada familia de modelos</summary><div class="tw" id="r-pares"></div><div class="prosa">${D.textos_comp.familias || ''}</div></details></div></div>
        <div class="panel"><header><h2>Selección del modelo y respuesta a la pregunta</h2></header><div class="cuerpo prosa">${D.textos_comp.seleccion || ''}</div></div>
      </div></section>`;
    $$('.card', app).forEach(b => b.addEventListener('click', () => ir(b.dataset.ir)));
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
        : [{ type: 'line', x0: 0.5, x1: 30.5, y0: 0, y1: 0, line: { color: css('--ink'), width: 1 } }];
      const ann = [];
      for (const e of EST) {
        const hu = huDe(e, D.estaciones[e].mejor, per === 'c' ? 'hu_c' : 'hu')[K_HU];
        if (hu < 30) sh.push({ type: 'line', x0: hu + 0.5, x1: hu + 0.5, yref: 'paper', y0: 0, y1: 1, line: { color: colE(e), width: 1.4, dash: 'dashdot' } });
        ann.push({ x: hu < 30 ? hu + 0.7 : 29.8, xanchor: hu < 30 ? 'left' : 'right', yref: 'paper', y: e === 'Racarumi' ? 0.06 : 0.97, text: `${e}: H cota ${txtHU(hu)} d`, showarrow: false, font: { color: colE(e), size: 12 } });
      }
      plot('#r-curva', tr, base({ xaxis: { title: { text: 'Horizonte de pronóstico (días)' }, range: [0.5, 30.5], dtick: 5 }, yaxis: { title: { text: ETQ[met] } }, shapes: sh, annotations: ann }), 400);
    };
    onSeg(app, 'r-met', v => { met = v; curva(); }); onSeg(app, 'r-per', v => { per = v; curva(); }); curva();
    const modBar = h => {
      $('#r-hv').textContent = h + ' d';
      const tr = EST.map((e, i) => { const S = D.estaciones[e]; return { type: 'bar', x: S.modelos, y: S.modelos.map(n => S.met_c[n].NSE[h - 1]), name: e, marker: { color: S.modelos.map(colM) },
        xaxis: i ? 'x2' : 'x', yaxis: i ? 'y2' : 'y', text: S.modelos.map(n => fmt(S.met_c[n].NSE[h - 1], 3)), textposition: 'outside', cliponaxis: false, hovertemplate: '%{x}: NSE %{y:.3f}<extra>' + e + '</extra>', showlegend: false }; });
      const rng = i => { const S = D.estaciones[EST[i]], v = S.modelos.map(n => S.met_c[n].NSE[h - 1]).concat([S.ref_c.pers[h - 1], S.ref_c.clim[h - 1]]); const lo = Math.min(...v), hi = Math.max(...v); const pad = Math.max(0.02, (hi - lo) * 0.25); return [Math.max(-1, lo - pad), Math.min(1.02, hi + pad)]; };
      const ref = i => { const S = D.estaciones[EST[i]], xr = i ? 'x2' : 'x', yr = i ? 'y2' : 'y'; return [
        { type: 'line', xref: xr + ' domain', x0: 0, x1: 1, yref: yr, y0: S.ref_c.pers[h - 1], y1: S.ref_c.pers[h - 1], line: { color: colM('Persistencia'), dash: 'dash', width: 1.4 } },
        { type: 'line', xref: xr + ' domain', x0: 0, x1: 1, yref: yr, y0: S.ref_c.clim[h - 1], y1: S.ref_c.clim[h - 1], line: { color: colM('Climatología'), dash: 'dot', width: 1.6 } }]; };
      plot('#r-mod', tr, base({ grid: { rows: 1, columns: 2, pattern: 'independent' }, hovermode: 'closest', margin: { l: 50, r: 10, t: 34, b: 100 },
        xaxis: { tickangle: -35 }, xaxis2: { tickangle: -35 }, yaxis: { title: { text: 'NSE' }, range: rng(0) }, yaxis2: { range: rng(1) }, shapes: ref(0).concat(ref(1)),
        annotations: [{ text: '<b>Racarumi</b>', xref: 'x domain', yref: 'paper', x: 0.5, y: 1.07, showarrow: false, font: { color: colE('Racarumi') } },
          { text: '<b>Tamshiyacu</b>', xref: 'x2 domain', yref: 'paper', x: 0.5, y: 1.07, showarrow: false, font: { color: colE('Tamshiyacu') } }] }), 380);
    };
    $('#r-h').addEventListener('input', ev => modBar(+ev.target.value)); modBar(7);
    // estabilidad
    const tr = EST.map(e => { const S = D.estaciones[e], s = S.estabilidad.filter(r => r.modelo === S.mejor);
      return { type: 'bar', x: s.map(r => 'prueba ' + r.prueba), y: s.map(r => r[K_HU]), name: `${e} · ${S.mejor}`, marker: { color: colE(e) },
        error_y: { type: 'data', symmetric: false, array: s.map(r => Math.max(0, r[K_P95] - r[K_HU])), arrayminus: s.map(() => 0), color: css('--ink-2'), thickness: 1.2, width: 3 },
        text: s.map(r => txtHU(r[K_HU])), textposition: 'outside', cliponaxis: false, hovertemplate: '%{x}: H cota %{text} d<extra>' + e + '</extra>' }; });
    plot('#r-est', tr, base({ barmode: 'group', hovermode: 'closest', yaxis: { title: { text: 'H cota 95 % (días); bigote: hasta p95' }, range: [0, 34] }, legend: { orientation: 'h', y: -0.18 } }), 380);
    const mem = h => {
      const Ls = ['1', '3', '7', '15', '30', '60'];
      plot('#r-mem', EST.map(e => ({ x: Ls.map(Number), y: Ls.map(L => D.estaciones[e].memoria[L].hab_pers[h - 1]), name: e, mode: 'lines+markers', line: { color: colE(e), width: 2.4 }, marker: { size: 8 }, hovertemplate: 'L = %{x} d: %{y:.3f}' }))
        .concat(EST.map(e => ({ x: [30], y: [D.estaciones[e].memoria['30 sin calendario'].hab_pers[h - 1]], name: `${e}: sin calendario`, mode: 'markers', marker: { symbol: 'x', size: 11, color: colE(e), line: { width: 2 } }, hovertemplate: 'L = 30 sin calendario: %{y:.3f}' }))),
        base({ hovermode: 'closest', xaxis: { type: 'log', title: { text: 'Días de historia que ve el modelo (L)' }, tickvals: [1, 3, 7, 15, 30, 60] }, yaxis: { title: { text: 'Habilidad frente a la persistencia' } } }), 340);
    };
    onSeg(app, 'r-memh', v => mem(+v)); mem(1);
    const cols = [['estación', 'Estación'], ['modelo', 'Modelo', (v, r) => dotM(v) + (D.estaciones[r['estación']].mejor === v ? ' <span class="chip ok">seleccionado</span>' : '')],
      ['NSE medio selección', 'NSE selección'], ['NSE h=1', 'NSE 1 d'], ['NSE h=7', 'NSE 7 d'], ['NSE h=30', 'NSE 30 d'], ['MAE h=7 (m³/s)', 'MAE 7 d'],
      ['H cota 95 % (d)', 'H cota', v => txtHU(v)], ['H puntual (d)', 'H puntual', v => txtHU(v)], ['H p05–p95 (d)', 'H p05–p95'], ['NSE ≥ 0.5 hasta (d)', 'NSE≥0.5 (d)', v => txtHU(v)],
      ['H cota, prueba completa (d)', 'H cota completa', v => txtHU(v)], ['CSI diario h=3', 'CSI diario 3 d']];
    tabla('#r-tabla', D.comparativa, cols, { marca: r => D.estaciones[r['estación']].mejor === r.modelo });
    tabla('#r-pares', D.pares, [['estación', 'Estación'], ['comparación', 'Comparación'], ['Δ NSE medio selección', 'Δ NSE selección'], ['Δ NSE h=1', 'Δ NSE 1 d'],
      ['Δ NSE h=7', 'Δ NSE 7 d'], ['Δ NSE h=30', 'Δ NSE 30 d'], ['Δ H puntual (d)', 'Δ H puntual (d)', v => fmt(v, 0)]]);
    $$('#r-tabla td').forEach(td => { if (td.innerHTML.includes('class="dot"')) td.classList.remove('n'); });
  }

  // ---------------------------------------------------------------- ESTACIÓN
  function vEstacion(e) {
    const S = D.estaciones[e], app = $('#app'), mj = S.mejor, colorE = e === 'Racarumi' ? '--rac' : '--tam';
    const dec = e === 'Tamshiyacu' ? 0 : 1, U = 'm³/s';
    const hf = huDe(e, mj), T = S.textos;
    const secs = [['s-exp', 'Explorador'], ['s-hor', 'Desempeño'], ['s-hu', 'Horizontes'], ['s-crec', 'Crecidas'], ['s-ev', 'Eventos'], ['s-est', 'Estabilidad'], ['s-mem', 'Historia'], ['s-imp', 'Variables'], ['s-conc', 'Conclusiones']];
    const opM = (sel, extra = []) => extra.concat(S.modelos).map(n => `<option ${n === sel ? 'selected' : ''}>${esc(n)}</option>`).join('');
    app.innerHTML = `<section class="vista" style="--c:var(${colorE})">
      <div class="ficha"><div><span class="eyebrow">${esc(S.cuenca)} · vertiente ${S.vertiente === 'Pacífico' ? 'del Pacífico' : 'amazónica'} · ${fmt(S.area, 0)} km² · registro ${esc(S.periodo)}</span><h1>${esc(e)}</h1></div>
        <div class="kpis">
          <div class="kpi"><div class="l">Horizonte útil</div><div class="v" style="color:var(${colorE})">${txtHU(hf[K_HU])} d</div><div class="s">${esc(mj)}, cota 95 %</div></div>
          <div class="kpi"><div class="l">Incertidumbre</div><div class="v">${rangoH(hf)} d</div><div class="s">H puntual ${txtHU(hf[K_PUN])} d; p05–p95</div></div>
          <div class="kpi"><div class="l">NSE ≥ 0.5</div><div class="v">${txtHU(hf[K_CAL])} d</div><div class="s">calidad suficiente</div></div>
          <div class="kpi"><div class="l">P95 (entrenam.)</div><div class="v">${fmt(S.P95, dec)}</div><div class="s">${U}</div></div>
        </div></div>
      <nav class="indice">${secs.map(([id, t]) => `<a href="#${id}">${t}</a>`).join('')}</nav>

      <div class="panel sec" id="s-exp"><header><h2>Explorador de pronósticos</h2>
        <div class="ctrl"><label>Modelo <select id="e-mod">${opM(mj, ['Persistencia', 'Climatología'])}</select></label>
          ${seg('e-h', H.map(h => [h, h + ' d']), 3)}
          <label><input type="checkbox" id="e-pers"> comparar con persistencia</label>
          <label>Ir a <select id="e-ev"><option value="">todo el periodo de prueba</option>${S.eventos.map((v, i) => `<option value="${i}">crecida ${v.fecha} (${fmt(v.pico, 0)} ${U})</option>`).join('')}</select></label></div>
        <span class="sub">Negro: caudal observado. En color: lo pronosticado para cada día, emitido <b id="e-hl">3</b> días antes. Use la barra inferior o arrastre para hacer zoom.</span></header>
        <div class="cuerpo"><div id="e-graf" class="fig"></div><div class="cifras" id="e-cif"></div></div></div>

      <div class="g-2" style="margin-top:16px">
        <div class="panel sec" id="s-hor"><header><h2>Desempeño por horizonte</h2>
          <div class="ctrl"><select id="h-met">${Object.entries(ETQ).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
            <label>Banda IC 95 % <select id="h-ic">${opM(mj)}</select></label></div>
          <span class="sub">Seis modelos y el combinado en prueba (2016–fin). Haga clic en la leyenda para ocultar curvas. Banda: IC 95 % marginal por horizonte.</span></header>
          <div class="cuerpo"><div id="h-graf" class="fig"></div><details class="lect"><summary>Lectura</summary><div class="prosa">${T.prueba || ''}${T.fig02 || ''}</div></details>
            <details class="lect" open><summary>Regla de selección (validación 2012–2015)</summary><div class="tw" id="h-sel"></div><div class="prosa">${T.seleccion || ''}</div></details>
            <details class="lect"><summary>Ajuste, presupuesto de búsqueda, semillas y retransformación</summary><div class="tw" id="h-pres"></div><div class="tw" id="h-sem"></div><div class="prosa">${T.ajuste || ''}${T.semillas || ''}${T.retransformacion || ''}</div></details></div></div>
        <div class="panel sec" id="s-hu"><header><h2>Horizontes por modelo</h2>
          <span class="sub">H cota 95 % (cifra de las conclusiones); H puntual con su rango bootstrap p05–p95; NSE ≥ 0.5 (complementario). Una barra en 30 significa "30 o más".</span></header>
          <div class="cuerpo"><div id="hu-graf" class="fig"></div><details class="lect" open><summary>Lectura</summary><div class="prosa">${T.horizonte || ''}</div></details>
            <details class="lect"><summary>Fechas comunes y longitud de bloque</summary><div class="tw" id="hu-bloq"></div><div class="prosa">${T.comun || ''}</div></details></div></div>
      </div>

      <div class="panel sec" id="s-crec" style="margin-top:16px"><header><h2>Caudales elevados (sobre el P95 = ${fmt(S.P95, dec)} ${U})</h2>
        <div class="ctrl"><label>Modelo <select id="c-mod">${opM(mj)}</select></label>${seg('c-modo', [['rel', 'error relativo'], ['abs', 'error absoluto']], 'rel', true)}</div>
        <span class="sub">(a) Error en días altos y ordinarios; (b) detección diaria de días sobre el P95 (no distingue avisos de eventos nuevos: ver la pestaña Anticipación); (c) observado frente a pronosticado en el horizonte elegido en el explorador.</span></header>
        <div class="cuerpo"><div class="g-2"><div id="c-err" class="fig"></div><div id="c-det" class="fig"></div></div>
          <div class="g-2"><div id="c-disp" class="fig"></div><div class="prosa">${T.crecidas || ''}</div></div>
          <details class="lect"><summary>Las mayores crecidas de la prueba</summary><div class="prosa">${T.fig05 || ''}${T.fig04 || ''}</div></details></div></div>

      <div class="panel sec" id="s-ev" style="margin-top:16px"><header><h2>Errores por evento (${esc(mj)})</h2>${seg('ev-h', [['1', '1 d'], ['3', '3 d'], ['7', '7 d']], '1')}
        <span class="sub">Todos los eventos de la prueba. Errores firmados (negativo = subestimación): pronóstico para el día del pico emitido h días antes y máximo pronosticado en la ventana del evento extendida h + 3 días, con su desfase (positivo = tarde).</span></header>
        <div class="cuerpo"><div class="tw" id="ev-res"></div><div class="tw" id="ev-tabla"></div><details class="lect" open><summary>Lectura</summary><div class="prosa">${T.eventos || ''}</div></details></div></div>

      <div class="g-2" style="margin-top:16px">
        <div class="panel sec" id="s-est"><header><h2>Estabilidad con varios orígenes</h2>
          <span class="sub">En cada origen, ε, escalones, P95, climatología, hiperparámetros, épocas y semillas se eligieron con su propio pasado. Barra: H cota 95 %; bigote: hasta p95.</span></header>
          <div class="cuerpo"><div id="est-graf" class="fig"></div><details class="lect" open><summary>Lectura</summary><div class="prosa">${T.estabilidad || ''}</div></details></div></div>
        <div class="panel"><header><h2>Sensibilidad a los registros con escalones</h2></header>
          <div class="cuerpo"><div class="tw" id="sens-tabla"></div><div class="prosa">${T.sensibilidad || ''}</div></div></div>
      </div>

      <div class="g-2" style="margin-top:16px">
        <div class="panel sec" id="s-mem"><header><h2>Sensibilidad a la longitud de la historia</h2>${seg('m-met', [['hab_pers', 'vs persistencia'], ['NSE', 'NSE']], 'hab_pers', true)}
          <span class="sub">XGBoost con L días de historia (mismas muestras de prueba) y L = 30 sin calendario (rojo punteado). Mide información predictiva, no memoria física.</span></header>
          <div class="cuerpo"><div id="m-graf" class="fig"></div><details class="lect" open><summary>Lectura</summary><div class="prosa">${T.memoria || ''}</div></details></div></div>
        <div class="panel sec" id="s-imp"><header><h2>Qué información usa el modelo</h2>
          <span class="sub">Aumento del error (%) al desordenar cada grupo de variables en la prueba (XGBoost). Mide cuánto usa el modelo cada grupo, no causalidad. Escala de color logarítmica.</span></header>
          <div class="cuerpo"><div id="i-graf" class="fig"></div><details class="lect" open><summary>Lectura</summary><div class="prosa">${T.importancia || ''}</div></details></div></div>
      </div>
      <div class="panel sec" id="s-conc" style="margin-top:16px"><header><h2>Conclusiones para ${esc(e)}</h2></header><div class="cuerpo prosa">${T.conclusiones || ''}</div></div>
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
      const tr = [{ x: xs, y: S.serie.q, name: 'Observado', line: { color: css('--ink'), width: 1.8 }, hovertemplate: '%{y:,.' + dec + 'f} ' + U }];
      if ($('#e-pers').checked && n !== 'Persistencia') tr.push({ x: s.x, y: valores(hSel, 'Persistencia'), name: `Persistencia (h = ${hSel} d)`, line: { color: colM('Persistencia'), width: 1.2, dash: 'dash' }, hovertemplate: '%{y:,.' + dec + 'f} ' + U });
      tr.push({ x: s.x, y: valores(hSel, n), name: `${n} (h = ${hSel} d)`, line: { color: colM(n), width: 1.8 }, hovertemplate: '%{y:,.' + dec + 'f} ' + U });
      plot('#e-graf', tr, base({ xaxis: { type: 'date', rangeslider: { visible: true, thickness: 0.08, bgcolor: css('--surface-2') }, range: rango || undefined },
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
      for (const n of S.modelos) tr.push({ x: HH, y: S.met[n][met], name: n, line: { color: colM(n), width: n === mj ? 3 : 1.6, dash: n === COMB ? 'dot' : 'solid' }, hovertemplate: '%{y:.3f}' });
      const sh = (met === 'hab_pers' || met === 'hab_clim' || met === 'PBIAS') ? [{ type: 'line', x0: 0.5, x1: 30.5, y0: 0, y1: 0, line: { color: css('--ink'), width: 1 } }]
        : met === 'NSE' ? [{ type: 'line', x0: 0.5, x1: 30.5, y0: 0.5, y1: 0.5, line: { color: css('--ink-3'), width: 1, dash: 'dashdot' } }] : [];
      plot('#h-graf', tr, base({ xaxis: { title: { text: 'Horizonte (días)' }, dtick: 5, range: [0.5, 30.5] }, yaxis: { title: { text: ETQ[met] } }, shapes: sh }), 420);
    };
    $('#h-met').addEventListener('change', hor); $('#h-ic').addEventListener('change', hor); hor();

    tabla('#h-pres', S.presupuesto, [['modelo', 'Modelo', v => dotM(v)], ['combinaciones', 'Combinaciones', v => fmt(v, 0)], ['segundos', 'Segundos', v => fmt(v, 0)], ['NSE_sel_mejor', 'NSE selección, mejor'], ['NSE_sel_peor', 'NSE selección, peor']]);
    tabla('#h-sel', S.seleccion, [['modelo', 'Modelo', (v, r) => dotM(v) + (r.seleccionado ? ' <span class="chip ok">seleccionado</span>' : '')], ['NSE medio selección', 'NSE medio'],
      ['diferencia con el mejor', 'Diferencia'], ['IC90 inferior', 'IC 90 % inf.'], ['IC90 superior', 'IC 90 % sup.'], ['clase', 'Clase']], { marca: r => r.seleccionado });
    tabla('#h-sem', S.semillas, [['modelo', 'Modelo', v => dotM(v)], ['semilla', 'Semilla'], ['H puntual (d)', 'H puntual', v => txtHU(v)], ['NSE h=1', 'NSE 1 d'], ['NSE h=7', 'NSE 7 d'], ['NSE h=30', 'NSE 30 d']]);
    const claves = [[K_HU, 'H cota 95 %', css('--accent')], [K_PUN, 'H puntual', css('--ink-3')], [K_CAL, 'NSE ≥ 0.5', css('--good')]];
    const trHU = claves.map(([k, t, c], j) => ({ type: 'bar', orientation: 'h', y: S.hu.map(r => r.modelo), x: S.hu.map(r => r[k]), name: t, marker: { color: c },
      text: S.hu.map(r => txtHU(r[k])), textposition: 'outside', cliponaxis: false, hovertemplate: '%{y}: %{text} d<extra>' + t + '</extra>',
      error_x: j === 1 ? { type: 'data', symmetric: false, array: S.hu.map(r => Math.max(0, r[K_P95] - r[k])), arrayminus: S.hu.map(r => Math.max(0, r[k] - r[K_P05])), color: css('--ink-2'), thickness: 1.2, width: 3 } : undefined }));
    plot('#hu-graf', trHU, base({ barmode: 'group', hovermode: 'closest', xaxis: { title: { text: 'Días' }, range: [0, 34] }, yaxis: { autorange: 'reversed' }, margin: { l: 150, r: 20, t: 20, b: 44 } }), 420);
    tabla('#hu-bloq', S.bloques, [['bloque', 'Bloque bootstrap'], [K_HU, 'H cota', v => txtHU(v)], [K_P05, 'p05', v => txtHU(v)], ['H mediana (d)', 'Mediana', v => txtHU(v)], [K_P95, 'p95', v => txtHU(v)], ['P(H ≥ 30)', 'P(H ≥ 30)']]);

    let modoErr = 'rel';
    const crec = () => {
      const n = $('#c-mod').value, c = S.crec[n], p = S.crec['Persistencia'], ka = modoErr === 'rel' ? 'error_rel_altos' : 'MAE_altos', ko = modoErr === 'rel' ? 'error_rel_ordinarios' : 'MAE_ordinarios';
      const un = modoErr === 'rel' ? '%' : U, fm = modoErr === 'rel' ? '%{y:.1f} %' : '%{y:,.0f} ' + U;
      plot('#c-err', [
        { x: HH, y: c[ka], name: `${n}: días > P95`, line: { color: colM(n), width: 2.6 }, hovertemplate: fm },
        { x: HH, y: c[ko], name: `${n}: ordinarios`, line: { color: colM(n), width: 1.3, dash: 'dot' }, hovertemplate: fm },
        { x: HH, y: p[ka], name: 'Persistencia: días > P95', line: { color: colM('Persistencia'), width: 2, dash: 'dash' }, hovertemplate: fm },
        { x: HH, y: p[ko], name: 'Persistencia: ordinarios', line: { color: colM('Persistencia'), width: 1, dash: 'dot' }, hovertemplate: fm }],
      base({ title: { text: modoErr === 'rel' ? '(a) Error relativo mediano' : '(a) Error absoluto medio (MAE)', font: { size: 13 }, x: 0.01 }, xaxis: { title: { text: 'Horizonte (días)' }, dtick: 5 }, yaxis: { title: { text: un }, tickformat: modoErr === 'rel' ? '' : ',.0f' }, margin: { l: 60, r: 10, t: 40, b: 44 } }), 340);
      plot('#c-det', [
        { x: HH, y: c.CSI, name: `CSI ${n}`, line: { color: colM(n), width: 2.6 }, hovertemplate: '%{y:.2f}' },
        { x: HH, y: c.POD, name: 'POD (aciertos)', line: { color: css('--good'), width: 1.4 }, hovertemplate: '%{y:.2f}' },
        { x: HH, y: c.FAR, name: 'FAR (falsas alarmas)', line: { color: css('--bad'), width: 1.4 }, hovertemplate: '%{y:.2f}' },
        { x: HH, y: p.CSI, name: 'CSI persistencia', line: { color: colM('Persistencia'), width: 2, dash: 'dash' }, hovertemplate: '%{y:.2f}' }],
      base({ title: { text: '(b) Detección diaria de días sobre el P95', font: { size: 13 }, x: 0.01 }, xaxis: { title: { text: 'Horizonte (días)' }, dtick: 5 }, yaxis: { range: [0, 1.02] }, margin: { l: 44, r: 10, t: 40, b: 44 } }), 340);
      disp();
    };
    const disp = () => {
      const n = $('#c-mod').value, s = serieH(hSel), v = S.pred.h[hSel].mod[n];
      const o = s.ms.map(obsEn), alto = o.map(x => x != null && x > S.P95);
      const tr = [false, true].map(a => ({ type: 'scattergl', mode: 'markers', x: o.filter((_, i) => alto[i] === a), y: v.filter((_, i) => alto[i] === a),
        name: a ? 'días > P95' : 'días ordinarios', marker: { size: a ? 6 : 4, color: a ? css('--bad') : colM(n), opacity: a ? 0.85 : 0.35 }, hovertemplate: 'obs %{x:,.' + dec + 'f} · pron %{y:,.' + dec + 'f}<extra></extra>' }));
      const val = o.filter(x => x != null).concat(v.filter(x => x != null));
      const mx = Math.max(...val) * 1.03, mn = e === 'Tamshiyacu' ? Math.min(...val) * 0.95 : 0;
      tr.push({ x: [mn, mx], y: [mn, mx], mode: 'lines', line: { color: css('--ink-3'), dash: 'dash', width: 1 }, name: '1:1', hoverinfo: 'skip' });
      plot('#c-disp', tr, base({ title: { text: `(c) ${n}, ${hSel} días de anticipación`, font: { size: 13 }, x: 0.01 }, hovermode: 'closest', xaxis: { title: { text: 'Observado (' + U + ')' }, range: [mn, mx], tickformat: ',.0f' }, yaxis: { title: { text: 'Pronosticado (' + U + ')' }, range: [mn, mx], tickformat: ',.0f' }, margin: { l: 64, r: 10, t: 40, b: 44 },
        shapes: [{ type: 'line', x0: S.P95, x1: S.P95, yref: 'paper', y0: 0, y1: 1, line: { color: css('--bad'), dash: 'dot', width: 1 } }, { type: 'line', y0: S.P95, y1: S.P95, xref: 'paper', x0: 0, x1: 1, line: { color: css('--bad'), dash: 'dot', width: 1 } }] }), 380);
    };
    $('#c-mod').addEventListener('change', crec); onSeg(app, 'c-modo', v => { modoErr = v; crec(); }); crec();

    const evT = h => { tabla('#ev-res', S.eventos_res.filter(r => r.h === h), [['eventos con pronóstico', 'Eventos', v => fmt(v, 0)], ['error firmado mediano (m³/s)', 'Error firmado mediano'],
        ['error relativo firmado mediano (%)', 'Error rel. mediano (%)', v => fmt(v, 1)], ['eventos subestimados en el pico', 'Subestimados', v => fmt(v, 0)],
        ['desfase p25 (d)', 'Desfase p25', v => fmt(v, 0)], ['desfase mediano (d)', 'Desfase mediano', v => fmt(v, 0)], ['desfase p75 (d)', 'Desfase p75', v => fmt(v, 0)], ['eventos con desfase = h', 'Desfase = h', v => fmt(v, 0)]]);
      tabla('#ev-tabla', S.eventos_pron.filter(r => r.h === h), [['inicio', 'Inicio'], ['pico obs (m³/s)', 'Pico obs.'], ['pronóstico para el pico', 'Pron. para el pico'],
        ['error firmado en el pico (m³/s)', 'Error firmado'], ['error relativo firmado en el pico (%)', 'Error rel. (%)', v => fmt(v, 1)], ['máximo pronosticado', 'Máx. pronosticado'],
        ['error relativo firmado del máximo (%)', 'Error rel. máx. (%)', v => fmt(v, 1)], ['desfase del máximo (d)', 'Desfase (d)', v => fmt(v, 0)]]); };
    onSeg(app, 'ev-h', v => evT(+v)); evT(1);

    const cortes = [...new Set(S.estabilidad.map(r => r.prueba))];
    const mods = [...new Set(S.estabilidad.map(r => r.modelo))];
    const fe = (c, n) => S.estabilidad.find(r => r.prueba === c && r.modelo === n) || {};
    plot('#est-graf', mods.map(n => ({ type: 'bar', x: cortes.map(c => 'prueba ' + c), y: cortes.map(c => fe(c, n)[K_HU]),
      error_y: { type: 'data', symmetric: false, array: cortes.map(c => Math.max(0, (fe(c, n)[K_P95] ?? 0) - (fe(c, n)[K_HU] ?? 0))), arrayminus: cortes.map(() => 0), color: css('--ink-2'), thickness: 1, width: 2 },
      name: n, marker: { color: colM(n) }, text: cortes.map(c => txtHU(fe(c, n)[K_HU])), textposition: 'outside', cliponaxis: false })),
    base({ barmode: 'group', hovermode: 'closest', yaxis: { title: { text: 'H cota 95 % (días)' }, range: [0, 34] } }), 360);
    if (S.sens_resumen.length) tabla('#sens-tabla', S.sens_resumen, [['indicador', 'Indicador'], ['solo años sin escalones', 'Solo años sin escalones'], ['controles: mínimo', 'Controles: mín.'],
      ['p25', 'p25'], ['mediana', 'Mediana'], ['p75', 'p75'], ['máximo', 'Máx.'], ['controles ≤ variante restringida (%)', 'Controles ≤ variante (%)', v => fmt(v, 0)]]);
    else $('#sens-tabla').innerHTML = '<p class="prosa">Esta estación no tiene escalones de nivel: el análisis no aplica.</p>';

    const memG = met => {
      const Ls = ['1', '3', '7', '15', '30', '60', '30 sin calendario'], pal = ['#440154', '#3b528b', '#21918c', '#27ad81', '#5ec962', '#bddf26', '#d62728'];
      plot('#m-graf', Ls.map((L, i) => ({ x: HH, y: S.memoria[L][met], name: `L = ${L}`, line: { color: pal[i], width: L === '1' || L === '3' ? 2.6 : 1.6, dash: i === 6 ? 'dot' : 'solid' }, hovertemplate: '%{y:.3f}' })),
        base({ xaxis: { title: { text: 'Horizonte (días)' }, dtick: 5 }, yaxis: { title: { text: met === 'NSE' ? 'NSE' : 'Habilidad frente a la persistencia' } } }), 360);
    };
    onSeg(app, 'm-met', memG); memG('hab_pers');
    const z = S.imp.v.map(r => r.map(x => Math.log10(Math.max(x, 0) + 1)));
    plot('#i-graf', [{ type: 'heatmap', z, x: S.imp.h.map(h => h.replace('h=', '') + ' d'), y: S.imp.grupos, text: S.imp.v.map(r => r.map(x => fmt(x, 0) + ' %')), texttemplate: '%{text}',
      hovertemplate: '%{y}<br>horizonte %{x}: +%{text}<extra></extra>', colorscale: 'Viridis', showscale: false, xgap: 2, ygap: 2 }],
    base({ hovermode: 'closest', xaxis: { title: { text: 'Horizonte' } }, yaxis: { autorange: 'reversed' }, margin: { l: 190, r: 10, t: 10, b: 44 } }), 330);
  }

  // ---------------------------------------------------------------- ANTICIPACIÓN
  function vAnticipacion() {
    const app = $('#app'), T = A.textos;
    const avisa = e => (A.sintesis.find(r => r['estación'] === e) || {})['modelo (avisos)'];
    app.innerHTML = `<section class="vista">
      <div class="cab"><span class="eyebrow">Ampliación metodológica · cuaderno 04 · verificación por eventos</span>
        <h1>¿Con cuántos días reales de anticipación se puede avisar un nuevo cruce del P95?</h1>
        <p>Solo cuentan avisos emitidos <b>antes</b> del cruce, desde días en que el río llevaba 7 días observados bajo el umbral. La anticipación es <b>real</b> (fecha del cruce − fecha de emisión del primer aviso correcto), y detecciones, omisiones y falsas alarmas se cuentan en las mismas unidades (eventos y episodios de aviso). Un vacío nunca cuenta como día bajo. El P95 es un umbral estadístico, no oficial.</p></div>
      <div class="pila">
        <div class="panel"><header><h2>Magnitud frente a anticipación de eventos nuevos</h2><span class="sub">Magnitud: modelo seleccionado en validación (H cota 95 %). Avisos: modelo con mayor CSI calibrado en validación (con FAR ≤ 0.5) y su regla.</span></header>
          <div class="cuerpo"><div class="tw" id="a-sint"></div><div class="prosa">${T.conclusiones || ''}</div></div></div>
        <div class="panel"><header><h2>Detección según la anticipación real exigida</h2>
          <div class="ctrl">${seg('a-est', EST.map(e => [e, e]), 'Racarumi', true)}<label>Modelo <select id="a-mod"></select></label>${seg('a-reg', [['calibrada', 'regla calibrada'], ['fija (u = P95, h_max = 30)', 'regla fija (u = P95)']], 'calibrada', true)}</div>
          <span class="sub">POD(A): cruces avisados con al menos A días reales de anticipación, entre los cruces con emisiones elegibles los A días previos. CSI(A) incluye las falsas alarmas del sistema (no dependen de A). Discontinuas: tendencia de 3 días.</span></header>
          <div class="cuerpo"><div class="g-2"><div id="a-curva" class="fig"></div><div id="a-n" class="fig"></div></div><div class="cifras" id="a-cif"></div>
            <details class="lect" open><summary>Lectura</summary><div class="prosa">${T.prueba || ''}${T.fig01 || ''}</div></details></div></div>
        <div class="panel"><header><h2>Todos los candidatos en prueba</h2>${seg('a-est3', EST.map(e => [e, e]), 'Racarumi', true)}
          <span class="sub">Regla calibrada en validación (f × P95 y h_max). Conteos de eventos y episodios; días de aviso por año como carga del sistema.</span></header>
          <div class="cuerpo"><div class="tw" id="a-todos"></div></div></div>
        <div class="panel"><header><h2>Catálogo de cruces</h2>${seg('a-est2', EST.map(e => [e, e]), 'Racarumi', true)}
          <span class="sub">Modelo para avisos. Error de fecha: primer día con pronóstico sobre el P95 − día del cruce (positivo = tarde; vacío si la trayectoria no cruza el P95).</span></header>
          <div class="cuerpo"><div class="tw" id="a-ev"></div><details class="lect" open><summary>Lectura</summary><div class="prosa">${T.eventos_prueba || ''}${T.fig02 || ''}</div></details></div></div>
        <div class="g-2">
          <div class="panel"><header><h2>Cruces disponibles y calibración</h2></header><div class="cuerpo"><div class="tw" id="a-cruces"></div><div class="prosa">${T.eventos || ''}${T.calibracion || ''}</div></div></div>
          <div class="panel"><header><h2>Sensibilidad, fechas comunes y límites</h2></header><div class="cuerpo"><div class="tw" id="a-sens"></div><div class="tw" id="a-comun"></div><div class="prosa">${T.sensibilidad || ''}${T.comun || ''}${T.limitaciones || ''}</div></div></div>
        </div>
      </div></section>`;
    tabla('#a-sint', A.sintesis, [['estación', 'Estación'], ['modelo (magnitud)', 'Modelo (magnitud)', v => dotM(v)], ['H cota 95 % magnitud (d)', 'H magnitud (d)', v => txtHU(v)],
      ['modelo (avisos)', 'Modelo (avisos)', v => dotM(v)], ['cruces evaluables', 'Cruces', v => fmt(v, 0)], ['aciertos', 'Aciertos', v => fmt(v, 0)], ['falsas alarmas', 'Falsas alarmas', v => fmt(v, 0)],
      ['POD', 'POD'], ['FAR', 'FAR'], ['CSI', 'CSI'], ['anticipación útil (d)', 'Anticipación útil (d)', v => fmt(v, 0)], ['anticipación real mediana (d)', 'Anticipación mediana (d)', v => fmt(v, 0)],
      ['mejor referencia', 'Mejor referencia'], ['CSI mejor referencia', 'CSI ref.'], ['carácter', 'Carácter']]);
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
        shapes: [{ type: 'line', x0: 0.5, x1: 30.5, y0: 0.5, y1: 0.5, line: { color: css('--ink-3'), dash: 'dashdot', width: 1 } }] }), 380);
      plot('#a-n', [
        { type: 'bar', x: K, y: r.aciertos, name: 'Avisados con ≥ A días', marker: { color: css('--good') } },
        { type: 'bar', x: K, y: r.evaluables.map((v, i) => v - r.aciertos[i]), name: 'No avisados con ≥ A días', marker: { color: css('--warn') } }],
      base({ title: { text: `Cruces evaluables a cada A · falsas alarmas del sistema: ${fmt(f.falsas_alarmas, 0)}`, font: { size: 13 }, x: 0.01 }, barmode: 'stack', xaxis: { title: { text: 'Anticipación real exigida A (días)' }, dtick: 5 }, yaxis: { title: { text: 'Cruces' } }, margin: { l: 50, r: 10, t: 40, b: 44 } }), 380);
      $('#a-cif').innerHTML = `<span>u = <b>${fmt(f.f, 2)} × P95</b>, h_max <b>${fmt(f.hmax, 0)} d</b></span><span>aciertos <b>${fmt(f.aciertos, 0)}</b> de ${fmt(f.evaluables, 0)} cruces</span><span>falsas alarmas <b>${fmt(f.falsas_alarmas, 0)}</b> · repetidos ${fmt(f.repetidos, 0)}</span><span>POD <b>${fmt(f.POD, 2)}</b> · FAR <b>${fmt(f.FAR, 2)}</b> · CSI <b>${fmt(f.CSI, 2)}</b></span><span>anticipación real mediana <b>${fmt(f.anticipacion_mediana, 0)} d</b></span><span>por año calendario: <b>${fmt(f.dias_aviso_anio, 0)}</b> días con aviso, ${fmt(f.falsas_alarmas_anio, 1)} falsas alarmas (cobertura ${fmt(100 * f.cobertura, 0)} %)</span>`;
    };
    onSeg(app, 'a-est', v => { est = v; opciones(); dibuja(); });
    onSeg(app, 'a-reg', v => { regla = v; dibuja(); });
    $('#a-mod').addEventListener('change', dibuja);
    opciones(); dibuja();
    const todos = e => tabla('#a-todos', A.resumen.filter(r => r['estación'] === e && r.regla === 'calibrada'), [['modelo', 'Modelo', (v, r) => dotM(v) + (r['modelo para avisos'] ? ' <span class="chip ok">avisos</span>' : '')],
      ['f', 'f'], ['hmax', 'h_max', v => fmt(v, 0)], ['evaluables', 'Cruces', v => fmt(v, 0)], ['aciertos', 'Aciertos', v => fmt(v, 0)], ['omisiones', 'Omisiones', v => fmt(v, 0)],
      ['falsas_alarmas', 'FA', v => fmt(v, 0)], ['repetidos', 'Repetidos', v => fmt(v, 0)], ['POD', 'POD'], ['FAR', 'FAR'], ['CSI', 'CSI'], ['anticipacion_util', 'Antic. útil', v => fmt(v, 0)],
      ['anticipacion_mediana', 'Antic. mediana', v => fmt(v, 0)], ['dias_aviso_anio', 'Días aviso/año', v => fmt(v, 0)], ['falsas_alarmas_anio', 'FA/año', v => fmt(v, 1)], ['cobertura', 'Cobertura', v => fmt(100 * v, 0) + ' %']]);
    onSeg(app, 'a-est3', todos); todos('Racarumi');
    const evT = e => tabla('#a-ev', A.por_evento.filter(r => r['estación'] === e), [['fecha', 'Cruce', v => esc(String(v).slice(0, 10))], ['elegible', 'Elegible', v => v ? 'sí' : 'no'],
      ['motivo', 'Motivo'], ['evaluable', 'Evaluable', v => v ? 'sí' : 'no'], ['detectado', 'Detectado', v => v ? 'sí' : 'no'], ['anticipacion_real', 'Anticipación real (d)', v => fmt(v, 0)],
      ['error_fecha_umbral', 'Error fecha (d)', v => fmt(v, 0)], ['error_fecha_A1', 'Error 1 d antes', v => fmt(v, 0)], ['error_fecha_A3', 'Error 3 d antes', v => fmt(v, 0)],
      ['error_fecha_A7', 'Error 7 d antes', v => fmt(v, 0)], ['pico 15 d (m³/s)', 'Pico 15 d', v => fmt(v, e === 'Tamshiyacu' ? 0 : 1)]]);
    onSeg(app, 'a-est2', evT); evT('Racarumi');
    $$('#a-sint td, #a-todos td').forEach(td => { if (td.innerHTML.includes('class="dot"')) td.classList.remove('n'); });
  }

  // ---------------------------------------------------------------- MÉTODO
  function vMetodo() {
    const filaP = e => { const S = D.estaciones[e]; return S.modelos.filter(n => S.parametros[n]).map(n => `<tr><td>${esc(e)}</td><td>${dotM(n)}</td><td style="text-align:left">${esc(JSON.stringify(S.parametros[n]).replace(/[{}"]/g, '').replace(/,/g, ', ').replace(/:/g, ' = ') || '—')}</td><td class="n">${fmt(S.nse_val[n], 3)}</td></tr>`).join(''); };
    const div = e => D.estaciones[e].division.map(r => `<tr><td>${esc(e)}</td><td>${esc(r.bloque)}</td><td>${esc(r['periodo de emisión'])}</td><td class="n">${fmt(r.muestras, 0)}</td><td class="n">${fmt(r['Q medio (m³/s)'], 1)}</td><td class="n">${fmt(r['días > P95 en t (%)'], 1)}</td></tr>`).join('');
    $('#app').innerHTML = `<section class="vista"><div class="cab"><span class="eyebrow">Método · protocolo de evaluación</span><h1>Cómo se obtuvieron los resultados</h1>
      <p>Mismo protocolo en las dos estaciones (cuadernos <code>01_Modelos_Racarumi</code>, <code>02_Modelos_Tamshiyacu</code>, <code>03_Comparacion_y_Seleccion</code> y <code>04_Anticipacion_Crecidas</code>, con las funciones de <code>comun.py</code>; casos de verificación de avisos en <code>pruebas_avisos.py</code> y comprobaciones del protocolo en <code>pruebas_protocolo.py</code>).</p></div>
      <div class="met">
        <div class="panel"><h3>Datos</h3><p>Única fuente: CAMELS-PE v1.0.1. Caudal observado diario con los errores eliminados en el EDA. Vacíos de 3 días o menos se interpolan solo en las entradas y solo entre días ≤ t; los objetivos nunca se imputan.</p></div>
        <div class="panel"><h3>Seis modelos</h3><p>Regresión lineal, Random Forest, XGBoost, KNN, MLP y LSTM, y el combinado por horizonte, con las mismas fechas y horizontes; 30 días + calendario (KNN elige cuántos días usa). Sin particiones aleatorias: iteraciones y épocas se eligen con validación temporal; la LSTM se detiene con un bloque distinto (2005–2008). Seleccionado: el más simple entre el mejor y sus equivalentes (±0.01 de NSE, bootstrap pareado).</p></div>
        <div class="panel"><h3>Sin información futura</h3><p>ε, escalones, P95 y estandarizaciones con el entrenamiento; validación en dos bloques: la corrección de Duan se estima en 2009–2011 y los candidatos se comparan en 2012–2015; avisos con la mediana pronosticada (sin factores); estocásticos con ${D.SEMILLAS.length} semillas predefinidas.</p></div>
        <div class="panel"><h3>Horizonte útil</h3><p>H: mayor h consecutivo desde 1 con NSE &gt; 0 que supera a persistencia y climatología. La misma definición en cada réplica del bootstrap conjunto; la cifra de las conclusiones es la cota 95 % (percentil 5). 30 significa "30 o más".</p></div>
        <div class="panel"><h3>Anticipación de crecidas</h3><p>Verificación por eventos: elegibilidad causal (7 días observados bajo el P95), tres estados (alto, bajo, desconocido), un único universo de eventos para POD, FAR y CSI, episodios partidos cada ${D.AVISO.dmax} días, emparejamiento uno a uno, tolerancia ±${D.AVISO.tol} días y anticipación real.</p></div>
        <div class="panel"><h3>Robustez</h3><p>Fechas comunes por intersección explícita, bootstrap pareado entre estaciones, cuatro orígenes con selección interna, bloques de 15 días a 3 meses y, en Tamshiyacu, 20 controles para los años con escalones.</p></div>
      </div>
      <div class="pila" style="margin-top:14px">
        <div class="panel"><header><h2>División temporal</h2></header>
          <div class="cuerpo tw"><table class="t"><thead><tr><th>Estación</th><th>Bloque</th><th>Periodo de emisión</th><th>Muestras</th><th>Q medio (m³/s)</th><th>Días &gt; P95 (%)</th></tr></thead><tbody>${div('Racarumi')}${div('Tamshiyacu')}</tbody></table></div></div>
        <div class="panel"><header><h2>Hiperparámetros elegidos en validación (bloque de selección)</h2></header>
          <div class="cuerpo tw"><table class="t"><thead><tr><th>Estación</th><th>Modelo</th><th style="text-align:left">Hiperparámetros</th><th>NSE medio selección</th></tr></thead><tbody>${filaP('Racarumi')}${filaP('Tamshiyacu')}</tbody></table></div></div>
        <div class="panel"><header><h2>Limitaciones</h2></header><div class="cuerpo prosa">${D.textos_comp.limitaciones || ''}</div></div>
        <div class="panel"><header><h2>Reproducir</h2></header><div class="cuerpo prosa"><p>Con <code>CAMELS-PE_v1.0.1.zip</code> en la raíz del repositorio, ejecute en orden los cuadernos 01 a 04 de <code>modelos/</code>, luego <code>python modelos/interactivo/generar_html.py</code> (vuelve a crear este archivo con Plotly incrustado; abre sin internet) y <code>python modelos/manifiesto.py</code> (huellas de datos y salidas).</p></div></div>
      </div></section>`;
  }

  let ini = 'resumen';
  try { const h = decodeURIComponent(location.hash.slice(1)); if (render[h]) ini = h; } catch (e) { /* sin hash */ }
  ir(ini);
  window.addEventListener('hashchange', () => { const h = decodeURIComponent(location.hash.slice(1)); if (render[h] && h !== vista) ir(h); });
})();
