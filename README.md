# ¿Cuánto aviso nos da un río?

**Pronóstico del caudal diario y anticipación de crecidas en dos ríos del Perú con ciencia de datos**

Proyecto Integrador del curso **Ciencia de Datos Ambientales** · Universidad de Ingeniería y Tecnología (UTEC), 2026

**Equipo:** 

- Luis Angel Cupe Espinoza
- Yely Lanasca Justiniano 
- Lia Kim Alcantara Tineo 
- Mayra Madelyn Marzano Mejia 
- María Fernanda Torres Carbajal 

**Datos:** CAMELS-PE v1.0.1 (SENAMHI; Llauca et al., 2026), única fuente de todo el estudio.

---

## Resumen

Un pronóstico de caudal sirve para avisar con tiempo, pero ¿cuánto tiempo? Este estudio responde esa pregunta en dos ríos de memoria hidrológica muy distinta: **Racarumi**, en el río Chancay-Lambayeque (vertiente del Pacífico, 2 363 km², crecidas que suben en uno o dos días), y **Tamshiyacu**, en el Amazonas (≈ 720 000 km², un ciclo anual lento). Se evalúan dos resultados que no deben confundirse: hasta qué **horizonte** se pronostica bien la **magnitud** del caudal diario (1 a 30 días) y con cuántos **días reales** se puede **avisar un nuevo cruce** del percentil 95, un caudal elevado.

El estudio compara seis modelos entrenados (regresión lineal, KNN, Random Forest, XGBoost, MLP y LSTM) y un modelo fundacional sin ajuste local (Chronos-2), primero solo con el caudal de la propia estación y después con información adicional: estaciones aguas arriba, lluvia de la cuenca e índices de humedad antecedente. Todas las decisiones se toman en validación con reglas fijadas de antemano y se evalúan una sola vez en un periodo de prueba independiente (2016 en adelante).

**Respuesta principal.** El río pesa más que el modelo: con su propio caudal, Tamshiyacu admite un pronóstico útil de la magnitud a **30 días o más**, mientras que Racarumi llega a **unos 6 días**. Agregar información mejora la magnitud de corto plazo con el mismo modelo —San Regis reduce el error de Tamshiyacu un 33–45 % a 1–3 días; la lluvia del mismo día reduce el de Racarumi un 12–27 % y da 1 día de aviso en varias configuraciones—, pero la selección hecha solo en validación no logra elegir esas mejoras de forma confiable, y **ningún sistema de avisos elegido de antemano cumple el criterio de utilidad** en Racarumi; en Tamshiyacu hay demasiado pocos eventos para evaluarlo. Más anticipación requeriría pronósticos de lluvia, estaciones más lejanas en la red y, sobre todo, más eventos.

## Preguntas y cuadernos

| | Pregunta | Dónde |
|---|---|---|
| — | ¿Qué calidad tienen los registros y qué cuencas conviene modelar? | Diagnóstico: `chancay_eda/`, `amazonas_eda/` |
| **P1** | ¿Hasta qué horizonte se pronostica bien la magnitud del caudal con la información local de cada estación? | `modelos/` 01, 02, 03 |
| **P2** | ¿Con cuántos días reales se avisan los nuevos cruces del P95, con cuántas omisiones y falsas alarmas? | 04 |
| **P3** | ¿Cuánto aporta el caudal de las estaciones aguas arriba inmediatas? | 05 |
| **P4** | ¿Cuánto aporta la lluvia de la cuenca, según cuándo esté disponible? | 06 |
| **P5** | ¿Compite un modelo fundacional con sus pesos publicados (Chronos-2) con los modelos entrenados? | 07, 08 |
| **P6** | Con todas las combinaciones de entradas y modelos, ¿qué configuración se elige en validación para la magnitud y para los avisos, y cómo rinde en la prueba? | 08 |
| — | Síntesis: respuestas, incertidumbre y alcance | 09 |

## Datos y selección de las cuencas

El diagnóstico revisó cuatro cuencas candidatas de CAMELS-PE, dos por vertiente, y comparó la calidad de sus registros observados y la utilidad del caudal simulado PISCO-ARNOVIC. Se seleccionó una cuenca por vertiente:

