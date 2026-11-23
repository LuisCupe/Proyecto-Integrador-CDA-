"""Protocolo COMÚN de comparación de configuraciones (cuadernos 05, 06 y 08).

Una *configuración* es (conjunto de entradas, latencia de las fuentes externas, modelo). Los cuadernos 05 (caudal aguas
arriba), 06 (precipitación) y 08 (comparación integrada y selección final, con Chronos-2) usan estas mismas funciones,
así que comparten exactamente las mismas reglas:

- **Filas y fechas:** cada experimento (estación + diseño de `entradas.py`) fija sus filas; todas sus configuraciones se
  ajustan, validan y prueban en ellas. Las comparaciones entre dos configuraciones se hacen SIEMPRE en las emisiones
  comunes de ambas (la prueba con Requena termina en 2020-03).
- **Validación:** bloque de selección 2012–2015 con la corrección de Duan de 2009–2011 (`comun.ValidacionCausal`);
  regla de v4 (`comun.seleccion_pareada`): mayor NSE medio, IC 90 % por bootstrap pareado de meses, la más simple entre
  el mejor y sus equivalentes. Orden de simplicidad: menos fuentes externas primero (`entradas.n_fuentes`) y, entre
  configuraciones con las mismas entradas, el modelo más simple (`ORDEN_MODELOS`; Chronos-2 al final).
- **Avisos:** reglas del cuaderno 04 (trayectoria mediana, f y h_max calibrados con FAR ≤ 0.5) y protocolo común de
  selección para avisos (`comun.seleccion_avisos`: regla en 2009–2011, comparación en 2012–2015).
- **Prueba:** 2016–fin, climatología hasta 2015, horizonte útil con la cota 95 % del bootstrap conjunto por meses,
  ganancias por bandas con IC 90 %, IC de Wilson para POD, FAR y CSI. La prueba nunca cambia una selección.

Chronos-2 entra como candidato con los mismos campos que un modelo entrenado (`pronostico_externo`): punto en el bloque
de selección, mediana en toda la validación (si existe, para avisos), punto y mediana en la prueba.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

import aguas_arriba as A
import comun as C
import entradas as EN

CHRONOS = 'Chronos-2'
MODELOS = list(C.MODELOS)
ORDEN_MODELOS = list(C.ORDEN_SIMPLICIDAD) + [CHRONOS]      # Chronos-2: el más complejo (120 M de parámetros)
BANDAS = list(A.BANDAS)
ABREV = {'A:San Regis': 'SR', 'A:Requena': 'RQ', 'A:Cirato': 'C'}
ESCENARIOS = ('mismo día', 'un día de retraso')
SIG = {'reduce el error': '+', 'aumenta el error': '−', 'sin diferencia demostrada': '≈'}
CLASE = dict(mejora='▲', peor='▼', equivalente='=', inconcluso='?', mejor='★')
COLOR = {**C.COLOR, CHRONOS: '#1f1f7a'}


# ----------------------------------------------------------------------------- etiquetas
def etiqueta(conj: str, lat: int) -> str:
    """'Q+P+IA+A:San Regis', 1 → 'Q+P+IA+SR (t−1)'."""
    s = '+'.join(ABREV.get(f, f) for f in conj.split('+'))
    if conj == 'Q+Pd':
        s = 'Q+Pd (control)'
    return s + (' (t−1)' if lat else '')


def en_escenario(conj: str, lat: int, escenario: str) -> bool:
    """'mismo día': fuentes externas hasta t; 'un día de retraso': hasta t−1. Q (sin fuentes externas) está en los dos.
    El control Q+Pd no compite."""
    if (conj, lat) in EN.CONJUNTOS_CONTROL:
        return False
    if conj == 'Q':
        return True
    return lat == (0 if escenario == 'mismo día' else 1)


def disponibilidad(conj: str, lat: int) -> str:
    if conj == 'Q':
        return 'solo caudal local (hasta t)'
    fuentes = ', '.join({'P': 'lluvia', 'IA': 'índices antecedentes', 'Pd': 'lluvia diaria'}.get(f, f[2:]) for f in EN.fichas(conj))
    return f"caudal local hasta t; {fuentes} hasta {'t−1' if lat else 't'}" + (' (disponibilidad supuesta)' if not lat else '')


def orden_configuraciones(claves) -> list:
    """Claves (conj, lat, modelo) en orden de simplicidad: menos fuentes, luego el orden de aparición del conjunto y el
    modelo más simple."""
    claves = list(claves)
    pos = {}
    for c, l, _ in claves:
        pos.setdefault((c, l), len(pos))
    return sorted(claves, key=lambda k: (EN.n_fuentes(k[0]), k[1], pos[(k[0], k[1])], ORDEN_MODELOS.index(k[2])))


def nombre(k) -> str:
    return f'{etiqueta(k[0], k[1])} · {k[2]}'


# ----------------------------------------------------------------------------- experimento
@dataclass
class Experimento:
    estacion: str
    F: EN.Fuentes
    m: C.Muestras
    p: dict
    VC: C.ValidacionCausal
    mx: C.Muestras
    D: dict
    P95: float
    clim: pd.Series                      # climatología de referencia de la prueba (hasta 2015)

    @property
    def conjuntos(self):
        return list(self.D)

    @property
    def fechas_val(self):
        return self.m.fechas[self.p['val']]


def cargar(estacion: str, diseno: dict) -> Experimento:
    F, m, p, VC, mx, D = EN.experimento(estacion, diseno)
    return Experimento(estacion, F, m, p, VC, mx, D, float(np.nanpercentile(F.q.loc[:C.FIN_ENTRENAMIENTO], 95)),
                       C.climatologia_referencia(F.q, 'prueba'))


def ajustar(x: Experimento, modelos=MODELOS, conjuntos=None, solo_cache: bool = False) -> tuple[dict, pd.DataFrame]:
    """Ajusta (o lee de la caché con identidad completa idéntica) cada conjunto × modelo. `solo_cache=True` exige que
    TODAS las configuraciones ya estén en la caché (para reutilizar en el 08 lo que entrenaron 05 y 06): si falta una,
    falla en lugar de entrenarla en otro cuaderno."""
    R, filas = {}, []
    for (conj, lat) in (conjuntos or x.conjuntos):
        d = x.D[(conj, lat)]
        for n in modelos:
            if solo_cache:
                texto = EN.clave_cache(d, n, list(C.SEMILLAS if n in C.ESTOCASTICOS else [C.SEMILLA]))
                ruta = EN._ruta(texto)
                if not ruta.exists():
                    raise FileNotFoundError(f'{x.estacion} {etiqueta(conj, lat)} {n}: no está en la caché; debe generarse en su cuaderno')
            r = EN.ajustar(d, n)
            if solo_cache:
                assert r['en_cache'], (x.estacion, conj, lat, n)
            R[(conj, lat, n)] = r
            filas.append({'estación': x.estacion, 'conjunto': etiqueta(conj, lat), 'modelo': n, 'leído de la caché': bool(r['en_cache']),
                          'minutos de ajuste': r['segundos'] / 60, 'hiperparámetros': json.dumps(r['mejor'], ensure_ascii=False)})
    return R, pd.DataFrame(filas)


def pronosticos(x: Experimento, R: dict) -> dict:
    """Pronósticos en caudal con la conversión de v4: `sel` (bloque de selección, Duan de 2009–2011), `valmed`
    (trayectoria mediana en toda la validación, para avisos), `pru` (prueba, Duan de toda la validación), `prumed`
    (mediana de prueba) y `ext` (muestra extendida)."""
    P = {}
    m, p, VC = x.m, x.p, x.VC
    for (conj, lat, n), r in R.items():
        d = x.D[(conj, lat)]
        fac = C.factor_duan(m.y[p['val']], r['yv'])
        P[(conj, lat, n)] = dict(sel=VC.a_q(r['yv']), valmed=C.a_caudal(m, r['yv'], p['val']), pru=C.a_caudal(m, r['yp'], d.ip, fac),
                                 prumed=C.a_caudal(m, r['yp'], d.ip), ext=C.a_caudal(d.mx, r['yx'], np.arange(len(d.mx.fechas)), fac),
                                 ip=d.ip, mx=d.mx)
    return P


def pronostico_externo(x: Experimento, conj: str, lat: int, fechas, punto, mediana, ip=None) -> dict:
    """Candidato sin entrenamiento local (Chronos-2): `fechas`, `punto` y `mediana` son sus pronósticos (n, 30) en
    cualquier conjunto de emisiones que contenga el bloque de selección y la prueba del experimento. Se alinean por
    fecha; si cubren toda la validación, también se guarda la mediana de validación (avisos)."""
    f = pd.DatetimeIndex(fechas)
    if ip is None:
        ip = x.D[(conj, lat)].ip if (conj, lat) in x.D else x.p['pru']
    def tomar(objetivo, Z):
        pos = f.get_indexer(objetivo)
        assert (pos >= 0).all(), f'{x.estacion} {etiqueta(conj, lat)}: faltan {int((pos < 0).sum())} emisiones del experimento'
        return np.asarray(Z, float)[pos]
    out = dict(sel=tomar(x.VC.fechas_sel, punto), pru=tomar(x.m.fechas[ip], punto), prumed=tomar(x.m.fechas[ip], mediana), ip=ip,
               ext=None, mx=None, valmed=None)
    if x.fechas_val.isin(f).all():
        out['valmed'] = tomar(x.fechas_val, mediana)
    return out


def comunes(*ips) -> np.ndarray:
    out = ips[0]
    for i in ips[1:]:
        out = np.intersect1d(out, i)
    return out


def _en(P_k: dict, ip: np.ndarray, campo: str = 'pru') -> np.ndarray:
    pos = np.searchsorted(P_k['ip'], ip)
    assert np.array_equal(P_k['ip'][pos], ip), 'emisiones fuera de la prueba de la configuración'
    return P_k[campo][pos]


# ----------------------------------------------------------------------------- validación
def tabla_validacion(x: Experimento, P: dict, claves=None, R: dict | None = None) -> pd.DataFrame:
    filas = []
    for k in (claves or P):
        filas.append({'estación': x.estacion, 'conjunto': etiqueta(k[0], k[1]), 'modelo': k[2], 'escenario de disponibilidad': disponibilidad(k[0], k[1]),
                      'NSE medio selección': C.nse_medio(P[k]['sel'], x.VC.obs_sel),
                      'hiperparámetros': json.dumps(R[k]['mejor'], ensure_ascii=False) if R and k in R else ('contexto y punto del cuaderno 07' if k[2] == CHRONOS else '')})
    return pd.DataFrame(filas)


def seleccion_por_conjunto(x: Experimento, P: dict, conjuntos=None, modelos=None, B: int = 1000) -> tuple[dict, pd.DataFrame]:
    """En cada conjunto, la regla de v4 entre los modelos disponibles."""
    SELM, filas = {}, []
    for conj, lat in (conjuntos or x.conjuntos):
        mods = [n for n in (modelos or ORDEN_MODELOS) if (conj, lat, n) in P]
        tab, s, mj = C.seleccion_pareada(x.VC.fechas_sel, x.VC.obs_sel, {n: P[(conj, lat, n)]['sel'] for n in mods}, B=B, orden=ORDEN_MODELOS)
        SELM[(conj, lat)] = s
        for n in mods:
            filas.append({'estación': x.estacion, 'conjunto': etiqueta(conj, lat), 'modelo': n, 'NSE medio selección': tab.loc[n, 'NSE medio selección'],
                          'clase': tab.loc[n, 'clase'], 'diferencia con el mejor': tab.loc[n, 'diferencia con el mejor'],
                          'IC90 inferior': tab.loc[n, 'IC90 inferior'], 'IC90 superior': tab.loc[n, 'IC90 superior'], 'seleccionado': n == s})
    return SELM, pd.DataFrame(filas)


def efecto_entrada_validacion(x: Experimento, P: dict, comparaciones, modelos=None, B: int = 1000) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ΔNSE medio (IC 90 %, clase de la regla del proyecto) y G por bandas de cada entrada con el MISMO modelo en el
    bloque de selección. comparaciones: [(nombre, (conj_con, lat_con), (conj_sin, lat_sin)), …]."""
    filas, filas_b = [], []
    for nom, con, sin in comparaciones:
        for n in (modelos or ORDEN_MODELOS):
            if (*con, n) not in P or (*sin, n) not in P:
                continue
            t = A.delta_nse(x.VC.fechas_sel, x.VC.obs_sel, {'sin': P[(*sin, n)]['sel'], 'con': P[(*con, n)]['sel']}, base='sin', B=B).loc['con']
            filas.append({'estación': x.estacion, 'entrada': nom, 'modelo': n, 'ΔNSE medio': t['ΔNSE medio'], 'IC90 inferior': t['IC90 inferior'],
                          'IC90 superior': t['IC90 superior'], 'clase': t['clase']})
            _, gb = A.ganancia(x.VC.fechas_sel, x.VC.obs_sel, P[(*con, n)]['sel'], P[(*sin, n)]['sel'], B=B)
            for banda, g in gb.iterrows():
                filas_b.append({'estación': x.estacion, 'entrada': nom, 'modelo': n, 'banda': banda, **g.to_dict()})
    return pd.DataFrame(filas), pd.DataFrame(filas_b)


