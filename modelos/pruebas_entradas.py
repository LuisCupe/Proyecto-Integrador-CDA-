# -*- coding: utf-8 -*-
"""Controles automáticos de las entradas, la caché, Chronos-2 y el manifiesto (T01–T29).
Uso, desde esta carpeta:  python pruebas_entradas.py   (termina con error si alguna comprobación falla).

Comprueban propiedades y fallos reales con casos sintéticos y con los datos del proyecto: contratos de fechas, rezagos
y acumulados de lluvia calculados a mano, causalidad de todas las fichas de entrada, recurrencias del IPA, fronteras de
los bloques, escaladores, muestras pareadas, horizonte útil, bootstrap, anticipación, identidad de la caché, manifiesto
y separación de salidas rápidas. Los casos de avisos (T12, T14, T15) están en pruebas_avisos.py y los de bloques y
muestra extendida (T05, T08) también en pruebas_protocolo.py; aquí se repiten solo los que dependen de entradas.py."""
import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import sys

import comun as C
import entradas as EN
import lluvia as LL

# Fases: «previa» (por omisión) no necesita salidas de ningún cuaderno; «posterior» (--posterior) además
# comprueba contra las salidas del 06 (§10) y del 08 y el manifiesto, y debe ejecutarse después de producirlos.
POSTERIOR = '--posterior' in sys.argv

casos = []


def caso(nombre, ok):
    casos.append((nombre, bool(ok)))


def lanza(f, *a, **k):
    try:
        f(*a, **k)
    except (ValueError, FileNotFoundError, AssertionError):
        return True
    return False


H = len(C.HORIZONTES)
L = C.L_VENTANA
dias = pd.date_range('2000-01-01', periods=400)
p_sint = pd.Series(np.arange(1, 401, dtype=float), index=dias)          # P distinta cada día (mm)

# T01. Fechas duplicadas, desordenadas o con un día ausente: rechazo explícito; un día ausente no se trata como el anterior.
dup = pd.concat([p_sint.iloc[:5], p_sint.iloc[4:6]])
desord = p_sint.iloc[[1, 0, 2, 3]]
hueco = p_sint.drop(dias[100])
caso('T01 duplicadas / desordenadas / día ausente se rechazan',
     lanza(EN.comprobar_diaria, dup) and lanza(EN.comprobar_diaria, desord) and lanza(EN.comprobar_diaria, hueco)
     and lanza(EN.indices_lluvia, hueco) and not lanza(EN.comprobar_diaria, p_sint))
f_e = dias[[95, 99, 100, 130, 200]]
X_h, _, ok_h = LL.matriz_lluvia(hueco, f_e)
caso('T01 un día ausente invalida solo las emisiones cuya ventana lo contiene (no se desplaza la serie)',
     list(ok_h) == [True, True, False, False, True])

# T02. Rezagos y acumulados contra un cálculo manual, con latencia 0 y 1, en las tres representaciones.
t = dias[150]
for lat in (0, 1):
    X, nom, ok = LL.matriz_lluvia(p_sint, pd.DatetimeIndex([t]), desfase=lat)
    v = lambda k: p_sint[t - pd.Timedelta(days=k + lat)]
    manual = [v(k) for k in range(7)] + [sum(v(k) for k in range(7, 15)), sum(v(k) for k in range(15, 30)), sum(v(k) for k in range(30, 90))]
    Xd, nomd, _ = EN.lluvia_diaria(p_sint, pd.DatetimeIndex([t]), L, lat)
    manual_d = [v(k) for k in range(L)] + [sum(v(k) for k in range(L, 90))]
    caso(f'T02 lluvia tabular, latencia {lat}: 7 días + 3 sumas = cálculo manual', np.allclose(np.expm1(X[0]), manual) and ok[0])
    caso(f'T02 lluvia diaria (Pd), latencia {lat}: 30 días + suma = cálculo manual', np.allclose(np.expm1(Xd[0]), manual_d) and len(nomd) == L + 1)

