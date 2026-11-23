# -*- coding: utf-8 -*-
"""Casos sintéticos con resultado esperado para la verificación de avisos de nuevos cruces (comun.evaluar_avisos).
Uso, desde esta carpeta:  python pruebas_avisos.py   (termina con error si algún caso no da lo esperado)."""
import numpy as np
import pandas as pd

import comun as C

U = 50.0                                   # umbral del fenómeno (hace de P95)
D0 = pd.Timestamp('2020-01-01')
dia = lambda k: D0 + pd.Timedelta(days=k)


def serie(n=80, altos=(), nan=()):
    q = pd.Series(10.0, index=pd.date_range(D0, periods=n))
    for a, b in altos:
        q.iloc[a:b + 1] = 100.0
    for k in nan:
        q.iloc[k] = np.nan
    return q


def trayectorias(fechas, regla):
    """regla(k_emision) → día absoluto pronosticado para el cruce (o None); el resto de la trayectoria queda bajo."""
    pred = np.full((len(fechas), 30), 10.0)
    for i, t in enumerate(fechas):
        k = (t - D0).days
        d = regla(k)
        if d is not None and 1 <= d - k <= 30:
            pred[i, d - k - 1:] = 100.0                      # sube el día d y se mantiene
    return pred


RESULTADOS = []                            # todos los resultados, para comprobar la coherencia de fórmulas


def evaluar(q, regla, fin=60, **kw):
    fechas = pd.date_range(dia(8), dia(fin))
    r = C.evaluar_avisos(fechas, trayectorias(fechas, regla), q, U, **{'hmax': 30, 'tol': 2, 'dmax': 7, 'reinicio': 7, **kw})
    RESULTADOS.append(r)
    return r


casos = []

# 1. Aviso previo correcto: desde 7 días antes se pronostica el cruce en la fecha exacta (hmax = 7).
r = evaluar(serie(altos=[(30, 32)]), lambda k: 30 if k < 30 else None, hmax=7)
s = r['resumen']
casos.append(('aviso previo', s['aciertos'] == 1 and s['falsas_alarmas'] == 0 and
              r['eventos'].loc[r['eventos']['evaluable'], 'anticipacion_real'].iloc[0] == 7 and r['por_A'].loc[7, 'POD'] == 1
              and r['por_A'].loc[8, 'POD'] == 0))

# 2. Horizonte nominal ≠ anticipación real: solo avisa la emisión del día 29 con su salida t+3 (τ = 32, dentro de ±2).
r = evaluar(serie(altos=[(30, 32)]), lambda k: 32 if k == 29 else None)
ev = r['eventos'].iloc[0]
casos.append(('anticipación real 1 día', ev['detectado'] and ev['anticipacion_real'] == 1 and r['por_A'].loc[2, 'POD'] == 0))

# 3. Aviso con fecha errada (fuera de tolerancia): falsa alarma y omisión, no acierto.
r = evaluar(serie(altos=[(30, 32)]), lambda k: 36 if 20 <= k < 30 else None)
s = r['resumen']
casos.append(('fecha fuera de tolerancia', s['aciertos'] == 0 and s['omisiones'] == 1 and s['falsas_alarmas'] >= 1))

# 4. Duplicación: dos episodios aciertan el mismo cruce → 1 acierto + 1 repetido, sin falsas alarmas.
r = evaluar(serie(altos=[(30, 32)]), lambda k: 30 if k in (15, 16, 17, 25, 26, 27) else None)
s = r['resumen']
casos.append(('duplicación', s['aciertos'] == 1 and s['repetidos'] == 1 and s['falsas_alarmas'] == 0 and
              r['eventos'].iloc[0]['anticipacion_real'] == 15))

# 5. Hueco antes del cruce: el cruce no es elegible; los avisos hacia él son "no verificables", no falsas alarmas.
r = evaluar(serie(altos=[(30, 32)], nan=[26]), lambda k: 30 if 18 <= k < 26 else None)
s = r['resumen']
casos.append(('hueco', s['evaluables'] == 0 and s['falsas_alarmas'] == 0 and s['episodios_no_verificables'] >= 1
              and s['cruces_identificados'] == 1))