def seleccion_configuracion(x: Experimento, P: dict, candidatos, B: int = 1000) -> dict:
    """Regla de v4 entre configuraciones (conj, lat, modelo). Devuelve la elegida (la más simple entre la de mayor NSE
    medio y sus equivalentes), la mayor, la tabla completa y un resumen con los candidatos que la validación no
    distingue del mayor (equivalentes e inconclusos)."""
    cand = orden_configuraciones(candidatos)
    nom = {k: nombre(k) for k in cand}
    tab, s, mj = C.seleccion_pareada(x.VC.fechas_sel, x.VC.obs_sel, {nom[k]: P[k]['sel'] for k in cand}, B=B, orden=[nom[k] for k in cand])
    inv = {v: k for k, v in nom.items()}
    # Clases de la regla de v4 frente al de mayor NSE medio (IC 90 % pareado): «equivalente» = IC dentro de ±margen
    # (diferencia demostrada pequeña: la regla puede elegirlo); «inconcluso» = IC demasiado ancho para afirmar que es
    # equivalente, mejor o peor (NO es equivalencia ni indistinguibilidad demostrada; la regla no lo elige); «peor» = IC < 0.
    eq = tab[tab['clase'].isin(['mejor', 'equivalente'])].sort_values('NSE medio selección', ascending=False)
    nd = tab[tab['clase'].isin(['mejor', 'equivalente', 'inconcluso'])].sort_values('NSE medio selección', ascending=False)
    res = {'candidatos': len(cand), 'mayor NSE medio': mj, 'NSE medio del mayor': tab.loc[mj, 'NSE medio selección'],
           'seleccionada (la más simple entre el mayor y sus equivalentes)': s, 'NSE medio de la seleccionada': tab.loc[s, 'NSE medio selección'],
           'equivalentes al mayor (IC dentro de ±0.01)': int((tab['clase'] == 'equivalente').sum()),
           'inconclusas (IC demasiado ancho; no es equivalencia)': int((tab['clase'] == 'inconcluso').sum()),
           'peores (IC < 0)': int((tab['clase'] == 'peor').sum()),
           'no demostradas peores (mayor + equivalentes + inconclusas)': len(nd),
           'equivalentes: las 5 de mayor NSE medio': ' | '.join(f"{k} ({v:.3f})" for k, v in eq['NSE medio selección'].head(5).items()),
           'inconclusas: las 5 de mayor NSE medio': ' | '.join(f"{k} ({v:.3f})" for k, v in tab[tab['clase'] == 'inconcluso'].sort_values('NSE medio selección', ascending=False)['NSE medio selección'].head(5).items()) or '—'}
    return dict(elegida=inv[s], mayor=inv[mj], tabla=tab, resumen=res, equivalentes=[inv[i] for i in eq.index],
                no_peores=[inv[i] for i in nd.index])


