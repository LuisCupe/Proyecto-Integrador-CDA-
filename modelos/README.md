# Modelamiento del caudal y de la anticipación de crecidas (cuadernos 01–09)

Esta carpeta contiene la segunda parte del estudio **«¿Cuánto aviso nos da un río?»**: el pronóstico del caudal observado diario a **1–30 días** y la anticipación de **nuevos cruces del P95** en las dos estaciones seleccionadas en el diagnóstico de datos, **Racarumi** (Chancay-Lambayeque, vertiente del Pacífico, 2 363 km²) y **Tamshiyacu** (Amazonas, ~720 000 km²). Los nueve cuadernos forman una sola secuencia: primero los modelos con información local (01–04), después cada fuente de información adicional por separado (05–07) y, al final, la comparación integrada con la selección del proyecto (08) y la síntesis (09).

Se distinguen siempre dos resultados: la **magnitud** del caudal (qué tan bien se pronostica cada día futuro, medido con el horizonte útil) y la **anticipación** de crecidas (con cuántos días reales se avisa un nuevo cruce del P95, medido con eventos). Una mejora de la magnitud no implica más días de aviso.

## Cuadernos

| Cuaderno | Pregunta | Contenido |
|---|---|---|
| `01_Modelos_Racarumi.ipynb` | P1 | Seis modelos con el caudal local (30 días) y el calendario en Racarumi: ajuste en validación, regla de selección, horizonte útil con su incertidumbre, caudales altos, errores por evento, sensibilidad a la historia y al calendario, importancia de variables y estabilidad con cuatro orígenes |
| `02_Modelos_Tamshiyacu.ipynb` | P1 | El mismo análisis en Tamshiyacu, con el tratamiento de los escalones de nivel del registro |
| `03_Comparacion_y_Seleccion.ipynb` | P1 | Comparación de modelos y estaciones sobre fechas comunes explícitas: horizonte útil con bootstrap pareado (H3/HP1), caudales elevados (H4/HP3), estabilidad e información predictiva |
| `04_Anticipacion_Crecidas.ipynb` | P2 | Verificación de avisos por eventos: elegibilidad causal, anticipación real, POD(A) con su denominador, falsas alarmas, sensibilidad a las reglas; fija las reglas que usan 06, 08 y 09 |
| `05_Estaciones_Aguas_Arriba.ipynb` | P3 | Caudal de San Regis y Requena como entrada en Tamshiyacu (y Cirato en Racarumi, exploratorio), con los seis modelos y las fuentes hasta t y hasta t−1 |
| `06_Lluvia_Escorrentia.ipynb` | P4 | Lluvia media de la cuenca (PISCOp v2.1) e índices antecedentes con los seis modelos; hidrología de la respuesta; escenario idealizado de lluvia futura observada |
| `07_Chronos2.ipynb` | P5 | Chronos-2 con sus pesos publicados, sin ajuste local: contexto y pronóstico puntual elegidos en validación, predicciones de todas las combinaciones del 08, pronóstico probabilístico (cobertura, CRPS) |
| `08_Entradas_y_Modelos.ipynb` | P6 | **Comparación integrada y selección final**: seis modelos + Chronos-2 con todas las combinaciones de entradas disponibles, selección en validación para la magnitud y para los avisos, evaluación en la prueba, matriz de experimentos y registro de verificaciones |
| `09_Sintesis_Integral.ipynb` | Síntesis | Verifica que todas las salidas sean compatibles y coincidan con el manifiesto, reevalúa los avisos desde las trayectorias guardadas y responde P1–P6 con su alcance |
| `Modelamiento_Interactivo.html` | — | Resultados interactivos de los cuadernos 01–04 (se abre con doble clic, sin internet) |

## Código, pruebas y trazabilidad

| Archivo | Contenido |
|---|---|
| `comun.py` | Datos, muestras, referencias, métricas, bootstrap, los seis modelos, la LSTM, la verificación de avisos y la regla de selección: el mismo método para las dos estaciones |
| `entradas.py` | Fuentes de entrada (lluvia, IPA k = 0.90 y 0.97, días secos, caudal aguas arriba) con latencia y contrato de fechas diarias, representación por familia de modelos, ajuste con caché de identidad completa y diseños de los experimentos de 05, 06 y 08 |
| `integrado.py` | Protocolo común de comparación de 05, 06 y 08: escenarios de disponibilidad, orden de simplicidad, selección, efecto de cada entrada y del método, métricas de prueba y avisos |
| `aguas_arriba.py` · `lluvia.py` · `chronos2.py` | Estaciones aguas arriba; lluvia de la cuenca y escenario idealizado; Chronos-2 (entradas causales, pronóstico y caché verificada por identidad, contenido y reproducción) |
| `pruebas_avisos.py` · `pruebas_protocolo.py` · `pruebas_entradas.py` | 17, 17 y 48 comprobaciones automáticas (más 3 posteriores a la ejecución): casos sintéticos de avisos, ausencia de información futura, fronteras de los bloques, regla de selección, causalidad de las entradas, identidad de la caché, cachés dañadas y manifiesto. Los cuadernos se detienen si alguna falla |
| `manifiesto.py` | Escribe `salidas/manifiesto.json`: huellas SHA-256 de datos, tablas de depuración del diagnóstico, código y salidas, con las versiones de software y el resultado de las pruebas |
| `interactivo/` | Generador de `Modelamiento_Interactivo.html` (`python interactivo/generar_html.py`) |

