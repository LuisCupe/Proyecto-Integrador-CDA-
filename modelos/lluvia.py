"""Lluvia-escorrentía (cuaderno 06): lluvia de cuenca, variables de lluvia, modelos por horizonte y respuesta.

Usa exactamente el protocolo v4 de `comun.py` (división temporal, ε, escalones, validación causal, mallas, regla de
selección). Lo único nuevo es que la entrada puede incluir la lluvia media de la cuenca (PISCOp v2.1, columna `prec`
de CAMELS-PE):

- **lluvia observada hasta t, disponibilidad supuesta** (antecedente): escenario RETROSPECTIVO que supone que la lluvia
  del día de emisión t (dato diario de PISCOp) ya se conoce al emitir; no se ha demostrado que esté disponible a tiempo;
- **lluvia disponible hasta t−1**: la misma lluvia con un día de retraso (la de t se desconoce al emitir);
- **lluvia futura observada, escenario idealizado** t+1 … t+h: la lluvia que cayó después de emitir, como si se conociera
  (un pronóstico de lluvia perfecto). No está disponible al emitir; mide el beneficio que se obtiene con ESA información y
  ESTOS modelos, no un límite superior matemático garantizado. Para el horizonte h solo se usa la lluvia hasta t+h.
Fecha de emisión en datos diarios: t es el día cuyo caudal medio diario ya se observó; los objetivos son t+1 … t+30.
Las etiquetas de estos escenarios son las constantes ESC_* de este módulo y las usan los cuadernos 06–09.

Las variables de lluvia entran como log(1 + P) (P en mm, de un día o sumada en un bloque), porque el objetivo es un
cambio logarítmico del caudal. Con mm sin transformar, la regresión lineal extrapola mal en lluvias extremas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin

# Etiquetas únicas de los escenarios de lluvia: las mismas en tablas, figuras, módulos y síntesis
ESC_BASE = 'Solo caudal'
ESC_OBS = '+ lluvia observada hasta t (disponibilidad supuesta)'
ESC_LAT = '+ lluvia disponible hasta t−1'
ESC_FUT = '+ lluvia futura observada (escenario idealizado)'

import comun as C
import aguas_arriba as A

# Bloques de la lluvia ANTECEDENTE (días antes de t; 0 = el propio día t). Días 0–6 uno por uno; luego sumas.
BLOQUES_PASADO = [(k, k) for k in range(7)] + [(7, 14), (15, 29), (30, 89)]
# Bloques de la lluvia FUTURA (días después de t); para el horizonte h se recortan a ≤ h.
BLOQUES_FUTURO = [(1, 1), (2, 2), (3, 3), (4, 7), (8, 15), (16, 30)]
DIAS_PASADO = max(b for _, b in BLOQUES_PASADO) + 1          # 90 días antecedentes
DIAS_FUTURO = max(b for _, b in BLOQUES_FUTURO)              # 30 días


def cargar_lluvia(nombre: str) -> pd.Series:
    """Lluvia media diaria de la cuenca de la estación (mm/d, PISCOp v2.1) de CAMELS-PE, con calendario completo."""
    gid = C.ESTACIONES[nombre]['gid']
    df = pd.read_csv(C.asegurar_camels() / '03_timeseries' / 'by_catchment' / f'{gid}.csv', parse_dates=['date']).set_index('date')
    if df.index.duplicated().any():
        raise ValueError(f'{nombre}: fechas duplicadas en CAMELS-PE')
    p = df['prec'].sort_index().asfreq('D')
    p.name = f'P {nombre}'
    return p


def _nombre_bloque(a: int, b: int, futuro: bool) -> str:
    s = '+' if futuro else '−'
    if a == b:
        return f'P(t{s}{a})' if a else 'P(t)'
    return f'ΣP(t{s}{a}…t{s}{b})' if futuro else f'ΣP(t−{b}…t−{a})'


def matriz_lluvia(p: pd.Series, fechas: pd.DatetimeIndex, desfase: int = 0) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Lluvia ANTECEDENTE para cada emisión t: log(1 + P) de los días t … t−6 y de las sumas de t−7…t−14, t−15…t−29 y
    t−30…t−89 (P en mm). `desfase` = d desplaza todo d días hacia atrás (la lluvia del día t no se conocería hasta d días después:
    sensibilidad a la latencia del producto). Devuelve (X, nombres, válida)."""
    idx = pd.date_range(fechas.min() - pd.Timedelta(days=DIAS_PASADO + desfase), fechas.max())
    pv = p.reindex(idx).to_numpy()
    pos = idx.get_indexer(fechas) - desfase
    cols, nom = [], []
    for a, b in BLOQUES_PASADO:
        ventana = pv[pos[:, None] - np.arange(a, b + 1)[None, :]]
        cols.append(ventana.sum(1))                                   # NaN si falta algún día del bloque
        nom.append(_nombre_bloque(a, b, False) + (f' [latencia {desfase} d]' if desfase else ''))
    X = np.log1p(np.column_stack(cols))
    return X, nom, np.isfinite(X).all(1)