def etiqueta_periodo(x: Experimento, ip, nombre: str | None = None) -> str:
    """Etiqueta de un periodo de prueba a partir de sus emisiones reales (primer y último mes de emisión)."""
    f = x.m.fechas[ip]
    r = f'prueba {f.min():%Y-%m} a {f.max():%Y-%m}'
    return f'{nombre} ({r})' if nombre else r


# ----------------------------------------------------------------------------- prueba: magnitud
def metricas_prueba(x: Experimento, P: dict, claves=None, ip=None, B: int = 1000) -> tuple[pd.DataFrame, dict, dict]:
    """NSE por horizonte, NSE medio, RMSE y horizonte útil (cota 95 %) de cada configuración, en su propia prueba o en
    las emisiones `ip` (comunes a todas las claves; deben estar en la prueba de cada una)."""
    filas, HZ, TAB = [], {}, {}
    m = x.m
    for k in (claves or P):
        ipk = P[k]['ip'] if ip is None else ip
        pr = _en(P[k], ipk)
        obs, fp = m.q_obs[ipk], m.fechas[ipk]
        pers, cl = C.pred_persistencia(m, ipk), C.pred_climatologia(m, ipk, x.clim)
        t = TAB[k] = C.tabla_metricas(obs, pr, pers, cl)
        hz = HZ[k] = C.horizontes(t, C.bootstrap_curvas(fp, obs, pr, pers, cl, B=B))
        filas.append({'estación': x.estacion, 'conjunto': etiqueta(k[0], k[1]), 'modelo': k[2], 'escenario de disponibilidad': disponibilidad(k[0], k[1]),
                      'periodo de prueba': f'{fp.min():%Y-%m} a {fp.max():%Y-%m}', 'emisiones': len(ipk),
                      'climatología hasta': C.CLIMATOLOGIA_HASTA['prueba'], 'NSE medio': C.nse_medio(pr, obs),
                      **{f'NSE h={h}': t.loc[h, 'NSE'] for h in (1, 3, 7, 15, 30)}, 'RMSE h=1 (m³/s)': t.loc[1, 'RMSE'],
                      'H puntual (d)': hz['H_puntual'], 'H cota 95 % (d)': hz['H_cota'], 'H p05–p95 de las réplicas (d)': f"{hz['H_p05']}–{hz['H_p95']}",
                      'P(H ≥ 30)': hz['P_H30']})
    return pd.DataFrame(filas), HZ, TAB