| Vertiente | Seleccionada | Motivo | No seleccionada |
|---|---|---|---|
| Pacífico | **Chancay-Lambayeque (Racarumi)** | Registro «apto»: 42.5 años, 0.32 % de vacíos, homogéneo y bien fechado | Chicama (Salinar): «apta con reservas», con 11.5 % de vacíos, y su estación aguas arriba (El Tambo) con fechas corruptas en 1998–2022 |
| Amazónica | **Amazonas (Tamshiyacu)** | 41 años y 0.46 % de vacíos, con dos estaciones aguas arriba (San Regis en el Marañón y Requena en el Ucayali) cuyo balance cierra con Tamshiyacu | Alto Huallaga (Tingo María): 11.2 % de vacíos y registro no homogéneo entre 1997–2020 y 2021–2025 |

Hallazgos del diagnóstico que condicionan el modelamiento: el caudal simulado **no puede sustituir** al observado en ninguna estación (falla frente a la climatología o en la variabilidad diaria), por lo que todo se modela con el **observado**; Cirato tiene fechas corridas hasta 2022 y solo 13 meses útiles en común con Racarumi; Tamshiyacu y San Regis tienen **escalones de nivel** en 1985–2014, que se excluyen de las ventanas de entrada; y Requena termina en 2020-03.

## Método

- **Pronóstico directo** del caudal observado Q(t + h), h = 1…30, emitido el día t con la información disponible en t; los modelos aprenden el cambio logarítmico respecto a hoy.
- **División temporal:** entrenamiento hasta 2008, validación 2009–2015 (corrección de retransformación en 2009–2011 y comparación de candidatos en 2012–2015, sin solape) y prueba desde 2016-01. Todo parámetro de preparación se estima con el entrenamiento.
- **Referencias:** persistencia y climatología del día del año. **Horizonte útil:** mayor h con NSE > 0 que supera a ambas referencias, informado con su cota 95 % de un bootstrap conjunto por meses.
- **Regla de selección fijada de antemano:** mayor NSE medio de los 30 horizontes en 2012–2015; el más simple entre el mejor y sus **equivalentes** (IC 90 % de la diferencia dentro de ±0.01), con los candidatos **inconclusos** informados aparte.
- **Avisos verificados por eventos:** nuevos cruces del P95 con elegibilidad causal, anticipación real, POD, FAR y CSI sobre un único universo de eventos, con IC de Wilson.
- **Disponibilidad de las fuentes externas:** el mismo día (supuesto optimista) y con un día de retraso; la lluvia futura observada se evalúa solo como escenario idealizado.
- **Reproducibilidad:** pruebas automáticas que detienen los cuadernos si fallan, cachés que se reutilizan solo con identidad completa idéntica y un manifiesto con las huellas SHA-256 de datos, código y salidas que la síntesis verifica antes de usar cualquier resultado.

El detalle del protocolo y de los resultados por etapa está en [`modelos/README.md`](modelos/README.md).

## Resultados principales

| | Racarumi (Chancay-Lambayeque) | Tamshiyacu (Amazonas) |
|---|---|---|
| Horizonte útil con caudal local (cota 95 %) | **6 días** (LSTM; 4–6 según el modelo) | **≥ 30 días** (XGBoost); 17–27 en fechas comunes |
| Avisos con caudal local | No alcanza el criterio de utilidad | 3 de 3 cruces con 3 días (3 eventos: descriptivo) |
| Estación aguas arriba | Cirato: sin mejora demostrada (exploratorio) | San Regis: −33 a −45 % de error a 1–3 días; Requena: sin reducción demostrada |
| Lluvia de la cuenca | Del mismo día: −12 a −27 % de error a 1–3 días; con un día de retraso, casi nada | Complementa a San Regis a 4–30 días, también con retraso |
| Lluvia futura observada (idealizado) | −62 a −69 % de error; ~6 días de aviso sobre los 32 cruces | −7 a −19 % desde 8 días |
| Chronos-2 | Mayor NSE en validación, pero no mantiene esa ventaja en la prueba | Peor que la configuración seleccionada en 34 de 36 comparaciones |
| **Selección final para la magnitud** | **Q · Chronos-2**: NSE medio 0.490 y 5 días en la prueba | **Q · KNN**: 0.906 y ≥ 30 días (Q+SR · KNN en el periodo con Requena, mismo día) |
| **Selección final para avisos** | **Q+P · KNN** (mismo día) / **Q · Random Forest** (retraso): 16 de 32 cruces, FAR 0.57–0.61; **no cumplen** | No se selecciona: 3 cruces en la prueba |