## Protocolo de evaluación

- **Datos:** CAMELS-PE v1.0.1 como única fuente, con los errores eliminados en el diagnóstico. Los vacíos de ≤ 3 días se interpolan solo en las entradas y solo con días ≤ t; los objetivos nunca se imputan. En Tamshiyacu se excluyen las ventanas que cruzan un escalón de nivel.
- **División temporal:** entrenamiento hasta 2008, validación 2009–2015 y prueba desde 2016-01 hasta el fin de cada registro (Racarumi 2023-08; Tamshiyacu 2025-12). ε, escalones, P95 y estandarizaciones se calculan solo con el entrenamiento.
- **Validación en dos bloques:** 2009–2011 solo estima la corrección de retransformación de Duan; 2012–2015 solo compara candidatos (separación ≥ 30 días). Ningún pronóstico comparado usa factores estimados con datos posteriores.
- **Modelos:** regresión lineal, KNN, Random Forest, XGBoost, MLP y LSTM, con mallas predefinidas y sin particiones aleatorias; Random Forest, XGBoost, MLP y LSTM con 3 semillas. En 07–08 se agrega Chronos-2 con sus pesos publicados.
- **Regla de selección (fijada antes de evaluar):** mayor NSE medio de los 30 horizontes en 2012–2015; diferencias pareadas con IC 90 % por bootstrap de meses; se elige el más simple entre el mayor y sus **equivalentes** (IC dentro de ±0.01). Un candidato **inconcluso** (IC demasiado ancho) no es equivalente y no se elige por simple. La prueba nunca decide.
- **Horizonte útil:** mayor h consecutivo desde 1 con NSE > 0 y habilidad positiva frente a la persistencia y a la climatología; la cifra informada es la cota 95 % de un bootstrap conjunto por meses. H = 30 significa «30 o más».
- **Avisos:** trayectoria mediana pronosticada, elegibilidad causal (7 días observados bajo el P95), un único universo de eventos para POD, FAR y CSI, tolerancia ±2 días y anticipación real. Criterio de utilidad: anticipación útil ≥ 1 día (POD(A) ≥ 0.5 con FAR ≤ 0.5), también con los IC de Wilson.
- **Disponibilidad de las fuentes externas:** escenario **mismo día** (hasta t; supuesto optimista, no demostrado para PISCOp) y **un día de retraso** (hasta t−1). La **lluvia futura observada** es un escenario idealizado que no compite en ninguna selección.
- **Identificador del protocolo:** el código y las salidas lo registran como `v4`; las etapas registran también su identificador de ejecución y el cuaderno 09 exige que sean compatibles antes de combinarlas.

## Resultados principales

**Modelos con información local (01–04).** El horizonte útil de la magnitud es de **6 días en Racarumi** (LSTM; 4–6 según el modelo) y de **30 días o más en Tamshiyacu** (XGBoost); en fechas comunes, 4–6 frente a 17–27 días con cualquier modelo. En Racarumi, ningún sistema de avisos alcanza el criterio de utilidad; en Tamshiyacu, 3 de 3 cruces con 3 días (descriptivo).

**Fuentes adicionales con el mismo modelo (05–07).**

| Fuente | Racarumi | Tamshiyacu |
|---|---|---|
| Estación aguas arriba | Cirato (exploratorio, 13 meses): sin mejora demostrada | **San Regis:** −33 a −45 % de error a 1–3 días con los seis modelos (7–22 % con un día de retraso). **Requena:** sin reducción demostrada |
| Lluvia observada hasta t | −12 a −27 % a 1–3 días con los seis modelos; 1 día de aviso puntual en seis configuraciones evaluadas | complementa a San Regis a 4–30 días, también con un día de retraso |
| Lluvia hasta t−1 | casi sin ganancia | conserva casi todo el efecto |
| Índices antecedentes | sin mejora consistente | sin mejora consistente con los modelos entrenados |
| Lluvia futura observada (idealizado) | −62 a −69 % de error con XGBoost; ~6 días de aviso sobre los 32 cruces | −7 % a 8–15 días y −19 % a 16–30 días |
| Chronos-2 (contexto elegido en validación) | 2 048 días; bandas P10–P90 con 77–79 % de cobertura, pero 42–57 % en días sobre el P95 | 512 días (los escalones de nivel impidieron distinguir contextos más largos) |

**Selección final del proyecto (08), hecha solo en validación y evaluada en la prueba sin cambiarla.**

