# -*- coding: utf-8 -*-
"""Comparación sistemática de ENTRADAS y MODELOS (cuaderno 08), con el protocolo v4 de `comun.py`.

Pregunta: ¿cuánto del desempeño se debe a la información de entrada y cuánto al método? Para separar los dos efectos:
- **efecto de una entrada:** el MISMO modelo, con la misma búsqueda de hiperparámetros, las mismas filas y la misma
  evaluación, con y sin esa entrada;
- **efecto del método:** modelos distintos con la MISMA información, fechas y condiciones de evaluación.

Solo se usa información disponible en CAMELS-PE v1.0.1: caudal local, calendario, lluvia media de la cuenca (PISCOp v2.1)
y caudal de las estaciones aguas arriba con registro confiable. No se usan humedad del suelo, lluvia espacial ni
pronósticos meteorológicos. La lluvia FUTURA observada no entra aquí (escenario idealizado de los cuadernos 06 y 07).

Fuentes de entrada (fichas que forman un conjunto):
- 'P'   lluvia antecedente: log(1 + P) de los días t … t−6 y de las sumas t−7…t−14, t−15…t−29 y t−30…t−89 (cuaderno 06);
- 'Pd'  la misma lluvia con el detalle temporal que recibe la LSTM: log(1 + P) de CADA día t … t−29 y la suma
        t−30…t−89 (comparación controlada del método con el mismo contenido temporal);
- 'IA'  índices antecedentes: índice de precipitación antecedente IPA_k(t) = k·IPA_k(t−1) + P(t) con k = 0.90 y 0.97
        (memoria de ~10 y ~33 días) y días consecutivos secos (P < 1 mm/d) hasta t, en log(1 + x). Se agregan SOBRE 'P'
        para comprobar si aportan información adicional a los acumulados;
- 'A:<estación>' caudal aguas arriba: nivel log Q_u(t) y cambios de los 29 días previos (cuaderno 05).
`latencia` d desplaza TODAS las fuentes externas d días hacia atrás (el dato del día t llega d días tarde), incluidos
los índices derivados de la lluvia (que se toman en t − d, calculados solo con lluvia hasta t − d); el caudal local
siempre llega hasta t.

Representación por familia de modelos (no es idéntica; ver `inventario_entradas`): los modelos tabulares reciben la
lluvia como 7 días + 3 sumas (o 30 días + 1 suma con 'Pd') y los índices solo en la fecha disponible; la LSTM recibe
canales diarios de 30 días de lluvia e índices más la suma t−30…t−89; el KNN usa de cada caudal el nivel y los últimos
`ventana` − 1 cambios (hiperparámetro).
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.neighbors import KNeighborsRegressor
from sklearn.preprocessing import StandardScaler

import aguas_arriba as A
import comun as C
import lluvia as LL

K_IPA = (0.90, 0.97)
UMBRAL_SECO = 1.0                      # mm/d de lluvia media de la cuenca
VERSION_EXPERIMENTO = 'entradas-2'      # versión del diseño de entradas (forma parte de la identidad de la caché)
RUTA_CACHE = Path(__file__).resolve().parent / C.ruta_salidas() / 'entradas' / 'cache'


# ----------------------------------------------------------------------------- índices de lluvia
def comprobar_diaria(s, nombre: str = 'serie'):
    """Contrato de datos: índice de fechas único, creciente y diario sin días ausentes (T01). Un día ausente no se
    trata como el día anterior: se rechaza."""
    idx = pd.DatetimeIndex(s.index)
    if idx.has_duplicates:
        raise ValueError(f'{nombre}: fechas duplicadas')
    if not idx.is_monotonic_increasing:
        raise ValueError(f'{nombre}: fechas desordenadas')
    if len(idx) > 1 and (np.diff(idx.values).astype('timedelta64[D]').astype(int) != 1).any():
        raise ValueError(f'{nombre}: faltan días en el índice (frecuencia diaria exigida)')


def indices_lluvia(p: pd.Series, inicio: str = 'cero') -> pd.DataFrame:
    """IPA_0.90, IPA_0.97 (mm) y días consecutivos secos (P < UMBRAL_SECO) de la serie diaria completa, calculados
    hacia adelante (cada valor usa solo la lluvia hasta ese día).
    Arranque: `inicio='cero'` (principal) empieza el IPA en 0 el primer día del registro; `inicio='estacionario'`
    (sensibilidad) lo empieza en P̄/(1 − k), con P̄ la media de la lluvia del entrenamiento. Una diferencia inicial se
    atenúa como k^n: con k = 0.97 tarda 152 días en bajar al 1 %, y en Racarumi la lluvia empieza solo 60 días antes de
    la primera ventana de la LSTM, así que el arranque NO es despreciable en las primeras emisiones de entrenamiento:
    su efecto se mide con la sensibilidad del cuaderno 08. En Tamshiyacu la distancia es de 1 338 días.
    Días secos: si el registro empieza en una racha seca, su duración previa es desconocida y se cuenta desde el primer
    día; la primera lluvia ≥ UMBRAL_SECO elimina esa ambigüedad (en las dos estaciones ocurre en los 3 primeros días)."""
    comprobar_diaria(p, 'lluvia')
    v = p.to_numpy(float)
    if not np.isfinite(v).all():
        raise ValueError('la lluvia tiene vacíos: el IPA no se puede propagar')
    if (v < 0).any():
        raise ValueError('lluvia negativa')
    pm = float(p.loc[:C.FIN_ENTRENAMIENTO].mean())
    out = {}
    for k in K_IPA:
        a = np.zeros(len(v))
        a0 = 0.0 if inicio == 'cero' else pm / (1 - k)
        for i in range(len(v)):
            a[i] = k * (a[i - 1] if i else a0) + v[i]
        out[f'IPA k={k:.2f}'] = a
    seco = np.zeros(len(v))
    for i in range(len(v)):
        seco[i] = (seco[i - 1] + 1 if i else 1.0) if v[i] < UMBRAL_SECO else 0.0
    out['días secos consecutivos'] = seco
    return pd.DataFrame(out, index=p.index)


# ----------------------------------------------------------------------------- fuentes de una estación
@dataclass
class Fuentes:
    nombre: str
    q: pd.Series
    eps: float
    esc: pd.DatetimeIndex
    P: pd.Series
    IA: pd.DataFrame
    arriba: dict = field(default_factory=dict)           # nombre → dict(q, eps, esc)

    @classmethod
    def cargar(cls, nombre: str, arriba=()):
        q, _ = C.cargar_serie(nombre)
        P = LL.cargar_lluvia(nombre)
        ar = {}
        for n in arriba:
            qa, _ = A.cargar_arriba(n)
            eps_a = C.eps_entrenamiento(qa) if A.ARRIBA[n]['inicio'] is None else float(qa.mean() / 100)
            esc_a = C.escalones(qa) if A.ARRIBA[n]['inicio'] is None else pd.DatetimeIndex([])
            ar[n] = dict(q=qa, eps=eps_a, esc=esc_a)
        return cls(nombre, q, C.eps_entrenamiento(q), C.escalones(q), P, indices_lluvia(P), ar)

    def con_ipa(self, inicio: str) -> 'Fuentes':
        """Las mismas fuentes con otro arranque del IPA (sensibilidad)."""
        return dataclasses.replace(self, IA=indices_lluvia(self.P, inicio=inicio))


def fichas(conjunto: str) -> list[str]:
    """'Q', 'Q+P', 'Q+P+IA', 'Q+A:San Regis', 'Q+P+A:San Regis+A:Requena' … → lista de fichas sin 'Q'."""
    f = [x for x in conjunto.split('+') if x]
    assert f[0] == 'Q', 'todo conjunto empieza por el caudal local Q'
    assert 'IA' not in f or 'P' in f or 'Pd' in f, "'IA' se agrega sobre la lluvia (se evalúa su aporte adicional)"
    return f[1:]


def _desplazar(fechas: pd.DatetimeIndex, d: int) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(fechas) - pd.Timedelta(days=d)


def matriz(m: C.Muestras, F: Fuentes, conjunto: str, latencia: int = 0):
    """Variables tabulares del conjunto para las emisiones de `m`.
    Devuelve (X, nombres, estructura, válida). X = [bloque de caudal local (L columnas) | calendario (2) | fuentes].
    `estructura`: tupla de (inicio, largo, tipo) por bloque; tipo 'ventana' (nivel + L−1 cambios, el KNN elige cuántos
    usa), 'fijo' (se usan todas) o 'calendario'."""
    Xq, nom = C.matriz_tabular(m)
    L = m.L
    cols, nombres = [Xq], list(nom)
    est = [(0, L, 'ventana'), (L, 2, 'calendario')]
    ok = np.ones(len(m.fechas), bool)
    j = L + 2
    for f in fichas(conjunto):
        if f == 'P':
            Xp, n, okp = LL.matriz_lluvia(F.P, m.fechas, desfase=latencia)
            cols.append(Xp); nombres += n; ok &= okp
            est.append((j, Xp.shape[1], 'fijo')); j += Xp.shape[1]
        elif f == 'Pd':
            Xp, n, okp = lluvia_diaria(F.P, m.fechas, L, latencia)
            cols.append(Xp); nombres += n; ok &= okp
            est.append((j, Xp.shape[1], 'fijo')); j += Xp.shape[1]
        elif f == 'IA':
            V = np.log1p(F.IA.reindex(_desplazar(m.fechas, latencia)).to_numpy())
            cols.append(V); nombres += [f'log(1+{c})' + (f' [latencia {latencia} d]' if latencia else '') for c in F.IA.columns]
            ok &= np.isfinite(V).all(1)
            est.append((j, V.shape[1], 'fijo')); j += V.shape[1]
        elif f.startswith('A:'):
            n_a = f[2:]
            d = F.arriba[n_a]
            vent, oka = A.ventanas_entrada(d['q'], _desplazar(m.fechas, latencia), L, d['eps'], d['esc'])
            Xa, na = A.matriz_arriba(vent, n_a)
            cols.append(Xa); nombres += na; ok &= oka
            est.append((j, L, 'ventana')); j += L
        else:
            raise ValueError(f)
    X = np.column_stack(cols)
    return X, nombres, tuple(est), ok & np.isfinite(X).all(1)


def lluvia_diaria(p: pd.Series, fechas: pd.DatetimeIndex, L: int = C.L_VENTANA, latencia: int = 0):
    """Ficha 'Pd': log(1 + P) de cada día t−d … t−d−L+1 y log(1 + ΣP t−d−L … t−d−89): el mismo contenido temporal de
    lluvia que los canales de la LSTM, en forma tabular. Devuelve (X, nombres, válida)."""
    idx = pd.date_range(fechas.min() - pd.Timedelta(days=LL.DIAS_PASADO + latencia), fechas.max())
    pv = p.reindex(idx).to_numpy()
    pos = idx.get_indexer(fechas) - latencia
    dias = pv[pos[:, None] - np.arange(0, L)[None, :]]
    resto = pv[pos[:, None] - np.arange(L, LL.DIAS_PASADO)[None, :]].sum(1)
    X = np.log1p(np.column_stack([dias, resto]))
    suf = f' [latencia {latencia} d]' if latencia else ''
    nom = [f'P(t−{k})' if k else 'P(t)' for k in range(L)] + [f'ΣP(t−{LL.DIAS_PASADO - 1}…t−{L})']
    return X, [n + suf for n in nom], np.isfinite(X).all(1)


def canales_lstm(m: C.Muestras, F: Fuentes, conjunto: str, latencia: int = 0) -> np.ndarray:
    """Canales adicionales de la LSTM (n, L, k) SIN estandarizar. Contienen la misma FUENTE que `matriz`, pero no la
    misma representación temporal: P: log(1 + P) de CADA día de la ventana (t−d−L+1 … t−d) y la suma de
    t−d−30 … t−d−89 repetida (los tabulares con 'P' reciben 7 días y 3 sumas; con 'Pd', este mismo contenido);
    IA: las tres series diarias de la ventana (los tabulares, solo su valor en t − d); A: log Q_u y su cambio respecto
    al último día de la ventana (equivalente al bloque tabular de nivel + 29 cambios). 'Pd' produce los mismos canales
    que 'P'."""
    L = m.L
    pos_rel = np.arange(-L + 1, 1)
    out = []
    for f in fichas(conjunto):
        if f in ('P', 'Pd', 'IA'):
            serie = (np.log1p(F.P.to_frame()) if f != 'IA' else np.log1p(F.IA))
            idx = pd.date_range(m.fechas.min() - pd.Timedelta(days=L + latencia + 1), m.fechas.max())
            V = serie.reindex(idx).to_numpy()
            pos = idx.get_indexer(_desplazar(m.fechas, latencia))
            W = V[pos[:, None] + pos_rel[None, :]]                         # (n, L, k)
            out.append(W)
            if f in ('P', 'Pd'):
                Xp, _, _ = LL.matriz_lluvia(F.P, m.fechas, desfase=latencia)
                out.append(np.repeat(Xp[:, -1][:, None, None], L, 1))     # log(1 + ΣP t−30…t−89)
        elif f.startswith('A:'):
            d = F.arriba[f[2:]]
            vent, _ = A.ventanas_entrada(d['q'], _desplazar(m.fechas, latencia), L, d['eps'], d['esc'])
            out.append(np.stack([vent, vent - vent[:, -1:]], axis=2))
    if not out:
        return np.zeros((len(m.fechas), L, 0), np.float32)
    return np.concatenate(out, axis=2).astype(np.float32)


# ----------------------------------------------------------------------------- modelos
class KNNEntradas(BaseEstimator, RegressorMixin):
    """KNN de v4 generalizado a varias fuentes: de cada bloque 'ventana' (caudal local y aguas arriba) usa el nivel y
    los últimos ventana−1 cambios; los bloques 'fijo' (lluvia, índices) y el calendario entran completos. Todas las
    columnas se estandarizan con el bloque de ajuste. Con solo el caudal local equivale a `comun.KNNVentana`."""

    def __init__(self, n_neighbors=10, weights='uniform', ventana=30, estructura=()):
        self.n_neighbors, self.weights, self.ventana, self.estructura = n_neighbors, weights, ventana, estructura

    def _cols(self):
        c = []
        for ini, largo, tipo in self.estructura:
            if tipo == 'ventana':
                v = min(self.ventana, largo)
                c += [ini] + list(range(ini + largo - v + 1, ini + largo))
            else:
                c += list(range(ini, ini + largo))
        return c

    def fit(self, X, y):
        self.cols_ = self._cols()
        self.esc_ = StandardScaler().fit(X[:, self.cols_])
        self.knn_ = KNeighborsRegressor(n_neighbors=self.n_neighbors, weights=self.weights, n_jobs=-1)
        self.knn_.fit(self.esc_.transform(X[:, self.cols_]), y)
        return self

    def predict(self, X):
        return self.knn_.predict(self.esc_.transform(X[:, self.cols_]))


def crear(nombre: str, params: dict, semilla: int, estructura):
    if nombre == 'KNN':
        return KNNEntradas(estructura=estructura, **params)
    return C.crear_tabular(nombre, params, semilla)


class LSTMEntradas:
    """LSTM de v4 (mismo protocolo de épocas: entrena hasta 2004, detiene con 2005–2008 y reentrena E épocas) con
    canales adicionales estandarizados con el bloque de ajuste."""

    def __init__(self, m, E, ent_in, parada, oculto, dropout, semilla=C.SEMILLA):
        self.m, self.E, self.ent_in, self.parada = m, E, ent_in, parada
        self.oculto, self.dropout, self.semilla = oculto, dropout, semilla

    def _x(self, m, E, idx, est):
        mu, sd, me, se = est
        base = C.secuencias(m, idx, mu, sd)
        if E.shape[2] == 0:
            return base
        return np.concatenate([base, ((E[idx] - me) / se).astype(np.float32)], axis=2)

    def _est(self, idx):
        m, E = self.m, self.E
        me = E[idx].reshape(-1, E.shape[2]).mean(0) if E.shape[2] else 0.0
        se = E[idx].reshape(-1, E.shape[2]).std(0) + 1e-6 if E.shape[2] else 1.0
        return float(m.ventana[idx].mean()), float(m.ventana[idx].std()), me, se

    def ajustar(self, ent):
        m = self.m
        est = self._est(self.ent_in)
        ym, ys = m.y[self.ent_in].mean(0), m.y[self.ent_in].std(0)
        _, ep = C.entrenar_lstm(self._x(m, self.E, self.ent_in, est), (m.y[self.ent_in] - ym) / ys,
                                self._x(m, self.E, self.parada, est), (m.y[self.parada] - ym) / ys,
                                oculto=self.oculto, dropout=self.dropout, semilla=self.semilla)
        self.epocas = max(ep, 1)
        return self.reajustar(ent)

    def reajustar(self, ent):
        m = self.m
        self.est_ = self._est(ent)
        self.ym, self.ys = m.y[ent].mean(0), m.y[ent].std(0)
        self.red, _ = C.entrenar_lstm(self._x(m, self.E, ent, self.est_), (m.y[ent] - self.ym) / self.ys, epocas=self.epocas,
                                      oculto=self.oculto, dropout=self.dropout, semilla=self.semilla)
        return self

    def predecir(self, idx, m=None, E=None):
        m = self.m if m is None else m
        E = self.E if E is None else E
        return C.predecir_lstm(self.red, self._x(m, E, idx, self.est_)) * self.ys + self.ym


# ----------------------------------------------------------------------------- experimento con caché reanudable
@dataclass
class Datos:
    """Todo lo que necesita un ajuste: muestras comunes y extendidas, partición, validación causal y entradas."""
    estacion: str
    conjunto: str
    latencia: int
    m: C.Muestras
    p: dict
    VC: C.ValidacionCausal
    X: np.ndarray
    E: np.ndarray
    estructura: tuple
    nombres: list
    ip: np.ndarray                     # índices de prueba (muestra común de esta estación)
    mx: C.Muestras                     # muestra extendida de prueba (filas con entrada válida)
    Xx: np.ndarray
    Ex: np.ndarray


def huella(*arrays) -> str:
    h = hashlib.sha256()
    for a in arrays:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode()); h.update(str(a.shape).encode()); h.update(a.tobytes())
    return h.hexdigest()


def version_libreria(nombre: str) -> str:
    """Versión de la librería que ajusta el modelo: entra en la clave de la caché (otra versión puede dar otro resultado)."""
    import sklearn
    if nombre == 'XGBoost':
        import xgboost
        return f'xgboost {xgboost.__version__}'
    if nombre == 'LSTM':
        import torch
        return f'torch {torch.__version__}'
    return f'scikit-learn {sklearn.__version__}'


def _pasos_lstm(d: Datos):
    ie = d.p['ent']
    ie_in = ie[d.m.fechas[ie] + pd.Timedelta(days=d.m.y.shape[1]) <= pd.Timestamp(C.FIN_PARADA)]
    ie_par = ie[d.m.fechas[ie] > pd.Timestamp(C.FIN_PARADA)]
    return ie_in, ie_par


# Funciones cuyo código determina las predicciones guardadas en la caché. Su huella se calcula sobre el árbol
# sintáctico SIN docstrings: un cambio de documentación no invalida la caché; un cambio de lógica sí.
CODIGO_CACHE = {'entradas': ['_ajuste', '_pasos_lstm', 'crear', 'KNNEntradas', 'LSTMEntradas'],
                'comun': ['MALLAS', 'ETAPAS', 'combinaciones', 'KNNVentana', '_y_estandar', 'crear_tabular', 'predecir_por_etapas',
                          'nse_medio', 'a_caudal', 'factor_duan', 'inicio_seleccion', 'ValidacionCausal', 'secuencias', '_RedLSTM',
                          'entrenar_lstm', 'predecir_lstm', '_torch']}
def _volcado(nodo) -> str:
    """Árbol sintáctico en texto con TODOS los campos (también los vacíos): Python 3.13 omite por omisión los campos
    vacíos en `ast.dump`, y sin `show_empty=True` la huella cambiaría entre 3.12 y 3.13 sin que cambie el código."""
    try:
        return ast.dump(nodo, include_attributes=False, show_empty=True)
    except TypeError:                                  # Python < 3.13: ya muestra los campos vacíos
        return ast.dump(nodo, include_attributes=False)


def huella_codigo(fuentes: dict | None = None) -> str:
    """SHA-256 del código (sin docstrings ni comentarios) de CODIGO_CACHE. `fuentes`: {módulo: texto} para calcularla
    sobre otra versión de los archivos (por ejemplo, la de un commit anterior)."""
    h = hashlib.sha256()
    for mod, nombres in CODIGO_CACHE.items():
        texto = fuentes[mod] if fuentes else Path(inspect.getsourcefile(C if mod == 'comun' else _este())).read_text(encoding='utf-8')
        arbol = ast.parse(texto)
        defs = {}
        for nodo in arbol.body:
            if isinstance(nodo, (ast.FunctionDef, ast.ClassDef)):
                defs[nodo.name] = nodo
            elif isinstance(nodo, ast.Assign) and isinstance(nodo.targets[0], ast.Name):
                defs[nodo.targets[0].id] = nodo
        for n in nombres:
            nodo = defs[n]
            for sub in ast.walk(nodo):
                if isinstance(sub, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and sub.body and \
                        isinstance(sub.body[0], ast.Expr) and isinstance(getattr(sub.body[0], 'value', None), ast.Constant) \
                        and isinstance(sub.body[0].value.value, str):
                    sub.body = sub.body[1:] or [ast.Pass()]
            h.update(f'{mod}.{n}:'.encode()); h.update(_volcado(nodo).encode())
    return h.hexdigest()


def _este():
    import sys
    return sys.modules[__name__]


def huella_particion(d: Datos) -> str:
    """Identidad de las filas de ajuste, validación (calibración y selección), parada de la LSTM y prueba."""
    ie_in, ie_par = _pasos_lstm(d)
    return huella(d.p['ent'], d.p['val'], d.VC.cal, d.VC.sel, ie_in, ie_par, d.ip,
                  d.m.fechas.values.astype('int64'), d.mx.fechas.values.astype('int64'))


def clave_cache(d: Datos, nombre: str, semillas) -> str:
    """Identidad COMPLETA de la inferencia: experimento, protocolo, estación, conjunto, latencia, modelo, software,
    malla, semilla de la búsqueda y semillas finales, datos (entradas X y E, objetivos, fechas, muestra extendida),
    estructura y nombres de las variables, partición exacta (ajuste, calibración, selección, parada de la LSTM, prueba),
    fronteras de los bloques y huella del código que entrena y predice. El identificador de la ejecución NO entra: un
    cambio de documentación o de evaluación no cambia las predicciones, y un cambio de lógica ya cambia la huella del
    código; el identificador se guarda como dato en la entrada. La evaluación (referencias, métricas) no entra: se recalcula."""
    clave = dict(v=VERSION_EXPERIMENTO, protocolo=C.VERSION, est=d.estacion, conj=d.conjunto, lat=d.latencia,
                 modelo=nombre, software=version_libreria(nombre), semilla_busqueda=C.SEMILLA,
                 malla={k: [str(x) for x in v] for k, v in C.MALLAS[nombre].items()}, semillas=semillas,
                 datos=huella(d.X, d.E, d.m.y, d.m.fechas.values.astype('int64'), d.Xx, d.Ex, d.mx.fechas.values.astype('int64')),
                 estructura=[list(x) for x in d.estructura], nombres=huella(np.array(d.nombres, dtype=str)),
                 particion=huella_particion(d),
                 bloques=dict(fin_ent=C.FIN_ENTRENAMIENTO, fin_parada=C.FIN_PARADA, fin_val=C.FIN_VALIDACION,
                              años_cal=C.AÑOS_CALIBRACION, L=C.L_VENTANA, H=len(C.HORIZONTES)),
                 codigo=huella_codigo())
    return json.dumps(clave, sort_keys=True)


def _ruta(texto: str) -> Path:
    return RUTA_CACHE / (hashlib.sha1(texto.encode()).hexdigest()[:20] + '.npz')


def _leer(ruta: Path, texto: str, d: Datos):
    z = np.load(ruta, allow_pickle=False)
    if str(z['clave']) != texto:
        return None
    out = dict(yv=z['yv'], yp=z['yp'], yx=z['yx'], busqueda=pd.read_json(io.StringIO(str(z['busqueda']))), mejor=json.loads(str(z['mejor'])),
               segundos=float(z['segundos']), en_cache=True)
    H = len(C.HORIZONTES)
    forma = out['yv'].shape == (len(d.p['val']), H) and out['yp'].shape == (len(d.ip), H) and out['yx'].shape == (len(d.mx.fechas), H)
    finitos = all(np.isfinite(out[k]).all() for k in ('yv', 'yp', 'yx'))
    fechas = (np.array_equal(z['fechas_val'], d.m.fechas[d.p['val']].values.astype('datetime64[D]'))
                             and np.array_equal(z['fechas_pru'], d.m.fechas[d.ip].values.astype('datetime64[D]'))
                             and np.array_equal(z['fechas_ext'], d.mx.fechas.values.astype('datetime64[D]')))
    if not (forma and finitos and fechas):
        raise ValueError(f'{ruta.name}: la caché no corresponde a las filas del experimento (forma {forma}, finitos {finitos}, fechas {fechas})')
    return out


def _guardar(ruta: Path, texto: str, d: Datos, out: dict):
    RUTA_CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(ruta, yv=out['yv'], yp=out['yp'], yx=out['yx'], busqueda=out['busqueda'].to_json(),
                        mejor=json.dumps(out['mejor']), segundos=out['segundos'], clave=texto, revision=C.REVISION,
                        fechas_val=d.m.fechas[d.p['val']].values.astype('datetime64[D]'),
                        fechas_pru=d.m.fechas[d.ip].values.astype('datetime64[D]'),
                        fechas_ext=d.mx.fechas.values.astype('datetime64[D]'))



def ajustar(d: Datos, nombre: str, semillas=None, cache: bool = True) -> dict:
    """Búsqueda de hiperparámetros en el bloque de selección (2012–2015, Duan de 2009–2011) con la malla de v4 y ajuste
    final con las semillas de v4: entrenamiento → validación; entrenamiento + validación → prueba (común y extendida).
    Devuelve cambios log pronosticados (promedio de las semillas en log: la mediana geométrica de los miembros, no el
    promedio de sus caudales; es la misma regla de v4 para Duan y para las trayectorias de avisos) y la búsqueda.
    Caché en salidas/entradas/cache/ con la identidad completa de `clave_cache`; al leer comprueba la clave, formas,
    valores finitos y fechas guardadas. Solo se reutiliza una entrada con identidad completa idéntica : no hay
    migración ni verificación por analogía con otros modelos o particiones."""
    semillas = list(semillas or (C.SEMILLAS if nombre in C.ESTOCASTICOS else [C.SEMILLA]))
    texto = clave_cache(d, nombre, semillas)
    ruta = _ruta(texto)
    if cache and ruta.exists():
        out = _leer(ruta, texto, d)
        if out is not None:
            return out
    out = _ajuste(d, nombre, semillas)
    if cache:
        _guardar(ruta, texto, d, out)
    return out


def _ajuste(d: Datos, nombre: str, semillas) -> dict:
    t0 = time.time()
    m, p, X, E = d.m, d.p, d.X, d.E
    ie, iv, ip = p['ent'], p['val'], d.ip
    it = np.concatenate([ie, iv])
    jx = np.arange(len(d.mx.fechas))
    filas = []
    if nombre == 'LSTM':
        ie_in, ie_par = _pasos_lstm(d)
        for params in C.combinaciones(C.MALLAS['LSTM']):
            t1 = time.time()
            lp = LSTMEntradas(m, E, ie_in, ie_par, **params).ajustar(ie)
            filas.append(dict(parametros=json.dumps({**params, 'epocas': lp.epocas}), NSE_sel=C.nse_medio(d.VC.a_q(lp.predecir(iv)), d.VC.obs_sel),
                              segundos=time.time() - t1))
        mejor = json.loads(max(filas, key=lambda f: f['NSE_sel'])['parametros'])
        mejor.pop('epocas')
        yv_s, yp_s, yx_s = [], [], []
        for s in semillas:
            lp = LSTMEntradas(m, E, ie_in, ie_par, semilla=s, **mejor).ajustar(ie)
            yv_s.append(lp.predecir(iv))
            lp.reajustar(it)
            yp_s.append(lp.predecir(ip)); yx_s.append(lp.predecir(jx, d.mx, d.Ex))
    else:
        malla = dict(C.MALLAS[nombre])
        etapa = C.ETAPAS.get(nombre)
        etapas = malla.pop(etapa) if etapa else None
        for params in C.combinaciones(malla):
            t1 = time.time()
            if etapa:
                mod = crear(nombre, {**params, etapa: max(etapas)}, C.SEMILLA, d.estructura).fit(X[ie], m.y[ie])
                for k, yv in C.predecir_por_etapas(nombre, mod, X[iv], etapas).items():
                    filas.append(dict(parametros=json.dumps({**params, etapa: k}), NSE_sel=C.nse_medio(d.VC.a_q(yv), d.VC.obs_sel),
                                      segundos=(time.time() - t1) / len(etapas)))
            else:
                mod = crear(nombre, params, C.SEMILLA, d.estructura).fit(X[ie], m.y[ie])
                filas.append(dict(parametros=json.dumps(params), NSE_sel=C.nse_medio(d.VC.a_q(mod.predict(X[iv])), d.VC.obs_sel),
                                  segundos=time.time() - t1))
        mejor = json.loads(max(filas, key=lambda f: f['NSE_sel'])['parametros'])
        yv_s, yp_s, yx_s = [], [], []
        for s in semillas:
            yv_s.append(crear(nombre, mejor, s, d.estructura).fit(X[ie], m.y[ie]).predict(X[iv]))
            mod = crear(nombre, mejor, s, d.estructura).fit(X[it], m.y[it])
            yp_s.append(mod.predict(X[ip])); yx_s.append(mod.predict(d.Xx))
    out = dict(yv=np.mean(yv_s, 0).astype(np.float32), yp=np.mean(yp_s, 0).astype(np.float32), yx=np.mean(yx_s, 0).astype(np.float32),
               busqueda=pd.DataFrame(filas), mejor=mejor, segundos=time.time() - t0, en_cache=False)
    return out


# ----------------------------------------------------------------------------- preparación de una estación
def preparar(F: Fuentes, exigir=(), exigir_ent_val=()):
    """Muestras de la estación (protocolo v4) restringidas a las emisiones en que todos los conjuntos `exigir`
    [(conjunto, latencia), …] tienen entrada válida; en entrenamiento y validación se exige además `exigir_ent_val`
    (así todas las variantes se ajustan con exactamente las mismas filas). Devuelve (m, p, VC, mx), con mx la muestra
    extendida de prueba (emisiones con entrada válida y al menos un objetivo verificable)."""
    L, H = C.L_VENTANA, len(C.HORIZONTES)
    m0 = C.construir_muestras(F.q, L=L, H=H, esc=F.esc, eps=F.eps)
    ok = np.ones(len(m0.fechas), bool)
    for conj, lat in exigir:
        ok &= matriz(m0, F, conj, lat)[3]
    ev = m0.fechas <= pd.Timestamp(C.FIN_VALIDACION)
    for conj, lat in exigir_ent_val:
        ok &= ~ev | matriz(m0, F, conj, lat)[3]
    m = A.subconjunto(m0, np.where(ok)[0])
    p = C.particion(m)
    VC = C.ValidacionCausal(m, p['val'])
    mx0 = C.construir_muestras(F.q, L=L, H=H, esc=F.esc, eps=F.eps, exigir_todos=False)
    okx = mx0.fechas > pd.Timestamp(C.FIN_VALIDACION)
    for conj, lat in exigir:
        okx &= matriz(mx0, F, conj, lat)[3]
    mx = A.subconjunto(mx0, np.where(okx)[0])
    return m, p, VC, mx


# Diseño del experimento (fijado antes de ejecutar). Cada conjunto se evalúa con los seis modelos de v4.
SR, RQ = 'A:San Regis', 'A:Requena'
CONJUNTOS_CONTROL = {('Q+Pd', 0)}       # comparación controlada del método: no compite en las selecciones

# Filas de cada experimento: las emisiones en que TODOS los conjuntos `exigir` (con su latencia) tienen entrada válida;
# en entrenamiento y validación se exige además `exigir_ent_val` (Requena termina en 2020-03: se exige solo ahí y su
# prueba se restringe a las emisiones con Requena válida). Así todas las variantes de un experimento se ajustan y
# validan con exactamente las mismas filas y se comparan en las mismas fechas.
FILAS = {
    # Racarumi: v4 con 91 días de lluvia previos (cuaderno 06 y comparación integrada del 08)
    'Racarumi': dict(arriba=(), exigir=[('Q+P+IA', 0), ('Q+P+IA', 1), ('Q+Pd', 0)], exigir_ent_val=[]),
    # Tamshiyacu, todas las emisiones de los modelos base (cuaderno 06: lluvia)
    'Tamshiyacu (todas las emisiones)': dict(arriba=(), exigir=[('Q+P+IA', 0), ('Q+P+IA', 1)], exigir_ent_val=[]),
    # Tamshiyacu con las estaciones aguas arriba (cuaderno 05 y comparación integrada del 08). Requena se
    # exige también con un día de retraso en entrenamiento y validación (10 emisiones menos), para evaluar las fuentes
    # externas hasta t y hasta t−1 con las mismas filas.
    'Tamshiyacu (con San Regis)': dict(arriba=('San Regis', 'Requena'),
                                       exigir=[('Q+P+IA', 0), ('Q+P+IA', 1), (f'Q+{SR}', 0), (f'Q+{SR}', 1)],
                                       exigir_ent_val=[(f'Q+{RQ}', 0), (f'Q+{RQ}', 1)]),
}


def _con_retraso(conjuntos):
    """Cada conjunto con latencia 0 y, si usa alguna fuente externa, también con latencia 1 (el caudal local siempre
    llega hasta t: 'Q' no tiene versión con retraso)."""
    return [(c, l) for c in conjuntos for l in ((0,) if c == 'Q' else (0, 1))]


DISENO_LLUVIA = {        # cuaderno 06 (precipitación)
    'Racarumi': dict(FILAS['Racarumi'], conjuntos=_con_retraso(['Q', 'Q+P', 'Q+P+IA']) + [('Q+Pd', 0)]),
    'Tamshiyacu': dict(FILAS['Tamshiyacu (todas las emisiones)'], conjuntos=_con_retraso(['Q', 'Q+P', 'Q+P+IA'])),
}
DISENO_ARRIBA = {        # cuaderno 05 (caudal aguas arriba)
    'Tamshiyacu': dict(FILAS['Tamshiyacu (con San Regis)'], conjuntos=_con_retraso(['Q', f'Q+{SR}', f'Q+{RQ}', f'Q+{SR}+{RQ}'])),
}
DISENO_INTEGRADO = {     # cuaderno 08 (comparación integrada): todas las combinaciones implementadas en cada cuenca
    'Racarumi': dict(FILAS['Racarumi'], conjuntos=_con_retraso(['Q', 'Q+P', 'Q+P+IA'])),
    'Tamshiyacu': dict(FILAS['Tamshiyacu (con San Regis)'],
                       conjuntos=_con_retraso(['Q', 'Q+P', 'Q+P+IA', f'Q+{SR}', f'Q+P+{SR}', f'Q+P+IA+{SR}', f'Q+{RQ}', f'Q+P+{RQ}', f'Q+P+IA+{RQ}',
                                               f'Q+{SR}+{RQ}', f'Q+P+{SR}+{RQ}', f'Q+P+IA+{SR}+{RQ}'])),   # las 12 combinaciones de {—, P, P+IA} × {—, SR, RQ, SR+RQ}
}
DISENO = DISENO_INTEGRADO


def n_fuentes(conjunto: str) -> int:
    """Número de fuentes externas del conjunto (lluvia, índices y cada estación cuentan uno): orden de simplicidad de
    las entradas (menos fuentes = más simple)."""
    return len(fichas(conjunto))


def experimento(estacion: str, diseno: dict | None = None):
    """(F, m, p, VC, mx, {(conjunto, latencia): Datos}) del diseño de la estación (por omisión, DISENO). La variante con
    Requena se prueba solo en las emisiones con Requena válida (2016-01 a 2020-03, prueba común del cuaderno 05)."""
    dz = (diseno or DISENO)[estacion]
    F = Fuentes.cargar(estacion, dz['arriba'])
    m, p, VC, mx = preparar(F, dz['exigir'], dz['exigir_ent_val'])
    D = {}
    for conj, lat in dz['conjuntos']:
        ip = None
        if RQ in conj:
            ok = matriz(m, F, conj, lat)[3]
            ip = p['pru'][ok[p['pru']]]
        D[(conj, lat)] = datos(F, m, p, VC, mx, conj, lat, ip)
    return F, m, p, VC, mx, D


def sensibilidad_ipa(F: Fuentes, m, p, VC, mx, conjunto: str = 'Q+P+IA', latencia: int = 0) -> Datos:
    """Las mismas filas y el mismo conjunto con el IPA arrancado en su valor estacionario."""
    return datos(F.con_ipa('estacionario'), m, p, VC, mx, conjunto, latencia)


def inventario_entradas(d: Datos) -> list[dict]:
    """Ficha verificable de lo que recibe cada familia de modelos con este conjunto: variables, dimensión, días
    cubiertos y fecha más reciente de cada fuente respecto a la emisión t."""
    L = d.m.L
    filas = []
    for f in ['Q'] + fichas(d.conjunto):
        lat = 0 if f == 'Q' else d.latencia
        if f == 'Q':
            tab = f'log Q(t) y {L - 1} cambios diarios (t−{L - 1} … t−1) + sen/cos del día del año'
            lstm = f'log Q diario t−{L - 1} … t (estandarizado) + calendario'
            dias_t, dias_l = f't−{L - 1} … t', f't−{L - 1} … t'
        elif f == 'P':
            tab, lstm = '7 días (t … t−6) + sumas t−7…14, t−15…29, t−30…89 (10 variables)', f'{L} días diarios + suma t−30…89 (2 canales)'
            dias_t, dias_l = 't−89 … t (detalle diario solo 7 días)', f't−89 … t (detalle diario {L} días)'
        elif f == 'Pd':
            tab, lstm = f'{L} días diarios + suma t−30…89 ({L + 1} variables)', f'{L} días diarios + suma t−30…89 (2 canales)'
            dias_t, dias_l = f't−89 … t (detalle diario {L} días)', f't−89 … t (detalle diario {L} días)'
        elif f == 'IA':
            tab, lstm = 'IPA 0.90, IPA 0.97 y días secos en t (3 variables)', f'las 3 series diarias t−{L - 1} … t (3 canales)'
            dias_t, dias_l = 't (resume toda la lluvia previa)', f't−{L - 1} … t'
        else:
            tab = f'{f[2:]}: log Q(t) y {L - 1} cambios'; lstm = f'{f[2:]}: log Q diario y cambio respecto al último día (2 canales)'
            dias_t = dias_l = f't−{L - 1} … t'
        sufijo = f' (todo desplazado {lat} d: última fecha t−{lat})' if lat else ''
        filas.append({'conjunto': d.conjunto, 'latencia (d)': d.latencia, 'fuente': f, 'tabulares (lineal, RF, XGBoost, MLP)': tab + sufijo,
                      'KNN': 'igual que tabulares; de cada caudal usa el nivel y los últimos ventana − 1 cambios' if f in ('Q',) or f.startswith('A:') else 'igual que tabulares',
                      'LSTM': lstm + sufijo, 'días cubiertos (tabulares)': dias_t, 'días cubiertos (LSTM)': dias_l,
                      'misma representación temporal': f in ('Q', 'Pd') or f.startswith('A:')})
    return filas


def datos(F: Fuentes, m, p, VC, mx, conjunto: str, latencia: int = 0, ip=None) -> Datos:
    """Entradas del conjunto para las filas del experimento. `ip`: filas de prueba (por defecto, toda la prueba común);
    las filas de entrenamiento, validación y `ip` deben tener entrada válida. La muestra extendida se restringe a las
    filas con entrada válida para este conjunto."""
    ip = p['pru'] if ip is None else ip
    usadas = np.concatenate([p['ent'], p['val'], ip])
    X, nom, est, ok = matriz(m, F, conjunto, latencia)
    assert ok[usadas].all(), f'{F.nombre} {conjunto}: entrada no válida en filas del experimento'
    E = canales_lstm(m, F, conjunto, latencia)
    assert np.isfinite(E[usadas]).all()
    Xx, _, _, okx = matriz(mx, F, conjunto, latencia)
    mx = A.subconjunto(mx, np.where(okx)[0])
    Xx = Xx[okx]
    Ex = canales_lstm(mx, F, conjunto, latencia)
    assert np.isfinite(Ex).all() and np.isfinite(Xx).all()
    return Datos(F.nombre, conjunto, latencia, m, p, VC, X, E, est, nom, ip, mx, Xx, Ex)


# ----------------------------------------------------------------------------- Cirato (exploratorio)
# Con 13 meses no hay bloque de selección: hiperparámetros FIJOS, elegidos antes de ejecutar y moderados para muestras
# pequeñas (pocos parámetros efectivos, regularización), los mismos en todos los conjuntos, horizontes y modos.
CIRATO_FIJOS = {'Regresión lineal': {}, 'Random Forest': dict(n_estimators=300, min_samples_leaf=5, max_features=0.5),
                'XGBoost': dict(max_depth=2, n_estimators=100, learning_rate=0.1, subsample=0.8),
                'KNN': dict(n_neighbors=10, weights='uniform'), 'MLP': dict(hidden_layer_sizes=(32,), alpha=1e-2, max_iter=500),
                'LSTM': dict(oculto=16, epocas=60)}


class _LSTMCirato:
    """LSTM de v4 (`comun.entrenar_lstm`) sobre las ventanas diarias de Lc días de cada fuente, con épocas fijas."""

    def __init__(self, Lc, canales, semilla, oculto=16, epocas=60):
        self.Lc, self.canales, self.semilla, self.oculto, self.epocas = Lc, canales, semilla, oculto, epocas

    def _seq(self, X):
        return np.stack([X[:, j * self.Lc:(j + 1) * self.Lc][:, ::-1] for j in range(self.canales)], axis=2).astype(np.float32)

    def fit(self, X, y):
        S_ = self._seq(X)
        self.mu, self.sd = S_.reshape(-1, self.canales).mean(0), S_.reshape(-1, self.canales).std(0) + 1e-6
        self.ym, self.ys = float(y.mean()), float(y.std() + 1e-9)
        self.red, _ = C.entrenar_lstm((S_ - self.mu) / self.sd, ((y - self.ym) / self.ys)[:, None], oculto=self.oculto,
                                      semilla=self.semilla, epocas=self.epocas)
        return self

    def predict(self, X):
        return C.predecir_lstm(self.red, (self._seq(X) - self.mu) / self.sd)[:, 0] * self.ys + self.ym


def _modelo_cirato(nombre: str, semilla: int, Lc: int, canales: int):
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline
    from xgboost import XGBRegressor
    p = CIRATO_FIJOS[nombre]
    if nombre == 'Regresión lineal':
        return LinearRegression()
    if nombre == 'Random Forest':
        return RandomForestRegressor(random_state=semilla, n_jobs=2, **p)
    if nombre == 'XGBoost':
        return XGBRegressor(random_state=semilla, n_jobs=2, verbosity=0, **p)
    if nombre == 'KNN':
        return make_pipeline(StandardScaler(), KNeighborsRegressor(**p))
    if nombre == 'MLP':
        return make_pipeline(StandardScaler(), MLPRegressor(random_state=semilla, **p))
    return _LSTMCirato(Lc, canales, semilla, **p)


def cirato_exploratorio(F: Fuentes, qC: pd.Series, epsC: float, desde: str, hasta: str, horizontes=(1, 2, 3), Lc: int = 7,
                        B: int = 1000, semilla: int = C.SEMILLA, modo: str = 'retrospectivo', min_ent: int = 60,
                        modelos=('Regresión lineal', 'XGBoost')) -> pd.DataFrame:
    """Prueba exploratoria en el único periodo con fechas confiables de Cirato (13 meses), con los cuatro conjuntos
    (Q, Q+P, Q+C, Q+P+C). Ventanas de Lc días (caudal de Racarumi, caudal de Cirato y log(1 + P) diaria de la cuenca), un
    modelo por horizonte, evaluación por bloques mensuales purgando las emisiones a menos de Lc + h días del mes
    evaluado. Con tan pocos datos no hay bloque de selección: cada modelo usa los hiperparámetros FIJOS de CIRATO_FIJOS. G de cada conjunto frente a Q (mismo modelo)
    con IC 90 % por bootstrap de meses.
    `modo='retrospectivo'` (principal): entrena con los meses anteriores Y posteriores al evaluado (validación cruzada
    temporal con separación de Lc + h días; NO es una simulación prospectiva). `modo='prospectivo'` (sensibilidad):
    entrena solo con emisiones cuyo objetivo termina antes del mes evaluado; los meses con menos de `min_ent` emisiones de
    entrenamiento no se evalúan. `epsC` debe fijarse sin los meses evaluados (en el prospectivo, con el bloque inicial)."""
    idx = pd.date_range(desde, hasta)
    zr = np.log(F.q.reindex(idx) + F.eps)
    zc = np.log(qC.reindex(idx) + epsC)
    lp = np.log1p(F.P.reindex(idx))
    filas = []
    for h in horizontes:
        Wr = np.column_stack([zr.shift(k) for k in range(Lc)])
        Wc = np.column_stack([zc.shift(k) for k in range(Lc)])
        Wp = np.column_stack([lp.shift(k) for k in range(Lc)])
        y = (zr.shift(-h) - zr).to_numpy()
        ok = np.isfinite(Wr).all(1) & np.isfinite(Wc).all(1) & np.isfinite(Wp).all(1) & np.isfinite(y)
        f = idx[ok]
        R = np.column_stack([Wr[ok][:, 0], Wr[ok][:, 1:] - Wr[ok][:, :1]])
        Cc = np.column_stack([Wc[ok][:, 0], Wc[ok][:, 1:] - Wc[ok][:, :1]])
        # tabulares: nivel + cambios; la LSTM recibe las ventanas diarias (mismo contenido) como canales
        conj = {'Q': (R, Wr[ok], 1), 'Q+P': (np.column_stack([R, Wp[ok]]), np.column_stack([Wr[ok], Wp[ok]]), 2),
                'Q+C': (np.column_stack([R, Cc]), np.column_stack([Wr[ok], Wc[ok]]), 2),
                'Q+P+C': (np.column_stack([R, Wp[ok], Cc]), np.column_stack([Wr[ok], Wp[ok], Wc[ok]]), 3)}
        yy, z0 = y[ok], zr.to_numpy()[ok]
        obs = np.exp(z0 + yy) - F.eps
        meses = f.to_period('M')
        for mod in modelos:
            pr = {k: np.full(len(yy), np.nan) for k in conj}
            for mes in meses.unique():
                te = meses == mes
                ini, fin = f[te].min(), f[te].max()
                if modo == 'prospectivo':
                    tr = f + pd.Timedelta(days=h) < ini
                    if tr.sum() < min_ent:
                        continue
                else:
                    tr = (f < ini - pd.Timedelta(days=Lc + h)) | (f > fin + pd.Timedelta(days=Lc + h))
                for k, (Xt, Xs, nc) in conj.items():
                    X = Xs if mod == 'LSTM' else Xt
                    pr[k][te] = np.exp(z0[te] + _modelo_cirato(mod, semilla, Lc, nc).fit(X[tr], yy[tr]).predict(X[te])) - F.eps
            ev = np.isfinite(pr['Q'])
            for k in conj:
                fila = {'h': h, 'modelo': mod, 'conjunto': k, 'modo': modo, 'emisiones evaluadas': int(ev.sum()),
                        'meses evaluados': int(len(meses[ev].unique())), 'desde': f'{f[ev].min():%Y-%m-%d}',
                        'NSE': C.nse(obs[ev], pr[k][ev]), 'NSE persistencia': C.nse(obs[ev], np.exp(z0[ev]) - F.eps)}
                if k != 'Q':
                    ph, _ = A.ganancia(f[ev], obs[ev][:, None], pr[k][ev][:, None], pr['Q'][ev][:, None], B=B, semilla=semilla)
                    fila.update({'G frente a Q': float(ph['G'].iloc[0]), 'IC90 inferior': float(ph['IC90 inferior'].iloc[0]),
                                 'IC90 superior': float(ph['IC90 superior'].iloc[0]), 'lectura': ph['lectura'].iloc[0]})
                filas.append(fila)
    return pd.DataFrame(filas)