Hipótesis planteadas en el diagnóstico y contrastadas en el modelamiento: **HP1** (horizonte útil mayor en la cuenca amazónica) se sostiene con la cifra conservadora (4–6 frente a 17–27 días en fechas comunes; probabilidad 0.87 para el par seleccionado); **HP2** (la LSTM no supera de forma demostrada a los modelos clásicos a 1–3 días) se sostiene: en Racarumi la LSTM es seleccionada, pero su ventaja es inconclusa; **HP3** (peor desempeño en caudales extremos) se confirma en Racarumi en términos relativos y absolutos, y en Tamshiyacu solo en m³/s.

## Alcance y limitaciones

Es una **comparación académica de configuraciones** evaluadas retrospectivamente, no un sistema operativo de alerta; un cruce del P95 es un caudal elevado, no una inundación. Las familias de modelos reciben las mismas fuentes con representaciones distintas, por lo que una diferencia entre ellas no aísla el efecto del algoritmo. Hay pocos eventos (Racarumi: 13 y 14 cruces en validación y 32 en la prueba; Tamshiyacu: 2, 2 y 3). La disponibilidad del dato del mismo día no está demostrada para la lluvia ni para San Regis. El periodo de prueba se consultó durante el desarrollo; las reglas se fijaron antes de la evaluación final y la prueba no interviene en ninguna selección, pero no es una prueba ciega. Dos estaciones no permiten generalizar a todas las cuencas de cada vertiente.

## Estructura del repositorio

```
Proyecto-CDA/
├── README.md                    este documento
├── requirements.txt             entorno (Python 3.13)
├── chancay_eda/                 diagnóstico de la cuenca del Chancay-Lambayeque (Racarumi, Cirato)
│   ├── EDA_Chancay-Lambayeque_CAMELS-PE.ipynb
│   └── salidas/                 figuras, tablas (incluidos los errores eliminados) y mapa interactivo
├── amazonas_eda/                diagnóstico de la cuenca amazónica (Tamshiyacu, San Regis, Requena)
│   ├── EDA_Amazonas_CAMELS-PE.ipynb
│   └── salidas/
└── modelos/                     modelamiento: cuadernos 01–09, módulos, pruebas y salidas
    ├── 01_Modelos_Racarumi.ipynb … 09_Sintesis_Integral.ipynb
    ├── Modelamiento_Interactivo.html
    ├── comun.py · entradas.py · integrado.py · aguas_arriba.py · lluvia.py · chronos2.py
    ├── pruebas_*.py · manifiesto.py · interactivo/
    └── salidas/                 resultados de cada etapa y manifiesto.json
```

`CAMELS-PE_v1.0.1.zip` (~120 MB) no se incluye por su tamaño: se descarga aparte y se coloca en la raíz del repositorio.

## Cómo reproducir

1. **Entorno** (Python 3.13):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
2. **Datos:** descargar CAMELS-PE v1.0.1 del repositorio indicado en el artículo (https://doi.org/10.5194/essd-2026-386) y dejar `CAMELS-PE_v1.0.1.zip` en la raíz. Los cuadernos lo extraen la primera vez.
3. **Diagnóstico:** ejecutar cada cuaderno de `chancay_eda/` y `amazonas_eda/` desde su carpeta (*Restart & Run All*).
4. **Modelamiento:** ejecutar en orden los cuadernos 01–09 de `modelos/`, como se indica en [`modelos/README.md`](modelos/README.md). Chronos-2 descarga sus pesos de Hugging Face la primera vez.

## Fuentes y créditos

- Llauca, H., Montesinos-Caceres, C., Gutierrez-Reynaga, M. y Lavado-Casimiro, W. (2026). *CAMELS-PE: Hydrometeorological time series and catchment attributes for 136 catchments in Peru* [Preprint]. Earth System Science Data Discussions. https://doi.org/10.5194/essd-2026-386
- Caudal simulado PISCO-ARNOVIC v1.1; forzantes PISCOp v2.1, PISCOt, PISCOeo_pm y ERA5-Land, incluidos en CAMELS-PE.
- Ansari, A. F. et al. (2025). Chronos-2 (amazon/chronos-2), modelo fundacional de series de tiempo, usado con sus pesos publicados.
- Plotly.js 2.35.2 (MIT) y Leaflet 1.9.4 (BSD-2), incluidos en `modelos/interactivo/vendor/`; mapas base de Esri (requieren internet; sin conexión el mapa usa capas vectoriales).