def referencias_prueba(x: Experimento, ip) -> pd.DataFrame:
    m = x.m
    obs = m.q_obs[ip]
    pers, cl = C.pred_persistencia(m, ip), C.pred_climatologia(m, ip, x.clim)
    filas = []
    for nom, pr in [('Persistencia', pers), ('Climatología', cl)]:
        t = C.tabla_metricas(obs, pr, pers, cl)
        filas.append({'estación': x.estacion, 'conjunto': '—', 'modelo': nom, 'emisiones': len(ip), 'NSE medio': C.nse_medio(pr, obs),
                      **{f'NSE h={h}': t.loc[h, 'NSE'] for h in (1, 3, 7, 15, 30)}, 'RMSE h=1 (m³/s)': t.loc[1, 'RMSE']})
    return pd.DataFrame(filas)


def efecto_entrada_prueba(x: Experimento, P: dict, comparaciones, modelos=None, B: int = 1000, ip=None) -> pd.DataFrame:
    """G = 1 − MSE(con)/MSE(sin) por bandas con IC 90 %, con el MISMO modelo, en las emisiones de prueba comunes (y, si
    se da `ip`, solo en esas emisiones: por ejemplo, el periodo común de todas las configuraciones con Requena)."""
    filas = []
    m = x.m
    for nom, con, sin in comparaciones:
        for n in (modelos or ORDEN_MODELOS):
            if (*con, n) not in P or (*sin, n) not in P:
                continue
            ipc = comunes(P[(*con, n)]['ip'], P[(*sin, n)]['ip'], *([] if ip is None else [ip]))
            _, gb = A.ganancia(m.fechas[ipc], m.q_obs[ipc], _en(P[(*con, n)], ipc), _en(P[(*sin, n)], ipc), B=B)
            for banda, g in gb.iterrows():
                filas.append({'estación': x.estacion, 'entrada': nom, 'modelo': n, 'banda': banda, 'emisiones': len(ipc),
                              'periodo': f'{m.fechas[ipc].min():%Y-%m} a {m.fechas[ipc].max():%Y-%m}', **g.to_dict()})
    return pd.DataFrame(filas)


