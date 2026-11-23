# -*- coding: utf-8 -*-
"""Escribe salidas/manifiesto.json: versión del protocolo, software, huellas SHA-256 de los datos de entrada y de
todas las salidas de la ejecución final, y huellas del código que carga y depura los datos. Uso, desde esta carpeta:
    python manifiesto.py      # después del 08 (antes del 09, que lo exige) y otra vez después del 09 y del HTML
Ejecuta las pruebas previas y, si existen las salidas del 06 y del 08, la fase posterior (pruebas_entradas.py --posterior).
Solo describe la ejecución FINAL (salidas/); en modo rápido (CDA_RAPIDO=1) se niega a escribir."""
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import aguas_arriba as A
import comun as C

AQUI = Path(__file__).resolve().parent
# Módulos de cálculo que importan los cuadernos (integrado.py es el protocolo común de 05, 06 y 08).
# Sus SHA-256 van en `codigo_sha256` y el 09 los verifica antes de usar cualquier salida.
MODULOS = ('comun.py', 'aguas_arriba.py', 'lluvia.py', 'chronos2.py', 'entradas.py', 'integrado.py')


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def version(mod):
    try:
        return __import__(mod).__version__
    except Exception:
        return None


def main():
    if C.es_rapido():
        raise SystemExit('modo rápido: el manifiesto solo describe la ejecución final (salidas/)')
    C.asegurar_camels()
    anterior = AQUI / 'salidas' / 'manifiesto.json'
    anterior = json.loads(anterior.read_text(encoding='utf-8')) if anterior.exists() else {}
    entradas = {}
    estaciones = {**{e: d for e, d in C.ESTACIONES.items() if e in ('Racarumi', 'Tamshiyacu')}, **A.ARRIBA}
    for e, d in estaciones.items():
        for p in [C.RUTA_CAMELS / '03_timeseries' / 'by_catchment' / f"{d['gid']}.csv",
                  C.RUTA_CAMELS / '02_attributes' / 'topographic_attributes.csv',
                  C.RAIZ / d['eda'] / 'salidas' / 'tablas' / 'tabla_outliers_eliminados.csv',
                  C.RAIZ / d['eda'] / 'salidas' / 'tablas' / 'tabla_atribucion_balance.csv']:      # reglas de depuración
            if p.exists():
                entradas[p.relative_to(C.RAIZ).as_posix()] = sha(p)
    if C.RUTA_ZIP.exists():
        entradas[C.RUTA_ZIP.name] = sha(C.RUTA_ZIP)
    salidas = {p.relative_to(AQUI).as_posix(): sha(p) for p in sorted((AQUI / 'salidas').rglob('*'))
               if p.is_file() and p.name != 'manifiesto.json' and 'cache' not in p.parts}
    codigo = [AQUI / n for n in ('comun.py', 'aguas_arriba.py', 'lluvia.py', 'chronos2.py', 'entradas.py', 'integrado.py', 'pruebas_avisos.py', 'pruebas_protocolo.py', 'pruebas_entradas.py', 'manifiesto.py',
                                 'README.md')] + \
        [AQUI / 'interactivo' / n for n in ('generar_html.py', 'app.js', 'plantilla.html')]
    # Código que carga, depura y transforma los datos (lo verifica el 09 antes de recargar insumos)
    codigo_sha = {n: sha(AQUI / n) for n in MODULOS}
    for p in sorted(AQUI.glob('*.ipynb')) + [AQUI / 'Modelamiento_Interactivo.html'] + codigo:
        if p.exists():
            salidas[p.relative_to(AQUI).as_posix()] = sha(p)
    try:
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=AQUI, capture_output=True, text=True).stdout.strip()
        cambios = subprocess.run(['git', 'status', '--porcelain', '--', '.'], cwd=AQUI, capture_output=True, text=True).stdout.splitlines()
        cambios = [c for c in cambios if not c.endswith('salidas/manifiesto.json')]
    except Exception:
        commit, cambios = None, None
    pruebas = {}
    for script in ('pruebas_avisos.py', 'pruebas_protocolo.py', 'pruebas_entradas.py'):
        r = subprocess.run([sys.executable, script], cwd=AQUI, capture_output=True, text=True)
        pruebas[script] = dict(correcto=r.returncode == 0, salida=(r.stdout.strip().splitlines() or [''])[-1])
    resumen = {e: json.loads((AQUI / 'salidas' / e.lower() / 'resumen.json').read_text(encoding='utf-8')) for e in ('Racarumi', 'Tamshiyacu')}
    etapas = {}
    for k in ('racarumi', 'tamshiyacu', 'anticipacion', 'aguas_arriba', 'lluvia', 'chronos', 'entradas', 'sintesis'):
        f = AQUI / 'salidas' / k / 'resumen.json'
        if f.exists():
            r = json.loads(f.read_text(encoding='utf-8'))
            etapas[k] = dict(version=r.get('version'), revision=r.get('revision'), rapido=r.get('rapido'), minutos=r.get('minutos'))
    # Software: el de esta generación del manifiesto y el registrado en la ejecución que produjo las salidas de 01, 02 y 05–07
    software_previo = anterior.get('software_ejecucion_v4') or anterior.get('software')
    # Cambios respecto al manifiesto anterior: el manifiesto no se regenera a ciegas; queda registrado qué archivos
    # cambiaron, cuáles son nuevos y cuáles desaparecieron, para revisar su procedencia.
    previo = anterior.get('salidas_sha256', {})
    cambios_previo = dict(revision_anterior=anterior.get('revision'), generado_anterior=anterior.get('generado'),
                          modificados=sorted(k for k in salidas if k in previo and previo[k] != salidas[k]),
                          nuevos=sorted(k for k in salidas if k not in previo), retirados=sorted(k for k in previo if k not in salidas))
    # Cambios respecto al último manifiesto con otro identificador guardado en git. La ruta del manifiesto en git se
    # resuelve desde la raíz real del repositorio; si no hay git o no hay un manifiesto anterior, se registra el estado.
    cambios_revision = dict(estado='no recuperado: git no disponible')
    try:
        prefijo = subprocess.run(['git', 'rev-parse', '--show-prefix'], cwd=AQUI, capture_output=True, text=True, check=True).stdout.strip()
        ruta_git = f'{prefijo}salidas/manifiesto.json'
        hist = subprocess.run(['git', 'log', '--format=%H', '--', 'salidas/manifiesto.json'], cwd=AQUI, capture_output=True, text=True, check=True).stdout.split()
        cambios_revision = dict(estado='no recuperado: ningún manifiesto anterior de otra revisión en git', ruta_git=ruta_git)
        for h in hist:
            txt = subprocess.run(['git', 'show', f'{h}:{ruta_git}'], cwd=AQUI, capture_output=True, text=True).stdout
            if not txt:
                continue
            mv = json.loads(txt)
            if mv.get('revision') != C.REVISION:
                pv = mv.get('salidas_sha256', {})
                cambios_revision = dict(estado='recuperado', ruta_git=ruta_git, revision_anterior=mv.get('revision'), commit_del_manifiesto=h[:7],
                                        modificados=sorted(k for k in salidas if k in pv and pv[k] != salidas[k]),
                                        nuevos=sorted(k for k in salidas if k not in pv), retirados=sorted(k for k in pv if k not in salidas))
                break
    except Exception as ex:
        cambios_revision = dict(estado=f'no recuperado: {type(ex).__name__}')
    if any(not v['correcto'] for v in pruebas.values()):
        raise SystemExit(f'pruebas con fallas: {pruebas}; no se escribe el manifiesto')
    man = dict(protocolo=C.VERSION, revision=C.REVISION, generado=datetime.now().isoformat(timespec='seconds'), commit_base=commit,
               archivos_sin_commit=cambios, cambios_respecto_al_anterior=cambios_previo, cambios_respecto_a_la_revision_anterior=cambios_revision, pruebas=pruebas, codigo_sha256=codigo_sha, etapas=etapas,
               ejecucion={e: dict(rapido=r['rapido'], minutos=r.get('minutos'), modelo_seleccionado=r['mejor_modelo'],
                                  mayor_nse=r.get('mayor_nse'), validacion=r.get('validacion'), muestras=r.get('muestras'),
                                  inventario=r.get('inventario')) for e, r in resumen.items()},
               bloques=dict(fin_entrenamiento=C.FIN_ENTRENAMIENTO, fin_parada_lstm=C.FIN_PARADA, inicio_seleccion=str(C.inicio_seleccion().date()),
                            fin_validacion=C.FIN_VALIDACION, años_calibracion=C.AÑOS_CALIBRACION),
               seleccion=dict(margen_nse=C.MARGEN_NSE, B=C.B_SELECCION, orden_simplicidad=C.ORDEN_SIMPLICIDAD, modelos=C.MODELOS,
                              modelo_auxiliar=C.BASE_AUX),
               software=dict(python=platform.python_version(), **{m: version(m) for m in
                             ['numpy', 'pandas', 'sklearn', 'xgboost', 'torch', 'chronos', 'matplotlib', 'seaborn', 'nbformat']}),
               software_ejecucion_v4=software_previo,
               protocolo_avisos=C.AVISO, semillas=C.SEMILLAS, mallas={k: {kk: [str(x) for x in vv] for kk, vv in v.items()} for k, v in C.MALLAS.items()},
               entradas_sha256=entradas, salidas_sha256=salidas)
    ruta_man = AQUI / 'salidas' / 'manifiesto.json'
    ruta_man.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    # Fase POSTERIOR de las pruebas : necesita las salidas del 06 (§10) y del 08 y el manifiesto recién escrito (T20 reproduce
    # en un proceso limpio pronósticos guardados; T21 revisa el manifiesto). Si falla, el manifiesto se retira.
    if (AQUI / 'salidas' / 'lluvia' / 'predicciones.npz').exists() and all((AQUI / 'salidas' / 'entradas' / f'predicciones_{e}.npz').exists() for e in ('racarumi', 'tamshiyacu')):
        r = subprocess.run([sys.executable, 'pruebas_entradas.py', '--posterior'], cwd=AQUI, capture_output=True, text=True)
        man['pruebas']['pruebas_entradas.py --posterior'] = dict(correcto=r.returncode == 0, salida=(r.stdout.strip().splitlines() or [''])[-1])
        if r.returncode != 0:
            ruta_man.unlink()
            raise SystemExit(f'pruebas posteriores con fallas; manifiesto retirado:\n{r.stdout[-2000:]}')
        ruta_man.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    print('cambios respecto al anterior:', {k: (len(v) if isinstance(v, list) else v) for k, v in cambios_previo.items()})
    for k in ('modificados', 'retirados'):
        for f in cambios_previo[k]:
            print(f'  {k}: {f}')
    print('manifiesto:', len(entradas), 'entradas,', len(salidas), 'salidas | pruebas:', {k: v['salida'] for k, v in pruebas.items()},
          '| archivos sin commit:', len(cambios) if cambios is not None else 'git no disponible')


if __name__ == '__main__':
    main()
