# -*- coding: utf-8 -*-
"""Funciones comunes del modelamiento (secciones 3.5 y 3.6 del Proyecto Integrador) — protocolo v4.

Pronóstico diario del caudal observado a 1–30 días usando **solo los caudales antecedentes** de la propia
estación y el calendario. Única fuente de datos: CAMELS-PE v1.0.1 (carpeta o ZIP en la raíz del repositorio)
más la tabla de errores eliminados por el EDA de cada cuenca.

Convenciones
- t: fecha de emisión (último día con caudal observado conocido). h: horizonte (1–30 días); se pronostica Q(t + h).
- Los modelos aprenden el cambio logarítmico y_h = log(Q_{t+h} + ε) − log(Q_t + ε); la persistencia es y_h = 0.
- Todas las métricas se calculan en m³/s, después de invertir la transformación.
- Umbral de caudal elevado: P95 del entrenamiento; "alto" significa Q > P95 (estrictamente mayor).
"""
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
RUTA_CAMELS = RAIZ / 'CAMELS-PE_v1.0.1' / 'CAMELS-PE'
RUTA_ZIP = RAIZ / 'CAMELS-PE_v1.0.1.zip'
VERSION = 'v4'
# Identificador de la ejecución final del protocolo. Cada etapa lo registra en su resumen.json y las etapas posteriores
# exigen que figure en REVISIONES_COMPATIBLES: 01–04 se ejecutaron el 18-11-2026 y 05–09 el 22-11-2026 con el mismo
# protocolo, así que ambos identificadores son compatibles. Una síntesis nunca combina salidas de otras configuraciones.
REVISION = 'v4 integrada r7 (2026-11-22)'
REVISIONES_COMPATIBLES = ('v4 integrada r4 (2026-11-18)', 'v4 integrada r7 (2026-11-22)')

ESTACIONES = {
    'Racarumi': dict(gid='PE_200907', eda='chancay_eda', cuenca='Chancay-Lambayeque', vertiente='Pacífico'),
    'Tamshiyacu': dict(gid='PE_240103', eda='amazonas_eda', cuenca='Ucayali–Amazonas', vertiente='Amazónica'),
}
HORIZONTES = list(range(1, 31))
L_VENTANA = 30                          # días antecedentes, incluido t
FIN_ENTRENAMIENTO = '2008-12-31'
FIN_PARADA = '2004-12-31'               # LSTM: entrena hasta aquí y detiene con 2005–2008 (bloque distinto de la validación)
FIN_VALIDACION = '2015-12-31'           # prueba: 2016-01-01 hasta el fin del registro
SEMILLA = 42
SEMILLAS = [42, 43, 44]                 # semillas predefinidas de los modelos estocásticos
SEP_EVENTOS = 7                         # días seguidos observados bajo el umbral que separan dos eventos

# Validación en dos bloques (v4): los primeros AÑOS_CALIBRACION años de la validación solo estiman la corrección de
# retransformación; los siguientes (selección) solo comparan candidatos. Entre ambos hay al menos 30 días: ningún
# objetivo del bloque de calibración cae en el de selección. Así cada pronóstico evaluado usa solo factores del pasado.
AÑOS_CALIBRACION = 3                    # principal: calibración 2009–2011, selección 2012–2015
MARGEN_NSE = 0.01                       # diferencia de NSE medio con importancia práctica (decisión del proyecto)
B_SELECCION = 1000                      # réplicas del bootstrap pareado por meses para comparar candidatos

# Protocolo de avisos de nuevos cruces (fijado antes de la prueba). Los avisos usan la MEDIANA pronosticada
# (exp del cambio log, sin corrección de Duan): no necesita ningún factor estimado y f absorbe el sesgo.
AVISO = dict(factores=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1], hmax=[3, 7, 15, 30], tol=2, dmax=7, reinicio=7,
             pod_min=0.5, far_max=0.5)

# Política de la climatología de referencia (la misma en todas las etapas desde v4): se calcula con los datos que
# también usó el modelo evaluado. Validación (modelos ajustados hasta 2008) → climatología hasta FIN_ENTRENAMIENTO;
# prueba (modelos reajustados con entrenamiento + validación) → climatología hasta FIN_VALIDACION. Las dos son anteriores
# a la prueba. Usar `climatologia_referencia(q, bloque)` en lugar de fijar `hasta` a mano.
CLIMATOLOGIA_HASTA = {'validación': FIN_ENTRENAMIENTO, 'prueba': FIN_VALIDACION}

MODELOS = ['Regresión lineal', 'Random Forest', 'XGBoost', 'KNN', 'MLP', 'LSTM']
# Ante desempeños equivalentes se elige el más simple (lineal < análogos < bosque < boosting < red densa < red recurrente)
ORDEN_SIMPLICIDAD = ['Regresión lineal', 'KNN', 'Random Forest', 'XGBoost', 'MLP', 'LSTM']
ESTOCASTICOS = ['Random Forest', 'XGBoost', 'MLP', 'LSTM']      # se repiten con SEMILLAS
BASE_AUX = 'XGBoost'                    # modelo de los análisis auxiliares (historia, importancia, registros)
COMB = 'Combinado por horizonte'
SLUG = {'Regresión lineal': 'lineal', 'Random Forest': 'rf',
        'XGBoost': 'xgb', 'KNN': 'knn', 'MLP': 'mlp', 'LSTM': 'lstm', COMB: 'combinado'}
COLOR = {'Persistencia': '#7f7f7f', 'Climatología': '#bcbd22', 'Tendencia 3 días': '#444444',
         'Regresión lineal': '#8c564b', 'Random Forest': '#2ca02c',
         'XGBoost': '#e377c2', 'KNN': '#17becf', 'MLP': '#9467bd', 'LSTM': '#ff7f0e', COMB: '#000000'}


# ----------------------------------------------------------------------------- salidas y compatibilidad entre etapas
def es_rapido() -> bool:
    """CDA_RAPIDO=1: mallas mínimas para probar el código. Sus cifras no se usan."""
    return os.environ.get('CDA_RAPIDO') == '1'


def ruta_salidas() -> Path:
    """Carpeta de salidas (relativa a `modelos/`): `salidas` en la ejecución final y `salidas_rapido` en modo rápido.
    Una prueba rápida nunca sobrescribe ni se mezcla con resultados finales."""
    return Path('salidas_rapido' if es_rapido() else 'salidas')