def concordancia(val_b: pd.DataFrame, pru_b: pd.DataFrame) -> pd.DataFrame:
    """Pares modelo × banda según su lectura en validación / prueba (+ reduce, ≈ sin diferencia demostrada, − aumenta)."""
    cc = val_b.merge(pru_b, on=['estación', 'entrada', 'modelo', 'banda'], suffixes=(' val', ' prueba'))
    cc['par'] = cc['lectura val'].map(SIG) + '/' + cc['lectura prueba'].map(SIG)
    return cc.pivot_table(index=['estación', 'entrada'], columns='par', values='G val', aggfunc='count', fill_value=0, sort=False)


def comparar_con(x: Experimento, P: dict, referencia, otros, B: int = 1000, ip=None, campo: str = 'pru') -> pd.DataFrame:
    """ΔNSE medio (IC 90 %, clase) y G por bandas de cada configuración de `otros` frente a `referencia`, en las
    emisiones de prueba comunes (o en el bloque de selección si campo='sel')."""
    filas = []
    for k in otros:
        if k == referencia:
            continue
        if campo == 'sel':
            f, obs, a, b = x.VC.fechas_sel, x.VC.obs_sel, P[k]['sel'], P[referencia]['sel']
        else:
            ipc = comunes(P[k]['ip'], P[referencia]['ip']) if ip is None else ip
            f, obs, a, b = x.m.fechas[ipc], x.m.q_obs[ipc], _en(P[k], ipc), _en(P[referencia], ipc)
        t = A.delta_nse(f, obs, {'ref': b, 'otro': a}, base='ref', B=B).loc['otro']
        _, gb = A.ganancia(f, obs, a, b, B=B)
        filas.append({'estación': x.estacion, 'referencia': nombre(referencia), 'configuración': nombre(k), 'emisiones': len(obs),
                      'NSE medio referencia': C.nse_medio(b, obs), 'NSE medio': t['NSE medio'], 'ΔNSE medio': t['ΔNSE medio'],
                      'IC90 inferior': t['IC90 inferior'], 'IC90 superior': t['IC90 superior'], 'clase': t['clase'],
                      **{f'G {banda}': gb.loc[banda, 'G'] for banda in BANDAS}, **{f'lectura {banda}': gb.loc[banda, 'lectura'] for banda in BANDAS}})
    return pd.DataFrame(filas)


def efecto_metodo(x: Experimento, P: dict, SELM: dict, conjuntos=None, B: int = 1000) -> pd.DataFrame:
    """Cada modelo frente al seleccionado en validación para su conjunto (misma información, mismas fechas)."""
    out = []
    for conj, lat in (conjuntos or x.conjuntos):
        ref = (conj, lat, SELM[(conj, lat)])
        otros = [(conj, lat, n) for n in ORDEN_MODELOS if (conj, lat, n) in P]
        t = comparar_con(x, P, ref, otros, B=B)
        t.insert(1, 'conjunto', etiqueta(conj, lat)); t.insert(2, 'modelo', [k.split(' · ')[-1] for k in t['configuración']])
        out.append(t)
    return pd.concat(out, ignore_index=True)


def crecidas(x: Experimento, P: dict, claves=None, horizontes=(1, 3, 7), ip=None) -> pd.DataFrame:
    filas = []
    for k in (claves or P):
        ipk = P[k]['ip'] if ip is None else ip
        t = C.metricas_crecida(x.m.q_obs[ipk], _en(P[k], ipk), x.P95)
        for h in horizontes:
            filas.append({'estación': x.estacion, 'h': h, 'conjunto': etiqueta(k[0], k[1]), 'modelo': k[2], 'días altos': int(t.loc[h, 'n_altos']),
                          'MAE altos (m³/s)': t.loc[h, 'MAE_altos'], 'PBIAS altos (%)': t.loc[h, 'PBIAS_altos'],
                          'MAE ordinarios (m³/s)': t.loc[h, 'MAE_ordinarios'], 'POD diario': t.loc[h, 'POD'], 'CSI diario': t.loc[h, 'CSI']})
    return pd.DataFrame(filas)