# Datos reales: fuentes de Tamshiyacu (lluvia, índices y San Regis) para causalidad y canales.
F = EN.Fuentes.cargar('Tamshiyacu', ('San Regis',))
q = F.q
m = C.construir_muestras(q, L=L, H=H, esc=F.esc, eps=F.eps)
sel = np.where((m.fechas > pd.Timestamp('2009-01-01')) & (m.fechas < pd.Timestamp('2012-01-01')))[0][::40]
ms = EN.A.subconjunto(m, sel)
t0 = ms.fechas[len(sel) // 2]
E1 = EN.canales_lstm(ms, F, 'Q+P+IA', 0)
caso('T02 canal diario de lluvia de la LSTM = log(1 + P) del día', np.allclose(E1[3, :, 0], np.log1p(F.P.reindex(pd.date_range(ms.fechas[3] - pd.Timedelta(days=L - 1), ms.fechas[3])).to_numpy())))
E2 = EN.canales_lstm(ms, F, 'Q+P+IA', 1)
caso('T02 latencia 1 desplaza lluvia, suma antigua e índices de la LSTM un día', np.allclose(E2[3, :, 0], np.log1p(F.P.reindex(pd.date_range(ms.fechas[3] - pd.Timedelta(days=L), ms.fechas[3] - pd.Timedelta(days=1))).to_numpy()))
     and np.allclose(E2[3, -1, 2:5], np.log1p(F.IA.loc[ms.fechas[3] - pd.Timedelta(days=1)].to_numpy())))
X1 = EN.matriz(ms, F, 'Q+P+IA', 1)[0]
caso('T02 latencia 1: los índices tabulares son los de t − 1 (calculados solo con lluvia hasta t − 1)',
     np.allclose(X1[3, -3:], np.log1p(F.IA.loc[ms.fechas[3] - pd.Timedelta(days=1)].to_numpy())))

# T03. Cambiar TODOS los datos posteriores a una emisión no cambia sus características (fijando las emisiones examinadas).
F2 = EN.Fuentes(F.nombre, F.q.copy(), F.eps, F.esc, F.P.copy(), None, {k: dict(v) for k, v in F.arriba.items()})
F2.P[F2.P.index > t0] = F2.P[F2.P.index > t0] * 5 + 40
F2.IA = EN.indices_lluvia(F2.P)
F2.arriba['San Regis']['q'] = F.arriba['San Regis']['q'].copy()
F2.arriba['San Regis']['q'][F2.arriba['San Regis']['q'].index > t0] *= 3
antes = ms.fechas <= t0
for conj in ['Q+P+IA', 'Q+Pd', 'Q+A:San Regis', 'Q+P+A:San Regis']:
    for lat in (0, 1):
        Xa, _, _, oka = EN.matriz(ms, F, conj, lat)
        Xb, _, _, okb = EN.matriz(ms, F2, conj, lat)
        Ea, Eb = EN.canales_lstm(ms, F, conj, lat), EN.canales_lstm(ms, F2, conj, lat)
        caso(f'T03 {conj} latencia {lat}: sin información posterior a la emisión',
             np.allclose(Xa[antes], Xb[antes], equal_nan=True) and np.allclose(Ea[antes], Eb[antes], equal_nan=True)
             and np.array_equal(oka[antes], okb[antes]) and not np.allclose(Xa[~antes], Xb[~antes], equal_nan=True))

# T04. IPA: lluvia constante, impulso aislado y tramo seco frente a la recurrencia conocida; arranque documentado.
c = pd.Series(np.full(300, 5.0), index=dias[:300])
ia = EN.indices_lluvia(c)
n = np.arange(300)
ok4 = all(np.allclose(ia[f'IPA k={k:.2f}'], 5 * (1 - k ** (n + 1)) / (1 - k)) for k in EN.K_IPA)
imp = pd.Series(np.zeros(60), index=dias[:60]); imp.iloc[10] = 20.0
ii = EN.indices_lluvia(imp)
ok4 &= all(np.allclose(ii[f'IPA k={k:.2f}'].iloc[10:], 20 * k ** np.arange(50)) and (ii[f'IPA k={k:.2f}'].iloc[:10] == 0).all() for k in EN.K_IPA)
sec = ii['días secos consecutivos'].to_numpy()
ok4 &= list(sec[:12]) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0, 1] and sec[-1] == 49
est = EN.indices_lluvia(c, inicio='estacionario')
ok4 &= all(np.allclose(est[f'IPA k={k:.2f}'], 5 / (1 - k)) for k in EN.K_IPA)
caso('T04 IPA y días secos: constante, impulso, tramo seco y arranque estacionario', ok4)
caso('T04 lluvia con vacío o negativa se rechaza', lanza(EN.indices_lluvia, imp.where(imp.index != dias[5])) and lanza(EN.indices_lluvia, imp - 1))

# T05. Fronteras de partición en el experimento del 08 (incluida la parada de la LSTM).
for e in ['Racarumi', 'Tamshiyacu']:
    Fe, me, pe, VCe, mxe, De = EN.experimento(e)
    d = De[('Q', 0)]
    fe = me.fechas
    ie_in, ie_par = EN._pasos_lstm(d)
    fin = lambda idx: (fe[idx] + pd.Timedelta(days=H)).max()
    caso(f'T05 {e}: ningún objetivo de ajuste, parada o calibración invade el bloque siguiente',
         fin(pe['ent']) <= pd.Timestamp(C.FIN_ENTRENAMIENTO) and fin(ie_in) <= pd.Timestamp(C.FIN_PARADA)
         and fe[ie_par].min() > pd.Timestamp(C.FIN_PARADA) and fe[pe['val']].min() > pd.Timestamp(C.FIN_ENTRENAMIENTO)
         and fin(pe['val']) <= pd.Timestamp(C.FIN_VALIDACION) and fe[d.ip].min() > pd.Timestamp(C.FIN_VALIDACION)
         and (fe[pe['val']][VCe.cal] + pd.Timedelta(days=H)).max() < fe[pe['val']][VCe.sel].min())
    # T07. Comparaciones sobre la misma muestra: todos los conjuntos comparten filas; Requena es un subconjunto explícito.
    rq = [k for k in De if 'Requena' in k[0]]
    ok7 = all(np.array_equal(De[k].ip, pe['pru']) for k in De if k not in rq)
    for k in rq:
        comunes = np.intersect1d(De[k].ip, De[('Q', 0)].ip)
        ok7 &= np.array_equal(comunes, De[k].ip) and len(De[k].ip) < len(pe['pru']) and me.fechas[De[k].ip].max() <= pd.Timestamp('2020-03-31')
    caso(f'T07 {e}: mismas filas en todos los conjuntos; Requena, subconjunto de fechas comunes explícito', ok7)
    if e == 'Racarumi':
        DR = De