| Cuenca · periodo de prueba | Escenario | Magnitud: seleccionada → prueba | Mejor en la prueba (no se elige con él) | Avisos: seleccionada → prueba |
|---|---|---|---|---|
| Racarumi · prueba 2016-01 a 2023-08 | mismo día | **Q · Chronos-2** → NSE medio 0.490, H = 5 d | Q+P+IA · LSTM (0.541) | **Q+P · KNN** → 16/32 cruces, FAR 0.57: **no cumple** |
| Racarumi · prueba 2016-01 a 2023-08 | un día de retraso | **Q · Chronos-2** → 0.490, 5 d | Q+P+IA (t−1) · LSTM (0.530) | **Q · Random Forest** → 16/32, FAR 0.61: **no cumple** |
| Tamshiyacu · con San Regis (prueba 2016-01 a 2025-12) | ambos | **Q · KNN** → 0.906, H ≥ 30 d | Q+P+SR · MLP (0.922) | no se selecciona (3 cruces) |
| Tamshiyacu · común con Requena (prueba 2016-01 a 2020-03) | mismo día / retraso | **Q+SR · KNN** → 0.855, 18 d / **Q · KNN** → 0.850, 17 d | Q+P+IA · MLP (0.884) | no se selecciona (0 cruces) |

Chronos-2 resulta seleccionado para la magnitud en Racarumi por su ventaja en validación, que no mantiene en la prueba; en avisos participa como candidato pero no resulta seleccionado. Ninguna selección coincide con lo mejor observado en la prueba: las ganancias de las entradas externas son reales con el mismo modelo, pero la validación disponible no basta para elegirlas de forma confiable.

## Ejecutar

Requiere `CAMELS-PE_v1.0.1.zip` (o su carpeta) en la raíz del repositorio, las tablas de depuración del diagnóstico (`chancay_eda/` y `amazonas_eda/`) y el entorno de `requirements.txt`. Desde esta carpeta, en este orden (tiempos en CPU de 2 núcleos, sin caché):

```bash
python pruebas_avisos.py && python pruebas_protocolo.py && python pruebas_entradas.py   # si una falla, no siga
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 01_Modelos_Racarumi.ipynb       # ~30 min
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 02_Modelos_Tamshiyacu.ipynb     # ~20 min
jupyter nbconvert --to notebook --execute --inplace 03_Comparacion_y_Seleccion.ipynb
jupyter nbconvert --to notebook --execute --inplace 04_Anticipacion_Crecidas.ipynb
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 05_Estaciones_Aguas_Arriba.ipynb  # ~1.5 h
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 06_Lluvia_Escorrentia.ipynb       # ~3 h
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 07_Chronos2.ipynb                 # ~6 h (minutos en GPU)
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 08_Entradas_y_Modelos.ipynb        # ~2.5 h
python manifiesto.py                     # pruebas previas y posteriores; huellas de datos, código y salidas
jupyter nbconvert --to notebook --execute --inplace 09_Sintesis_Integral.ipynb
python interactivo/generar_html.py
python manifiesto.py                     # registra también el 09 y el HTML
```

Los ajustes de 05, 06 y 08 y las predicciones de Chronos-2 se guardan en cachés locales (`salidas/entradas/cache/`, `salidas/chronos/cache/`; no se suben) y solo se reutilizan con **identidad completa idéntica** (datos, filas, partición, malla, semillas, código y software; en Chronos-2 además el contenido y la reproducción de una muestra). Con `CDA_RAPIDO=1` los cuadernos usan mallas mínimas y escriben en `salidas_rapido/`, que nunca se mezcla con `salidas/`.

**Salidas:** `salidas/<etapa>/` con figuras, tablas, `resumen.json` y pronósticos (`racarumi`, `tamshiyacu`, `comparacion`, `anticipacion`, `aguas_arriba`, `lluvia`, `chronos`, `entradas`, `sintesis`) y `salidas/manifiesto.json`.

## Alcance y limitaciones

- **Comparación académica de configuraciones**, evaluadas retrospectivamente con datos depurados; no es un sistema operativo de alerta. Un cruce del P95 es un caudal elevado bajo una definición estadística, no una inundación.
- **Representaciones distintas:** todas las familias reciben las mismas fuentes con la misma disponibilidad, pero cada una con su representación; una diferencia entre familias no aísla el efecto del algoritmo.
- **Pocos eventos:** Racarumi tiene 13 y 14 cruces en los bloques de validación y 32 en la prueba; Tamshiyacu, 2, 2 y 3 (ninguno en el periodo común con Requena).
- **Disponibilidad del mismo día no demostrada** para la lluvia y San Regis.
- **Periodo de prueba consultado durante el desarrollo:** las reglas se fijaron antes de la evaluación final y la prueba no interviene en ninguna selección (comprobado en el 08), pero no es una prueba ciega.
- **Dos estaciones** no permiten generalizar a todas las cuencas de cada vertiente.