# 6. Un vacío no es un día bajo: tras el NaN del día 20 no hay emisiones elegibles por 7 días.
el = C.elegibilidad(C.estado_diario(serie(nan=[20]), U, dia(0), dia(40)))
casos.append(('vacío ≠ bajo', not el.loc[dia(20):dia(26)].any() and el.loc[dia(27)]))

# 7. Evento largo con una pausa de 3 días: el segundo cruce no es nuevo (menos de 7 días bajo) y no se evalúa.
cr = C.cruces(C.estado_diario(serie(altos=[(30, 39), (43, 50)]), U, dia(0), dia(70)))
casos.append(('evento largo', len(cr) == 2 and cr['elegible'].tolist() == [True, False]))

# 8. Un día alto dentro de un evento ya iniciado no vuelve correcto un aviso de inicio pronosticado tarde.
r = evaluar(serie(altos=[(30, 45)]), lambda k: 38 if 22 <= k < 30 else None)
s = r['resumen']
casos.append(('día alto no es inicio', s['aciertos'] == 0 and s['falsas_alarmas'] >= 1))

# 9. Aviso encendido toda la temporada: se parte cada 7 días y cada tramo sin acierto es una falsa alarma.
r = evaluar(serie(n=140, altos=[(90, 92)]), lambda k: k + 1 if k < 90 else None, fin=100, hmax=3)
s = r['resumen']
casos.append(('aviso continuo', s['falsas_alarmas'] >= 5 and s['aciertos'] == 1))

# 10. Sin avisos: FAR no definida (no se reemplaza por un valor favorable) y anticipación útil 0.
r = evaluar(serie(altos=[(30, 32)]), lambda k: None)
s = r['resumen']
casos.append(('sin avisos', np.isnan(s['FAR']) and s['POD'] == 0 and s['anticipacion_util'] == 0))

# 11. Cruce después de la última emisión (borde final): el episodio que lo avisa es "no verificable"; no cuenta como
#     acierto en la FAR ni queda fuera de POD y CSI. Una falsa alarma real: FAR = 1, CSI = 0, POD sin definir.
r = evaluar(serie(altos=[(64, 66)]), lambda k: 26 if 20 <= k <= 22 else (64 if 55 <= k else None), fin=60)
s = r['resumen']
casos.append(('borde final', s['aciertos'] == 0 and s['falsas_alarmas'] == 1 and s['episodios_no_verificables'] == 1
              and s['evaluables'] == 0 and s['FAR'] == 1 and s['CSI'] == 0 and np.isnan(s['POD'])))

# 12. Falta la emisión del día anterior al cruce: el cruce no entra al universo; los avisos desde días antes son
#     "no verificables" (ni acierto ni falsa alarma), en las tres métricas por igual.
fechas = pd.date_range(dia(8), dia(60)).delete(29 - 8)
r = C.evaluar_avisos(fechas, trayectorias(fechas, lambda k: 30 if 24 <= k <= 28 else None), serie(altos=[(30, 32)]), U,
                     hmax=30, tol=2, dmax=7, reinicio=7)
s = r['resumen']
casos.append(('emisión faltante antes del cruce', s['evaluables'] == 0 and s['aciertos'] == 0 and s['falsas_alarmas'] == 0
              and s['episodios_no_verificables'] == 1))

# 13. Sin eventos pero con avisos: todo es falsa alarma; POD sin definir, FAR = 1, CSI = 0.
r = evaluar(serie(), lambda k: 25 if 20 <= k <= 22 else None)
s = r['resumen']
casos.append(('sin eventos', s['evaluables'] == 0 and s['falsas_alarmas'] == 1 and np.isnan(s['POD']) and s['FAR'] == 1
              and s['CSI'] == 0))