# T06. Escaladores y estadísticos solo con el bloque de ajuste: valores extremos en validación y prueba no los cambian.
d = DR[('Q+P+IA', 0)]
lp = EN.LSTMEntradas(d.m, d.E, *EN._pasos_lstm(d), oculto=8, dropout=0.0)
E_mod = d.E.copy(); E_mod[np.concatenate([d.p['val'], d.ip])] *= 1e3
lp2 = EN.LSTMEntradas(d.m, E_mod, *EN._pasos_lstm(d), oculto=8, dropout=0.0)
a, b = lp._est(d.p['ent']), lp2._est(d.p['ent'])
caso('T06 estandarización de la LSTM solo con el bloque de ajuste', all(np.allclose(x, y) for x, y in zip(a, b)))
# Por el camino real (entradas._ajuste: búsqueda en la selección + ajuste final), separando dos controles:
# (a) AJUSTE: con la misma validación (VC sin cambios), alterar entradas de prueba y objetivos de validación y prueba no
#     cambia los pronósticos de validación (los modelos de validación se ajustan solo con el entrenamiento);
# (b) SELECCIÓN: alterar SOLO la prueba (entradas, objetivos y caudales observados) y reconstruir con ella la muestra y la
#     validación causal no cambia ni los hiperparámetros elegidos ni los pronósticos de validación.
# En los dos, los pronósticos de prueba sí cambian (la comprobación no es trivial).
import dataclasses
dK = DR[('Q+P', 0)]
mK = dataclasses.replace(dK.m, y=dK.m.y.copy()); mK.y[np.r_[dK.p['val'], dK.ip]] += 5.0
XK = dK.X.copy(); XK[dK.ip] *= 1e3
dK2 = dataclasses.replace(dK, m=mK, X=XK)                         # VC original: control del ajuste
mP = dataclasses.replace(dK.m, y=dK.m.y.copy(), q_obs=dK.m.q_obs.copy()); mP.y[dK.ip] += 5.0; mP.q_obs[dK.ip] *= 50
dK3 = dataclasses.replace(dK, m=mP, X=XK, VC=C.ValidacionCausal(mP, dK.p['val']))   # validación reconstruida con la prueba alterada
oka = okb = True
for n in ('Regresión lineal', 'KNN'):
    r1, r2, r3 = EN._ajuste(dK, n, [C.SEMILLA]), EN._ajuste(dK2, n, [C.SEMILLA]), EN._ajuste(dK3, n, [C.SEMILLA])
    oka &= np.array_equal(r1['yv'], r2['yv']) and r1['mejor'] == r2['mejor'] and not np.allclose(r1['yp'], r2['yp'])
    okb &= np.array_equal(r1['yv'], r3['yv']) and r1['mejor'] == r3['mejor'] and not np.allclose(r1['yp'], r3['yp'])
caso('T06a ajuste (lineal y KNN, camino real): validación sin información de validación ni de prueba', oka)
caso('T06b selección (lineal y KNN, camino real, validación reconstruida): la prueba no entra en la elección', okb)
qa = F.arriba['San Regis']['q'].copy(); qa[qa.index > C.FIN_ENTRENAMIENTO] *= 10
caso('T06 ε de la estación aguas arriba solo con entrenamiento', C.eps_entrenamiento(qa) == F.arriba['San Regis']['eps'])

# T08. Muestra extendida: un objetivo faltante a h = 30 conserva la emisión en h = 1 y la excluye donde no es verificable.
qs = pd.Series(np.exp(np.sin(np.arange(200) / 9.0)) + 2, index=pd.date_range('2001-01-01', periods=200))
qs.iloc[150] = np.nan
mxs = C.construir_muestras(qs, L=L, H=H, esc=pd.DatetimeIndex([]), eps=0.01, exigir_todos=False)
i = mxs.fechas.get_loc(qs.index[150] - pd.Timedelta(days=30))
caso('T08 objetivo ausente a h=30: se evalúa a h=1…29 y no a h=30', np.isfinite(mxs.q_obs[i, :29]).all() and np.isnan(mxs.q_obs[i, 29]))

# T09, T10, T11. Métricas reproducibles, horizonte útil y réplicas compartidas.
rng = np.random.default_rng(1)
fe9 = pd.date_range('2016-01-01', periods=400)
obs = rng.gamma(2, 10, (400, H)); pr = obs * rng.normal(1, 0.2, obs.shape); pe9 = obs * rng.normal(1, 0.4, obs.shape); cl = np.full_like(obs, obs.mean())
t1, t2 = C.tabla_metricas(obs, pr, pe9, cl), C.tabla_metricas(obs, pr, pe9, cl)
b1, b2 = C.bootstrap_curvas(fe9, obs, pr, pe9, cl, B=50), C.bootstrap_curvas(fe9, obs, pr, pe9, cl, B=50)
caso('T09 dos ejecuciones de las métricas y del bootstrap dan lo mismo', t1.equals(t2) and all(np.array_equal(b1[k], b2[k]) for k in b1))


def tab(ok):
    return pd.DataFrame({'NSE': np.where(ok, 0.5, -0.1), 'hab_pers': np.where(ok, 0.1, -0.1), 'hab_clim': np.full(H, 0.1)}, index=range(1, H + 1))


ok10 = np.ones(H, bool); ok10[3] = False
caso('T10 H = 3 si falla en h = 4 aunque vuelva a cumplir; H = 0 si falla en h = 1; H = 30 si cumple todo',
     C.horizonte_util(tab(ok10)) == 3 and C.horizonte_util(tab(~np.ones(H, bool))) == 0 and C.horizonte_util(tab(np.ones(H, bool))) == 30
     and C.horizonte_util(tab(np.r_[False, np.ones(H - 1, bool)])) == 0)
