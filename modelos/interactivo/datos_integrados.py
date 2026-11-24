# -*- coding: utf-8 -*-
"""Datos de los cuadernos 05–09 para Modelamiento_Interactivo.html (vistas P3–P6 y síntesis).

No entrena ni selecciona: lee las tablas de modelos/salidas/{aguas_arriba,lluvia,chronos,entradas,sintesis}/,
las predicciones guardadas de Chronos-2 y las interpretaciones escritas en los cuadernos 05–09.
Lo usa generar_html.py; también se puede ejecutar solo para revisar el tamaño:  python datos_integrados.py
"""
import json
import re
from pathlib import Path

import markdown
import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
MOD = AQUI.parent
SAL = MOD / 'salidas'
H_BANDAS = [1, 3, 7, 15]                      # horizontes del explorador de bandas de Chronos-2
LIMPIEZA = [(r' ?\((ver )?(la )?(sección|secciones|figura|figuras) [\d.–, y]+\)', ''), (r'(?<=\w) \(cuaderno 0\d\)', '')]
LISTA = re.compile(r'^ *([-*]|\d+\.) ')
SECCION = re.compile(r'^##\s+(\d+)\.', re.M)


def _normalizar(t):
    out = []
    for l in t.split('\n'):
        sang = len(l) - len(l.lstrip(' '))
        if sang:
            l = ' ' * (sang * 2) + l.lstrip(' ')
        if LISTA.match(l) and not sang and out and out[-1].strip() and not LISTA.match(out[-1]) and not out[-1].startswith(' '):
            out.append('')
        out.append(l)
    return '\n'.join(out)


def md(t, quitar_titulo=True):
    for a, b in LIMPIEZA:
        t = re.sub(a, b, t)
    t = t.strip()
    if quitar_titulo:
        t = re.sub(r'^(---\s*\n)?#+ .*\n', '', t)
    return markdown.markdown(_normalizar(t), extensions=['tables', 'sane_lists'])


class Cuaderno:
    """Celdas markdown de un cuaderno ejecutado, agrupadas por sección (## N.)."""

    def __init__(self, nombre):
        nb = json.loads((MOD / nombre).read_text(encoding='utf-8'))
        self.secciones = {}
        sec = 0
        for c in nb['cells']:
            if c['cell_type'] != 'markdown':
                continue
            s = ''.join(c['source'])
            m = SECCION.search(s)
            if m:
                sec = int(m.group(1))
            self.secciones.setdefault(sec, []).append(s)

    def interpretacion(self, sec):
        """Celdas «Interpretación»/«Lectura» de la sección, sin su rótulo en negrita."""
        cel = [s for s in self.secciones.get(sec, []) if re.match(r'^\*\*(Interpretaci|Lectura|Efecto del m|Horizonte útil)', s.strip())]
        return ''.join(md(re.sub(r'^\*\*Interpretaci[oó]n[^*]*\*\*:?\s*', '', s.strip()), quitar_titulo=False) for s in cel)

    def seccion(self, sec):
        """La celda que abre la sección (p. ej. Conclusiones), sin el título."""
        cel = self.secciones.get(sec, [])
        return md(cel[0]) if cel else ''

    def buscar(self, titulo):
        for sec, cel in self.secciones.items():
            if cel and re.search(r'^##\s+\d+\.\s+' + titulo, cel[0], re.M):
                return sec
        raise KeyError(titulo)


def _num(x, d=4):
    x = np.asarray(x, float)
    return [None if not np.isfinite(v) else round(float(v), d) for v in x]


def _reg(df, d=4):
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].round(d)
    return json.loads(df.to_json(orient='records', force_ascii=False, date_format='iso'))


def _efecto(df):
    """Tablas de G (mismo modelo, prueba) en formato compacto: una fila por entrada × modelo × banda."""
    return [{'est': r['estación'], 'ent': r['entrada'], 'mod': r['modelo'], 'b': r['banda'], 'per': r['periodo'],
             'G': round(float(r['G']), 4), 'lo': round(float(r['IC90 inferior']), 4), 'hi': round(float(r['IC90 superior']), 4),
             'l': {'reduce el error': 1, 'aumenta el error': -1}.get(r['lectura'], 0)} for _, r in df.iterrows()]


def aguas_arriba():
    tb = SAL / 'aguas_arriba' / 'tablas'
    nb = Cuaderno('05_Estaciones_Aguas_Arriba.ipynb')
    return dict(
        efecto=_efecto(pd.read_csv(tb / 'tabla_efecto_entrada_prueba.csv')),
        transito=_reg(pd.read_csv(tb / 'tabla_transito_ccf.csv'), 3),
        fisica=_reg(pd.read_csv(tb / 'tabla_verificacion_fisica.csv'), 1),
        seleccion=_reg(pd.read_csv(tb / 'tabla_configuracion_seleccionada.csv'), 3),
        textos={'datos': nb.interpretacion(2), 'desfase': nb.interpretacion(3), 'validacion': nb.interpretacion(5),
                'prueba': nb.interpretacion(6), 'crecidas': nb.interpretacion(7), 'cruces': nb.interpretacion(8),
                'cirato': nb.interpretacion(10), 'conclusiones': nb.seccion(nb.buscar('Conclusiones'))})


