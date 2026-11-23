"""Estaciones aguas arriba (cuaderno 05): carga, muestras conjuntas, variables y tiempo de tránsito.

Usa exactamente el protocolo v4 de `comun.py` (división temporal, ε, escalones, validación causal, mallas, regla de
selección). Lo único nuevo es que la entrada puede incluir la ventana de 30 días de una o más estaciones aguas arriba.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import comun as C

# Estaciones aguas arriba inmediatas (decisión del proyecto). `inicio` = primer día con fechas confiables según el EDA.
ARRIBA = {
    'San Regis': dict(gid='PE_220105', eda='amazonas_eda', destino='Tamshiyacu', rio='Marañón', inicio=None),
    'Requena': dict(gid='PE_250101', eda='amazonas_eda', destino='Tamshiyacu', rio='Ucayali', inicio=None),
    'Cirato': dict(gid='PE_4724D566', eda='chancay_eda', destino='Racarumi', rio='Chancay', inicio='2022-08-01'),
}


def cargar_arriba(nombre: str) -> tuple[pd.Series, dict]:
    """Caudal observado depurado (m³/s) de una estación aguas arriba, con las mismas reglas del EDA:
    errores eliminados (4.3), meses excluidos por inconsistencia de balance atribuible (4.4) y, si el EDA encontró un
    error de fechas, solo el periodo con fechas confiables (2.7). Todo lo excluido queda como NaN (dato desconocido)."""
    e = ARRIBA[nombre]
    nueva = nombre not in C.ESTACIONES            # se registra solo mientras se carga: C.ESTACIONES sigue con las dos estaciones
    C.ESTACIONES.setdefault(nombre, dict(gid=e['gid'], eda=e['eda'], cuenca='', vertiente=''))   # objetivo (fechas comunes, pruebas)
    try:
        q, info = C.cargar_serie(nombre)
    finally:
        if nueva:
            del C.ESTACIONES[nombre]
    meses = []
    ruta = C.RAIZ / e['eda'] / 'salidas' / 'tablas' / 'tabla_atribucion_balance.csv'
    if ruta.exists():
        t = pd.read_csv(ruta)
        meses = t.loc[t['estación responsable'] == nombre, 'mes'].tolist()
        for mes in meses:
            q.loc[mes] = np.nan
    if e['inicio'] is not None:
        q.loc[:pd.Timestamp(e['inicio']) - pd.Timedelta(days=1)] = np.nan
        q = q.loc[e['inicio']:]
    info.update(meses_excluidos=meses, inicio_confiable=e['inicio'], vacios=float(q.isna().mean() * 100),
                inicio=q.first_valid_index(), fin=q.last_valid_index())
    return q, info


def ventanas_entrada(q: pd.Series, fechas: pd.DatetimeIndex, L: int, eps: float,
                     esc: pd.DatetimeIndex | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Ventana de L días (t−L+1 … t) de log(Q + ε) de una estación de ENTRADA, para cada fecha de emisión t.
    Mismas reglas que la estación objetivo: vacíos ≤ 3 días interpolados solo entre días ≤ t, Q(t) observado y ningún
    escalón de nivel dentro de la ventana. Devuelve (ventanas, válida)."""
    idx = pd.date_range(min(q.index.min(), fechas.min() - pd.Timedelta(days=L)), max(q.index.max(), fechas.max()))
    z = np.log(q.reindex(idx) + eps)
    zi = C.rellenar_cortos(z).to_numpy()
    zv = z.to_numpy()
    pos = idx.get_indexer(fechas)
    cols = pos[:, None] + np.arange(-L + 1, 1)[None, :]
    vent = zi[cols]
    ok = np.isfinite(vent).all(1) & np.isfinite(zv[pos])
    if esc is not None and len(esc):
        marca = np.zeros(len(idx))
        marca[idx.get_indexer(esc)] = 1
        cum = np.concatenate([[0], np.cumsum(marca)])
        # un escalón el día d separa d−1 de d: cuenta si d está en (t−L+1, t]
        ok &= (cum[pos + 1] - cum[pos - L + 2]) == 0
    return vent, ok


