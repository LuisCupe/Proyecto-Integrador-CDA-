# -*- coding: utf-8 -*-
"""Pruebas del protocolo de modelamiento (v4) con los datos reales y con casos sintéticos.
Uso, desde esta carpeta:  python pruebas_protocolo.py   (termina con error si alguna comprobación falla).

Comprueba que no entra información posterior en las entradas ni en la corrección de retransformación, que los bloques
temporales no se solapan, que la regla de selección se comporta como está escrita y que los objetivos estandarizados
se devuelven en su escala."""
import numpy as np
import pandas as pd

import comun as C

casos = []
H = len(C.HORIZONTES)

for est in C.ESTACIONES:
    q, _ = C.cargar_serie(est)
    eps, esc = C.eps_entrenamiento(q), C.escalones(q)
    m = C.construir_muestras(q, L=C.L_VENTANA, H=H, esc=esc, eps=eps)
    p = C.particion(m)
    f = m.fechas
    obj_fin = lambda idx: (f[idx] + pd.Timedelta(days=H)).max()

    # 1. Bloques sin solape: ningún objetivo de un bloque cae en el siguiente.
    casos.append((f'{est}: bloques temporales', obj_fin(p['ent']) <= pd.Timestamp(C.FIN_ENTRENAMIENTO)
                  and f[p['val']].min() > pd.Timestamp(C.FIN_ENTRENAMIENTO) and obj_fin(p['val']) <= pd.Timestamp(C.FIN_VALIDACION)
                  and f[p['pru']].min() > pd.Timestamp(C.FIN_VALIDACION)))

    # 2. Validación causal: calibración termina (con sus objetivos) antes de la selección, que empieza en 2012-01-01.
    vc = C.ValidacionCausal(m, p['val'])
    fv = f[p['val']]
    casos.append((f'{est}: calibración antes de selección', (fv[vc.cal] + pd.Timedelta(days=H)).max() < fv[vc.sel].min()
                  and fv[vc.sel].min() >= pd.Timestamp('2012-01-01') and fv[vc.cal].min() >= pd.Timestamp('2009-01-01')
                  and len(set(vc.cal) & set(vc.sel)) == 0))

    # 3. El factor solo usa la calibración: cambiar los pronósticos del bloque de selección no lo cambia, y cada fila
    #    de selección solo depende de su propio pronóstico.
    rng = np.random.default_rng(0)
    yv = rng.normal(0, 0.1, (len(p['val']), H))
    yv2 = yv.copy(); yv2[vc.sel] += 1.0
    yv3 = yv.copy(); yv3[vc.cal] += 0.05
    yv4 = yv.copy(); yv4[vc.sel[0]] += 0.5
    cambio = np.abs(vc.a_q(yv4) - vc.a_q(yv)).sum(axis=1) > 0
    casos.append((f'{est}: factor solo con calibración', np.allclose(vc.factor(yv), vc.factor(yv2))
                  and not np.allclose(vc.factor(yv), vc.factor(yv3)) and cambio[0] and not cambio[1:].any()
                  and vc.a_q(yv).shape == (len(vc.sel), H)))

    # 4. Entradas causales: alterar el caudal posterior a una fecha no cambia las entradas de emisiones anteriores
    #    (la interpolación de vacíos cortos solo usa días ≤ t).
    corte = pd.Timestamp('2010-06-01')
    q2 = q.copy(); q2[q2.index >= corte] *= 2.0
    m2 = C.construir_muestras(q2, L=C.L_VENTANA, H=H, esc=esc, eps=eps)
    a = np.where(m.fechas < corte)[0]; b = np.where(m2.fechas < corte)[0]
    casos.append((f'{est}: entradas sin información futura', len(a) > 0 and np.array_equal(m.fechas[a], m2.fechas[b])
                  and np.allclose(m.ventana[a], m2.ventana[b], equal_nan=True) and np.allclose(m.zt[a], m2.zt[b])))

    # 5. Preparación solo con entrenamiento: ε y P95 no cambian si se alteran validación y prueba.
    q3 = q.copy(); q3[q3.index > C.FIN_ENTRENAMIENTO] *= 3.0
    casos.append((f'{est}: ε y P95 de entrenamiento', C.eps_entrenamiento(q3) == eps
                  and np.nanpercentile(q3.loc[:C.FIN_ENTRENAMIENTO], 95) == np.nanpercentile(q.loc[:C.FIN_ENTRENAMIENTO], 95)))

    # 6. Separación ≥ 30 días también en los orígenes de estabilidad. Cada origen DEBE poder evaluarse
    #    (antes un ValueError se ignoraba y la prueba aprobaba sin evaluar nada) y el control detecta una violación
    #    sintética (bloque de selección adelantado 10 días).
    ok, evaluados, detecta = True, 0, True
    for fe_c, fv_c, fp_c in [('1994-12-31', '2001-12-31', '2008-12-31'), ('2001-12-31', '2008-12-31', '2015-12-31')]:
        mc = C.construir_muestras(q, L=C.L_VENTANA, H=H, esc=C.escalones(q, fe_c), eps=C.eps_entrenamiento(q, fe_c))
        pc = C.particion(mc, fe_c, fv_c, fp_c)
        try:
            vcc = C.ValidacionCausal(mc, pc['val'], fe_c)
        except ValueError:
            ok = False
            continue
        fc = mc.fechas[pc['val']]
        separados = lambda ini_sel: (fc[vcc.cal] + pd.Timedelta(days=H)).max() < ini_sel
        ok &= separados(fc[vcc.sel].min()) and fc[vcc.sel].min() >= C.inicio_seleccion(fe_c)
        detecta &= not separados(fc[vcc.sel].min() - pd.Timedelta(days=10) - (fc[vcc.sel].min() - (fc[vcc.cal] + pd.Timedelta(days=H)).max()))
        evaluados += 1
    casos.append((f'{est}: bloques en otros orígenes (2 de 2 evaluados; detecta una violación sintética)', bool(ok and evaluados == 2 and detecta)))

    # 7. Muestra extendida por horizonte: las emisiones con los 30 objetivos verificables son
    #    exactamente la muestra común, con las mismas entradas y objetivos; ningún objetivo queda después de un escalón.
    mx = C.construir_muestras(q, L=C.L_VENTANA, H=H, esc=esc, eps=eps, exigir_todos=False)
    todos = np.isfinite(mx.y).all(1)
    pos = mx.fechas.get_indexer(m.fechas)
    sin_cruce = True
    for d in esc:
        dentro = (mx.fechas < d) & (mx.fechas + pd.Timedelta(days=H) >= d)
        for i in np.where(dentro)[0][:50]:
            h0 = (d - mx.fechas[i]).days                                  # primer horizonte en o después del escalón
            sin_cruce &= bool(np.isnan(mx.y[i, h0 - 1:]).all())
    casos.append((f'{est}: muestra extendida contiene la común', (pos >= 0).all() and todos.sum() == len(m.fechas)
                  and np.array_equal(mx.fechas[todos], m.fechas) and np.allclose(mx.ventana[pos], m.ventana)
                  and np.allclose(mx.y[pos], m.y) and len(mx.fechas) >= len(m.fechas) and sin_cruce))