def matriz_futura(p: pd.Series, fechas: pd.DatetimeIndex, H: int = 30) -> tuple[np.ndarray, np.ndarray]:
    """Lluvia FUTURA observada P(t+1) … P(t+H) de cada emisión (mm/d), día por día. Solo para el escenario idealizado.
    Devuelve (F, válida)."""
    idx = pd.date_range(fechas.min(), fechas.max() + pd.Timedelta(days=H))
    pv = p.reindex(idx).to_numpy()
    pos = idx.get_indexer(fechas)
    F = pv[pos[:, None] + np.arange(1, H + 1)[None, :]]
    return F, np.isfinite(F).all(1)


def futuro_para_h(F: np.ndarray, h: int) -> tuple[np.ndarray, list[str]]:
    """Variables de lluvia futura para el horizonte h: log(1 + P) de los bloques de BLOQUES_FUTURO recortados a ≤ h días
    (nunca la lluvia posterior a la fecha objetivo t+h). F está en mm (matriz_futura)."""
    cols, nom = [], []
    for a, b in BLOQUES_FUTURO:
        if a > h:
            continue
        b = min(b, h)
        cols.append(np.log1p(F[:, a - 1:b].sum(1)))
        nom.append(_nombre_bloque(a, b, True))
    return np.column_stack(cols), nom


class PorHorizonte(BaseEstimator, RegressorMixin):
    """Un modelo por horizonte con las mismas variables pasadas y, si `futuro`, la lluvia futura recortada a ≤ h.

    X = [variables conocidas en t (n_pasado columnas) | P(t+1) … P(t+30) (30 columnas, solo si futuro)].
    Para XGBoost es equivalente a la estrategia de v4 (un árbol por horizonte en cada ronda) y para la regresión
    lineal a la multisalida de sklearn; se usa en las tres variantes para que el estimador sea el mismo y la única
    diferencia sea la información de entrada."""

    def __init__(self, nombre='XGBoost', params=None, semilla=C.SEMILLA, n_pasado=0, futuro=False, H=30):
        self.nombre, self.params, self.semilla, self.n_pasado, self.futuro, self.H = nombre, params, semilla, n_pasado, futuro, H

    def _X(self, X, h):
        if not self.futuro:
            return X[:, :self.n_pasado]
        fut, _ = futuro_para_h(X[:, self.n_pasado:self.n_pasado + self.H], h)
        return np.column_stack([X[:, :self.n_pasado], fut])

    def fit(self, X, y):
        assert X.shape[1] == self.n_pasado + (self.H if self.futuro else 0), 'columnas de entrada inesperadas'
        self.modelos_ = [C.crear_tabular(self.nombre, dict(self.params or {}), self.semilla).fit(self._X(X, h), y[:, h - 1])
                         for h in range(1, y.shape[1] + 1)]
        return self

    def predict(self, X, iteration_range=None):
        kw = {} if iteration_range is None else dict(iteration_range=iteration_range)
        return np.column_stack([m.predict(self._X(X, h), **kw) for h, m in enumerate(self.modelos_, start=1)])