# Réplicas compartidas ENTRE comparaciones: con (pred = a, ref = b) y (pred = b, ref = a), en cada réplica
# (1 − hab₁)(1 − hab₂) = (MSEa/MSEb)(MSEb/MSEa) = 1 solo si las dos llamadas remuestrean los mismos bloques.
ba, bb = C.bootstrap_curvas(fe9, obs, pr, pe9, cl, B=200), C.bootstrap_curvas(fe9, obs, pe9, pr, cl, B=200)
otra = C.bootstrap_curvas(fe9, obs, pe9, pr, cl, B=200, semilla=7)
# Réplicas compartidas ENTRE horizontes: con los 30 horizontes idénticos, las 30 columnas de cada réplica deben ser iguales.
o1 = np.repeat(obs[:, :1], H, 1); p1 = np.repeat(pr[:, :1], H, 1); r1_ = np.repeat(pe9[:, :1], H, 1)
bh = C.bootstrap_curvas(fe9, o1, p1, r1_, np.full_like(o1, o1.mean()), B=200)
caso('T11 mismas réplicas entre comparaciones y entre horizontes (y distintas con otra semilla)',
     np.allclose((1 - ba['hab_pers']) * (1 - bb['hab_pers']), 1) and not np.allclose((1 - ba['hab_pers']) * (1 - otra['hab_pers']), 1)
     and np.allclose(bh['NSE'], bh['NSE'][:, :1]) and np.allclose(bh['hab_pers'], bh['hab_pers'][:, :1]))

# T13. Mediana positiva con POD < 0.5 o FAR > 0.5: anticipación útil 0 sin tocar la mediana de los aciertos.
porA = pd.DataFrame({'POD': [0.9, 0.8, 0.7], 'evaluables': [10, 10, 10]}, index=[1, 2, 3])
caso('T13 FAR > 0.5 da anticipación útil 0 aunque POD(A) sea alta', C.anticipacion_util({'FAR': 0.6, 'anticipacion_mediana': 2.0}, porA) == 0
     and C.anticipacion_util({'FAR': 0.4}, porA) == 3)

# T16. La caché no devuelve predicciones de otra partición, latencia, identificador de ejecución o código.
d0 = DR[('Q', 0)]
k0 = EN.clave_cache(d0, 'Regresión lineal', [42])
p_mod = dict(d0.p); p_mod['ent'] = d0.p['ent'][1:]
d_part = dataclasses.replace(d0, p=p_mod)
d_lat = dataclasses.replace(d0, latencia=1)
rev, sem = C.REVISION, C.SEMILLA
C.REVISION = 'otra'; k_rev = EN.clave_cache(d0, 'Regresión lineal', [42]); C.REVISION = rev
C.SEMILLA = 7; k_sem = EN.clave_cache(d0, 'Regresión lineal', [42]); C.SEMILLA = sem
fuentes = {'comun': Path(C.__file__).read_text(encoding='utf-8'), 'entradas': Path(EN.__file__).read_text(encoding='utf-8')}
f_doc = dict(fuentes); f_doc['entradas'] = f_doc['entradas'].replace('"""Búsqueda de hiperparámetros', '"""Otro texto. Búsqueda de hiperparámetros')
f_cod = dict(fuentes); f_cod['entradas'] = f_cod['entradas'].replace("NSE_sel=C.nse_medio(d.VC.a_q(mod.predict(X[iv]))", "NSE_sel=-C.nse_medio(d.VC.a_q(mod.predict(X[iv]))")
caso('T16 la clave cambia con la partición, la latencia, la semilla de búsqueda y la lógica; no con la documentación ni con la etiqueta de revisión',
     len({k0, EN.clave_cache(d_part, 'Regresión lineal', [42]), EN.clave_cache(d_lat, 'Regresión lineal', [42]), k_sem}) == 4 and k_rev == k0
     and EN.clave_cache(d0, 'Regresión lineal', [42]) == k0 and EN.huella_codigo(fuentes) == EN.huella_codigo()
     and EN.huella_codigo(f_doc) == EN.huella_codigo() and EN.huella_codigo(f_cod) != EN.huella_codigo())

# T17, T18. Manifiesto y modo de ejecución: un archivo alterado, un manifiesto ausente o una salida de otro modo detienen.
tmp = Path(tempfile.mkdtemp())
try:
    (tmp / 'salidas' / 'x').mkdir(parents=True)
    f1 = tmp / 'salidas' / 'x' / 'a.csv'; f1.write_text('1,2\n')
    import hashlib
    man = dict(revision=C.REVISION, salidas_sha256={'salidas/x/a.csv': hashlib.sha256(f1.read_bytes()).hexdigest()})
    ok17 = lanza(C.verificar_archivos, [f1], tmp)                                  # sin manifiesto
    (tmp / 'salidas' / 'manifiesto.json').write_text(json.dumps(man))
    ok17 &= not lanza(C.verificar_archivos, [f1], tmp)                             # correcto
    f1.write_text('1,3\n')
    ok17 &= lanza(C.verificar_archivos, [f1], tmp)                                 # alterado
    man['revision'] = 'v3'; f1.write_text('1,2\n'); (tmp / 'salidas' / 'manifiesto.json').write_text(json.dumps(man))
    ok17 &= lanza(C.verificar_archivos, [f1], tmp)                                 # revisión incompatible
    caso('T17 manifiesto ausente, archivo alterado o revisión incompatible detienen la síntesis final', ok17)
    r = tmp / 'salidas' / 'x' / 'resumen.json'
    r.write_text(json.dumps({'version': C.VERSION, 'revision': C.REVISION, 'rapido': True}))
    ok18 = lanza(C.verificar_resumen, r)
    r.write_text(json.dumps({'version': C.VERSION, 'revision': 'otra', 'rapido': False}))
    ok18 &= lanza(C.verificar_resumen, r)
    r.write_text(json.dumps({'version': C.VERSION, 'revision': C.REVISION, 'rapido': False}))
    ok18 &= not lanza(C.verificar_resumen, r)
    r.write_text(json.dumps({'version': C.VERSION, 'rapido': False, 'minutos': 1}))       # sin revisión y sin huella en el manifiesto
    ok18 &= lanza(C.verificar_resumen, r)
    man2 = dict(revision=C.REVISION, salidas_sha256={'salidas/x/resumen.json': hashlib.sha256(r.read_bytes()).hexdigest()})
    (tmp / 'salidas' / 'manifiesto.json').write_text(json.dumps(man2))
    ok18 &= not lanza(C.verificar_resumen, r)                                                  # acreditado por el manifiesto
    os.environ['CDA_RAPIDO'] = '1'
    ok18 &= str(C.ruta_salidas()) == 'salidas_rapido' and lanza(C.verificar_resumen, r)
    os.environ.pop('CDA_RAPIDO')
    caso('T18 salidas rápidas y finales no se mezclan; revisión no compatible se rechaza', ok18 and str(C.ruta_salidas()) == 'salidas')