def subconjunto(m: C.Muestras, sel: np.ndarray) -> C.Muestras:
    """Muestras restringidas a las filas `sel` (mismo orden)."""
    return C.Muestras(fechas=m.fechas[sel], ventana=m.ventana[sel], doy=m.doy[sel], zt=m.zt[sel], y=m.y[sel],
                      q_obs=m.q_obs[sel], q_t=m.q_t[sel], eps=m.eps, L=m.L, info=dict(m.info),
                      interpolada=None if m.interpolada is None else m.interpolada[sel])


def matriz_arriba(vent: np.ndarray, nombre: str) -> tuple[np.ndarray, list[str]]:
    """Variables de una estación aguas arriba con la misma forma que las de la estación objetivo: nivel de hoy
    log Q_u(t) y cambios respecto a hoy en los L−1 días previos."""
    L = vent.shape[1]
    rel = vent[:, :-1] - vent[:, -1:]
    nom = [f'{nombre}: log Q(t)'] + [f'{nombre}: Δlog Q(t−{k})' for k in range(L - 1, 0, -1)]
    return np.column_stack([vent[:, -1], rel]), nom


def grupos_con_arriba(nombres: list[str]) -> dict[str, list[int]]:
    """Grupos para la importancia por permutación: los de `comun` para la estación objetivo y uno por estación aguas
    arriba (nivel de hoy, cambios de 1–3 días y cambios de 4–29 días)."""
    propios = [n for n in nombres if ':' not in n]
    g = {k: v for k, v in C.grupos_variables(propios).items()}
    for i, n in enumerate(nombres):
        if ':' not in n:
            continue
        est, var = n.split(': ', 1)
        if var == 'log Q(t)':
            clave = f'{est}: caudal de hoy'
        else:
            k = int(var.split('−')[1].rstrip(')'))
            clave = f'{est}: cambio 1–3 días' if k <= 3 else f'{est}: cambio 4–29 días'
        g.setdefault(clave, []).append(i)
    return g


# ----------------------------------------------------------------------------- tiempo de tránsito
def coef_ar(x: np.ndarray, pmax: int = 10) -> np.ndarray:
    """AR(p) por mínimos cuadrados sobre una serie sin vacíos internos (media restada), p elegido por AIC (1…pmax)."""
    x = np.asarray(x, float) - np.nanmean(x)
    mejor = None
    for p in range(1, pmax + 1):
        Y = x[p:]
        Xl = np.column_stack([x[p - k:len(x) - k] for k in range(1, p + 1)])
        ok = np.isfinite(Y) & np.isfinite(Xl).all(1)
        b, *_ = np.linalg.lstsq(Xl[ok], Y[ok], rcond=None)
        res = Y[ok] - Xl[ok] @ b
        aic = ok.sum() * np.log(np.mean(res ** 2)) + 2 * p
        if mejor is None or aic < mejor[0]:
            mejor = (aic, b)
    return mejor[1]


def filtrar_ar(x: pd.Series, b: np.ndarray) -> pd.Series:
    """Residuo e(t) = x(t) − Σ b_k x(t−k) (los NaN se propagan: no se rellena nada)."""
    xc = x - x.mean()
    e = xc.copy()
    for k, bk in enumerate(b, start=1):
        e = e - bk * xc.shift(k)
    return e


def _dlog(q: pd.Series, eps: float, excluir) -> pd.Series:
    """Δlog(Q + ε) con NaN en los días de escalón de nivel (su cambio no es hidrológico)."""
    d = np.log(q.asfreq('D') + eps).diff()
    if excluir is not None and len(excluir):
        d.loc[d.index.isin(excluir)] = np.nan
    return d


