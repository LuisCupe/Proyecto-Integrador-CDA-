# -*- coding: utf-8 -*-
"""Genera modelos/Modelamiento_Interactivo.html (v2) a partir de las salidas de los cuadernos 01–09.

No entrena nada: lee modelos/salidas/, las interpretaciones escritas en los cuadernos ejecutados (celdas con
metadata 'clave' en 01–04; celdas «Interpretación» y «Conclusiones» en 05–09, vía datos_integrados.py),
REVISION_METODOLOGICA.md y el caudal observado de CAMELS-PE (vía comun.py).

Uso, desde esta carpeta:
    python generar_html.py                      # completo (requiere CAMELS-PE en la raíz del repositorio)
    python generar_html.py --base-html ARCHIVO  # reutiliza los datos de 01–04 ya incrustados en un HTML generado
                                                # antes (no necesita CAMELS-PE); 05–09 se leen de salidas/
Plotly 2.35.2 y Leaflet 1.9.4 se incrustan desde vendor/ (o desde eda_interactivo/generador/vendor/):
el HTML abre con doble clic y sin internet.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import markdown
import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
MOD = AQUI.parent
RAIZ = MOD.parent
sys.path.insert(0, str(MOD))
sys.path.insert(0, str(AQUI))
import comun as C  # noqa: E402
import datos_integrados as DI  # noqa: E402
PLOTLY_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js'
PLOTLY_LOCAL = [AQUI / 'vendor' / 'plotly-2.35.2.min.js', RAIZ / 'eda_interactivo' / 'generador' / 'vendor' / 'plotly-2.35.2.min.js']
LEAFLET_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js'
VENDOR_EDA = RAIZ / 'eda_interactivo' / 'generador' / 'vendor'

SAL = MOD / C.ruta_salidas()                     # salidas_rapido/ con CDA_RAPIDO=1
EST = ['Racarumi', 'Tamshiyacu']
H_CLAVE = [1, 2, 3, 5, 7, 10, 15, 20, 30]
CUADERNO = {'Racarumi': '01_Modelos_Racarumi.ipynb', 'Tamshiyacu': '02_Modelos_Tamshiyacu.ipynb'}
LIMPIEZA = [(r' ?\((ver )?(la )?(sección|secciones|figura|figuras) [\d.–, y]+\)', ''), (r'(?<=\w) \(cuaderno 0\d\)', '')]
LISTA = re.compile(r'^ *([-*]|\d+\.) ')


def num(x, d=4):
    x = np.asarray(x, float)
    return [None if not np.isfinite(v) else round(float(v), d) for v in x]


def normalizar(t):
    """Adapta el markdown de Jupyter a Python-Markdown: sangría de 2 → 4 espacios y línea en blanco antes de cada lista."""
    out = []
    for l in t.split('\n'):
        sang = len(l) - len(l.lstrip(' '))
        if sang:
            l = ' ' * (sang * 2) + l.lstrip(' ')
        if LISTA.match(l) and not sang and out and out[-1].strip() and not LISTA.match(out[-1]) and not out[-1].startswith(' '):
            out.append('')
        out.append(l)
    return '\n'.join(out)


def md_html(t, quitar_titulo=True):
    for a, b in LIMPIEZA:
        t = re.sub(a, b, t)
    t = re.sub(r'^\*\*Interpretaci[oó]n[^*]*\*\*\s*', '', t.strip())
    if quitar_titulo:
        t = re.sub(r'^(---\s*\n)?#+ .*\n', '', t)
    return markdown.markdown(normalizar(t), extensions=['tables', 'sane_lists'])


def textos(nb_path):
    nb = json.loads(nb_path.read_text(encoding='utf-8'))
    return {c['metadata']['clave']: md_html(''.join(c['source'])) for c in nb['cells'] if c.get('metadata', {}).get('clave')}


def registros(df):
    return json.loads(df.to_json(orient='records', force_ascii=False, date_format='iso'))


def estacion(e):
    base = SAL / e.lower()
    tb = base / 'tablas'
    leer = lambda n, **kw: pd.read_csv(tb / f'{n}.csv', **kw)
    res = json.loads((base / 'resumen.json').read_text(encoding='utf-8'))
    C.verificar_resumen(base / 'resumen.json')       # mismo protocolo y mismo modo de ejecución
    met, met_c = leer('tabla_metricas_prueba'), leer('tabla_metricas_prueba_comun')
    ref, ref_c = leer('tabla_referencias_prueba', index_col=0), leer('tabla_referencias_prueba_comun', index_col=0)
    hu, hu_c = leer('tabla_horizonte_util'), leer('tabla_horizonte_util_comun')
    crec = leer('tabla_crecidas_prueba')
    mem = leer('tabla_memoria')
    imp = leer('tabla_importancia', index_col=0)
    div = leer('tabla_division', index_col=0)
    sens_p = tb / 'tabla_sensibilidad_registros.csv'
    sens = pd.read_csv(sens_p) if sens_p.stat().st_size > 5 else pd.DataFrame()
    sres_p = tb / 'tabla_sensibilidad_registros_resumen.csv'
    sres = pd.read_csv(sres_p).rename(columns={'Unnamed: 0': 'indicador'}) if sres_p.exists() and sres_p.stat().st_size > 5 else pd.DataFrame()
    modelos = list(hu['modelo'])
    m_out, mc_out = {}, {}
    for n in modelos:
        t = met[met['modelo'] == n].set_index('h').sort_index()
        m_out[n] = {k: num(t[k]) for k in ['NSE', 'KGE', 'MAE', 'RMSE', 'PBIAS', 'hab_pers', 'hab_clim']}
        ic = pd.read_csv(tb / f"ic_habilidad_{C.SLUG[n]}.csv", index_col=0)
        m_out[n]['ic'] = {k: num(ic[k]) for k in ['pers_inf', 'pers_sup', 'clim_inf', 'clim_sup']}
        tc = met_c[met_c['modelo'] == n].set_index('h').sort_index()
        mc_out[n] = {k: num(tc[k]) for k in ['NSE', 'MAE', 'hab_pers', 'hab_clim']}
    c_out = {}
    for n, g in crec.groupby('modelo'):
        g = g.set_index('h').sort_index()
        c_out[n] = {k: num(g[k]) for k in ['error_rel_altos', 'error_rel_ordinarios', 'MAE_altos', 'MAE_ordinarios', 'PBIAS_altos', 'POD', 'FAR', 'CSI', 'n_altos']}
    z = np.load(base / 'predicciones.npz', allow_pickle=False)
    nombres = [str(x) for x in z['modelos']]
    f_p = pd.to_datetime(z['fechas_pru'], unit='D')
    dec = 0 if e == 'Tamshiyacu' else 2
    t0 = f_p.min()
    d_off = ((f_p - t0).days).to_numpy()
    p_out = {}
    for h in H_CLAVE:
        mods = {n: num(z[f'pru_{i}'][:, h - 1], dec) for i, n in enumerate(nombres)}
        mods['Persistencia'] = num(z['pers_pru'][:, h - 1], dec)
        mods['Climatología'] = num(z['clim_pru'][:, h - 1], dec)
        p_out[str(h)] = {'d': (d_off + h).tolist(), 'mod': mods}
    q, info = C.cargar_serie(e)
    qs = q.loc[pd.Timestamp(C.FIN_VALIDACION) - pd.Timedelta(days=90):]
    ev = C.eventos(q, res['P95'], '2016-01-01')
    return dict(
        nombre=e, cuenca=res['cuenca'], vertiente=res['vertiente'], periodo=res['periodo'], P95=res['P95'], eps=res['eps'],
        mejor=res['mejor_modelo'], muestras=res['muestras'], escalones=res['escalones'], excluidas=res['excluidas_escalon'],
        area=info['area'], parametros=res['mejores_parametros'], nse_val=res['nse_val'], combinado=res['combinado'], modelos=modelos,
        mayor_nse=res['mayor_nse'], validacion=res['validacion'], seleccion=registros(leer('tabla_seleccion').round(4)),
        fechas_comunes=res['fechas_comunes'], inventario=res['inventario'],
        ref={'pers': num(ref['NSE persistencia']), 'clim': num(ref['NSE climatología'])},
        ref_c={'pers': num(ref_c['NSE persistencia']), 'clim': num(ref_c['NSE climatología'])},
        met=m_out, met_c=mc_out, crec=c_out, hu=registros(hu), hu_c=registros(hu_c),
        bloques=registros(leer('tabla_sensibilidad_bloque')),
        memoria={str(L): {'hab_pers': num(g.sort_values('h')['hab_pers']), 'NSE': num(g.sort_values('h')['NSE'])} for L, g in mem.groupby('L')},
        imp={'grupos': list(imp.index), 'h': list(imp.columns), 'v': [num(r * 100, 1) for r in imp.to_numpy()]},
        eventos=[{'inicio': str(r.inicio.date()), 'fin': str(r.fin.date()), 'dias': int(r.dias_sobre), 'pico': float(r.pico),
                  'fecha': str(r.fecha_pico.date())} for r in ev.sort_values('pico', ascending=False).itertuples()],
        eventos_pron=registros(leer('tabla_eventos_pronostico').round(2)), eventos_res=registros(leer('tabla_eventos_resumen').rename(columns={'Unnamed: 0': 'h'}).round(2)),
        estabilidad=registros(leer('tabla_estabilidad_temporal').drop(columns=['parámetros elegidos']).round(4)),
        sensibilidad=registros(sens.round(4)) if len(sens) else [], sens_resumen=registros(sres.round(3)) if len(sres) else [],
        semillas=registros(leer('tabla_semillas').round(4)), presupuesto=registros(leer('tabla_presupuesto_busqueda').round(3)),
        division=[{'bloque': i, **{k: (v if isinstance(v, str) else float(v)) for k, v in r.items()}} for i, r in div.iterrows()],
        pred={'t0': str(t0.date()), 'h': p_out}, serie={'t0': str(qs.index.min().date()), 'q': num(qs, dec)},
        textos=textos(MOD / CUADERNO[e]))


def anticipacion():
    tb = SAL / 'anticipacion' / 'tablas'
    pa = pd.read_csv(tb / 'tabla_anticipacion_por_A.csv')
    out = {}
    for (e, n, rg), g in pa.groupby(['estación', 'modelo', 'regla']):
        g = g.sort_values('A')
        out.setdefault(e, {}).setdefault(n, {})[rg] = {k: num(g[k], 3) for k in ['POD', 'CSI', 'evaluables', 'aciertos', 'aciertos_tardios', 'falsas_alarmas']}
    ant = pd.read_csv(tb / 'tabla_anticipacion_prueba.csv')
    pe = pd.read_csv(tb / 'tabla_anticipacion_por_evento.csv')
    return dict(por_A=out, resumen=registros(ant.round(3)), por_evento=registros(pe.round(2)),
                cruces=registros(pd.read_csv(tb / 'tabla_cruces.csv')), sintesis=registros(pd.read_csv(tb / 'tabla_sintesis.csv').round(3)),
                comun=registros(pd.read_csv(tb / 'tabla_anticipacion_comun.csv').round(3)),
                sensibilidad=registros(pd.read_csv(tb / 'tabla_sensibilidad_avisos.csv').round(3)),
                textos=textos(MOD / '04_Anticipacion_Crecidas.ipynb'))


def base_completa():
    datos = {'estaciones': {e: estacion(e) for e in EST}, 'H_CLAVE': H_CLAVE, 'MODELOS': C.MODELOS, 'COLORES': C.COLOR,
             'AVISO': C.AVISO, 'SEMILLAS': C.SEMILLAS}
    tc = SAL / 'comparacion' / 'tablas'
    datos['comparativa'] = registros(pd.read_csv(tc / 'tabla_comparativa_modelos.csv').round(4))
    datos['pares'] = registros(pd.read_csv(tc / 'tabla_pares_modelos.csv').round(4))
    datos['h3_pareado'] = {k: (float(v) if np.isfinite(v) else None) for k, v in pd.read_csv(tc / 'tabla_h3_pareado.csv', index_col=0).iloc[:, 0].round(4).items()}
    datos['textos_comp'] = textos(MOD / '03_Comparacion_y_Seleccion.ipynb')
    datos['anticipacion'] = anticipacion()
    return datos


def base_desde_html(ruta):
    """Datos de 01–04 ya incrustados en un Modelamiento_Interactivo.html anterior (v1 o v2)."""
    h = Path(ruta).read_text(encoding='utf-8')
    i = h.index('window.MOD = ') + len('window.MOD = ')
    datos = json.loads(h[i:h.index(';</script>', i)].replace('<\\/', '</'))
    datos.pop('int', None)
    return datos


def incrustar_leaflet(html):
    """Leaflet 1.9.4 (JS y CSS sin imágenes) desde vendor/ (o la carpeta vendor del EDA); si falta, lo carga desde cdnjs."""
    base = AQUI / 'vendor' if (AQUI / 'vendor' / 'leaflet-1.9.4.min.js').exists() else VENDOR_EDA
    js, cs = base / 'leaflet-1.9.4.min.js', base / 'leaflet-1.9.4.css'
    if js.exists() and cs.exists():
        css = '\n'.join(l for l in cs.read_text(encoding='utf-8').splitlines() if 'url(' not in l)
        html = html.replace('/*{{CSS_LEAFLET}}*/', css)
        return html.replace(f'<script src="{LEAFLET_CDN}"></script>', '<script>' + js.read_text(encoding='utf-8').replace('</script', '<\\/script') + '</script>')
    print('Aviso: no se encontró Leaflet en vendor/; el mapa lo cargará desde internet.')
    return html.replace('/*{{CSS_LEAFLET}}*/', '').replace('<style id="css-leaflet">', '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"><style id="css-leaflet">')


def incrustar_plotly(html):
    for p in PLOTLY_LOCAL:
        if p.exists():
            js = p.read_text(encoding='utf-8').replace('</script', '<\\/script')
            return html.replace(f'<script src="{PLOTLY_CDN}"></script>', '<script>' + js + '</script>'), True
    print('Aviso: no se encontró vendor/plotly-2.35.2.min.js; el HTML cargará Plotly desde internet.')
    return html, False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--base-html', help='HTML generado antes del que se reutilizan los datos de 01–04 (sin CAMELS-PE)')
    ap.add_argument('--salida', default=str(MOD / 'Modelamiento_Interactivo.html'))
    a = ap.parse_args()
    datos = base_desde_html(a.base_html) if a.base_html else base_completa()
    datos['int'] = DI.todo()
    datos['revision'] = md_html((MOD / 'REVISION_METODOLOGICA.md').read_text(encoding='utf-8'), quitar_titulo=True)
    js = json.dumps(datos, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('</', '<\\/')
    html = ((AQUI / 'plantilla.html').read_text(encoding='utf-8')
            .replace('/*{{APP}}*/', (AQUI / 'textos.js').read_text(encoding='utf-8') + '\n' + (AQUI / 'app.js').read_text(encoding='utf-8'))
            .replace('"{{DATOS}}"', js))
    html = incrustar_leaflet(html)
    html, local = incrustar_plotly(html)
    destino = Path(a.salida)
    destino.write_text(html, encoding='utf-8')
    print('OK', destino.name, round(destino.stat().st_size / 1e6, 2), 'MB', '(Plotly incrustado)' if local else '(Plotly por CDN)')


if __name__ == '__main__':
    main()