finally:
    shutil.rmtree(tmp)

# T19. Conteo de cobertura: pares emisión–horizonte, fechas objetivo únicas y eventos son cantidades distintas.
fe19 = pd.date_range('2020-01-01', periods=5)
o19 = np.array([[1, 9, 9], [9, 9, 1], [9, 1, 1], [1, 1, 1], [1, 1, 1]], float)
pares, unicas = C.conteo_altos(fe19, o19, 5.0)
caso('T19 pares emisión–horizonte (5) ≠ fechas objetivo únicas (2)', pares == 5 and unicas == 2)

# T23. Entradas de Chronos-2: alterar cualquier dato posterior al corte (t o t − latencia) no cambia las entradas,
# también con vacíos de 1–3 días que cruzan el corte; y un vacío cerrado antes del corte se rellena como en v4.
import chronos2 as CH
rng = np.random.default_rng(3)
dd = pd.date_range('2001-01-01', periods=400)
base = pd.Series(np.exp(np.sin(np.arange(400) / 15.0)) * 50 + rng.gamma(2, 3, 400), index=dd)
ok10 = True
for largo in (1, 2, 3):
    for lat in (0, 1, 2):
        for t_i in (150, 210, 300):
            u = base.copy(); u.iloc[t_i - lat - largo + 1:t_i - lat + 1] = np.nan          # vacío que termina justo en el corte
            u2 = u.copy(); u2.iloc[t_i - lat + 1:] = u2.iloc[t_i - lat + 1:] * 7 + 100      # todo lo posterior al corte, alterado
            f_ = pd.DatetimeIndex([dd[t_i]])
            e1 = CH.entradas(f_, CH.preparar(base, 1.0), 60, pasadas={'u': CH.preparar(u, 1.0)}, ocultar={'u': lat} if lat else None)[0]
            e2 = CH.entradas(f_, CH.preparar(base, 1.0), 60, pasadas={'u': CH.preparar(u2, 1.0)}, ocultar={'u': lat} if lat else None)[0]
            ok10 &= np.array_equal(e1['past_covariates']['u'], e2['past_covariates']['u'], equal_nan=True)
u = base.copy(); u.iloc[100:102] = np.nan
e3 = CH.entradas(pd.DatetimeIndex([dd[150]]), CH.preparar(base, 1.0), 60, pasadas={'u': CH.preparar(u, 1.0)})[0]['past_covariates']['u']
v4 = (np.exp(C.rellenar_cortos(np.log(u + 1.0))) - 1.0).loc[dd[91]:dd[150]].to_numpy()
caso('T23 Chronos-2: entradas invariantes ante datos posteriores al corte (vacíos de 1–3 días, latencia 0–2)', ok10)
caso('T23 Chronos-2: vacío cerrado antes del corte se rellena igual que en v4', np.allclose(e3, v4, rtol=1e-5))
# La entrada de una emisión no depende del lote: con un vacío que toca el inicio de su ventana, pedirla sola o junto con
# emisiones posteriores da lo mismo (y el vacío se rellena con el dato anterior a la ventana, como en v4).
u = base.copy(); u.iloc[89:92] = np.nan                                         # vacío de 3 días; la ventana de dd[150] empieza en dd[91]
sola = CH.entradas(pd.DatetimeIndex([dd[150]]), CH.preparar(base, 1.0), 60, pasadas={'u': CH.preparar(u, 1.0)})[0]['past_covariates']['u']
lote = CH.entradas(pd.DatetimeIndex([dd[150], dd[200], dd[300]]), CH.preparar(base, 1.0), 60, pasadas={'u': CH.preparar(u, 1.0)})[0]['past_covariates']['u']
v4b = (np.exp(C.rellenar_cortos(np.log(u + 1.0))) - 1.0).loc[dd[91]:dd[150]].to_numpy()
caso('T23 Chronos-2: la entrada de una emisión no depende del lote (vacío al inicio de la ventana)',
     np.array_equal(sola, lote, equal_nan=True) and np.isfinite(sola).all() and np.allclose(sola, v4b, rtol=1e-5))