def muestra_extendida(x: Experimento, P: dict, claves=None) -> pd.DataFrame:
    """Muestra común (30 objetivos) frente a la extendida (cada horizonte con los objetivos que existan), por horizonte."""
    filas = []
    m = x.m
    for k in (claves or P):
        if P[k].get('ext') is None:
            continue
        ip, mx = P[k]['ip'], P[k]['mx']
        persc, climc = C.pred_persistencia(m, ip), C.pred_climatologia(m, ip, x.clim)
        jx = np.arange(len(mx.fechas))
        persx, climx = C.pred_persistencia(mx, jx), C.pred_climatologia(mx, jx, x.clim)
        ox = mx.q_obs
        for h in C.HORIZONTES:
            j = h - 1
            okh = np.isfinite(ox[:, j])
            oc = m.q_obs[ip, j]
            pc, px = P[k]['pru'][:, j], P[k]['ext'][:, j]
            filas.append({'estación': x.estacion, 'conjunto': etiqueta(k[0], k[1]), 'modelo': k[2], 'h': h,
                          'emisiones (común)': len(ip), 'emisiones (extendida)': int(okh.sum()),
                          'NSE (común)': C.nse(oc, pc), 'NSE (extendida)': C.nse(ox[okh, j], px[okh]),
                          'hab. pers. (común)': C.habilidad(oc, pc, persc[:, j]), 'hab. pers. (extendida)': C.habilidad(ox[okh, j], px[okh], persx[okh, j]),
                          'hab. clim. (común)': C.habilidad(oc, pc, climc[:, j]), 'hab. clim. (extendida)': C.habilidad(ox[okh, j], px[okh], climx[okh, j])})
    ext = pd.DataFrame(filas)
    ext['ΔNSE (ext − común)'] = ext['NSE (extendida)'] - ext['NSE (común)']
    ext['signo de habilidad igual'] = ((np.sign(ext['hab. pers. (común)']) == np.sign(ext['hab. pers. (extendida)']))
                                       & (np.sign(ext['hab. clim. (común)']) == np.sign(ext['hab. clim. (extendida)'])))
    ext['banda'] = pd.cut(ext['h'], [0, 3, 7, 15, 30], labels=BANDAS)
    return ext


def resumen_extendida(ext: pd.DataFrame) -> pd.DataFrame:
    return ext.groupby(['estación', 'banda'], observed=True).agg(
        combinaciones=('modelo', 'size'), emisiones_extendida_medias=('emisiones (extendida)', 'mean'),
        ΔNSE_mediana=('ΔNSE (ext − común)', 'median'), ΔNSE_min=('ΔNSE (ext − común)', 'min'), ΔNSE_max=('ΔNSE (ext − común)', 'max'),
        habilidad_cambia_de_signo=('signo de habilidad igual', lambda s: int((~s).sum())))


# ----------------------------------------------------------------------------- avisos
def wilson(k: int, n: int, z: float = 1.6449) -> tuple[float, float]:
    """IC de Wilson al 90 % (aproximado: supone cruces independientes)."""
    if not n:
        return (np.nan, np.nan)
    p_ = k / n
    den = 1 + z ** 2 / n
    c_ = (p_ + z ** 2 / (2 * n)) / den
    hw = z * np.sqrt(p_ * (1 - p_) / n + z ** 2 / (4 * n ** 2)) / den
    return (c_ - hw, c_ + hw)


def _cumple(r) -> bool:
    return bool(np.isfinite(r['FAR']) and r['FAR'] <= C.AVISO['far_max'])


def calibrar_regla(fechas, tray, q, P95) -> dict:
    """Regla (f, h_max) con máximo CSI y FAR ≤ 0.5 (cuaderno 04) en las emisiones dadas."""
    AV = C.AVISO
    clave = lambda r: (_cumple(r), r['CSI'] if np.isfinite(r['CSI']) else -1, -abs(r['f'] - 1), -r['hmax'])
    mejor = None
    for f in AV['factores']:
        for hm in AV['hmax']:
            r = C.evaluar_avisos(fechas, tray, q, P95, f=f, hmax=hm, tol=AV['tol'], dmax=AV['dmax'], reinicio=AV['reinicio'])['resumen']
            fila = {k: r[k] for k in ['f', 'hmax', 'FAR', 'CSI', 'POD', 'aciertos', 'falsas_alarmas', 'evaluables']}
            if mejor is None or clave(fila) > clave(mejor):
                mejor = fila
    return mejor


def fila_avisos(s: dict) -> dict:
    """Conteos y métricas de un sistema de avisos en la prueba, con IC de Wilson al 90 %."""
    AV = C.AVISO
    lo_p, hi_p = wilson(s['aciertos'], s['evaluables'])
    lo_f, hi_f = wilson(s['falsas_alarmas'], s['aciertos'] + s['falsas_alarmas'])
    lo_c, hi_c = wilson(s['aciertos'], s['aciertos'] + s['omisiones'] + s['falsas_alarmas'])
    return {'f': s['f'], 'h_max': s['hmax'], 'cruces evaluables': s['evaluables'], 'aciertos': s['aciertos'], 'omisiones': s['omisiones'],
            'falsas alarmas': s['falsas_alarmas'], 'POD': s['POD'], 'POD IC90': f'{lo_p:.2f}–{hi_p:.2f}', 'FAR': s['FAR'],
            'FAR IC90': f'{lo_f:.2f}–{hi_f:.2f}', 'CSI': s['CSI'], 'CSI IC90 (aprox.)': f'{lo_c:.2f}–{hi_c:.2f}',
            'CSI IC90 inferior': lo_c, 'CSI IC90 superior': hi_c, 'anticipación útil (d)': s['anticipacion_util'],
            'anticipación útil, conjunto fijo (d)': s['anticipacion_util_conjunto_fijo'],
            'cumple a 1 día también con los IC': bool(s['anticipacion_util'] >= 1 and lo_p >= AV['pod_min'] and hi_f <= AV['far_max']),
            'anticipación mediana entre los aciertos (d)': s['anticipacion_mediana'], 'días con aviso por año': s['dias_aviso_anio']}