# 14. Aviso tardío por anticipación exigida: detectado con 1 día cuenta como omisión a A = 2 (sistema completo).
r = evaluar(serie(altos=[(30, 32)]), lambda k: 30 if k == 29 else None)
pa = r['por_A']
casos.append(('aviso tardío a A = 2', pa.loc[1, 'aciertos'] == 1 and pa.loc[2, 'aciertos'] == 0 and pa.loc[2, 'aciertos_tardios'] == 1
              and pa.loc[2, 'omisiones'] == 1 and (pa['falsas_alarmas'] == r['resumen']['falsas_alarmas']).all()))

# 14b. Conjunto fijo: un cruce sin emisiones A días antes sale de N_A pero sigue en el denominador fijo.
q = serie(altos=[(30, 32), (50, 52)])
fechas_b = pd.date_range(dia(8), dia(60)).delete(list(range(30 - 8 - 5, 30 - 8 - 1)))   # sin emisiones 4–5 días antes del 1.er cruce
rb = C.evaluar_avisos(fechas_b, trayectorias(fechas_b, lambda k: 30 if k < 30 else 50 if k < 50 else None), q, U, hmax=30)
pb = rb['por_A']
casos.append(('POD sobre conjunto fijo', pb.loc[1, 'evaluables'] == 2 and pb.loc[5, 'evaluables'] == 1
              and pb.loc[5, 'no_evaluables_a_A'] == 1 and pb.loc[5, 'POD'] == pb.loc[5, 'aciertos'] / 1
              and pb.loc[5, 'POD_conjunto_fijo'] == pb.loc[5, 'aciertos'] / 2
              and (pb['POD_conjunto_fijo'] <= pb['POD'].fillna(1) + 1e-12).all()
              and rb['resumen']['anticipacion_util_conjunto_fijo'] <= rb['resumen']['anticipacion_util']))

# 15. Fechas de emisión duplicadas: se rechazan.
try:
    C.evaluar_avisos(pd.DatetimeIndex([dia(10), dia(10)]), np.full((2, 30), 10.0), serie(), U)
    casos.append(('fechas duplicadas', False))
except ValueError:
    casos.append(('fechas duplicadas', True))

# 16. Coherencia de fórmulas en todos los resultados anteriores y en uno con varios eventos y falsas alarmas.
def coherente(res):
    s, pa = res['resumen'], res['por_A']
    Hh, M, F = s['aciertos'], s['omisiones'], s['falsas_alarmas']
    f_ = lambda a, b: a / b if b else np.nan
    igual = lambda x, y: (np.isnan(x) and np.isnan(y)) or abs(x - y) < 1e-12
    return (igual(s['POD'], f_(Hh, Hh + M)) and igual(s['FAR'], f_(F, Hh + F)) and igual(s['CSI'], f_(Hh, Hh + M + F))
            and Hh + M == s['evaluables'] and (res['episodios']['clase'] == 'acierto').sum() == Hh
            and int(res['eventos']['detectado'].sum()) == Hh and pa.loc[1, 'evaluables'] == s['evaluables']
            and pa.loc[1, 'aciertos'] == Hh and (pa['aciertos'] + pa['omisiones'] == pa['evaluables']).all())
varios = evaluar(serie(n=120, altos=[(30, 32), (60, 62), (95, 97)]), lambda k: (30 if 25 <= k < 30 else 70 if 50 <= k <= 52 else
                 97 if 90 <= k < 95 else None), fin=100)
casos.append(('coherencia POD/FAR/CSI', all(coherente(x) for x in RESULTADOS) and varios['resumen']['aciertos'] == 2
              and varios['resumen']['falsas_alarmas'] == 1 and varios['resumen']['omisiones'] == 1))

for nombre, ok in casos:
    print(f"{'OK ' if ok else 'FALLA'}  {nombre}")
assert all(ok for _, ok in casos), 'algún caso sintético no da el resultado esperado'
print(f'{len(casos)} casos correctos')