# T22. Protocolo común de selección para avisos (04, 06 y 08): la regla de cada candidato se calibra solo con 2009–2011
# (alterar sus trayectorias de 2012–2015 no la cambia), la comparación usa 2012–2015 y, entre candidatos iguales, gana el
# más simple; la función no recibe la prueba.
qR4, _ = C.cargar_serie('Racarumi'); m4 = C.construir_muestras(qR4, L=C.L_VENTANA, H=len(C.HORIZONTES), esc=C.escalones(qR4), eps=C.eps_entrenamiento(qR4)); p4 = C.particion(m4)
fv4 = m4.fechas[p4['val']]; P954 = float(np.nanpercentile(qR4.loc[:C.FIN_ENTRENAMIENTO], 95))
bueno = m4.q_obs[p4['val']].astype(float); flojo = np.repeat(m4.q_t[p4['val']][:, None], bueno.shape[1], 1)   # persistencia
s0 = C.inicio_seleccion()
alt = flojo.copy(); alt[np.asarray(fv4 >= s0)] *= 3.0                       # solo cambia el bloque 2012–2015
sa1 = C.seleccion_avisos(fv4, {'A': flojo, 'B': bueno, 'C': bueno.copy()}, qR4, P954, ['A', 'B', 'C'])
sa2 = C.seleccion_avisos(fv4, {'A': alt, 'B': bueno, 'C': bueno.copy()}, qR4, P954, ['A', 'B', 'C'])
caso('T22 selección para avisos: regla de 2009–2011 independiente de 2012–2015; empate → el más simple; sin la prueba',
     sa1['regla_bloque']['A'] == sa2['regla_bloque']['A'] and sa1['metricas_seleccion']['A'] != sa2['metricas_seleccion']['A']
     and sa1['elegido'] == 'B' and pd.Timestamp(sa1['periodo_seleccion'][-10:]) <= pd.Timestamp(C.FIN_VALIDACION))

# T24. Caché de Chronos-2: cambiar UNA emisión no muestreada obliga a recalcular; nunca se adopta un resultado antiguo.
tmpc = Path(tempfile.mkdtemp()); ruta0 = CH.RUTA_CACHE; CH.RUTA_CACHE = tmpc
try:
    ins = [{'target': np.arange(10, dtype=np.float32) + i} for i in range(20)]
    llamadas = []
    calc = lambda: (llamadas.append(1), np.ones((20, 30, 21), np.float32))[1]
    fch = pd.date_range('2016-01-01', periods=20)
    CH.con_cache({'x': 1}, fch, calc, entradas=ins)
    CH.con_cache({'x': 1}, fch, calc, entradas=ins)                               # misma identidad: no recalcula
    ins2 = [dict(d) for d in ins]; ins2[13] = {'target': ins[13]['target'].copy()}; ins2[13]['target'][4] = 999
    CH.con_cache({'x': 1}, fch, calc, entradas=ins2)                              # una emisión distinta: recalcula
    caso('T24 caché de Chronos-2: una emisión no muestreada distinta obliga a recalcular', len(llamadas) == 2)
    # El caso de la observación: una caché ANTIGUA (misma configuración, clave sin huella de entradas) cuyas 8 emisiones
    # muestreadas coinciden, pero con la emisión 13 (no muestreada) cambiada. Nunca debe adoptarse.
    import inspect
    kw = {'verificar': lambda sub: np.ones((len(sub), 30, 21), np.float32)} if 'verificar' in inspect.signature(CH.con_cache).parameters else {}
    ruta_v1, texto_v1 = CH._ruta_cache({'x': 2}, fch.values.astype('datetime64[D]'))
    np.savez_compressed(ruta_v1, Q=np.ones((20, 30, 21), np.float32), fechas=fch.values.astype('datetime64[D]'), clave=texto_v1)
    Q11 = CH.con_cache({'x': 2}, fch, lambda: np.zeros((20, 30, 21), np.float32), entradas=ins2, **kw)
    caso('T24 caché de Chronos-2: una caché antigua que coincide en las emisiones muestreadas no se adopta', bool((Q11 == 0).all()))
finally:
    CH.RUTA_CACHE = ruta0; shutil.rmtree(tmpc)

# T25. Identidad del modelo: cambia si cambia un archivo de pesos y nunca es un nombre de repositorio.
tmpm = Path(tempfile.mkdtemp())
try:
    (tmpm / 'config.json').write_text('{}'); (tmpm / 'model.safetensors').write_bytes(b'a' * 100)
    os.environ['CHRONOS2_MODELO'] = str(tmpm); h1 = CH.huella_modelo()
    (tmpm / 'model.safetensors').write_bytes(b'a' * 99 + b'b'); h2 = CH.huella_modelo()
    (tmpm / 'model.safetensors').unlink(); sin_pesos = lanza(CH.huella_modelo)
    caso('T25 identidad de Chronos-2: cambia con los pesos y falla (no devuelve un nombre) si faltan', h1 != h2 and len(h1) == 64 and sin_pesos)
finally:
    os.environ.pop('CHRONOS2_MODELO', None); shutil.rmtree(tmpm)

