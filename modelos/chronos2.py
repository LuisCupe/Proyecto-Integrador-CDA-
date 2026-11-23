"""Chronos-2 (cuaderno 07): pronóstico *zero-shot* del caudal con un modelo fundacional de series de tiempo.

Chronos-2 (Ansari et al., 2025; amazon/chronos-2, 120 M de parámetros) es un Transformer de tipo encoder preentrenado con
un gran corpus de series reales y sintéticas. **No se entrena con las cuencas del proyecto**: recibe, para cada fecha de
emisión t, la historia reciente del caudal (el "contexto") y, si se le dan, covariables, y devuelve 21 cuantiles del
caudal de t + 1 … t + 30 en una sola pasada (como en el Lab 9_4 del curso).

Convenciones (las mismas del protocolo v4, `comun.py`):
- El contexto de cada emisión termina en t (en t − d para una covariable con latencia d). Los vacíos ≤ 3 días se
  interpolan en log(Q + ε) por emisión y solo con días hasta ese corte; un vacío abierto en el corte y los vacíos
  más largos quedan como NaN: Chronos-2 los trata como dato desconocido.
- Si hay un escalón de nivel (EDA 2.7) dentro del contexto, se borran (NaN) los días anteriores al último escalón ≤ t: la
  escala anterior no es comparable. Se aplica a cada serie con sus propios escalones.
- Covariables **pasadas** (lluvia de la cuenca, caudal aguas arriba): solo valores ≤ t. Covariables **futuras**: valores
  observados de t + 1 … t + 30; solo para el escenario idealizado de lluvia futura observada (no disponible al emitir).
- Todo en unidades físicas (m³/s y mm/d): Chronos-2 escala cada serie internamente.

El cuantil 0.5 es la mediana. Para métricas cuadráticas (NSE, MSE) también se calcula la **media** aproximada integrando la
función de cuantiles (las 21 probabilidades con pesos de punto medio); cuál de las dos se usa se decide en el bloque de
selección 2012–2015 (cuaderno 07, sección 4). Los avisos usan la mediana, como en v4.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import comun as C

CUANTILES = [0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9,
             0.95, 0.99]
I50 = CUANTILES.index(0.5)
RUTA_MODELO_LOCAL = C.RAIZ / '_modelos_hf' / 'chronos-2'
RUTA_CACHE = Path(__file__).resolve().parent / C.ruta_salidas() / 'chronos' / 'cache'   # modo rápido: salidas_rapido/


# ----------------------------------------------------------------------------- modelo
def _unir_partes(ruta: Path) -> None:
    """Si el modelo se descargó en partes (model.safetensors.part00, part01…), las une en model.safetensors."""
    destino = ruta / 'model.safetensors'
    partes = sorted(ruta.glob('model.safetensors.part*'))
    if destino.exists() or not partes:
        return
    with open(destino, 'wb') as out:
        for p in partes:
            out.write(p.read_bytes())


def resolver_modelo() -> dict:
    """Carpeta EXACTA de los pesos que se cargan y su origen: variable de entorno CHRONOS2_MODELO, carpeta local
    `_modelos_hf/chronos-2` o, si no hay ninguna, la instantánea de 'amazon/chronos-2' en la caché de Hugging Face
    (se descarga la primera vez; la carpeta de la instantánea lleva el commit del repositorio)."""
    env = os.environ.get('CHRONOS2_MODELO')
    if env and Path(env).exists():
        return {'ruta': env, 'origen': 'local (CHRONOS2_MODELO)', 'commit': None}
    if RUTA_MODELO_LOCAL.exists():
        _unir_partes(RUTA_MODELO_LOCAL)
        return {'ruta': str(RUTA_MODELO_LOCAL), 'origen': 'local (_modelos_hf/chronos-2)', 'commit': None}
    from huggingface_hub import snapshot_download
    nombre = env or 'amazon/chronos-2'
    ruta = snapshot_download(nombre)
    return {'ruta': ruta, 'origen': f'Hugging Face ({nombre})', 'commit': Path(ruta).name}


def ruta_modelo() -> str:
    return resolver_modelo()['ruta']


def cargar_modelo():
    import torch
    from chronos import BaseChronosPipeline
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    disp = 'cuda' if torch.cuda.is_available() else 'cpu'
    pipe = BaseChronosPipeline.from_pretrained(ruta_modelo(), device_map=disp, torch_dtype=torch.float32)
    assert list(pipe.quantiles) == CUANTILES, 'cuantiles del modelo inesperados'
    return pipe, disp


def huella_modelo() -> str:
    """Identidad de los pesos REALMENTE cargados: SHA-256 de los archivos de la carpeta resuelta (pesos y
    configuración). Nunca devuelve un nombre de repositorio: si no encuentra los pesos, falla."""
    r = Path(ruta_modelo())
    archivos = sorted(x for x in r.iterdir() if x.is_file() and (x.suffix in ('.safetensors', '.json', '.bin')) and '.part' not in x.name)
    if not any(x.suffix in ('.safetensors', '.bin') for x in archivos):
        raise FileNotFoundError(f'no se encontraron los pesos de Chronos-2 en {r}')
    h = hashlib.sha256()
    for x in archivos:
        h.update(x.name.encode())
        with open(x, 'rb') as fh:
            for b in iter(lambda: fh.read(1 << 24), b''):
                h.update(b)
    return h.hexdigest()


def huella_pesos() -> str:
    """SHA-256 solo de model.safetensors (para compararla con la registrada en ejecuciones anteriores)."""
    f = Path(ruta_modelo()) / 'model.safetensors'
    h = hashlib.sha256()
    with open(f, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


# ----------------------------------------------------------------------------- series de entrada
def preparar(q: pd.Series, eps: float) -> pd.Series:
    """Serie diaria de ENTRADA SIN rellenar: los vacíos ≤ 3 días se interpolan en log(Q + ε) dentro de
    `entradas`, por emisión y solo con los días disponibles hasta el corte de esa serie (t, o t − latencia). Rellenar la
    serie completa y recortar después usaba el día siguiente al corte para cerrar un vacío que lo cruzaba."""
    s = q.asfreq('D').astype(float)
    s.attrs['eps'] = float(eps)
    return s


def _relleno_causal(v: np.ndarray, eps: float, max_dias: int = 3) -> np.ndarray:
    """Interpola en log(v + ε) los vacíos interiores de ≤ max_dias días de un segmento que termina en el corte; un vacío
    abierto al final (sin dato posterior disponible) queda vacío."""
    v = v.astype(float).copy()
    nan = ~np.isfinite(v)
    if not nan.any():
        return v
    z = np.log(np.where(nan, 1.0, v) + eps)
    i, n = 0, len(v)
    while i < n:
        if nan[i]:
            j = i
            while j < n and nan[j]:
                j += 1
            if i > 0 and j < n and j - i <= max_dias:
                z[i:j] = z[i - 1] + (z[j] - z[i - 1]) * np.arange(1, j - i + 1) / (j - i + 1)
                nan[i:j] = False
            i = j
        else:
            i += 1
    out = np.exp(z) - eps
    out[nan] = np.nan
    return np.clip(out, 0, None)


def entradas(fechas: pd.DatetimeIndex, objetivo: pd.Series, contexto: int, pasadas: dict | None = None,
             futuras: list | None = None, cortes: dict | None = None, ocultar: dict | None = None, H: int = 30) -> list[dict]:
    """Una entrada de Chronos-2 por fecha de emisión t.

    objetivo: serie diaria del caudal de la estación (de `preparar`). pasadas: {nombre: serie diaria} de covariables
    (las de `preparar` llevan su ε y se rellenan causalmente; las demás, como la lluvia, se usan tal cual).
    futuras: nombres de `pasadas` cuyos valores de t+1 … t+H se entregan como covariables futuras (escenario idealizado).
    cortes: {'objetivo' o nombre: escalones} → días anteriores al último escalón ≤ t en NaN.
    ocultar: {nombre: d} → los últimos d días (t−d+1 … t) de esa covariable en NaN (latencia del producto)."""
    pasadas, futuras, cortes, ocultar = pasadas or {}, futuras or [], cortes or {}, ocultar or {}
    fechas = pd.DatetimeIndex(fechas)
    # 4 días antes del inicio de la ventana más antigua: el relleno causal de un vacío que toca el inicio usa su dato
    # anterior, y la entrada de una emisión no depende de qué otras emisiones se pidan en el mismo lote
    idx = pd.date_range(fechas.min() - pd.Timedelta(days=contexto + 4), fechas.max() + pd.Timedelta(days=H))
    series = {'objetivo': objetivo.reindex(idx).to_numpy(np.float64)}
    series.update({k: s.reindex(idx).to_numpy(np.float64) for k, s in pasadas.items()})
    eps = {'objetivo': objetivo.attrs.get('eps'), **{k: s.attrs.get('eps') for k, s in pasadas.items()}}
    pos = idx.get_indexer(fechas)
    assert (pos >= contexto).all() and np.isfinite(series['objetivo'][pos]).all(), 'Q(t) debe estar observado'
    # posición del último escalón ≤ t de cada serie (−1 si no hay)
    ult = {}
    for k, esc in cortes.items():
        marca = np.zeros(len(idx), int)
        e = idx.get_indexer(pd.DatetimeIndex(esc))
        marca[e[e >= 0]] = 1
        ult[k] = np.maximum.accumulate(np.where(marca == 1, np.arange(len(idx)), -1))
    out = []
    for p in pos:
        i0 = p - contexto + 1

        def ventana(k):
            corte = p - (ocultar.get(k) or 0)                # último día disponible de la serie k para esta emisión
            if eps.get(k) is not None:
                a = i0 - 4                                    # 4 días previos: un vacío que toca el inicio usa su dato anterior
                seg = _relleno_causal(series[k][a:corte + 1], eps[k])
                v = np.full(p - i0 + 1, np.nan)
                v[:corte - i0 + 1] = seg[i0 - a:]
            else:
                v = series[k][i0:p + 1].copy()
                if ocultar.get(k):
                    v[-ocultar[k]:] = np.nan
            if k in ult and ult[k][p] > i0:
                v[:ult[k][p] - i0] = np.nan
            return v.astype(np.float32)
        d = {'target': ventana('objetivo')}
        if pasadas:
            d['past_covariates'] = {k: ventana(k) for k in pasadas}
        if futuras:
            d['future_covariates'] = {k: series[k][p + 1:p + 1 + H].astype(np.float32) for k in futuras}
            assert all(np.isfinite(v).all() for v in d['future_covariates'].values()), 'covariable futura incompleta'
        out.append(d)
    return out


def pronosticar(pipe, ins: list[dict], H: int = 30, lote: int = 128, etiqueta: str = '') -> np.ndarray:
    """Cuantiles (n, H, 21) en m³/s, ordenados (sin cruces) y recortados a ≥ 0."""
    t0, res = time.time(), []
    for i in range(0, len(ins), lote):
        pr = pipe.predict(ins[i:i + lote], prediction_length=H, batch_size=lote)
        res += [p[0].numpy().T for p in pr]                        # (q, H) → (H, q)
    Q = np.sort(np.stack(res).astype(np.float32), axis=-1).clip(min=0)
    if etiqueta:
        print(f'  {etiqueta}: {len(ins)} pronósticos en {time.time() - t0:,.0f} s', flush=True)
    return Q


def huella_entradas(ins: list[dict]) -> str:
    """SHA-256 de los VALORES que recibe Chronos-2 (contexto, covariables pasadas y futuras de cada emisión, con sus NaN).
    Entra en la clave de la caché: si cambian los datos, el preprocesamiento, los cortes o la latencia, la caché no se
    reutiliza."""
    h = hashlib.sha256()
    for d in ins:
        h.update(np.ascontiguousarray(d['target'], dtype=np.float32).tobytes())
        for grupo in ('past_covariates', 'future_covariates'):
            for k in sorted(d.get(grupo, {})):
                h.update(f'{grupo}:{k}'.encode())
                h.update(np.ascontiguousarray(d[grupo][k], dtype=np.float32).tobytes())
    return h.hexdigest()


def _ruta_cache(clave: dict, f: np.ndarray) -> tuple[Path, str]:
    texto = json.dumps(clave, sort_keys=True, default=str)
    return RUTA_CACHE / (hashlib.sha1(texto.encode() + f.tobytes()).hexdigest()[:16] + '.npz'), texto


def software() -> dict:
    import torch, chronos, transformers
    return {'chronos-forecasting': chronos.__version__, 'torch': torch.__version__, 'transformers': transformers.__version__}


def validar_contenido(z, texto: str, f: np.ndarray, H: int = 30) -> str:
    """Valida un archivo de caché ya abierto. Devuelve '' si es válido o el motivo del rechazo. Exige: exactamente las claves Q, fechas y clave; la misma
    identidad (texto de la clave) y las mismas fechas; Q de forma (emisiones, H, 21) y tipo flotante; todos los valores
    finitos y ≥ 0; y cuantiles no decrecientes en cada emisión y horizonte (lo que garantiza `pronosticar`)."""
    if set(z.files) != {'Q', 'fechas', 'clave'}:
        return f'claves inesperadas {sorted(z.files)}'
    if str(z['clave']) != texto:
        return 'identidad distinta'
    if not np.array_equal(z['fechas'], f):
        return 'fechas distintas'
    Q = z['Q']
    if Q.dtype.kind != 'f' or Q.shape != (len(f), H, len(CUANTILES)):
        return f'forma o tipo inválidos {Q.shape} {Q.dtype}'
    if not np.isfinite(Q).all():
        return 'valores no finitos'
    if (Q < 0).any():
        return 'caudales negativos'
    if (np.diff(Q, axis=-1) < 0).any():
        return 'cuantiles cruzados'
    return ''


def leer_cache(ruta: Path, texto: str, f: np.ndarray, H: int = 30) -> tuple[np.ndarray | None, str]:
    """Lee y valida un archivo de caché. Devuelve (Q, '') si es válido o (None, motivo). Un archivo
    ilegible (truncado, que no es un ZIP, con datos comprimidos corruptos o con objetos de Python) no detiene la
    ejecución: se informa como «ilegible» y la caché se recalcula."""
    import zipfile, zlib
    try:
        with np.load(ruta, allow_pickle=False) as z:
            motivo = validar_contenido(z, texto, f, H)
            return (None, motivo) if motivo else (np.array(z['Q']), '')
    except (OSError, EOFError, ValueError, KeyError, zipfile.BadZipFile, zlib.error) as e:
        return None, f'ilegible ({type(e).__name__}: {str(e)[:80]})'


def registrar_rechazo(ruta: Path, motivo: str) -> None:
    """Deja constancia de cada caché descartada: aviso en la salida y una línea en cache/rechazos.csv (no se sube)."""
    import warnings
    warnings.warn(f'caché de Chronos-2 descartada ({ruta.name}): {motivo}; se recalcula', stacklevel=2)
    reg = ruta.parent / 'rechazos.csv'
    nueva = not reg.exists()
    with open(reg, 'a', encoding='utf-8') as fh:
        if nueva:
            fh.write('fecha,archivo,motivo\n')
        fh.write(f'{datetime.now():%Y-%m-%d %H:%M:%S},{ruta.name},"{motivo.replace(chr(34), chr(39))}"\n')


def reproducir_muestra(pipe, ins: list[dict], Q: np.ndarray, k: int = 8, semilla: int = 42, H: int = 30,
                       tol: float = 2e-3) -> dict:
    """Comprobación independiente de una caché: vuelve a pronosticar k emisiones elegidas al azar (semilla
    fija, siempre incluye la primera y la última) con el mismo modelo y las mismas entradas y compara con lo guardado.
    Diferencia relativa = máx |ΔQ| / máx(|Q| de la muestra, 1). Chronos-2 es determinista (no muestrea); la tolerancia
    solo cubre diferencias de redondeo de float32 entre lotes de distinto tamaño."""
    n = len(ins)
    r = np.random.default_rng(semilla)
    idx = np.unique(np.concatenate([[0, n - 1], r.choice(n, size=min(k, n), replace=False)]))
    Qn = pronosticar(pipe, [ins[i] for i in idx], H)
    ref = Q[idx]
    dif = float(np.abs(Qn - ref).max() / max(float(np.abs(ref).max()), 1.0))
    return dict(emisiones_reproducidas=int(len(idx)), dif_relativa_max=dif, reproduce=bool(dif <= tol))


def con_cache(clave: dict, fechas: pd.DatetimeIndex, calcular, entradas: list[dict]) -> np.ndarray:
    return con_cache_info(clave, fechas, calcular, entradas)[0]


def con_cache_info(clave: dict, fechas: pd.DatetimeIndex, calcular, entradas: list[dict], H: int = 30,
                   reproducir=None, detalle: dict | None = None) -> tuple[np.ndarray, bool]:
    """Guarda los cuantiles en salidas/chronos/cache/<hash>.npz (no se sube a GitHub) y los reutiliza SOLO con identidad
    completa: configuración, identidad del modelo, versiones de inferencia, fechas y huella de los VALORES de
    entrada de cada emisión. Una caché de otra identidad nunca se adopta (cambiar una
    sola emisión cambia la huella y obliga a recalcular).
    Además de la identidad, se valida el CONTENIDO (`validar_contenido`) y, si se pasa `reproducir`
    (función Q → dict de `reproducir_muestra`), se vuelve a pronosticar una muestra de emisiones; una caché que no pasa
    cualquiera de las dos comprobaciones se descarta y se recalcula. `detalle` (dict) recibe el motivo y el resultado."""
    RUTA_CACHE.mkdir(parents=True, exist_ok=True)
    f = pd.DatetimeIndex(fechas).values.astype('datetime64[D]')
    clave = {**clave, 'software': software(), 'huella_entradas': huella_entradas(entradas), 'emisiones': len(f)}
    ruta, texto = _ruta_cache(clave, f)
    det = detalle if detalle is not None else {}
    det.update(archivo=ruta.name, motivo='no existía', reproduccion=None)
    if ruta.exists():
        Q, motivo = leer_cache(ruta, texto, f, H)
        if not motivo and reproducir is not None:
            rep = reproducir(Q)
            det['reproduccion'] = rep
            motivo = '' if rep['reproduce'] else f"no reproduce (dif. relativa {rep['dif_relativa_max']:.2e})"
        if not motivo:
            det['motivo'] = 'reutilizada'
            det['creada'] = datetime.fromtimestamp(ruta.stat().st_mtime).strftime('%Y-%m-%d %H:%M')   # hora local del archivo
            return Q, True
        det['motivo'] = f'descartada: {motivo}'
        registrar_rechazo(ruta, motivo)
    Q = calcular()
    assert Q.shape == (len(f), H, len(CUANTILES)) and np.isfinite(Q).all()
    # Escritura atómica: se escribe en un archivo temporal y se renombra; una interrupción no deja una
    # caché truncada con el nombre definitivo
    tmp = ruta.with_name(ruta.stem + '.tmp.npz')
    np.savez_compressed(tmp, Q=Q, fechas=f, clave=texto)
    os.replace(tmp, ruta)
    det['creada'] = datetime.fromtimestamp(ruta.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
    with np.load(ruta, allow_pickle=False) as z:
        assert validar_contenido(z, texto, f, H) == '', 'la caché recién escrita no es válida'
    return Q, False


# ----------------------------------------------------------------------------- de cuantiles a pronósticos y métricas
def pesos() -> np.ndarray:
    """Pesos de punto medio de las 21 probabilidades (suman 1): aproximan ∫ Q(u) du con la función de cuantiles."""
    u = np.array(CUANTILES)
    b = np.concatenate([[0], (u[1:] + u[:-1]) / 2, [1]])
    return np.diff(b)


def punto(Q: np.ndarray, tipo: str = 'mediana') -> np.ndarray:
    """Pronóstico puntual (n, H): 'mediana' (cuantil 0.5) o 'media' (integral aproximada de la función de cuantiles)."""
    return Q[..., I50] if tipo == 'mediana' else Q @ pesos()


def cuantil(Q: np.ndarray, u: float) -> np.ndarray:
    return Q[..., CUANTILES.index(u)]


def crps(obs: np.ndarray, Q: np.ndarray) -> np.ndarray:
    """CRPS aproximado (m³/s) por par emisión–horizonte: 2 Σ w_i ρ_{u_i}(y − q_i), con los pesos de `pesos()`. Para un
    pronóstico determinista el CRPS es el error absoluto, así que se compara directamente con el MAE de XGBoost."""
    u = np.array(CUANTILES)
    e = obs[..., None] - Q
    return 2 * (np.maximum(u * e, (u - 1) * e) * pesos()).sum(-1)


def cobertura(obs: np.ndarray, Q: np.ndarray, bajo: float, alto: float) -> np.ndarray:
    """Fracción de pares con obs dentro de [q_bajo, q_alto], por horizonte (ideal: alto − bajo)."""
    return ((obs >= cuantil(Q, bajo)) & (obs <= cuantil(Q, alto))).mean(0)