def verificar_resumen(ruta, **esperado) -> dict:
    """Lee el resumen.json de una etapa anterior y comprueba que es del mismo protocolo, de una ejecución declarada
    compatible (REVISIONES_COMPATIBLES) y del mismo modo de ejecución (una ejecución final no combina salidas rápidas,
    ni al revés). `esperado`: otras claves que deben coincidir."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f'{ruta}: falta la salida de una etapa anterior (ejecútela primero)')
    r = json.loads(ruta.read_text(encoding='utf-8'))
    if r.get('version') != VERSION:
        raise ValueError(f"{ruta}: protocolo {r.get('version')} distinto de {VERSION}")
    if bool(r.get('rapido')) != es_rapido():
        raise ValueError(f"{ruta}: salida {'rápida' if r.get('rapido') else 'final'} en una ejecución "
                         f"{'rápida' if es_rapido() else 'final'}; no se combinan")
    if r.get('revision') is None and not es_rapido():
        # Las etapas que no escriben el identificador en su resumen se acreditan con el manifiesto (la huella del resumen
        # debe coincidir con la registrada por un manifiesto compatible).
        man = ruta.parent.parent / 'manifiesto.json'
        if not man.exists():
            raise ValueError(f'{ruta}: sin revisión registrada y sin manifiesto que acredite su identidad')
        mj = json.loads(man.read_text(encoding='utf-8'))
        clave = f'{ruta.parent.parent.name}/{ruta.parent.name}/{ruta.name}'
        h = hashlib.sha256(ruta.read_bytes()).hexdigest()
        if mj.get('revision') not in REVISIONES_COMPATIBLES or mj.get('salidas_sha256', {}).get(clave) != h:
            raise ValueError(f'{ruta}: sin revisión registrada y su huella no coincide con un manifiesto compatible')
    elif r.get('revision') is not None and r.get('revision') not in REVISIONES_COMPATIBLES:
        raise ValueError(f"{ruta}: revisión {r.get('revision')!r} no declarada compatible con {REVISION!r}")
    for k, v in esperado.items():
        if r.get(k) != v:
            raise ValueError(f'{ruta}: {k} = {r.get(k)!r}, se esperaba {v!r}')
    return r


def clave_relativa(ruta, raiz) -> str:
    """Ruta relativa con '/' en cualquier sistema (claves del manifiesto). Acepta rutas de Windows (PureWindowsPath)."""
    from pathlib import PurePath
    r, b = PurePath(ruta), PurePath(raiz)
    return r.relative_to(b).as_posix()


def verificar_insumos(raiz: Path | None = None) -> list[dict]:
    """Antes de una síntesis final comprueba que los DATOS y las REGLAS DE DEPURACIÓN que se vuelven a cargar
    (series de CAMELS-PE, atributos, tablas de outliers y de atribución de balance de los EDA) y el código de los módulos
    coinciden con los registrados en el manifiesto. Si algo difiere o falta, se detiene e indica el insumo."""
    raiz = (Path(raiz) if raiz is not None else Path(__file__).resolve().parent).resolve()
    if es_rapido():
        return [dict(insumo='(modo rápido)', validado=False)]
    man = raiz / 'salidas' / 'manifiesto.json'
    if not man.exists():
        raise FileNotFoundError(f'{man}: falta el manifiesto; no se pueden verificar los insumos')
    mj = json.loads(man.read_text(encoding='utf-8'))
    filas, malos = [], []
    for grupo, base in (('entradas_sha256', RAIZ), ('codigo_sha256', raiz)):
        if grupo not in mj:
            raise ValueError(f'el manifiesto no registra {grupo}: regenérelo con manifiesto.py')
        for k, v in mj[grupo].items():
            f = base / k
            h = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
            filas.append(dict(insumo=k, grupo=grupo, validado=h == v))
            if h != v:
                malos.append(f'{k} ({"ausente" if h is None else "distinto"})')
    if malos:
        raise ValueError(f'insumos distintos de los registrados en el manifiesto: {malos}')
    return filas


def seleccion_avisos(fechas_val, pv: dict, q: pd.Series, P95: float, candidatos: list, H: int = len(HORIZONTES),
                     fin_ent: str = FIN_ENTRENAMIENTO) -> dict:
    """Protocolo COMÚN de selección para avisos (04, 06 y 08). pv: {candidato: trayectoria mediana (n, H) en las
    fechas de validación}; candidatos: en orden de simplicidad (el primero, el más simple).
    1. Regla de cada candidato (f, h_max: máximo CSI con FAR ≤ far_max) calibrada en el bloque de calibración
       (emisiones cuyos H objetivos terminan antes de inicio_seleccion; 2009–2011).
    2. Comparación de candidatos en el bloque de selección (2012–2015) con esa regla: mayor CSI con FAR ≤ far_max; si
       empatan, el más simple.
    3. Regla final del elegido (y de cada candidato, para informar la prueba): recalibrada en TODA la validación, como
       las reglas del cuaderno 04; se documenta explícitamente.
    Los hiperparámetros de los modelos ya se habían elegido con el bloque de selección (magnitud): la separación es
    entre calibración de la regla y comparación de candidatos, no un anidado de todo el procedimiento.
    Devuelve: regla_bloque, metricas_seleccion, regla_final, elegido, elegido_no_anidado, cruces_calibracion, cruces_seleccion."""
    A_ = AVISO
    f_ = pd.DatetimeIndex(fechas_val)
    s0 = inicio_seleccion(fin_ent)
    ical, isel = np.where(f_ + pd.Timedelta(days=H) < s0)[0], np.where(f_ >= s0)[0]

    def cumple(r):
        return bool(np.isfinite(r['FAR']) and r['FAR'] <= A_['far_max'])

    def clave(r):
        return (cumple(r), r['CSI'] if np.isfinite(r['CSI']) else -1, -abs(r['f'] - 1), -r['hmax'])

    def calibrar(idx, tray):
        mejor = None
        for fa in A_['factores']:
            for hm in A_['hmax']:
                r = evaluar_avisos(f_[idx], tray[idx], q, P95, f=fa, hmax=hm, tol=A_['tol'], dmax=A_['dmax'], reinicio=A_['reinicio'])['resumen']
                fila = {k: r[k] for k in ['f', 'hmax', 'evaluables', 'aciertos', 'omisiones', 'falsas_alarmas', 'POD', 'FAR', 'CSI', 'dias_aviso_anio']}
                fila['cumple_FAR'] = cumple(fila)
                if mejor is None or clave(fila) > clave(mejor):
                    mejor = fila
        return mejor

    regla_bloque, sel, final = {}, {}, {}
    for c in candidatos:
        tray = np.asarray(pv[c], float)
        regla_bloque[c] = calibrar(ical, tray)
        r = evaluar_avisos(f_[isel], tray[isel], q, P95, f=regla_bloque[c]['f'], hmax=regla_bloque[c]['hmax'], tol=A_['tol'],
                           dmax=A_['dmax'], reinicio=A_['reinicio'])['resumen']
        sel[c] = {k: r[k] for k in ['evaluables', 'aciertos', 'omisiones', 'falsas_alarmas', 'POD', 'FAR', 'CSI']}
        sel[c]['cumple_FAR'] = cumple(sel[c])
        final[c] = calibrar(np.arange(len(f_)), tray)
    orden = {c: i for i, c in enumerate(candidatos)}
    elegido = max(candidatos, key=lambda c: (sel[c]['cumple_FAR'], sel[c]['CSI'] if np.isfinite(sel[c]['CSI']) else -1, -orden[c]))
    no_anidado = max(candidatos, key=lambda c: (final[c]['cumple_FAR'], final[c]['CSI'] if np.isfinite(final[c]['CSI']) else -1, -orden[c]))
    return dict(regla_bloque=regla_bloque, metricas_seleccion=sel, regla_final=final, elegido=elegido, elegido_no_anidado=no_anidado,
                cruces_calibracion=regla_bloque[candidatos[0]]['evaluables'], cruces_seleccion=sel[candidatos[0]]['evaluables'],
                periodo_calibracion=f"{f_[ical].min():%Y-%m-%d} a {f_[ical].max():%Y-%m-%d}", periodo_seleccion=f"{f_[isel].min():%Y-%m-%d} a {f_[isel].max():%Y-%m-%d}")


def verificar_archivos(rutas, raiz: Path | None = None) -> list[dict]:
    """Integridad ANTES de usar salidas en una síntesis final: en la ejecución final exige salidas/manifiesto.json
    compatible y que cada archivo figure en él con la misma huella SHA-256; si falta el manifiesto o
    algo no coincide, se detiene. En modo rápido no hay manifiesto: devuelve la lista marcada como «no validado»."""
    raiz = (Path(raiz) if raiz is not None else Path(__file__).resolve().parent).resolve()
    filas = []
    man = raiz / 'salidas' / 'manifiesto.json'
    if es_rapido():
        return [dict(archivo=str(r), validado=False, motivo='modo rápido: sin manifiesto') for r in rutas]
    if not man.exists():
        raise FileNotFoundError(f'{man}: falta el manifiesto; la síntesis final no usa salidas sin verificar')
    mj = json.loads(man.read_text(encoding='utf-8'))
    if mj.get('revision') not in REVISIONES_COMPATIBLES:
        raise ValueError(f"manifiesto de la revisión {mj.get('revision')!r}, no compatible con {REVISION!r}")
    malos = []
    for r in rutas:
        r = Path(r)
        k = clave_relativa((r if r.is_absolute() else raiz / r).resolve(), raiz)      # '/' también en Windows
        h = hashlib.sha256((raiz / k).read_bytes()).hexdigest()
        ok = mj.get('salidas_sha256', {}).get(k) == h
        filas.append(dict(archivo=k, sha256=h[:16], en_manifiesto=k in mj.get('salidas_sha256', {}), validado=ok))
        if not ok:
            malos.append(k)
    if malos:
        raise ValueError(f'huellas distintas del manifiesto o ausentes en él: {malos}')
    return filas


# ----------------------------------------------------------------------------- datos
def asegurar_camels() -> Path:
    """Devuelve la ruta de CAMELS-PE; si solo existe el ZIP en la raíz, lo extrae."""
    if not RUTA_CAMELS.exists() and RUTA_ZIP.exists():
        with zipfile.ZipFile(RUTA_ZIP) as z:
            z.extractall(RUTA_CAMELS.parent)
    if not RUTA_CAMELS.exists():
        raise FileNotFoundError('Falta CAMELS-PE: coloque CAMELS-PE_v1.0.1.zip en la raíz del repositorio.')
    return RUTA_CAMELS


def cargar_serie(nombre: str) -> tuple[pd.Series, dict]:
    """Caudal observado diario (m³/s) con calendario completo y los errores del EDA puestos en NaN.
    Un NaN es "dato desconocido": nunca se interpreta como caudal bajo."""
    e = ESTACIONES[nombre]
    camels = asegurar_camels()
    topo = pd.read_csv(camels / '02_attributes' / 'topographic_attributes.csv').set_index('gauge_id')
    area = float(topo.loc[e['gid'], 'area'])
    archivo = camels / '03_timeseries' / 'by_catchment' / f"{e['gid']}.csv"
    df = pd.read_csv(archivo, parse_dates=['date']).set_index('date')
    if df.index.duplicated().any():
        raise ValueError(f'{nombre}: fechas duplicadas en CAMELS-PE')
    q = df['flow_obs'].sort_index() * area * 1000 / 86400              # mm/d → m³/s
    q = q.asfreq('D')
    q = q.loc[q.first_valid_index():q.last_valid_index()]
    elim = pd.read_csv(RAIZ / e['eda'] / 'salidas' / 'tablas' / 'tabla_outliers_eliminados.csv', parse_dates=['fecha'])
    fechas = elim.loc[elim['estación'] == nombre, 'fecha']
    q.loc[q.index.isin(fechas)] = np.nan
    q.name = nombre
    info = dict(area=area, inicio=q.index.min(), fin=q.index.max(), n_eliminados=int(len(fechas)),
                vacios=float(q.isna().mean() * 100), gid=e['gid'], archivo=archivo.relative_to(RAIZ).as_posix(),
                ceros=int((q == 0).sum()))
    return q, info


def eps_entrenamiento(q: pd.Series, hasta: str = FIN_ENTRENAMIENTO) -> float:
    """ε de log(Q + ε): 1 % del caudal medio del periodo de ajuste autorizado (fijo después)."""
    return float(q.loc[:hasta].mean() / 100)


def escalones(q: pd.Series, hasta: str = FIN_ENTRENAMIENTO) -> pd.DatetimeIndex:
    """Escalones de nivel del EDA (2.7): días 1 de mes cuyo |Δlog Q| supera el máximo |Δlog Q| de los demás días.
    El umbral se fija solo con el periodo autorizado (`hasta`) y luego se aplica a todo el registro. Detectar un
    salto no certifica que los bloques entre saltos tengan la escala correcta."""
    eps = eps_entrenamiento(q, hasta)
    d = np.log(q + eps).diff()
    dia1 = d.index.day == 1
    de = d.loc[:hasta]
    umbral = de[de.index.day != 1].abs().max()
    return d.index[dia1 & (d.abs() > umbral).to_numpy()]


def rellenar_cortos(z: pd.Series, max_dias: int = 3) -> pd.Series:
    """Interpolación lineal solo en vacíos interiores de ≤ max_dias días, usada solo en las ENTRADAS.
    Es causal para cada emisión porque construir_muestras exige Q(t) observado: el día que cierra cualquier vacío
    interpolado dentro de la ventana es ≤ t. Los objetivos nunca se interpolan."""
    nan = z.isna()
    grupo = (nan != nan.shift()).cumsum()
    largo = nan.groupby(grupo).transform('sum')
    zi = z.interpolate(limit_area='inside')
    return zi.where(~nan | (largo <= max_dias))


@dataclass
class Muestras:
    fechas: pd.DatetimeIndex          # t (emisión)
    ventana: np.ndarray               # (n, L) log Q (vacíos cortos interpolados), de t−L+1 a t
    doy: np.ndarray                   # (n,) día del año de t
    zt: np.ndarray                    # (n,) log(Q_t + ε) observado
    y: np.ndarray                     # (n, H) cambio log a cada horizonte
    q_obs: np.ndarray                 # (n, H) Q observado en t+h (m³/s)
    q_t: np.ndarray                   # (n,) Q_t (m³/s)
    eps: float
    L: int
    excluidas_escalon: int = 0
    info: dict = field(default_factory=dict)
    interpolada: np.ndarray | None = None   # (n,) la ventana de entrada contiene días interpolados (calidad)


def construir_muestras(q: pd.Series, L: int, H: int = 30, esc: pd.DatetimeIndex | None = None,
                       eps: float | None = None, permitidos: pd.Series | None = None, exigir_todos: bool = True) -> Muestras:
    """Una muestra por fecha t con ventana de L días consecutivos (vacíos ≤ 3 d interpolados), Q_t observado,
    los H objetivos observados (sin imputar) y sin escalón de nivel entre t−L+1 y t+H. Se evalúan solo
    emisiones con los 30 objetivos disponibles (conjunto común para todos los modelos y horizontes).
    `info` registra cuántas fechas se descartan y por qué.

    exigir_todos=False (muestra EXTENDIDA, solo para evaluar por horizonte): conserva toda emisión con entrada válida
    (ventana, Q_t y sin escalón ni día no permitido entre t−L+1 y t) y al menos un objetivo verificable; el objetivo h
    queda en NaN si no está observado o si entre t+1 y t+h hay un escalón o un día no permitido. Las entradas son las
    mismas que en la muestra común; la condición sobre los 30 objetivos solo selecciona la muestra de evaluación, no
    entrega información futura al modelo. No sirve para entrenar (y contiene NaN)."""
    if eps is None:
        eps = eps_entrenamiento(q)
    z = np.log(q + eps)
    zi = rellenar_cortos(z)
    n = len(z)
    zv, ziv = z.to_numpy(), zi.to_numpy()
    marca = np.zeros(n)
    if esc is not None and len(esc):
        marca[z.index.get_indexer(esc)] = 1
    cum = np.concatenate([[0], np.cumsum(marca)])
    if not exigir_todos:
        return _muestras_extendidas(z, zv, ziv, cum, L, H, eps, permitidos)
    idx = np.arange(L - 1, n - H)
    from numpy.lib.stride_tricks import sliding_window_view
    vent = sliding_window_view(ziv, L)[idx - (L - 1)]
    obj = np.stack([zv[idx + h] for h in range(1, H + 1)], axis=1)
    ok_v = np.isfinite(vent).all(1)
    ok_t = np.isfinite(zv[idx])
    ok_o = np.isfinite(obj).all(1)
    ok = ok_v & ok_t & ok_o
    con_escalon = (cum[idx + H + 1] - cum[idx - L + 2]) > 0
    excl = int((ok & con_escalon).sum())
    info = dict(candidatas=int(len(idx)), sin_Qt=int((~ok_t).sum()), ventana_incompleta=int((ok_t & ~ok_v).sum()),
                objetivo_faltante=int((ok_t & ok_v & ~ok_o).sum()), con_escalon=excl)
    ok &= ~con_escalon
    if permitidos is not None:
        malo = np.concatenate([[0], np.cumsum(~permitidos.reindex(z.index, fill_value=False).to_numpy())])
        ok &= (malo[idx + H + 1] - malo[idx - L + 1]) == 0
    crudo = ~np.isfinite(sliding_window_view(zv, L)[idx - (L - 1)]).all(1)
    idx, vent, obj, crudo = idx[ok], vent[ok], obj[ok], crudo[ok]
    fechas = z.index[idx]
    info['validas'] = int(len(idx))
    info['con_entrada_interpolada'] = int(crudo.sum())
    return Muestras(fechas=fechas, ventana=vent, doy=fechas.dayofyear.to_numpy(), zt=zv[idx],
                    y=obj - zv[idx][:, None], q_obs=np.exp(obj) - eps, q_t=np.exp(zv[idx]) - eps,
                    eps=eps, L=L, excluidas_escalon=excl, info=info, interpolada=crudo)


def _muestras_extendidas(z, zv, ziv, cum, L, H, eps, permitidos) -> Muestras:
    """Muestra extendida de `construir_muestras(..., exigir_todos=False)`."""
    from numpy.lib.stride_tricks import sliding_window_view
    n = len(zv)
    idx = np.arange(L - 1, n - 1)
    vent = sliding_window_view(ziv, L)[idx - (L - 1)]
    zpad = np.concatenate([zv, np.full(H, np.nan)])
    cpad = np.concatenate([cum, np.full(H, cum[-1])])
    obj = np.stack([zpad[idx + h] for h in range(1, H + 1)], axis=1)
    ok = np.isfinite(vent).all(1) & np.isfinite(zv[idx]) & ((cpad[idx + 1] - cpad[idx - L + 2]) == 0)
    corte = np.stack([(cpad[idx + h + 1] - cpad[idx + 1]) > 0 for h in range(1, H + 1)], axis=1)    # escalón en (t, t+h]
    if permitidos is not None:
        malo = np.concatenate([[0], np.cumsum(~permitidos.reindex(z.index, fill_value=False).to_numpy())])
        mpad = np.concatenate([malo, np.full(H, malo[-1])])
        ok &= (mpad[idx + 1] - mpad[idx - L + 1]) == 0
        corte |= np.stack([(mpad[idx + h + 1] - mpad[idx + 1]) > 0 for h in range(1, H + 1)], axis=1)
    obj = np.where(corte, np.nan, obj)
    ok &= np.isfinite(obj).any(1)
    crudo = ~np.isfinite(sliding_window_view(zv, L)[idx - (L - 1)]).all(1)
    idx, vent, obj, crudo = idx[ok], vent[ok], obj[ok], crudo[ok]
    fechas = z.index[idx]
    info = dict(validas=int(len(idx)), con_todos_los_objetivos=int(np.isfinite(obj).all(1).sum()),
                objetivos_por_h=np.isfinite(obj).sum(0).astype(int).tolist())
    return Muestras(fechas=fechas, ventana=vent, doy=fechas.dayofyear.to_numpy(), zt=zv[idx],
                    y=obj - zv[idx][:, None], q_obs=np.exp(obj) - eps, q_t=np.exp(zv[idx]) - eps,
                    eps=eps, L=L, info=info, interpolada=crudo)


def particion(m: Muestras, fin_ent: str = FIN_ENTRENAMIENTO, fin_val: str = FIN_VALIDACION,
              fin_pru: str | None = None) -> dict[str, np.ndarray]:
    """Índices por fecha de emisión. Ningún objetivo de entrenamiento o validación cruza al bloque siguiente
    (se descartan las últimas H emisiones de cada bloque). Las ventanas de entrada sí pueden empezar en el
    bloque anterior: esos días ya eran conocidos al emitir."""
    H = m.y.shape[1]
    f = m.fechas
    fe, fv = pd.Timestamp(fin_ent), pd.Timestamp(fin_val)
    off = pd.Timedelta(days=H)
    pru = (f > fv) if fin_pru is None else ((f > fv) & (f + off <= pd.Timestamp(fin_pru)))
    return dict(ent=np.where(f + off <= fe)[0], val=np.where((f > fe) & (f + off <= fv))[0], pru=np.where(pru)[0])


def matriz_tabular(m: Muestras, calendario: bool = True) -> tuple[np.ndarray, list[str]]:
    """Variables tabulares: nivel actual, cambios respecto a hoy en los L−1 días previos y estacionalidad."""
    rel = m.ventana[:, :-1] - m.ventana[:, -1:]
    nombres = [f'Δlog Q(t−{k})' for k in range(m.L - 1, 0, -1)]
    cols = [m.ventana[:, -1], rel]
    nom = ['log Q(t)'] + nombres
    if calendario:
        ang = 2 * np.pi * m.doy / 365.25
        cols += [np.sin(ang), np.cos(ang)]
        nom += ['sen(día del año)', 'cos(día del año)']
    return np.column_stack(cols), nom


def grupos_variables(nombres: list[str]) -> dict[str, list[int]]:
    g = {'Caudal de hoy (nivel)': [], 'Cambio en los últimos 1–3 días': [], 'Días 4–7': [],
         'Días 8–15': [], 'Días 16–30': [], 'Días 31 o más': [], 'Época del año': []}
    for i, n in enumerate(nombres):
        if n == 'log Q(t)':
            g['Caudal de hoy (nivel)'].append(i)
        elif n.startswith('Δlog'):
            k = int(n.split('−')[1].rstrip(')'))
            clave = ('Cambio en los últimos 1–3 días' if k <= 3 else 'Días 4–7' if k <= 7 else
                     'Días 8–15' if k <= 15 else 'Días 16–30' if k <= 30 else 'Días 31 o más')
            g[clave].append(i)
        else:
            g['Época del año'].append(i)
    return {k: v for k, v in g.items() if v}


def a_caudal(m: Muestras, y_pred: np.ndarray, idx: np.ndarray, factor=None, contar: bool = False):
    """Cambios log pronosticados → m³/s. `factor`: corrección de retransformación por horizonte (Duan), fijada
    en validación. Los valores negativos (posibles por −ε) se recortan a 0; con contar=True devuelve también
    cuántos se recortaron."""
    f = 1.0 if factor is None else np.asarray(factor)[None, :]
    bruto = np.exp(m.zt[idx][:, None] + y_pred) * f - m.eps
    out = np.maximum(bruto, 0.0)
    return (out, int((bruto < 0).sum())) if contar else out


def factor_duan(y_obs: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    """Corrección de retransformación de Duan por horizonte: media de exp(residuo en log)."""
    return np.mean(np.exp(y_obs - y_pred), axis=0)


def inicio_seleccion(fin_ent: str = FIN_ENTRENAMIENTO) -> pd.Timestamp:
    """Primer día del bloque de selección: AÑOS_CALIBRACION años después del fin del entrenamiento."""
    return pd.Timestamp(fin_ent) + pd.Timedelta(days=1) + pd.DateOffset(years=AÑOS_CALIBRACION)


class ValidacionCausal:
    """Divide la validación en calibración (emisiones cuyos 30 objetivos terminan antes del bloque de selección) y
    selección (emisiones desde inicio_seleccion). La corrección de Duan se estima solo con la calibración y se aplica
    a la selección: ningún pronóstico evaluado usa residuos posteriores a él.
    a_q(yv) recibe los cambios log pronosticados para TODA la validación y devuelve m³/s del bloque de selección."""

    def __init__(self, m: Muestras, iv: np.ndarray, fin_ent: str = FIN_ENTRENAMIENTO):
        H = m.y.shape[1]
        f = m.fechas[iv]
        s = inicio_seleccion(fin_ent)
        self.m, self.iv, self.inicio = m, iv, s
        self.cal = np.where(f + pd.Timedelta(days=H) < s)[0]
        self.sel = np.where(f >= s)[0]
        if len(self.cal) == 0 or len(self.sel) == 0:
            raise ValueError(f'validación sin bloque de calibración ({len(self.cal)}) o de selección ({len(self.sel)})')
        assert (f[self.cal] + pd.Timedelta(days=H)).max() < f[self.sel].min(), 'calibración y selección se solapan'
        self.obs_sel = m.q_obs[iv[self.sel]]
        self.fechas_sel = f[self.sel]

    def factor(self, yv: np.ndarray) -> np.ndarray:
        return factor_duan(self.m.y[self.iv[self.cal]], yv[self.cal])

    def a_q(self, yv: np.ndarray) -> np.ndarray:
        return a_caudal(self.m, yv[self.sel], self.iv[self.sel], self.factor(yv))

    def resumen(self) -> dict:
        f = self.m.fechas[self.iv]
        return {'calibración': f"{f[self.cal].min():%Y-%m-%d} a {f[self.cal].max():%Y-%m-%d}", 'muestras calibración': len(self.cal),
                'selección': f"{f[self.sel].min():%Y-%m-%d} a {f[self.sel].max():%Y-%m-%d}", 'muestras selección': len(self.sel),
                'excluidas por la separación de 30 días': int(len(f) - len(self.cal) - len(self.sel))}


# ----------------------------------------------------------------------------- fechas comunes
def fechas_prueba_validas(nombre: str) -> pd.DatetimeIndex:
    """Fechas de emisión de prueba con los 30 objetivos observados, con el protocolo principal de la estación."""
    q, _ = cargar_serie(nombre)
    m = construir_muestras(q, L=L_VENTANA, H=len(HORIZONTES), esc=escalones(q), eps=eps_entrenamiento(q))
    return m.fechas[particion(m)['pru']]


def fechas_comunes() -> pd.DatetimeIndex:
    """Intersección explícita de las fechas de emisión válidas de prueba de las dos estaciones. Como cada emisión
    exige sus 30 objetivos observados, los pares emisión–horizonte también son idénticos."""
    f = None
    for e in ESTACIONES:
        fe = fechas_prueba_validas(e)
        f = fe if f is None else f.intersection(fe)
    return f


# ----------------------------------------------------------------------------- referencias
def climatologia(q: pd.Series, hasta: str = FIN_ENTRENAMIENTO, ventana: int = 31, desde: str | None = None) -> pd.Series:
    """Caudal medio por día del año en [desde, hasta], suavizado con media móvil circular de 31 días."""
    qe = q.loc[desde:hasta].dropna()
    c = qe.groupby(qe.index.dayofyear).mean().reindex(range(1, 367)).interpolate(limit_direction='both')
    ext = pd.concat([c.iloc[-ventana:], c, c.iloc[:ventana]])
    return ext.rolling(ventana, center=True).mean().iloc[ventana:-ventana]


def climatologia_referencia(q: pd.Series, bloque: str) -> pd.Series:
    """Climatología de referencia según la política del proyecto (CLIMATOLOGIA_HASTA): 'validación' o 'prueba'."""
    return climatologia(q, hasta=CLIMATOLOGIA_HASTA[bloque])


def pred_persistencia(m: Muestras, idx: np.ndarray) -> np.ndarray:
    return np.repeat(m.q_t[idx][:, None], m.y.shape[1], axis=1)


def pred_climatologia(m: Muestras, idx: np.ndarray, clim: pd.Series) -> np.ndarray:
    H = m.y.shape[1]
    destino = m.fechas[idx].to_numpy()[:, None] + np.arange(1, H + 1) * np.timedelta64(1, 'D')
    doy = pd.DatetimeIndex(destino.ravel()).dayofyear.to_numpy().reshape(destino.shape)
    return clim.reindex(range(1, 367)).to_numpy()[doy - 1]


def pred_tendencia(q: pd.Series, fechas, H: int, eps: float, dias: int = 3) -> np.ndarray:
    """Referencia ingenua para avisos: extrapola la tendencia logarítmica de los últimos `dias` días."""
    fechas = pd.DatetimeIndex(fechas)
    z = np.log(q + eps)
    zt = z.reindex(fechas).to_numpy()
    zp = z.reindex(fechas - pd.Timedelta(days=dias)).to_numpy()
    pend = (zt - zp) / dias
    return np.maximum(np.exp(zt[:, None] + pend[:, None] * np.arange(1, H + 1)[None, :]) - eps, 0)


# ----------------------------------------------------------------------------- métricas
def nse(o, p):
    o, p = np.asarray(o, float), np.asarray(p, float)
    den = np.sum((o - o.mean()) ** 2)
    return float(1 - np.sum((o - p) ** 2) / den) if den > 0 else np.nan


def kge(o, p):
    o, p = np.asarray(o, float), np.asarray(p, float)
    if o.std() == 0 or p.std() == 0 or o.mean() == 0:
        return np.nan
    r = np.corrcoef(o, p)[0, 1]
    return float(1 - np.sqrt((r - 1) ** 2 + (p.std() / o.std() - 1) ** 2 + (p.mean() / o.mean() - 1) ** 2))


def rmse(o, p):
    return float(np.sqrt(np.mean((np.asarray(o, float) - np.asarray(p, float)) ** 2)))


def mae(o, p):
    return float(np.mean(np.abs(np.asarray(o, float) - np.asarray(p, float))))


def pbias(o, p):
    o, p = np.asarray(o, float), np.asarray(p, float)
    return float(100 * (p.sum() - o.sum()) / o.sum()) if o.sum() else np.nan


def habilidad(o, p, ref):
    """Skill = 1 − MSE(modelo) / MSE(referencia): > 0 si el modelo mejora a la referencia."""
    o, p, ref = (np.asarray(x, float) for x in (o, p, ref))
    d = np.mean((o - ref) ** 2)
    return float(1 - np.mean((o - p) ** 2) / d) if d > 0 else np.nan


def tabla_metricas(obs: np.ndarray, pred: np.ndarray, pers: np.ndarray, clim: np.ndarray) -> pd.DataFrame:
    filas = []
    for j in range(obs.shape[1]):
        o, p = obs[:, j], pred[:, j]
        filas.append(dict(h=j + 1, NSE=nse(o, p), KGE=kge(o, p), MAE=mae(o, p), RMSE=rmse(o, p), PBIAS=pbias(o, p),
                          hab_pers=habilidad(o, p, pers[:, j]), hab_clim=habilidad(o, p, clim[:, j])))
    return pd.DataFrame(filas).set_index('h')


def _bloques(fechas: pd.DatetimeIndex, dias_bloque: int | None):
    """Código de bloque de cada fecha de emisión: mes calendario (None) o bloques consecutivos de `dias_bloque` días."""
    if dias_bloque is None:
        etiqueta = fechas.to_period('M').astype(str)
    else:
        etiqueta = ((fechas - fechas.min()).days // dias_bloque).astype(str)
    _, cod = np.unique(np.asarray(etiqueta), return_inverse=True)
    return cod


def bootstrap_curvas(fechas, obs, pred, pers, clim, B: int = 1000, dias_bloque: int | None = None,
                     semilla: int = SEMILLA) -> dict:
    """Bootstrap de bloques aplicado a TODOS los horizontes a la vez (las mismas réplicas para los 30 h).
    Con las mismas fechas y la misma semilla, dos llamadas usan exactamente las mismas réplicas (comparaciones
    pareadas). Devuelve matrices (B, H) de NSE y habilidades."""
    rng = np.random.default_rng(semilla)
    cod = _bloques(pd.DatetimeIndex(fechas), dias_bloque)
    nb = cod.max() + 1

    def suma(x):
        out = np.zeros((nb, x.shape[1]))
        np.add.at(out, cod, x)
        return out
    sm, sp, sc = suma((obs - pred) ** 2), suma((obs - pers) ** 2), suma((obs - clim) ** 2)
    so, so2 = suma(obs), suma(obs ** 2)
    nn = np.bincount(cod, minlength=nb).astype(float)[:, None]
    k = rng.integers(0, nb, size=(B, nb))
    SM, SP, SC = sm[k].sum(1), sp[k].sum(1), sc[k].sum(1)
    SO, SO2, N = so[k].sum(1), so2[k].sum(1), nn[k].sum(1)
    return dict(NSE=1 - SM / (SO2 - SO ** 2 / N), hab_pers=1 - SM / SP, hab_clim=1 - SM / SC)


def _consecutivo(ok) -> int:
    """Mayor h consecutivo desde 1 en que ok[h−1] es verdadero (0 si falla en h = 1)."""
    ok = np.asarray(ok, bool)
    return int(len(ok) if ok.all() else np.argmin(ok))


def horizonte_util(tab: pd.DataFrame) -> int:
    """Definición principal (H): mayor h consecutivo desde 1 con NSE > 0, habilidad > 0 frente a la persistencia
    y habilidad > 0 frente a la climatología. Si h = 1 falla, H = 0."""
    ok = (tab['NSE'] > 0) & (tab['hab_pers'] > 0) & (tab['hab_clim'] > 0)
    return _consecutivo(ok.to_numpy())


def replicas_h(curvas: dict) -> np.ndarray:
    """La MISMA definición H aplicada a cada réplica del bootstrap conjunto."""
    return np.array([_consecutivo((n > 0) & (a > 0) & (b > 0))
                     for n, a, b in zip(curvas['NSE'], curvas['hab_pers'], curvas['hab_clim'])])


def horizontes(tab: pd.DataFrame, curvas: dict) -> dict:
    """Horizonte útil y su incertidumbre.
    - H_puntual: definición principal en la muestra de prueba.
    - H_cota: cota inferior UNILATERAL aproximada de 95 % = min(H_puntual, percentil 5 de H en las réplicas). Es la cifra
      que se usa en las conclusiones. Percentiles empíricos (inverted_cdf); H = 30 significa "30 o más" (no se encontró
      el límite dentro de los 30 días evaluados; no valida plazos mayores). El rango p05–p95 contiene el 90 % central de
      las réplicas (no es un intervalo bilateral de 95 %). El bootstrap remuestrea meses de emisiones con las
      predicciones FIJAS: no incluye la incertidumbre del entrenamiento, de la medición ni de las decisiones del estudio.
    - H_marginal: complementario; exige el límite inferior de cada IC 95 % marginal > 0 (no es una banda simultánea).
    - calidad: complementario; mayor h consecutivo con NSE ≥ 0.5 (no es una definición de utilidad operativa)."""
    rep = replicas_h(curvas)
    q = lambda p: int(np.quantile(rep, p, method='inverted_cdf'))
    inf_p = np.percentile(curvas['hab_pers'], 2.5, axis=0)
    inf_c = np.percentile(curvas['hab_clim'], 2.5, axis=0)
    pun = horizonte_util(tab)
    return dict(H_puntual=pun, H_cota=min(pun, q(0.05)), H_p05=q(0.05), H_mediana=q(0.5), H_p95=q(0.95),
                P_H30=float(np.mean(rep >= len(tab))),
                H_marginal=_consecutivo((tab['NSE'].to_numpy() > 0) & (inf_p > 0) & (inf_c > 0)),
                calidad=_consecutivo(tab['NSE'].to_numpy() >= 0.5))


COLS_H = {'H_cota': 'H cota 95 % (d)', 'H_puntual': 'H puntual (d)', 'H_p05': 'H p05 (d)', 'H_mediana': 'H mediana (d)',
          'H_p95': 'H p95 (d)', 'P_H30': 'P(H ≥ 30)', 'H_marginal': 'H marginal estricto (d)', 'calidad': 'NSE ≥ 0.5 hasta (d)'}


def fila_h(hz: dict) -> dict:
    return {COLS_H[k]: v for k, v in hz.items()}


def conteo_altos(fechas, obs: np.ndarray, umbral: float) -> tuple[int, int]:
    """(pares emisión–horizonte con Q observado > umbral, fechas objetivo únicas con Q > umbral). Una misma fecha alta
    aparece en hasta H pares; ninguno de los dos números es un número de eventos independientes."""
    fechas = pd.DatetimeIndex(fechas)
    alto = np.asarray(obs) > umbral
    i, j = np.where(alto)
    objetivo = fechas[i] + pd.to_timedelta(j + 1, unit='D')
    return int(alto.sum()), int(pd.DatetimeIndex(objetivo).nunique())


def metricas_crecida(obs: np.ndarray, pred: np.ndarray, umbral: float) -> pd.DataFrame:
    """Por horizonte, en días con Q observado > umbral (altos) y ≤ umbral (ordinarios): MAE, RMSE, error relativo
    mediano, sesgo (PBIAS) y una tabla de contingencia DIARIA de "día alto" (POD, FAR y CSI con las mismas unidades).
    Esta detección diaria incluye días dentro de eventos ya iniciados: no mide anticipación de nuevos cruces."""
    filas = []
    for j in range(obs.shape[1]):
        o, p = obs[:, j], pred[:, j]
        alto = o > umbral
        ob, pr = o > umbral, p > umbral
        a, b, c = int(np.sum(ob & pr)), int(np.sum(~ob & pr)), int(np.sum(ob & ~pr))
        filas.append(dict(h=j + 1, n_altos=int(alto.sum()), aciertos=a, falsas_alarmas=b, omisiones=c,
                          RMSE_altos=rmse(o[alto], p[alto]) if alto.any() else np.nan,
                          PBIAS_altos=pbias(o[alto], p[alto]) if alto.any() else np.nan,
                          RMSE_ordinarios=rmse(o[~alto], p[~alto]),
                          MAE_altos=mae(o[alto], p[alto]) if alto.any() else np.nan,
                          MAE_ordinarios=mae(o[~alto], p[~alto]),
                          error_rel_altos=float(np.median(np.abs(p[alto] - o[alto]) / o[alto]) * 100) if alto.any() else np.nan,
                          error_rel_ordinarios=float(np.median(np.abs(p[~alto] - o[~alto]) / np.maximum(o[~alto], 1e-9)) * 100),
                          POD=a / (a + c) if a + c else np.nan, FAR=b / (a + b) if a + b else np.nan,
                          CSI=a / (a + b + c) if a + b + c else np.nan))
    return pd.DataFrame(filas).set_index('h')


def eventos(q: pd.Series, umbral: float, desde: str | None = None, hasta: str | None = None,
            sep: int = SEP_EVENTOS) -> pd.DataFrame:
    """Descripción RETROSPECTIVA de eventos (no se usa para decidir qué emisiones son elegibles para avisar): días con
    Q observado > umbral; dos tramos separados por menos de `sep` días seguidos observados bajo el umbral forman un
    mismo evento (un vacío no termina un evento). `evaluable`: los `sep` días previos al inicio tienen dato y están
    bajo el umbral."""
    s = q.loc[desde:hasta]
    dias = s.index[(s > umbral).to_numpy()]
    if len(dias) == 0:
        return pd.DataFrame(columns=['inicio', 'fin', 'dias_sobre', 'pico', 'fecha_pico', 'evaluable', 'motivo'])
    grupos, actual = [], [dias[0]]
    for d in dias[1:]:
        hueco = q.loc[actual[-1] + pd.Timedelta(days=1):d - pd.Timedelta(days=1)]
        bajo = hueco.notna().to_numpy()
        racha = max((len(x) for x in ''.join('1' if v else '0' for v in bajo).split('0')), default=0)
        if racha < sep:
            actual.append(d)
        else:
            grupos.append(actual); actual = [d]
    grupos.append(actual)
    filas = []
    for g in grupos:
        v = s.loc[g]
        ini = g[0]
        previo = q.loc[ini - pd.Timedelta(days=sep):ini - pd.Timedelta(days=1)]
        motivo = ''
        if len(previo) < sep or previo.isna().any():
            motivo = 'vacío o inicio del registro antes del cruce'
        elif (previo > umbral).any():
            motivo = 'continúa un evento anterior'
        elif desde is not None and ini <= pd.Timestamp(desde):
            motivo = 'en el borde del periodo'
        filas.append(dict(inicio=ini, fin=g[-1], dias_sobre=len(g), pico=float(v.max()), fecha_pico=v.idxmax(),
                          evaluable=motivo == '', motivo=motivo))
    return pd.DataFrame(filas)


# ----------------------------------------------------------------------------- modelos
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MALLAS = {
    'Regresión lineal': {},
    'Random Forest': dict(max_depth=[10, 20], min_samples_leaf=[5, 20], max_features=[0.3, 1.0]),
    'XGBoost': dict(max_depth=[3, 6], learning_rate=[0.05, 0.1], reg_lambda=[1.0, 10.0], n_estimators=[100, 200, 400]),
    'KNN': dict(n_neighbors=[5, 10, 20, 40, 80], weights=['uniform', 'distance'], ventana=[3, 7, 15, 30]),
    'MLP': dict(hidden_layer_sizes=[(64,), (128, 64)], alpha=[1e-4, 1e-2], max_iter=[50, 200]),
    'LSTM': dict(oculto=[32, 64], dropout=[0.0, 0.2]),
}
# Iteraciones evaluadas por etapas con un solo ajuste (los primeros k árboles de un ajuste de 400 son idénticos a un
# ajuste de k árboles: sin parada temprana y con la misma semilla).
ETAPAS = {'XGBoost': 'n_estimators'}


def combinaciones(malla: dict) -> list[dict]:
    claves = list(malla)
    return [dict(zip(claves, v)) for v in product(*(malla[k] for k in claves))]


class KNNVentana(BaseEstimator, RegressorMixin):
    """KNN sobre [log Q(t), los últimos ventana−1 cambios respecto a hoy, sen y cos del día del año], estandarizados
    con el entrenamiento. Predice el promedio (o promedio ponderado por distancia) de los objetivos de los k vecinos
    del entrenamiento: nunca incluye la propia consulta ni ventanas posteriores al bloque de ajuste."""

    def __init__(self, n_neighbors=10, weights='uniform', ventana=30):
        self.n_neighbors, self.weights, self.ventana = n_neighbors, weights, ventana

    def _cols(self, X):
        L = X.shape[1] - 2
        v = min(self.ventana, L)
        return [0] + list(range(L - v + 1, L)) + [X.shape[1] - 2, X.shape[1] - 1]

    def fit(self, X, y):
        self.cols_ = self._cols(X)
        self.esc_ = StandardScaler().fit(X[:, self.cols_])
        self.knn_ = KNeighborsRegressor(n_neighbors=self.n_neighbors, weights=self.weights, n_jobs=-1)
        self.knn_.fit(self.esc_.transform(X[:, self.cols_]), y)
        return self

    def predict(self, X):
        return self.knn_.predict(self.esc_.transform(X[:, self.cols_]))


def _y_estandar(reg):
    """Envuelve un regresor para que aprenda los objetivos estandarizados por horizonte (media y desviación del bloque
    de ajuste) y devuelva las predicciones en la escala original."""
    return TransformedTargetRegressor(regressor=reg, transformer=StandardScaler(), check_inverse=False)


def crear_tabular(nombre: str, params: dict, semilla: int = SEMILLA):
    if nombre == 'Regresión lineal':
        return make_pipeline(StandardScaler(), LinearRegression())
    if nombre == 'Random Forest':
        # Un solo bosque para los 30 horizontes: con objetivos estandarizados por horizonte cada uno pesa lo mismo en
        # las particiones (sin estandarizar, el error de los horizontes largos domina porque su varianza es mayor).
        return _y_estandar(RandomForestRegressor(n_estimators=300, n_jobs=-1, random_state=semilla, **params))
    if nombre == 'XGBoost':
        from xgboost import XGBRegressor
        # Sin parada temprana; n_estimators se elige con la validación temporal. Un árbol por horizonte en cada ronda.
        return XGBRegressor(tree_method='hist', multi_strategy='one_output_per_tree', subsample=0.8, colsample_bytree=0.8,
                            n_jobs=2, random_state=semilla, verbosity=0, **params)
    if nombre == 'KNN':
        return KNNVentana(**params)
    if nombre == 'MLP':
        # Sin early_stopping (sklearn la haría con una partición aleatoria); max_iter se elige con validación temporal.
        # Objetivos estandarizados por horizonte (como la LSTM): sin ello la pérdida la dominan los horizontes largos
        # (en Tamshiyacu la varianza del objetivo a 30 días es ~200 veces la de 1 día) y h = 1 queda mal ajustado.
        return _y_estandar(make_pipeline(StandardScaler(), MLPRegressor(early_stopping=False, random_state=semilla,
                                                                        learning_rate_init=1e-3, **params)))
    raise ValueError(nombre)


def predecir_por_etapas(nombre: str, modelo, X: np.ndarray, etapas: list[int]) -> dict[int, np.ndarray]:
    """Predicciones de un modelo de boosting ya ajustado con max(etapas) árboles, truncado a cada número de etapas."""
    if nombre == 'XGBoost':
        return {k: modelo.predict(X, iteration_range=(0, k)) for k in etapas}
    raise ValueError(nombre)


def ajustar_malla(nombre: str, X, y, Xv, a_q, obs_v, semilla: int = SEMILLA) -> list[dict]:
    """Ajusta todas las combinaciones de la malla con (X, y) y mide el NSE medio en el bloque de selección (m³/s).
    a_q: función que convierte los cambios log pronosticados para toda la validación (Xv) en caudal del bloque de
    selección (ValidacionCausal.a_q); obs_v: caudal observado de ese bloque. Devuelve una fila por combinación."""
    import json
    import time
    malla = dict(MALLAS[nombre])
    filas = []
    etapa = ETAPAS.get(nombre)
    etapas = malla.pop(etapa) if etapa else None
    for params in combinaciones(malla):
        t0 = time.time()
        if etapa:
            mod = crear_tabular(nombre, {**params, etapa: max(etapas)}, semilla).fit(X, y)
            preds = predecir_por_etapas(nombre, mod, Xv, etapas)
            dt = (time.time() - t0) / len(etapas)
            for k, yv in preds.items():
                filas.append(dict(modelo=nombre, parametros=json.dumps({**params, etapa: k}), NSE_val=nse_medio(a_q(yv), obs_v),
                                  segundos=dt))
        else:
            mod = crear_tabular(nombre, params, semilla).fit(X, y)
            filas.append(dict(modelo=nombre, parametros=json.dumps(params), NSE_val=nse_medio(a_q(mod.predict(Xv)), obs_v),
                              segundos=time.time() - t0))
    return filas


def nse_medio(qpred, obs) -> float:
    return float(np.nanmean([nse(obs[:, j], qpred[:, j]) for j in range(obs.shape[1])]))


def _bloques_mes(fechas: pd.DatetimeIndex) -> list[np.ndarray]:
    mes = pd.DatetimeIndex(fechas).to_period('M')
    return [np.where(mes == u)[0] for u in mes.unique()]


def seleccion_pareada(fechas, obs: np.ndarray, preds: dict, B: int = B_SELECCION, margen: float = MARGEN_NSE,
                      orden: list[str] = ORDEN_SIMPLICIDAD, semilla: int = SEMILLA):
    """Regla de selección fijada antes de ejecutar v4 (bloque de selección de la validación):
    1. 'mejor' = mayor NSE medio de los 30 horizontes.
    2. Para cada otro candidato, diferencia de NSE medio frente al mejor con un bootstrap PAREADO por meses de emisión
       (las mismas réplicas para todos) e intervalo del 90 % (percentiles 5–95).
       equivalente: el intervalo cabe en (−margen, +margen) · peor: el intervalo queda por debajo de 0 · inconcluso: resto.
    3. 'seleccionado' = el más simple (según `orden`) entre el mejor y sus equivalentes.
    Una diferencia menor que el margen sin intervalo contenido NO se interpreta como igualdad (queda inconclusa).
    Devuelve (tabla, seleccionado, mejor)."""
    nombres = list(preds)
    obs = np.asarray(obs, float)
    P = {n: np.asarray(preds[n], float) for n in nombres}
    base = {n: nse_medio(P[n], obs) for n in nombres}
    mejor = max(nombres, key=lambda n: base[n])
    rng = np.random.default_rng(semilla)
    bl = _bloques_mes(fechas)
    reps = np.zeros((B, len(nombres)))
    for b in range(B):
        idx = np.concatenate([bl[j] for j in rng.integers(0, len(bl), len(bl))])
        o = obs[idx]
        den = ((o - o.mean(0)) ** 2).sum(0)
        for k, n in enumerate(nombres):
            reps[b, k] = np.mean(1 - ((o - P[n][idx]) ** 2).sum(0) / den)
    km = nombres.index(mejor)
    filas = []
    for k, n in enumerate(nombres):
        d = reps[:, k] - reps[:, km]
        p05, p95 = (np.nan, np.nan) if n == mejor else (float(np.percentile(d, 5)), float(np.percentile(d, 95)))
        if n == mejor:
            clase = 'mejor'
        elif p05 > -margen and p95 < margen:
            clase = 'equivalente'
        elif p95 < 0:
            clase = 'peor'
        else:
            clase = 'inconcluso'
        filas.append({'modelo': n, 'NSE medio selección': base[n], 'diferencia con el mejor': base[n] - base[mejor],
                      'IC90 inferior': p05, 'IC90 superior': p95, 'clase': clase})
    tab = pd.DataFrame(filas).set_index('modelo')
    candidatos = [n for n in nombres if tab.loc[n, 'clase'] in ('mejor', 'equivalente')]
    sel = min(candidatos, key=lambda n: orden.index(n) if n in orden else len(orden))
    tab['seleccionado'] = tab.index == sel
    return tab.sort_values('NSE medio selección', ascending=False), sel, mejor


# --- LSTM (PyTorch) -----------------------------------------------------------
def _torch():
    import torch
    torch.set_num_threads(2)
    return torch


def secuencias(m: Muestras, idx: np.ndarray, mu: float, sd: float) -> np.ndarray:
    """(n, L, 4): log Q estandarizado, log Q relativo a hoy, sen y cos del día del año de t (mismo calendario que los
    modelos tabulares). Cada ventana es independiente: no se transportan estados ocultos entre muestras."""
    v = m.ventana[idx]
    ang = 2 * np.pi * m.doy[idx] / 365.25
    L = v.shape[1]
    return np.stack([(v - mu) / sd, v - v[:, -1:], np.repeat(np.sin(ang)[:, None], L, 1),
                     np.repeat(np.cos(ang)[:, None], L, 1)], axis=2).astype(np.float32)


class _RedLSTM:
    def __init__(self, n_in, oculto, dropout, H):
        torch = _torch()
        nn = torch.nn

        class Red(nn.Module):
            def __init__(s):
                super().__init__()
                s.lstm = nn.LSTM(n_in, oculto, batch_first=True)
                s.drop = nn.Dropout(dropout)
                s.cabeza = nn.Linear(oculto, H)

            def forward(s, x):
                salida, _ = s.lstm(x)
                return s.cabeza(s.drop(salida[:, -1, :]))
        self.red = Red()


def entrenar_lstm(Xtr, Ytr, Xva=None, Yva=None, oculto=64, dropout=0.0, semilla=SEMILLA,
                  epocas=None, max_epocas=150, paciencia=15, lote=128, lr=1e-3):
    """Entrena una LSTM. Con (Xva, Yva) usa parada temprana con ese bloque y devuelve (red, mejor época);
    sin él entrena exactamente `epocas` épocas."""
    torch = _torch()
    torch.manual_seed(semilla)
    rng = np.random.default_rng(semilla)
    red = _RedLSTM(Xtr.shape[2], oculto, dropout, Ytr.shape[1]).red
    opt = torch.optim.Adam(red.parameters(), lr=lr)
    perdida = torch.nn.MSELoss()
    Xt, Yt = torch.from_numpy(Xtr), torch.from_numpy(Ytr.astype(np.float32))
    if Xva is not None:
        Xv, Yv = torch.from_numpy(Xva), torch.from_numpy(Yva.astype(np.float32))
    mejor, mejor_ep, estado, sin_mejora = np.inf, 0, None, 0
    total = epocas if epocas is not None else max_epocas
    for ep in range(1, total + 1):
        red.train()
        orden = rng.permutation(len(Xt))
        for i in range(0, len(orden), lote):
            b = orden[i:i + lote]
            opt.zero_grad()
            l = perdida(red(Xt[b]), Yt[b])
            l.backward()
            opt.step()
        if Xva is not None and epocas is None:
            red.eval()
            with torch.no_grad():
                lv = perdida(red(Xv), Yv).item()
            if lv < mejor - 1e-5:
                mejor, mejor_ep, sin_mejora = lv, ep, 0
                estado = {k: v.clone() for k, v in red.state_dict().items()}
            else:
                sin_mejora += 1
                if sin_mejora >= paciencia:
                    break
    if estado is not None:
        red.load_state_dict(estado)
    return red, (mejor_ep if epocas is None else epocas)


def predecir_lstm(red, X) -> np.ndarray:
    torch = _torch()
    red.eval()
    with torch.no_grad():
        return red(torch.from_numpy(X)).numpy()


class LSTMProtocolo:
    """LSTM con el protocolo de épocas v3: (1) entrena con `ent_in` y detiene con el bloque cronológico `parada`
    (posterior a ent_in y anterior a la validación) → épocas E; (2) reentrena con todo `ent` durante E épocas.
    Así el bloque que detiene el entrenamiento no es el mismo que compara candidatos."""

    def __init__(self, m: Muestras, ent_in, parada, oculto, dropout, semilla=SEMILLA):
        self.m, self.oculto, self.dropout, self.semilla = m, oculto, dropout, semilla
        self.ent_in, self.parada = ent_in, parada

    def ajustar(self, ent):
        m = self.m
        mu, sd = float(m.ventana[self.ent_in].mean()), float(m.ventana[self.ent_in].std())
        ym, ys = m.y[self.ent_in].mean(0), m.y[self.ent_in].std(0)
        _, ep = entrenar_lstm(secuencias(m, self.ent_in, mu, sd), (m.y[self.ent_in] - ym) / ys,
                              secuencias(m, self.parada, mu, sd), (m.y[self.parada] - ym) / ys,
                              oculto=self.oculto, dropout=self.dropout, semilla=self.semilla)
        self.epocas = max(ep, 1)
        return self.reajustar(ent)

    def reajustar(self, ent, epocas=None):
        m = self.m
        self.mu, self.sd = float(m.ventana[ent].mean()), float(m.ventana[ent].std())
        self.ym, self.ys = m.y[ent].mean(0), m.y[ent].std(0)
        self.red, _ = entrenar_lstm(secuencias(m, ent, self.mu, self.sd), (m.y[ent] - self.ym) / self.ys,
                                    epocas=epocas or self.epocas, oculto=self.oculto, dropout=self.dropout, semilla=self.semilla)
        return self

    def predecir(self, idx):
        return predecir_lstm(self.red, secuencias(self.m, idx, self.mu, self.sd)) * self.ys + self.ym


def importancia_grupos(modelo, X, y_obs_q, m: Muestras, idx, grupos: dict, horizontes, factor=None, repeticiones=5):
    """Aumento relativo del MSE (m³/s) al permutar juntas las columnas de cada grupo, por horizonte. Mide cuánto usa
    el modelo cada grupo; con variables correlacionadas no demuestra causalidad."""
    rng = np.random.default_rng(SEMILLA)
    base = a_caudal(m, modelo.predict(X), idx, factor)
    mse0 = {h: np.mean((y_obs_q[:, h - 1] - base[:, h - 1]) ** 2) for h in horizontes}
    filas = []
    for g, cols in grupos.items():
        acc = {h: [] for h in horizontes}
        for _ in range(repeticiones):
            Xp = X.copy()
            perm = rng.permutation(len(X))
            Xp[:, cols] = X[perm][:, cols]
            pr = a_caudal(m, modelo.predict(Xp), idx, factor)
            for h in horizontes:
                acc[h].append(np.mean((y_obs_q[:, h - 1] - pr[:, h - 1]) ** 2) / mse0[h] - 1)
        filas.append({'grupo': g, **{f'h={h}': float(np.mean(acc[h])) for h in horizontes}})
    return pd.DataFrame(filas).set_index('grupo')


# ----------------------------------------------------------------------------- avisos de nuevos cruces del P95
DESCONOCIDO, BAJO, ALTO = 0, 1, 2


def estado_diario(q: pd.Series, umbral: float, d0, d1) -> pd.Series:
    """Tres estados por día: 2 = alto (Q > umbral), 1 = bajo (Q ≤ umbral), 0 = desconocido (sin dato)."""
    s = q.reindex(pd.date_range(d0, d1))
    return pd.Series(np.where(s.isna(), DESCONOCIDO, np.where(s > umbral, ALTO, BAJO)), index=s.index)


def elegibilidad(estado: pd.Series, reinicio: int = 7) -> pd.Series:
    """Estado causal de elegibilidad: el día t permite avisar un NUEVO cruce si t y los `reinicio` − 1 días previos
    están observados y bajo el umbral. Solo usa información disponible en t (no agrupa eventos con datos futuros);
    un vacío no cuenta como día bajo."""
    bajo = (estado == BAJO).astype(int)
    return bajo.rolling(reinicio, min_periods=reinicio).sum().eq(reinicio)


def cruces(estado: pd.Series, reinicio: int = 7) -> pd.DataFrame:
    """Todos los cruces observados (día alto precedido de un día no alto) y si son **nuevos cruces elegibles**:
    los `reinicio` días previos están observados y bajo el umbral."""
    el = elegibilidad(estado, reinicio)
    alto = estado == ALTO
    prev = estado.shift(1)
    filas = []
    for d in estado.index[alto & (prev != ALTO)]:
        previo = estado.loc[d - pd.Timedelta(days=reinicio):d - pd.Timedelta(days=1)]
        if el.get(d - pd.Timedelta(days=1), False):
            motivo = ''
        elif len(previo) < reinicio or (previo == DESCONOCIDO).any():
            motivo = 'vacío o borde antes del cruce'
        else:
            motivo = f'menos de {reinicio} días bajo el umbral desde el evento anterior'
        filas.append(dict(fecha=d, elegible=motivo == '', motivo=motivo))
    return pd.DataFrame(filas, columns=['fecha', 'elegible', 'motivo'])


def evaluar_avisos(fechas, pred: np.ndarray, q: pd.Series, umbral: float, f: float = 1.0, hmax: int = 30,
                   tol: int = 2, dmax: int = 7, reinicio: int = 7, a_max: int = 30) -> dict:
    """Verificación por EVENTOS de avisos de nuevos cruces del umbral (P95), con unidades coherentes.

    1. Emisión elegible t: estado causal (elegibilidad). Solo desde ella se puede avisar un nuevo cruce.
    2. Aviso: alguna salida de la trayectoria pred(t, t+1 … t+hmax) supera u = f × umbral (f solo cambia la
       activación; el fenómeno sigue definido por el umbral). Fecha pronosticada del aviso τ = t + primer h con
       pred > u. Fecha pronosticada del cruce del umbral (para el error de fecha): primer h ≤ 30 con pred > umbral.
    3. Universo verificable U (el MISMO para POD, FAR y CSI): cruces nuevos elegibles d con una emisión elegible el
       día d − 1 dentro del periodo de emisiones. Un aviso es correcto para d ∈ U si t < d y |τ − d| ≤ tol. Si no
       acierta ningún cruce de U y en [τ−tol, τ+tol] hay días desconocidos, un cruce no elegible o un cruce elegible
       fuera de U (por ejemplo, después de la última emisión), es "no verificable" y no cuenta en ninguna métrica;
       si no, es falso. Un día alto dentro de un evento ya iniciado no hace correcto un aviso.
    4. Episodio: avisos en días de emisión consecutivos, partido cada `dmax` días para que un aviso encendido toda la
       temporada no cuente como uno solo. Emparejamiento uno a uno, en orden cronológico: cada episodio se asigna al
       primer cruce aún no emparejado para el que tiene un aviso correcto (acierto); si solo acierta cruces ya
       emparejados es "repetido" (ni acierto ni falsa alarma); si no tiene avisos correctos es falsa alarma (o "no
       verificable" si alguno de sus avisos no se puede verificar).
    5. Anticipación REAL de un acierto = d − (fecha de emisión del primer aviso correcto del episodio emparejado).
    6. Con los mismos H aciertos (cruces de U emparejados = episodios acertados), M omisiones y F falsas alarmas:
       POD = H/(H+M), FAR = F/(H+F), CSI = H/(H+M+F); un denominador nulo deja la métrica sin definir (NaN).
    7. Por anticipación exigida A se evalúa el SISTEMA COMPLETO: universo U_A = cruces de U con emisiones elegibles
       los días d − 1 … d − A; acierto a A = detectado con anticipación real ≥ A (un aviso tardío cuenta como omisión
       a A); F son todas las falsas alarmas del sistema en el periodo (no dependen de A). POD(A) = H_A/N_A y
       CSI(A) = H_A/(N_A + F). La FAR global se informa aparte. Como N_A puede bajar al aumentar A (faltan emisiones
       elegibles A días antes), también se informa POD sobre el conjunto FIJO U: POD_fijo(A) = H_A/N_1, donde un cruce
       sin emisiones suficientes cuenta como no anticipado a A (cota inferior; no reemplaza al indicador principal).
    8. Carga de avisos por año CALENDARIO del periodo de emisiones (y cobertura = días con emisión elegible / días).
    Devuelve dict con 'resumen', 'por_A', 'eventos', 'episodios' y 'avisos'."""
    fechas = pd.DatetimeIndex(fechas)
    if not (fechas.is_unique and fechas.is_monotonic_increasing):
        raise ValueError('las fechas de emisión deben ser únicas y crecientes')
    n, H = pred.shape
    d0 = fechas.min() - pd.Timedelta(days=reinicio + 1)
    d1 = fechas.max() + pd.Timedelta(days=H + tol + 1)
    est_s = estado_diario(q, umbral, d0, d1)
    el_s = elegibilidad(est_s, reinicio)
    cr = cruces(est_s, reinicio)
    est, el = est_s.to_numpy(), el_s.to_numpy()
    nd = len(est)
    dia = lambda x: int((x - d0).days)
    fecha = lambda k: d0 + pd.Timedelta(days=int(k))
    es_ons = np.zeros(nd, bool); es_noel = np.zeros(nd, bool)
    for r in cr.itertuples():
        (es_ons if r.elegible else es_noel)[dia(r.fecha)] = True
    ti = np.array([dia(t) for t in fechas])
    pos_em = {int(k): i for i, k in enumerate(ti)}
    k_min, k_max = int(ti.min()), int(ti.max())
    # ---------------- universo verificable U (antes de clasificar avisos)
    info_cr, U = {}, set()
    for r in cr.itertuples():
        d = dia(r.fecha)
        if not (k_min < d <= k_max + 1):
            continue                                           # fuera del periodo de emisiones
        ev_A = [(d - a) in pos_em and bool(el[d - a]) for a in range(1, a_max + 1)]
        evaluable = bool(r.elegible and ev_A[0])
        info_cr[d] = (r, ev_A, evaluable)
        if evaluable:
            U.add(d)
    u = f * umbral
    # ---------------- avisos (solo desde emisiones elegibles)
    av = []
    for i, k in enumerate(ti):
        if not el[k]:
            continue
        tr = pred[i]
        act = tr[:hmax] > u
        if not act.any():
            continue
        h_u = int(np.argmax(act)) + 1
        tau = k + h_u
        sobre = np.where(tr > umbral)[0]
        tau_p = k + int(sobre[0]) + 1 if len(sobre) else None
        lo, hi = max(tau - tol, 0), min(tau + tol, nd - 1)
        cand = [d for d in range(max(lo, k + 1), hi + 1) if es_ons[d]]
        ok_para = [d for d in cand if d in U]
        if ok_para:
            estado_av = 'correcto'
        elif cand or (est[lo:hi + 1] == DESCONOCIDO).any() or es_noel[lo:hi + 1].any():
            estado_av = 'no verificable'
        else:
            estado_av = 'falso'
        av.append(dict(k=k, emision=fechas[i], tau=fecha(tau), h_aviso=h_u,
                       tau_umbral=fecha(tau_p) if tau_p is not None else pd.NaT, estado=estado_av, cruces=ok_para))
    av = pd.DataFrame(av, columns=['k', 'emision', 'tau', 'h_aviso', 'tau_umbral', 'estado', 'cruces'])
    # ---------------- episodios (causales: días de emisión consecutivos, partidos cada dmax días)
    ep_id, cur, ini, ult = [], -1, None, None
    for k in av['k']:
        if ult is None or k - ult != 1 or k - ini >= dmax:
            cur += 1
            ini = k
        ep_id.append(cur)
        ult = k
    av['episodio'] = ep_id
    emparejado, episodios = {}, []
    for e_, g in av.groupby('episodio', sort=True):
        cand = sorted({d for lst in g['cruces'] for d in lst})
        libres = [d for d in cand if d not in emparejado]
        fila = dict(episodio=e_, inicio=g['emision'].min(), fin=g['emision'].max(), dias=len(g), cruce=pd.NaT,
                    primer_aviso_correcto=pd.NaT)
        if libres:
            d = libres[0]
            pr = g[g['cruces'].apply(lambda l: d in l)].iloc[0]
            emparejado[d] = dict(k=int(pr['k']), tau=pr['tau'], tau_umbral=pr['tau_umbral'])
            fila.update(clase='acierto', cruce=fecha(d), primer_aviso_correcto=pr['emision'])
        elif cand:
            fila['clase'] = 'repetido'
        elif (g['estado'] == 'no verificable').any():
            fila['clase'] = 'no verificable'
        else:
            fila['clase'] = 'falsa alarma'
        episodios.append(fila)
    episodios = pd.DataFrame(episodios, columns=['episodio', 'inicio', 'fin', 'dias', 'clase', 'cruce', 'primer_aviso_correcto'])
    # ---------------- cruces del periodo y anticipación real
    filas_ev = []
    for d, (r, ev_A, evaluable) in info_cr.items():
        e = emparejado.get(d)
        assert e is None or evaluable, 'solo se emparejan cruces del universo U'
        fila = dict(fecha=r.fecha, elegible=r.elegible, motivo=r.motivo, evaluable=evaluable,
                    max_A_evaluable=_consecutivo(ev_A) if r.elegible else 0, detectado=e is not None,
                    anticipacion_real=float(d - e['k']) if e else np.nan,
                    fecha_pronosticada=e['tau'] if e else pd.NaT,
                    error_fecha_umbral=float((e['tau_umbral'] - r.fecha).days) if e and pd.notna(e['tau_umbral']) else np.nan)
        for a in (1, 3, 7):
            err = np.nan
            if r.elegible and (d - a) in pos_em and el[d - a]:
                s_ = np.where(pred[pos_em[d - a]] > umbral)[0]
                err = float(s_[0] + 1 - a) if len(s_) else np.nan       # + = el cruce del umbral se pronostica tarde
            fila[f'error_fecha_A{a}'] = err
        filas_ev.append(fila)
    evs = pd.DataFrame(filas_ev, columns=['fecha', 'elegible', 'motivo', 'evaluable', 'max_A_evaluable', 'detectado',
                                          'anticipacion_real', 'fecha_pronosticada', 'error_fecha_umbral',
                                          'error_fecha_A1', 'error_fecha_A3', 'error_fecha_A7'])
    # ---------------- métricas (eventos / episodios)
    fa = int((episodios['clase'] == 'falsa alarma').sum())
    hits_ep = int((episodios['clase'] == 'acierto').sum())
    ev_ok = evs[evs['evaluable'].astype(bool)]
    n_ev = int(len(ev_ok))
    hits = int(ev_ok['detectado'].sum())
    # invariantes: el mismo H en las tres métricas y una sola clase por episodio
    assert hits == hits_ep == len(emparejado), f'H inconsistente: eventos {hits}, episodios {hits_ep}, emparejados {len(emparejado)}'
    assert n_ev == len(U) and int(evs['detectado'].sum()) == hits
    assert episodios['clase'].isin(['acierto', 'repetido', 'falsa alarma', 'no verificable']).all() if len(episodios) else True
    pod = hits / n_ev if n_ev else np.nan
    far = fa / (hits + fa) if hits + fa else np.nan
    csi = hits / (n_ev + fa) if n_ev + fa else np.nan
    elig_dias = int(el[ti].sum())
    dias_cal = int(k_max - k_min + 1)
    por_A = []
    for a in range(1, a_max + 1):
        base = ev_ok[ev_ok['max_A_evaluable'] >= a]
        ha = int((base['detectado'] & (base['anticipacion_real'] >= a)).sum())
        tard = int((base['detectado'] & (base['anticipacion_real'] < a)).sum())
        na = int(len(base))
        por_A.append(dict(A=a, evaluables=na, aciertos=ha, aciertos_tardios=tard, omisiones=na - ha, falsas_alarmas=fa,
                          POD=ha / na if na else np.nan, CSI=ha / (na + fa) if na + fa else np.nan,
                          no_evaluables_a_A=n_ev - na, POD_conjunto_fijo=ha / n_ev if n_ev else np.nan))
    por_A = pd.DataFrame(por_A).set_index('A')
    falsos = int((av['estado'] == 'falso').sum())
    resumen = dict(f=f, hmax=hmax, tol=tol, dmax=dmax, reinicio=reinicio, cruces_identificados=int(len(evs)),
                   cruces_elegibles=int(evs['elegible'].sum()), evaluables=n_ev, aciertos=hits, omisiones=n_ev - hits,
                   falsas_alarmas=fa, repetidos=int((episodios['clase'] == 'repetido').sum()),
                   episodios_no_verificables=int((episodios['clase'] == 'no verificable').sum()),
                   episodios=int(len(episodios)), POD=pod, FAR=far, CSI=csi,
                   anticipacion_mediana=float(ev_ok.loc[ev_ok['detectado'], 'anticipacion_real'].median()) if hits else np.nan,
                   dias_calendario=dias_cal, dias_elegibles=elig_dias, cobertura=elig_dias / dias_cal,
                   dias_aviso=int(len(av)), dias_aviso_falso=falsos,
                   episodios_anio=len(episodios) / dias_cal * 365.25, falsas_alarmas_anio=fa / dias_cal * 365.25,
                   dias_aviso_anio=len(av) / dias_cal * 365.25, dias_falso_anio=falsos / dias_cal * 365.25)
    resumen['anticipacion_util'] = anticipacion_util(resumen, por_A)
    resumen['anticipacion_util_conjunto_fijo'] = anticipacion_util(resumen, por_A, columna='POD_conjunto_fijo')
    return dict(resumen=resumen, por_A=por_A, eventos=evs, episodios=episodios, avisos=av.drop(columns=['k']))


def anticipacion_util(resumen: dict, por_A: pd.DataFrame, pod_min: float = AVISO['pod_min'],
                      far_max: float = AVISO['far_max'], columna: str = 'POD') -> int:
    """Criterio exploratorio fijado antes de la prueba: si FAR ≤ far_max, mayor A consecutivo desde 1 con
    POD(A) ≥ pod_min; si FAR > far_max o no está definida, 0. La FAR es la GLOBAL del sistema (no depende de A).
    columna='POD_conjunto_fijo': la misma regla sobre el conjunto fijo de cruces (sensibilidad, cota inferior)."""
    far = resumen['FAR']
    if not np.isfinite(far) or far > far_max:
        return 0
    return _consecutivo((por_A[columna] >= pod_min).fillna(False).to_numpy())