# T26. Caché de entradas.py (05, 06 y 08): una entrada de otra identidad nunca se adopta, aunque antes se haya verificado otro modelo o
# configuración en el mismo proceso; una entrada con la misma ruta pero clave distinta o fechas alteradas no se usa.
tmpe = Path(tempfile.mkdtemp()); rc0 = EN.RUTA_CACHE; EN.RUTA_CACHE = tmpe
try:
    d0 = DR[('Q', 0)]
    r_a = EN.ajustar(d0, 'Regresión lineal')                                     # crea la entrada
    r_b = EN.ajustar(d0, 'Regresión lineal')                                     # identidad idéntica: la lee
    XQ = d0.X.copy(); XQ[d0.p['ent'][:5]] += 0.01
    d_x = dataclasses.replace(d0, X=XQ)
    r_c = EN.ajustar(d_x, 'Regresión lineal')                                    # datos distintos: reajusta
    k_x = EN.clave_cache(d_x, 'Regresión lineal', [C.SEMILLA]); ruta_x = EN._ruta(k_x)
    z = dict(np.load(ruta_x, allow_pickle=False)); z['clave'] = np.array(str(z['clave']).replace('"v":', '"v_":'))
    np.savez_compressed(ruta_x, **z)                                             # misma ruta, clave alterada
    r_d = EN.ajustar(d_x, 'Regresión lineal')
    z = dict(np.load(ruta_x, allow_pickle=False)); z['clave'] = np.array(k_x); z['fechas_pru'] = z['fechas_pru'] + np.timedelta64(1, 'D')
    np.savez_compressed(ruta_x, **z)
    fechas_alteradas = lanza(EN.ajustar, d_x, 'Regresión lineal')
    caso('T26 caché del 08: solo identidad completa; datos o clave distintos reajustan; fechas alteradas se rechazan',
         (not r_a['en_cache']) and r_b['en_cache'] and (not r_c['en_cache']) and (not r_d['en_cache']) and fechas_alteradas
         and not any('migr' in n.lower() for n in dir(EN)))
finally:
    EN.RUTA_CACHE = rc0; shutil.rmtree(tmpe)

# T27. Manifiesto: todos los módulos de cálculo de esta carpeta (los .py que no son pruebas ni el propio manifiesto) están
# en manifiesto.MODULOS, cuyo SHA-256 verifica el 09; en particular integrado.py, el protocolo común de 05, 06 y 08.
import manifiesto as MF
aqui = Path(__file__).resolve().parent
locales = {p.name for p in aqui.glob('*.py') if not p.name.startswith('pruebas_') and p.name != 'manifiesto.py'}
importados = set()
for nbp in aqui.glob('*.ipynb'):
    for c in json.loads(nbp.read_text(encoding='utf-8'))['cells']:
        if c['cell_type'] == 'code':
            for ln in ''.join(c['source']).splitlines():
                ln = ln.strip()
                if ln.startswith(('import ', 'from ')):
                    importados |= {t.strip(',').split('.')[0] + '.py' for t in ln.replace('from ', '').replace('import ', ' ').split() if t.strip(',')}
caso('T27 manifiesto: todos los módulos de cálculo (incluido integrado.py) y todos los importados por los cuadernos tienen SHA-256',
     locales <= set(MF.MODULOS) and 'integrado.py' in MF.MODULOS and (importados & locales) <= set(MF.MODULOS) and 'integrado.py' in importados)

# T28. Caché de Chronos-2: se reutiliza solo con identidad, contenido válido y reproducción; cualquier archivo alterado
# (NaN, cuantiles cruzados, forma distinta, caudal negativo, claves extra) o que no se reproduce se descarta y se recalcula.
import chronos2 as CH
tmpc = Path(tempfile.mkdtemp()); rcc = CH.RUTA_CACHE; CH.RUTA_CACHE = tmpc
try:
    fch = pd.date_range('2010-01-01', periods=6)
    ins = [{'target': np.arange(10, dtype=np.float32) + i} for i in range(6)]
    base = np.sort(np.random.default_rng(1).gamma(2.0, 5.0, (6, 30, 21)).astype(np.float32), axis=-1)
    n_calc = []
    calc = lambda: (n_calc.append(1), base.copy())[1]
    clave = dict(estacion='prueba', variante='sintética')
    _w0 = __import__('warnings'); _w0.simplefilter('ignore', UserWarning)     # los rechazos esperados se avisan; aquí no interesan
    Q1, l1 = CH.con_cache_info(clave, fch, calc, ins)                       # crea
    Q2, l2 = CH.con_cache_info(clave, fch, calc, ins)                       # válida: la reutiliza
    ruta = next(tmpc.glob('*.npz'))
    def alterar(f_mod, extra=None):
        z = dict(np.load(ruta, allow_pickle=False)); z['Q'] = f_mod(z['Q'].copy())
        if extra:
            z.update(extra)
        np.savez_compressed(ruta, **z)
        det = {}
        _, leido = CH.con_cache_info(clave, fch, calc, ins, detalle=det)
        return (not leido) and det['motivo'].startswith('descartada')
    def nan_(Q): Q[2, 5, 7] = np.nan; return Q
    def cruz(Q): Q[1, 0, [3, 4]] = Q[1, 0, [4, 3]] + np.array([1, 0]); return Q
    def neg(Q): Q[0, 0, 0] = -1.0; return Q
    rech = [alterar(nan_), alterar(cruz), alterar(lambda Q: Q[:, :29]), alterar(neg), alterar(lambda Q: Q, {'otra': np.zeros(1)})]
    det_r = {}
    _, l_rep = CH.con_cache_info(clave, fch, calc, ins, reproducir=lambda Q: dict(emisiones_reproducidas=2, dif_relativa_max=0.5, reproduce=False), detalle=det_r)
    _, l_ok = CH.con_cache_info(clave, fch, calc, ins, reproducir=lambda Q: dict(emisiones_reproducidas=2, dif_relativa_max=0.0, reproduce=True))
    caso('T28 caché de Chronos-2: válida se reutiliza; NaN, cuantiles cruzados, forma distinta, negativos o claves extra se descartan; '
         'una que no se reproduce se recalcula', (not l1) and l2 and all(rech) and (not l_rep) and det_r['motivo'].startswith('descartada: no reproduce')
         and l_ok and np.array_equal(Q2, base) and len(n_calc) == 1 + len(rech) + 1)
finally:
    CH.RUTA_CACHE = rcc; shutil.rmtree(tmpc); __import__('warnings').simplefilter('default', UserWarning)