def ccf_preblanqueada(arriba: pd.Series, abajo: pd.Series, eps_a: float, eps_b: float, desfases=range(-5, 11),
                      ajuste: tuple[str, str] | None = None, excluir=None) -> pd.DataFrame:
    """Correlación cruzada preblanqueada entre las variaciones diarias Δlog(Q+ε) de la estación aguas arriba en t−k y
    de la de aguas abajo en t. El AR se ajusta a la serie aguas arriba (en el periodo `ajuste` si se indica) y se
    aplica a las dos. El desfase k del máximo estima el tiempo de tránsito en días; k > 0 = aguas arriba se adelanta.
    `excluir`: días de escalón de nivel (de cualquiera de las dos estaciones), cuyo cambio diario se descarta."""
    da, db = _dlog(arriba, eps_a, excluir), _dlog(abajo, eps_b, excluir)
    tramo = da if ajuste is None else da.loc[ajuste[0]:ajuste[1]]
    b = coef_ar(tramo.to_numpy())
    ea, eb = filtrar_ar(da, b), filtrar_ar(db, b)
    filas = []
    for k in desfases:
        par = pd.concat([ea.shift(k), eb], axis=1).dropna()
        filas.append(dict(desfase=k, r=float(np.corrcoef(par.iloc[:, 0], par.iloc[:, 1])[0, 1]) if len(par) > 30 else np.nan,
                          n=len(par)))
    t = pd.DataFrame(filas).set_index('desfase')
    t.attrs['orden_AR'] = len(b)
    return t


def ccf_simple(arriba: pd.Series, abajo: pd.Series, eps_a: float, eps_b: float, desfases=range(-5, 11),
               excluir=None) -> pd.Series:
    """Correlación cruzada SIN preblanquear de Δlog(Q+ε) (para mostrar cómo la autocorrelación la aplana)."""
    da, db = _dlog(arriba, eps_a, excluir), _dlog(abajo, eps_b, excluir)
    return pd.Series({k: pd.concat([da.shift(k), db], axis=1).dropna().corr().iloc[0, 1] for k in desfases})


def desfase_extremos(arriba: pd.Series, abajo: pd.Series, mes_inicio: int = 9, tipo: str = 'max',
                     min_dias: int = 330, excluir: pd.DatetimeIndex | None = None, margen: int = 15) -> pd.DataFrame:
    """Por año hidrológico (inicio en `mes_inicio`) con ≥ min_dias de dato en ambas estaciones: fecha del máximo (o
    mínimo) de cada una y desfase en días (abajo − arriba; > 0 = aguas arriba llega antes). Se descarta el año si
    alguna de las dos fechas cae a ≤ `margen` días de un escalón de nivel de cualquiera de las dos estaciones."""
    filas = []
    a, b = arriba.dropna(), abajo.dropna()
    años = sorted(set(a.index.year) | set(b.index.year))
    for y in años:
        i0 = pd.Timestamp(year=y, month=mes_inicio, day=1)
        i1 = i0 + pd.DateOffset(years=1) - pd.Timedelta(days=1)
        sa, sb = a.loc[i0:i1], b.loc[i0:i1]
        if len(sa) < min_dias or len(sb) < min_dias:
            continue
        fa = sa.idxmax() if tipo == 'max' else sa.idxmin()
        fb = sb.idxmax() if tipo == 'max' else sb.idxmin()
        cerca = False
        if excluir is not None and len(excluir):
            cerca = any(abs((f - e).days) <= margen for f in (fa, fb) for e in excluir)
        filas.append({'año hidrológico': f'{y}-{y + 1}', 'fecha arriba': fa.date(), 'fecha abajo': fb.date(),
                      'desfase (d)': (fb - fa).days, 'cerca de un escalón': cerca})
    return pd.DataFrame(filas)


# ----------------------------------------------------------------------------- comparación con el modelo sin estaciones aguas arriba
BANDAS = {'1–3 días': range(1, 4), '4–7 días': range(4, 8), '8–15 días': range(8, 16), '16–30 días': range(16, 31)}


def _sumas_mes(fechas, x):
    cod = C._bloques(pd.DatetimeIndex(fechas), None)
    out = np.zeros((cod.max() + 1, x.shape[1]))
    np.add.at(out, cod, x)
    return out, cod.max() + 1