def ajustar_malla_h(nombre: str, X, y, Xv, a_q, obs_v, n_pasado: int, futuro: bool, semilla: int = C.SEMILLA) -> list[dict]:
    """La misma búsqueda de `comun.ajustar_malla` (malla de v4, NSE medio en el bloque de selección, XGBoost
    evaluado por etapas con un solo ajuste) con el estimador PorHorizonte."""
    import json
    import time
    malla = dict(C.MALLAS[nombre])
    etapa = C.ETAPAS.get(nombre)
    etapas = malla.pop(etapa) if etapa else None
    filas = []
    for params in C.combinaciones(malla):
        t0 = time.time()
        if etapa:
            mod = PorHorizonte(nombre, {**params, etapa: max(etapas)}, semilla, n_pasado, futuro).fit(X, y)
            for k in etapas:
                yv = mod.predict(Xv, iteration_range=(0, k))
                filas.append(dict(modelo=nombre, parametros=json.dumps({**params, etapa: k}), NSE_val=C.nse_medio(a_q(yv), obs_v),
                                  segundos=(time.time() - t0) / len(etapas)))
        else:
            mod = PorHorizonte(nombre, params, semilla, n_pasado, futuro).fit(X, y)
            filas.append(dict(modelo=nombre, parametros=json.dumps(params), NSE_val=C.nse_medio(a_q(mod.predict(Xv)), obs_v),
                              segundos=time.time() - t0))
    return filas


def grupos_lluvia(nombres: list[str], n_pasado: int, futuro: bool) -> dict[str, list[int]]:
    """Grupos para la importancia por permutación: los de `comun` para el caudal y la época del año, cuatro de
    lluvia antecedente y, si `futuro`, cuatro de lluvia futura (sus 30 columnas diarias agrupadas en 1–3, 4–7, 8–15 y
    16–30 días; al permutar una columna diaria se permuta en todos los horizontes que la usan)."""
    def grupo_pasado(a):
        return ('Lluvia de hoy y ayer (t, t−1)' if a <= 1 else 'Lluvia de t−2 a t−6' if a <= 6 else
                'Lluvia de t−7 a t−29' if a <= 15 else 'Lluvia de t−30 a t−89 (humedad antecedente)')
    nombres_ll = {_nombre_bloque(a, b, False): grupo_pasado(a) for a, b in BLOQUES_PASADO}
    g = {k: v for k, v in C.grupos_variables([n for n in nombres if n.split(' [')[0] not in nombres_ll]).items()}
    for i, n in enumerate(nombres[:n_pasado]):
        if n.split(' [')[0] in nombres_ll:
            g.setdefault(nombres_ll[n.split(' [')[0]], []).append(i)
    if futuro:
        for d in range(1, DIAS_FUTURO + 1):
            clave = ('Lluvia futura t+1…t+3' if d <= 3 else 'Lluvia futura t+4…t+7' if d <= 7 else
                     'Lluvia futura t+8…t+15' if d <= 15 else 'Lluvia futura t+16…t+30')
            g.setdefault(clave, []).append(n_pasado + d - 1)
    return g