# T29. Caché de Chronos-2 ilegible: un archivo truncado, vacío, con bytes que no son un ZIP o con un arreglo de objetos
# (requiere pickle) no detiene la ejecución: se descarta como «ilegible», se registra en cache/rechazos.csv y se recalcula.
import warnings as _w
tmpc = Path(tempfile.mkdtemp()); rcc = CH.RUTA_CACHE; CH.RUTA_CACHE = tmpc
try:
    fch = pd.date_range('2011-01-01', periods=4)
    ins = [{'target': np.arange(8, dtype=np.float32) * (i + 1)} for i in range(4)]
    base = np.sort(np.random.default_rng(2).gamma(2.0, 3.0, (4, 30, 21)).astype(np.float32), axis=-1)
    n_calc = []
    calc = lambda: (n_calc.append(1), base.copy())[1]
    clave = dict(estacion='prueba', variante='ilegible')
    CH.con_cache_info(clave, fch, calc, ins)
    ruta = next(p for p in tmpc.glob('*.npz'))
    bueno = ruta.read_bytes()
    def danar(contenido):
        ruta.write_bytes(contenido)
        det = {}
        with _w.catch_warnings(record=True) as avisos:
            _w.simplefilter('always')
            Q, leido = CH.con_cache_info(clave, fch, calc, ins, detalle=det)
        return (not leido) and det['motivo'].startswith('descartada: ilegible') and np.array_equal(Q, base) and any('descartada' in str(a.message) for a in avisos)
    obj = tempfile.NamedTemporaryFile(suffix='.npz', delete=False); obj.close()
    with np.load(ruta, allow_pickle=False) as z0:
        np.savez(obj.name, Q=np.array([object()], dtype=object), fechas=z0['fechas'], clave=z0['clave'])   # misma identidad
    casos_il = [danar(bueno[: len(bueno) // 2]), danar(b''), danar(b'no es un zip' * 50), danar(Path(obj.name).read_bytes())]
    os.unlink(obj.name)
    reg = (tmpc / 'rechazos.csv').read_text(encoding='utf-8').strip().splitlines()
    _, l_fin = CH.con_cache_info(clave, fch, calc, ins)
    caso('T29 caché de Chronos-2 ilegible (truncada, vacía, no ZIP o con objetos): se descarta, se registra y se recalcula sin detener la ejecución',
         all(casos_il) and len(reg) == 1 + len(casos_il) and len(n_calc) == 1 + len(casos_il) and l_fin
         and not list(tmpc.glob('*.tmp.npz')))
finally:
    CH.RUTA_CACHE = rcc; shutil.rmtree(tmpc)

# T21. Rutas: la clave relativa usa '/' también con rutas de Windows (caso explícito, no depende del sistema).
from pathlib import PureWindowsPath
caso("T21 claves relativas con '/' también para rutas de Windows",
     C.clave_relativa(PureWindowsPath(r'C:\proy\modelos\salidas\lluvia\resumen.json'), PureWindowsPath(r'C:\proy\modelos')) == 'salidas/lluvia/resumen.json')

if POSTERIOR:
    # T20. Proceso limpio: un intérprete nuevo y aislado (python -I) reconstruye desde los datos las filas del experimento
    # y reajusta la regresión lineal de Racarumi con Q+P sin caché; sus pronósticos de prueba en m³/s deben coincidir con
    # los guardados por el cuaderno 06 (seis modelos desde el inicio, revisiones 6 y 7).
    import subprocess
    codigo = r"""
import os, sys, numpy as np
sys.path.insert(0, os.getcwd())
import comun as C, entradas as EN
F, m, p, VC, mx, D = EN.experimento('Racarumi', EN.DISENO_LLUVIA); d = D[('Q+P', 0)]
r = EN.ajustar(d, 'Regresión lineal', cache=False)
q = C.a_caudal(m, r['yp'], d.ip, C.factor_duan(m.y[p['val']], r['yv']))
z = np.load(os.path.join(str(C.ruta_salidas()), 'lluvia', 'predicciones.npz'))
print('IGUAL' if np.allclose(q.astype(np.float32), z['Racarumi|Q+P|Regresión lineal|media'], rtol=1e-5) else 'DISTINTO')
"""
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON') and k != 'CDA_RAPIDO'}
    salida = subprocess.run([sys.executable, '-I', '-c', codigo], cwd=Path(__file__).resolve().parent, capture_output=True, text=True, env=env)
    caso('T20 (posterior) un proceso limpio reproduce los pronósticos guardados del 06', salida.stdout.strip().endswith('IGUAL'))
    # T21 (posterior). El manifiesto existe y todas sus claves usan '/': si falta, es una FALLA, no una omisión.
    mp = Path(__file__).resolve().parent / 'salidas' / 'manifiesto.json'
    mj = json.loads(mp.read_text(encoding='utf-8')) if mp.exists() else None
    caso("T21 (posterior) manifiesto presente y con claves '/'", mj is not None and not any('\\' in k for k in list(mj['salidas_sha256']) + list(mj['entradas_sha256'])))
    caso('T27 (posterior) el manifiesto registra el SHA-256 de todos los módulos de cálculo, incluido integrado.py',
         mj is not None and set(mj.get('codigo_sha256', {})) == set(MF.MODULOS))

malos = [n for n, ok in casos if not ok]
for n, ok in casos:
    print(('OK   ' if ok else 'FALLA') + ' ' + n)
print(f"{len(casos) - len(malos)} de {len(casos)} comprobaciones correctas (fase {'previa + posterior' if POSTERIOR else 'previa'}; ninguna omitida)")
if malos:
    raise SystemExit(1)