def lluvia():
    tb = SAL / 'lluvia' / 'tablas'
    nb = Cuaderno('06_Lluvia_Escorrentia.ipynb')
    return dict(
        efecto=_efecto(pd.read_csv(tb / 'tabla_efecto_entrada_prueba.csv')),
        ccf=_reg(pd.read_csv(tb / 'tabla_respuesta_ccf.csv'), 3),
        balance=_reg(pd.read_csv(tb / 'tabla_balance.csv'), 3),
        idealizado=_reg(pd.read_csv(tb / 'tabla_idealizado_ganancia_bandas.csv'), 4),
        textos={'balance': nb.interpretacion(3), 'prueba': nb.interpretacion(6), 'crecidas': nb.interpretacion(7),
                'avisos': nb.interpretacion(8), 'idealizado': nb.interpretacion(10),
                'conclusiones': nb.seccion(nb.buscar('Conclusiones'))})


def chronos(series_obs):
    """series_obs: {estación: (t0 'AAAA-MM-DD', lista de caudales diarios)} para alinear las bandas."""
    tb = SAL / 'chronos' / 'tablas'
    nb = Cuaderno('07_Chronos2.ipynb')
    z = np.load(SAL / 'chronos' / 'predicciones.npz', allow_pickle=False)
    bandas = {}
    for e in ['Racarumi', 'Tamshiyacu']:
        f = pd.to_datetime(z[f'{e}|Q|fechas'])
        m = np.asarray(f >= pd.Timestamp('2016-01-01'))
        f = f[m]
        t0 = f.min()
        dec = 0 if e == 'Tamshiyacu' else 2
        d_off = (f - t0).days.to_numpy()
        hs = {}
        for h in H_BANDAS:
            hs[str(h)] = {'d': (d_off + h).tolist(), 'p': _num(z[f'{e}|Q|punto'][m, h - 1], dec),
                          'lo': _num(z[f'{e}|Q|P10'][m, h - 1], dec), 'hi': _num(z[f'{e}|Q|P90'][m, h - 1], dec)}
        bandas[e] = {'t0': str(t0.date()), 'h': hs}
    sint = SAL / 'sintesis' / 'tablas'
    return dict(
        contexto=_reg(pd.read_csv(tb / 'tabla_contexto.csv'), 4),
        probabilistico=_reg(pd.read_csv(tb / 'tabla_probabilistico.csv'), 4),
        condiciones=_reg(pd.read_csv(sint / 'tabla_chronos_probabilistico_condiciones.csv'), 4),
        frente=_reg(pd.read_csv(sint / 'tabla_chronos_frente_a_seleccionada.csv'), 4),
        idealizado=_reg(pd.read_csv(tb / 'tabla_idealizado.csv'), 4),
        bandas=bandas, H=H_BANDAS,
        textos={'contexto': nb.interpretacion(3), 'cache': nb.interpretacion(4), 'probabilistico': nb.interpretacion(5),
                'sensibilidad': nb.interpretacion(6), 'idealizado': nb.interpretacion(7),
                'conclusiones': nb.seccion(nb.buscar('Conclusiones'))})


def integrado():
    tb = SAL / 'entradas' / 'tablas'
    nb = Cuaderno('08_Entradas_y_Modelos.ipynb')
    m = pd.read_csv(tb / 'tabla_maestra.csv')
    v = pd.read_csv(tb / 'tabla_validacion.csv')
    hp = {f"{r['estación']}|{r['conjunto']}|{r['modelo']}": r['hiperparámetros'] for _, r in v.iterrows()}
    cand = []
    for _, r in m.iterrows():
        cand.append({'est': r['estación'], 'per': r['periodo de prueba'], 'c': r['conjunto'], 'mod': r['modelo'],
                     'disp': r['escenario de disponibilidad'], 'n': int(r['emisiones']),
                     'val': round(float(r['NSE medio selección']), 4), 'pru': round(float(r['NSE medio']), 4),
                     'h': _num([r['NSE h=1'], r['NSE h=3'], r['NSE h=7'], r['NSE h=15'], r['NSE h=30']], 4),
                     'H': None if pd.isna(r['H cota 95 % (d)']) else int(r['H cota 95 % (d)']),
                     'Hr': r['H p05–p95 de las réplicas (d)'] if isinstance(r['H p05–p95 de las réplicas (d)'], str) else '',
                     'sel': r['seleccionada para la magnitud'] if isinstance(r['seleccionada para la magnitud'], str) else '',
                     'hp': hp.get(f"{r['estación']}|{r['conjunto']}|{r['modelo']}", '')})
    comb = pd.concat([pd.read_csv(tb / 'tabla_tamshiyacu_combinaciones_prueba.csv'),
                      pd.read_csv(tb / 'tabla_tamshiyacu_requena_combinaciones_prueba.csv')])
    ver = pd.read_csv(tb / 'tabla_registro_verificaciones.csv')
    return dict(
        candidatos=cand, combinaciones=_efecto(comb),
        final=_reg(pd.read_csv(tb / 'tabla_final.csv'), 3),
        sel_mag=_reg(pd.read_csv(SAL / 'sintesis' / 'tablas' / 'tabla_seleccion_final_magnitud.csv'), 4),
        sel_val=_reg(pd.read_csv(tb / 'tabla_seleccion_magnitud_validacion.csv'), 4),
        sel_avisos=_reg(pd.read_csv(tb / 'tabla_seleccion_avisos.csv'), 3),
        verificaciones={'total': int(len(ver)), 'correctas': int((ver['resultado'] == 'correcto').sum()),
                        'grupos': _reg(ver.groupby('grupo').size().rename('n').reset_index())},
        textos={'validacion': nb.interpretacion(4), 'prueba': nb.interpretacion(5), 'avisos': nb.interpretacion(6),
                'final': nb.interpretacion(7), 'fuera': nb.interpretacion(8),
                'conclusiones': nb.seccion(nb.buscar('Conclusiones'))})