def avisos_evaluados(x: Experimento, P: dict, claves=None, R: dict | None = None, extendida: bool = True) -> tuple[pd.DataFrame, dict, dict]:
    """Cada configuración como sistema evaluado: regla calibrada en TODA la validación y evaluación en la prueba (común
    y, si hay pronósticos extendidos, extendida). No compiten entre sí: la selección está en `seleccion_avisos`."""
    AV = C.AVISO
    fv, q = x.fechas_val, x.F.q
    CAL, AVI, filas = {}, {}, []
    for k in (claves or P):
        if P[k].get('valmed') is None:
            continue
        CAL[k] = cal = calibrar_regla(fv, P[k]['valmed'], q, x.P95)
        muestras = [('común', x.m.fechas[P[k]['ip']], P[k]['prumed'])]
        if extendida and R is not None and k in R and P[k].get('mx') is not None:
            mx = P[k]['mx']
            muestras.append(('extendida', mx.fechas, C.a_caudal(mx, R[k]['yx'], np.arange(len(mx.fechas)))))
        for mu, fechas, tray in muestras:
            out = AVI[(*k, mu)] = C.evaluar_avisos(fechas, tray, q, x.P95, f=cal['f'], hmax=cal['hmax'], tol=AV['tol'], dmax=AV['dmax'], reinicio=AV['reinicio'])
            filas.append({'estación': x.estacion, 'conjunto': etiqueta(k[0], k[1]), 'modelo': k[2], 'muestra': mu,
                          'escenario de disponibilidad': disponibilidad(k[0], k[1]), 'CSI validación': cal['CSI'], 'FAR validación': cal['FAR'],
                          **fila_avisos(out['resumen'])})
    return pd.DataFrame(filas), CAL, AVI


def seleccion_avisos(x: Experimento, P: dict, candidatos) -> dict:
    """Protocolo común (`comun.seleccion_avisos`) con los candidatos en orden de simplicidad."""
    cand = orden_configuraciones(candidatos)
    return C.seleccion_avisos(x.fechas_val, {k: P[k]['valmed'] for k in cand}, x.F.q, x.P95, cand)


def avisos_efecto_entrada(AVI: dict, comparaciones, modelos=None) -> pd.DataFrame:
    """Cruces detectados con y sin la entrada (mismo modelo) y prueba binomial exacta de los discordantes."""
    from scipy.stats import binomtest
    filas = []
    for nom, con, sin in comparaciones:
        for n in (modelos or ORDEN_MODELOS):
            if (*con, n, 'común') not in AVI or (*sin, n, 'común') not in AVI:
                continue
            ec = AVI[(*con, n, 'común')]['eventos'].set_index('fecha')
            es = AVI[(*sin, n, 'común')]['eventos'].set_index('fecha')
            u = ec.index[ec['evaluable'].astype(bool)].intersection(es.index[es['evaluable'].astype(bool)])
            dc, ds = ec.loc[u, 'detectado'].astype(bool), es.loc[u, 'detectado'].astype(bool)
            b, c_ = int((dc & ~ds).sum()), int((~dc & ds).sum())
            filas.append({'entrada': nom, 'modelo': n, 'cruces': len(u), 'detectados con': int(dc.sum()), 'detectados sin': int(ds.sum()),
                          'solo con la entrada': b, 'solo sin la entrada': c_, 'p (binomial exacta)': binomtest(b, b + c_).pvalue if b + c_ else np.nan,
                          'falsas alarmas con': AVI[(*con, n, 'común')]['resumen']['falsas_alarmas'],
                          'falsas alarmas sin': AVI[(*sin, n, 'común')]['resumen']['falsas_alarmas']})
    return pd.DataFrame(filas)


def conteo_cruces(x: Experimento, ip=None) -> dict:
    """Nuevos cruces del P95 evaluables (elegibilidad causal del cuaderno 04) en el bloque de calibración de la regla
    (2009–2011), en el de comparación (2012–2015) y en la prueba. No depende del pronóstico: se usa la persistencia."""
    AV = C.AVISO
    fv = x.fechas_val
    s0 = C.inicio_seleccion()
    H = len(C.HORIZONTES)
    pv = C.pred_persistencia(x.m, x.p['val'])
    ical, isel = np.where(fv + pd.Timedelta(days=H) < s0)[0], np.where(fv >= s0)[0]
    ip = x.p['pru'] if ip is None else ip
    ev = lambda f, t: C.evaluar_avisos(f, t, x.F.q, x.P95, f=1.0, hmax=30, tol=AV['tol'], dmax=AV['dmax'], reinicio=AV['reinicio'])['resumen']['evaluables']
    return {'estación': x.estacion, 'P95 (m³/s)': x.P95, 'cruces evaluables 2009–2011 (regla)': ev(fv[ical], pv[ical]),
            'cruces evaluables 2012–2015 (comparación)': ev(fv[isel], pv[isel]),
            'cruces evaluables en la prueba': ev(x.m.fechas[ip], C.pred_persistencia(x.m, ip))}