def ganancia(fechas, obs: np.ndarray, pred: np.ndarray, base: np.ndarray, B: int = 1000,
             semilla: int = C.SEMILLA) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ganancia de la variante frente al modelo base en los mismos pares emisión–horizonte:
    G = 1 − MSE(variante) / MSE(base) (> 0: la variante reduce el error cuadrático en m³/s).
    IC 90 % por bootstrap de meses de emisión (las mismas réplicas para los 30 horizontes y para las bandas; con la misma
    semilla y fechas, las mismas réplicas para todas las variantes). Devuelve (por horizonte, por banda de horizontes)."""
    ev, nb = _sumas_mes(fechas, (obs - pred) ** 2)
    eb, _ = _sumas_mes(fechas, (obs - base) ** 2)
    k = np.random.default_rng(semilla).integers(0, nb, size=(B, nb))
    EV, EB = ev[k].sum(1), eb[k].sum(1)                       # (B, H)
    g_rep = 1 - EV / EB
    g = 1 - ev.sum(0) / eb.sum(0)
    por_h = pd.DataFrame({'G': g, 'IC90 inferior': np.percentile(g_rep, 5, 0), 'IC90 superior': np.percentile(g_rep, 95, 0),
                          'RMSE base (m³/s)': np.sqrt(eb.sum(0) / len(obs)), 'RMSE variante (m³/s)': np.sqrt(ev.sum(0) / len(obs))},
                         index=pd.Index(range(1, obs.shape[1] + 1), name='h'))
    filas = []
    for nombre, hs in BANDAS.items():
        j = np.array([h for h in hs if h <= obs.shape[1]]) - 1
        if len(j) == 0:
            continue
        gb = 1 - EV[:, j].sum(1) / EB[:, j].sum(1)
        filas.append({'banda': nombre, 'G': float(1 - ev[:, j].sum() / eb[:, j].sum()),
                      'IC90 inferior': float(np.percentile(gb, 5)), 'IC90 superior': float(np.percentile(gb, 95))})
    por_b = pd.DataFrame(filas).set_index('banda')
    for t in (por_h, por_b):
        t['lectura'] = np.where(t['IC90 inferior'] > 0, 'reduce el error',
                                np.where(t['IC90 superior'] < 0, 'aumenta el error', 'sin diferencia demostrada'))
    return por_h, por_b


def delta_nse(fechas, obs: np.ndarray, preds: dict, base: str, B: int = 1000, margen: float = C.MARGEN_NSE,
              semilla: int = C.SEMILLA) -> pd.DataFrame:
    """Diferencia de NSE medio (30 horizontes) de cada variante frente a `base`, con IC 90 % por bootstrap pareado de
    meses (las mismas réplicas para todas). Clases de la regla del proyecto: mejora (IC > 0), equivalente (IC dentro de
    ±margen), peor (IC < 0), inconcluso (resto)."""
    bl = C._bloques_mes(fechas)
    rng = np.random.default_rng(semilla)
    nombres = list(preds)
    reps = np.zeros((B, len(nombres)))
    for b in range(B):
        idx = np.concatenate([bl[j] for j in rng.integers(0, len(bl), len(bl))])
        o = obs[idx]
        den = ((o - o.mean(0)) ** 2).sum(0)
        for k, n in enumerate(nombres):
            reps[b, k] = np.mean(1 - ((o - preds[n][idx]) ** 2).sum(0) / den)
    kb = nombres.index(base)
    filas = []
    for k, n in enumerate(nombres):
        if n == base:
            continue
        d = reps[:, k] - reps[:, kb]
        lo, hi = float(np.percentile(d, 5)), float(np.percentile(d, 95))
        clase = ('mejora' if lo > 0 else 'equivalente' if (lo > -margen and hi < margen) else 'peor' if hi < 0 else 'inconcluso')
        filas.append({'variante': n, 'NSE medio': C.nse_medio(preds[n], obs), f'NSE medio {base}': C.nse_medio(preds[base], obs),
                      'ΔNSE medio': C.nse_medio(preds[n], obs) - C.nse_medio(preds[base], obs),
                      'IC90 inferior': lo, 'IC90 superior': hi, 'clase': clase})
    return pd.DataFrame(filas).set_index('variante')


# ----------------------------------------------------------------------------- Racarumi–Cirato (exploratorio)
def prueba_cirato(qR: pd.Series, qC: pd.Series, epsR: float, epsC: float, desde: str, hasta: str,
                  horizontes=(1, 2, 3), Lc: int = 7, B: int = 1000, semilla: int = C.SEMILLA) -> pd.DataFrame:
    """Prueba exploratoria en el único periodo con fechas confiables en ambas estaciones. Regresión lineal del cambio
    log de Racarumi a h días con su ventana de Lc días, con y sin la ventana de Lc días de Cirato. Validación cruzada
    dejando fuera un mes calendario completo y purgando del ajuste las emisiones a menos de Lc + h días de ese mes (sus
    ventanas u objetivos tocarían el mes evaluado). Pronóstico = mediana (exp del cambio log), en m³/s.
    G = 1 − MSE(con Cirato)/MSE(sin Cirato) con IC 90 % por bootstrap de meses.
    ALCANCE: es una evaluación RETROSPECTIVA por bloques: el modelo de cada mes se ajusta también con meses
    posteriores; no equivale a pronosticar entrenando solo con el pasado (el modo prospectivo está en el cuaderno 08,
    `entradas.cirato_exploratorio(modo='prospectivo')`) y no reproduce la partición histórica del estudio."""
    from sklearn.linear_model import LinearRegression
    idx = pd.date_range(desde, hasta)
    zr = np.log(qR.reindex(idx) + epsR)
    zc = np.log(qC.reindex(idx) + epsC)
    filas = []
    for h in horizontes:
        Xr = np.column_stack([zr.shift(k) for k in range(Lc)])
        Xc = np.column_stack([zc.shift(k) for k in range(Lc)])
        y = (zr.shift(-h) - zr).to_numpy()
        ok = np.isfinite(Xr).all(1) & np.isfinite(Xc).all(1) & np.isfinite(y)
        f = idx[ok]
        XR = np.column_stack([Xr[ok][:, 0], Xr[ok][:, 1:] - Xr[ok][:, :1]])
        XC = np.column_stack([XR, Xc[ok][:, 0], Xc[ok][:, 1:] - Xc[ok][:, :1]])
        yy, z0 = y[ok], zr.to_numpy()[ok]
        obs = np.exp(z0 + yy) - epsR
        pr = {'sin Cirato': np.full(len(yy), np.nan), 'con Cirato': np.full(len(yy), np.nan)}
        meses = f.to_period('M')
        for mes in meses.unique():
            te = meses == mes
            ini, fin = f[te].min(), f[te].max()
            tr = (f < ini - pd.Timedelta(days=Lc + h)) | (f > fin + pd.Timedelta(days=Lc + h))
            for et, X in (('sin Cirato', XR), ('con Cirato', XC)):
                mod = LinearRegression().fit(X[tr], yy[tr])
                pr[et][te] = np.exp(z0[te] + mod.predict(X[te])) - epsR
        pers = np.exp(z0) - epsR
        por_h, _ = ganancia(f, obs[:, None], pr['con Cirato'][:, None], pr['sin Cirato'][:, None], B=B, semilla=semilla)
        filas.append({'h': h, 'diseño': 'retrospectivo por bloques mensuales (ajusta con meses anteriores y posteriores al evaluado)',
                      'modelo': 'regresión lineal', 'periodo': f'{f.min():%Y-%m-%d} a {f.max():%Y-%m-%d}',
                      'emisiones': int(ok.sum()), 'meses': int(len(meses.unique())),
                      'NSE sin Cirato': C.nse(obs, pr['sin Cirato']), 'NSE con Cirato': C.nse(obs, pr['con Cirato']),
                      'NSE persistencia': C.nse(obs, pers),
                      'G (con frente a sin)': float(por_h['G'].iloc[0]), 'IC90 inferior': float(por_h['IC90 inferior'].iloc[0]),
                      'IC90 superior': float(por_h['IC90 superior'].iloc[0]), 'lectura': por_h['lectura'].iloc[0]})
    return pd.DataFrame(filas).set_index('h')