def _cuenta(s):
    """'6+ / 0≈ / 0− (mediana +38 %)' → [6, 0, 0, 38]."""
    m = re.match(r'\s*(\d+)\+ / (\d+)≈ / (\d+)− \(mediana ([+\-−]?\d+(?:\.\d+)?) %\)', str(s))
    if not m:
        return None
    return [int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4).replace('−', '-'))]


def sintesis():
    tb = SAL / 'sintesis' / 'tablas'
    nb = Cuaderno('09_Sintesis_Integral.ipynb')
    ef = pd.read_csv(tb / 'tabla_efecto_fuentes_seis_modelos.csv')
    bandas = [c for c in ef.columns if c.endswith('días')]
    fuentes = [{'origen': r['origen'], 'est': r['estación'], 'ent': r['entrada'], 'v': [_cuenta(r[b]) for b in bandas]} for _, r in ef.iterrows()]
    return dict(
        fuentes=fuentes, bandas=bandas,
        magnitud=_reg(pd.read_csv(tb / 'tabla_magnitud_horizonte.csv'), 4),
        avisos=_reg(pd.read_csv(tb / 'tabla_avisos_racarumi.csv'), 3),
        textos={'compatibilidad': nb.interpretacion(1), 'magnitud': nb.interpretacion(2), 'avisos': nb.interpretacion(3),
                'muestra': nb.interpretacion(4), 'chronos_bandas': nb.interpretacion(5),
                'respuestas': nb.seccion(nb.buscar('Respuestas')), 'limites': nb.seccion(nb.buscar('Límites'))})


EDA = MOD.parent / 'eda_interactivo'
ROL = {'Racarumi': 'objetivo', 'Tamshiyacu': 'objetivo', 'San Regis': 'arriba', 'Requena': 'arriba', 'Cirato': 'arriba'}


def mapa():
    """Capas del mapa del EDA (subcuencas de CAMELS-PE y cuencas hasta cada estación) y ubicación de las estaciones."""
    local = AQUI / 'apoyo' / 'mapa.json'
    if local.exists():
        return json.loads(local.read_text(encoding='utf-8'))
    capas = json.loads((EDA / 'generador' / 'apoyo' / 'capas.json').read_text(encoding='utf-8'))['capas']
    h = (EDA / 'EDA_Interactivo_Cuencas.html').read_text(encoding='utf-8')
    i = h.index('=', h.index('window.EDA')) + 1
    eda, _ = json.JSONDecoder().raw_decode(h[i:].lstrip())
    campos = ['id', 'cuenca', 'vertiente', 'area', 'lat', 'lon', 'elev', 'inicio', 'fin']
    est = {n: {**{k: m[k] for k in campos}, 'rol': ROL.get(n, 'eda')} for n, m in eda['meta'].items()}
    return {'cuencas': capas['cuencas'], 'camels': capas['camels'], 'estaciones': est}


def avisos_emitidos():
    """Avisos emitidos en la prueba por el sistema del cuaderno 04 (día de emisión, día anunciado y si acertó)."""
    a = pd.read_csv(SAL / 'anticipacion' / 'tablas' / 'tabla_avisos.csv')
    return [{'est': r['estación'], 'mod': r['modelo'], 'e': str(r['emision'])[:10], 't': str(r['tau'])[:10], 'h': int(r['h_aviso']),
             'ok': r['estado'] == 'correcto'} for _, r in a.iterrows()]


def todo(series_obs=None):
    return {'arriba': aguas_arriba(), 'lluvia': lluvia(), 'chronos': chronos(series_obs or {}),
            'integrado': integrado(), 'sintesis': sintesis(), 'mapa': mapa(), 'avisos': avisos_emitidos()}


if __name__ == '__main__':
    d = todo()
    for k, v in d.items():
        print(k, round(len(json.dumps(v, ensure_ascii=False)) / 1e6, 3), 'MB')
        for t, h in v.get('textos', {}).items():
            print('   ', t, len(h))