# ----------------------------------------------------------------------------- figuras
def fig_validacion(ax, x: Experimento, tab_val: pd.DataFrame, SELM: dict, modelos=None, titulo: str = ''):
    import seaborn as sns
    import matplotlib.pyplot as plt
    modelos = modelos or [n for n in ORDEN_MODELOS if n in set(tab_val['modelo'])]
    t = tab_val[tab_val['estación'] == x.estacion].pivot_table(index='conjunto', columns='modelo', values='NSE medio selección', sort=False)
    t = t[[n for n in modelos if n in t.columns]]
    sns.heatmap(t.T, annot=True, fmt='.3f', cmap='viridis', ax=ax, cbar=False, annot_kws={'fontsize': 7.5})
    cols = list(t.index)
    for (conj, lat), s in SELM.items():
        if etiqueta(conj, lat) in cols and s in t.columns:
            ax.add_patch(plt.Rectangle((cols.index(etiqueta(conj, lat)), list(t.columns).index(s)), 1, 1, fill=False, ec='crimson', lw=2))
    ax.set_title(titulo or f'{x.estacion}: NSE medio en el bloque de selección 2012–2015 (recuadro: seleccionado en el conjunto)', fontsize=9.5)
    ax.set_xlabel(''); ax.set_ylabel('')
    plt.setp(ax.get_xticklabels(), rotation=35, ha='right', rotation_mode='anchor', fontsize=9)
    return t


def fig_ganancias(entrada_pru: pd.DataFrame, estacion: str, comparaciones, ruta, titulo: str, modelos=None):
    import seaborn as sns
    import matplotlib.pyplot as plt
    sub = entrada_pru[(entrada_pru['estación'] == estacion) & entrada_pru['entrada'].isin(comparaciones)]
    modelos = [n for n in (modelos or ORDEN_MODELOS) if n in set(sub['modelo'])]
    nc = min(4, len(comparaciones)); nf = int(np.ceil(len(comparaciones) / nc))
    fig, ax = plt.subplots(nf, nc, figsize=(3.7 * nc + 1, 0.55 * len(modelos) * nf + 1.6 * nf), sharey=True, squeeze=False)
    ax = ax.ravel()
    for a in ax[len(comparaciones):]:
        a.axis('off')
    for a, c in zip(ax, comparaciones):
        s = sub[sub['entrada'] == c]
        g = s.pivot_table(index='modelo', columns='banda', values='G', sort=False).reindex(index=modelos, columns=BANDAS) * 100
        l = s.pivot_table(index='modelo', columns='banda', values='lectura', aggfunc='first', sort=False).reindex(index=modelos, columns=BANDAS)
        ann = g.round(0).astype('Int64').astype(str) + l.replace(SIG).fillna('')
        sns.heatmap(g, annot=ann.where(g.notna(), ''), fmt='', cmap='RdBu', center=0, vmin=-40, vmax=40, ax=a, cbar=False, annot_kws={'fontsize': 8})
        a.set_title(c, fontsize=9.5); a.set_xlabel(''); a.set_ylabel(''); a.tick_params(axis='x', labelrotation=30)
    alto = fig.get_figheight()                  # se reserva un margen fijo (en pulgadas) para el título general
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.55 / alto))
    fig.suptitle(titulo, fontsize=11, y=1 - 0.1 / alto, va='top')
    fig.savefig(ruta, dpi=200, bbox_inches='tight')
    return fig


def tabla_corta(df: pd.DataFrame, columnas_indice, columna_valor, formato=None, modelos=None):
    """Pivote compacto (filas: índice, columnas: modelos) para mostrar en los cuadernos."""
    d = df.copy()
    if formato:
        d['_v'] = d.apply(formato, axis=1)
        columna_valor = '_v'
    t = d.pivot_table(index=columnas_indice, columns='modelo', values=columna_valor, aggfunc='first', sort=False)
    return t[[n for n in (modelos or ORDEN_MODELOS) if n in t.columns]]


def fmt_delta(r) -> str:
    return f"{r['ΔNSE medio']:+.3f} {CLASE.get(r['clase'], '')}"


def fmt_g(r) -> str:
    return f"{r['G'] * 100:+.0f} % {SIG.get(r['lectura'], '')}"


# ----------------------------------------------------------------------------- salidas
def claves_npz(x: Experimento, P: dict) -> dict:
    """Pronósticos para `predicciones.npz` (mismo formato en 05, 06 y 08): por configuración, media (con Duan) y mediana
    de prueba y mediana de validación; por conjunto, fechas y observaciones de prueba; por estación, fechas de
    validación y del bloque de selección."""
    g = {f'{x.estacion}|fechas_val': x.fechas_val.values.astype('datetime64[D]'),
         f'{x.estacion}|fechas_sel': x.VC.fechas_sel.values.astype('datetime64[D]')}
    for (conj, lat, n), pr in P.items():
        k = f'{x.estacion}|{etiqueta(conj, lat)}'
        g[f'{k}|{n}|media'] = np.asarray(pr['pru'], np.float32)
        g[f'{k}|{n}|mediana'] = np.asarray(pr['prumed'], np.float32)
        g[f'{k}|{n}|sel'] = np.asarray(pr['sel'], np.float32)
        if pr.get('valmed') is not None:
            g[f'{k}|{n}|valmed'] = np.asarray(pr['valmed'], np.float32)
        g[f'{k}|fechas_pru'] = x.m.fechas[pr['ip']].values.astype('datetime64[D]')
        g[f'{k}|obs_pru'] = x.m.q_obs[pr['ip']].astype(np.float32)
    return g