# 8. Regla de selección (sintética): una copia exacta es equivalente; uno mucho peor es "peor"; se elige el más simple.
rng = np.random.default_rng(1)
fechas = pd.date_range('2012-01-01', periods=1200)
obs = 100 + np.cumsum(rng.normal(0, 3, (1200, 1)), 0) + rng.normal(0, 5, (1200, H))
bueno = obs + rng.normal(0, 4, obs.shape)
tab, sel, mejor = C.seleccion_pareada(fechas, obs, {'LSTM': bueno, 'Regresión lineal': bueno.copy(), 'KNN': obs + rng.normal(0, 40, obs.shape)}, B=200)
casos.append(('selección: copia equivalente, peor y más simple', tab.loc['Regresión lineal', 'clase'] in ('mejor', 'equivalente')
              and tab.loc['KNN', 'clase'] == 'peor' and sel == 'Regresión lineal' and tab['seleccionado'].sum() == 1))
# 9. Un candidato con diferencia pequeña pero muy incierta queda "inconcluso" y no se elige por simple.
ruido = obs + rng.normal(0, 4, obs.shape); ruido[:600] += rng.normal(0, 25, (600, H))
tab, sel, _ = C.seleccion_pareada(fechas, obs, {'XGBoost': bueno, 'Regresión lineal': ruido}, B=200)
casos.append(('selección: inconcluso no se elige', tab.loc['Regresión lineal', 'clase'] != 'equivalente' and sel == 'XGBoost'))

# 10. Objetivos estandarizados: Random Forest y MLP devuelven predicciones en la escala original de cada horizonte.
X = rng.normal(size=(400, 5)); Y = np.column_stack([X[:, 0] * 0.01, X[:, 0] * 10.0])
ok = True
for n, par in [('Random Forest', dict(max_depth=5, min_samples_leaf=5, max_features=1.0)),
               ('MLP', dict(hidden_layer_sizes=(16,), alpha=1e-4, max_iter=200))]:
    pr = C.crear_tabular(n, par).fit(X, Y).predict(X)
    ok &= pr.shape == Y.shape and 0.3 < pr[:, 1].std() / Y[:, 1].std() < 1.5 and 0.3 < pr[:, 0].std() / Y[:, 0].std() < 1.5
casos.append(('objetivos estandarizados en su escala', bool(ok)))

for nombre, ok in casos:
    print(f"{'OK ' if ok else 'FALLA'}  {nombre}")
assert all(ok for _, ok in casos), 'alguna comprobación del protocolo falló'
print(f'{len(casos)} comprobaciones correctas')