# ----------------------------------------------------------------------------- respuesta del caudal a la lluvia
def ccf_lluvia(p: pd.Series, q: pd.Series, eps: float, desfases=range(-3, 16), ajuste: tuple[str, str] | None = None,
               excluir=None) -> pd.DataFrame:
    """Correlación cruzada entre la lluvia P(t−k) y la variación diaria Δlog(Q+ε)(t), preblanqueada con un AR(p)
    (p por AIC) ajustado a la lluvia en el periodo `ajuste` y aplicado a las dos series. k > 0: la lluvia se
    adelanta al caudal. Devuelve columnas r (preblanqueada), r_simple y n."""
    dq = A._dlog(q, eps, excluir)
    pp = p.reindex(dq.index)
    tramo = pp if ajuste is None else pp.loc[ajuste[0]:ajuste[1]]
    b = A.coef_ar(tramo.to_numpy())
    ep, eq = A.filtrar_ar(pp, b), A.filtrar_ar(dq, b)
    filas = []
    for k in desfases:
        par = pd.concat([ep.shift(k), eq], axis=1).dropna()
        par2 = pd.concat([pp.shift(k), dq], axis=1).dropna()
        filas.append(dict(desfase=k, r=float(np.corrcoef(par.iloc[:, 0], par.iloc[:, 1])[0, 1]),
                          r_simple=float(np.corrcoef(par2.iloc[:, 0], par2.iloc[:, 1])[0, 1]), n=len(par)))
    t = pd.DataFrame(filas).set_index('desfase')
    t.attrs['orden_AR'] = len(b)
    return t


def balance_anual(p: pd.Series, q: pd.Series, area: float, mes_inicio: int = 9, min_dias: int = 330) -> pd.DataFrame:
    """Por año hidrológico (inicio en `mes_inicio`) con ≥ min_dias de caudal observado: lluvia (mm), escorrentía
    (mm, caudal medio de los días con dato × 365.25) y coeficiente de escorrentía Q/P."""
    qmm = q * 86400 / (area * 1000)                      # m³/s → mm/d
    filas = []
    for y in range(p.index.year.min(), p.index.year.max() + 1):
        i0 = pd.Timestamp(year=y, month=mes_inicio, day=1)
        i1 = i0 + pd.DateOffset(years=1) - pd.Timedelta(days=1)
        sq, sp = qmm.loc[i0:i1], p.loc[i0:i1]
        if sq.notna().sum() < min_dias or len(sp) < 365:
            continue
        P = float(sp.sum())
        Q = float(sq.mean() * 365.25)
        filas.append({'año hidrológico': f'{y}-{y + 1}', 'lluvia (mm)': P, 'escorrentía (mm)': Q, 'Q/P': Q / P,
                      'días con caudal': int(sq.notna().sum())})
    return pd.DataFrame(filas).set_index('año hidrológico')


def desfase_estacional(p: pd.Series, q: pd.Series, max_meses: int = 4) -> pd.DataFrame:
    """Correlación entre la climatología mensual de la lluvia desplazada k meses y la del caudal (k = 0 … max_meses):
    el k del máximo indica cuántos meses va el régimen del caudal detrás del de la lluvia."""
    cp = p.groupby(p.index.month).mean()
    cq = q.groupby(q.index.month).mean()
    filas = [{'desfase (meses)': k, 'r': float(np.corrcoef(np.roll(cp.to_numpy(), k), cq.to_numpy())[0, 1])} for k in range(max_meses + 1)]
    return pd.DataFrame(filas).set_index('desfase (meses)')


def respuesta_crecidas(p: pd.Series, q: pd.Series, umbral: float, ventana: int, sep: int = C.SEP_EVENTOS) -> pd.DataFrame:
    """Para cada evento sobre el umbral (C.eventos): fecha del pico, fecha del día más lluvioso en los `ventana` días
    previos al pico (incluido) y desfase pico − lluvia máxima (días). Descriptivo."""
    ev = C.eventos(q, umbral, sep=sep)
    filas = []
    for r in ev.itertuples():
        ini, fin = r.inicio, r.fin
        tramo = q.loc[ini:fin]
        fp = tramo.idxmax()
        lp = p.loc[fp - pd.Timedelta(days=ventana - 1):fp]
        fl = lp.idxmax()
        filas.append({'inicio': ini.date(), 'pico': fp.date(), 'Q pico (m³/s)': float(tramo.max()), 'lluvia máxima (mm/d)': float(lp.max()),
                      'fecha lluvia máxima': fl.date(), f'lluvia {ventana} d previos (mm)': float(lp.sum()),
                      'desfase pico − lluvia máxima (d)': int((fp - fl).days)})
    return pd.DataFrame(filas)
