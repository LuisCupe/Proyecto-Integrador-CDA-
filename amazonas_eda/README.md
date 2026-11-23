# EDA de la cuenca amazónica con CAMELS-PE: calidad del caudal observado y utilidad del simulado

Diagnóstico de datos (análisis exploratorio) del Proyecto Integrador de **Ciencia de Datos Ambientales** (UTEC, 2026), primera parte del estudio *«¿Cuánto aviso nos da un río?»*. Esta carpeta caracteriza la **cuenca del río Amazonas hasta Tamshiyacu** (vertiente del Atlántico, Loreto), formada por el Marañón y el Ucayali, una de las dos cuencas seleccionadas para el modelamiento.

**Pregunta del diagnóstico:** ¿qué calidad tienen los registros observados de San Regis, Requena y Tamshiyacu, y puede el caudal simulado PISCO-ARNOVIC sustituir al observado?

| Estación | Río | `gauge_id` CAMELS-PE | Área (km²) | Caudal observado en el archivo |
|---|---|---|---|---|
| San Regis | Marañón | PE_220105 | 360 046.8 | 1998-09-01 a 2025-12-31 |
| Requena | Ucayali | PE_250101 | 347 946.1 | 1996-07-01 a **2020-03-31** |
| Tamshiyacu | Amazonas | PE_240103 | 719 664.7 | 1984-09-01 a 2025-12-31 |

San Regis y Requena drenan hacia Tamshiyacu. El área intermedia es solo el 1.62 % del área de Tamshiyacu, por lo que el balance entre las tres estaciones es una verificación muy exigente.

## Estructura de carpetas

```
Proyecto-CDA/                                # raíz del repositorio
├── CAMELS-PE_v1.0.1/CAMELS-PE/       # ÚNICA fuente de datos (carpeta o CAMELS-PE_v1.0.1.zip; no se sube)
└── amazonas_eda/                        # ← esta carpeta
    ├── EDA_Amazonas_CAMELS-PE.ipynb     # cuaderno ejecutado (secciones 0–10)
    ├── README.md
    ├── requirements.txt
    └── salidas/
        ├── figuras/                     # fig01 … fig14 y fig02b (PNG)
        ├── tablas/                      # 14 tablas CSV
        └── mapa_estaciones_amazonas.html
```

## Datos y origen

| Dato | Fuente |
|---|---|
| Caudal observado `flow_obs` (mm/d) | SENAMHI, distribuido en **CAMELS-PE v1.0.1** (Llauca et al., 2026; https://doi.org/10.5194/essd-2026-386) |
| Caudal simulado `flow_sim` (mm/d) | **PISCO-ARNOVIC v1.1** (Llauca et al., 2023; https://doi.org/10.1016/j.ejrh.2023.101381; https://www.hydroshare.org/resource/f723d6c762ca45b6936dd9489bc44842) |
| Forzantes y atributos | CAMELS-PE (PISCOp v2.1, PISCOt, PISCOeo_pm, ERA5-Land; `02_attributes/`, `04_geospatial/`) |

Única fuente de datos: CAMELS-PE v1.0.1; el cuaderno no lee ningún otro archivo.

## Requisitos y ejecución

Python 3.13.16 con las versiones de `requirements.txt` (pandas 3.0.5, numpy 2.5.3, scipy 1.18.1, statsmodels 0.15.0, matplotlib 3.11.2, seaborn 0.13.2, geopandas 1.2.0, folium 0.20.0).

```bash
pip install -r requirements.txt
cd amazonas_eda
jupyter nbconvert --to notebook --execute --inplace EDA_Amazonas_CAMELS-PE.ipynb
```

Detalles de la ejecución:
- Rutas relativas: el cuaderno se ejecuta desde `amazonas_eda/`.
- Duración: unos 12–15 minutos, con bootstrap de 1 000 réplicas y semilla 42. Las series son largas y hay tres estaciones.

## Métodos (resumen)

1. **Inspección:** control de índice y tipos, coherencia de IDs, unidades y áreas (proyección equivalente EPSG:6933, porque las cuencas abarcan varias zonas UTM).
2. **Independencia del simulado (2.6):** extremos, coincidencia exacta de valores y saltos en el cambio de mes.
3. **Integridad temporal (2.7):**
   - desfase anual obs–sim y entre estaciones sobre variaciones de 7 días;
   - prueba de deriva del desfase con los años;
   - ventanas de 180 días;
   - **escalones de nivel** en el cambio de mes.
4. **Balance entre estaciones (2.8, 4.4):** Tamshiyacu frente a San Regis + Requena. Una inconsistencia se atribuye a una estación solo si su razón obs/sim mensual es anómala y la de las otras no.
5. **Faltantes y outliers:**
   - Las métricas usan solo días pareados y nunca se rellena el observado.
   - La detección usa IQR y MAD sobre log(Q + ε).
   - Solo se eliminan puntos con corroboración física.
6. **Obs vs sim:** NSE, KGE (r, α, β), PBIAS, RMSE, NSE-log, BE frente a la climatología mensual y FHV/FMS, con IC 95 % por bootstrap de bloques mensuales. Además: sensibilidad, homogeneidad, régimen y época.
7. **Hipótesis H1–H4:** criterios fijados a priori y una regla de decisión sobre el uso del simulado.

## Resultados principales

**Fechas correctas en las tres estaciones:**
- no hay deriva del desfase obs–sim;
- San Regis se adelanta 1 día a Tamshiyacu;
- el simulado llega 7–12 días tarde de forma constante, por el tránsito del modelo (la lluvia lo confirma).

**Escalones de nivel por bloques:**
- **Tamshiyacu:** 41 escalones (mediana 53 %, hasta +162 % en un día), siempre el **1 de enero o el 1 de setiembre**, en 1985–2014.
- **San Regis:** 17 escalones en 1999–2024.
- **Interpretación:** el registro parece armado por bloques enero–agosto / setiembre–diciembre con niveles distintos. Desde 2015 ambos registros son continuos.

**El balance cierra:** Q_T / (Q_SR + Q_RQ) = 1.022, frente a una razón de áreas de 1.016.

**Requena, estiaje de 2017 erróneo:**
- baja a 958 m³/s cuando el balance y el simulado indican ~4 000 m³/s;
- se excluyen 2017-06 a 2017-08 y 11 días.

| Indicador | San Regis | Requena | Tamshiyacu |
|---|---|---|---|
| Años con dato válido | 26.1 | 22.9 | 41.1 |
| % vacíos | 4.57 | 2.57 | 0.46 |
| NSE diario | 0.58 | 0.83 | 0.60 |
| KGE diario (IC 95 %) | 0.79 [0.75, 0.82] | 0.92 [0.89, 0.93] | 0.80 [0.77, 0.83] |
| BE vs climatología mensual | −0.41 | −0.16 | −0.65 |
| NSE mensual | 0.66 | 0.86 | 0.64 |
| RB_sim / RB_obs (IC 95 %) | 0.80 [0.74, 0.87] | 0.92 [0.86, 0.99] | 0.72 [0.68, 0.76] |
| Clasificación | apta con reservas | apta con reservas | apta con reservas |

- **Mapeo de cuantiles:** el simulado tiene los mismos extremos que el observado (en otras fechas), saltos 4–5 veces mayores el día 1 de cada mes y sesgo nulo por construcción. En Requena heredó el mínimo erróneo de 2017.
- **Decisión:** el simulado **no puede sustituir** al observado en ninguna estación.
  - Falla H1: es peor que la climatología mensual a escala diaria (BE < 0).
  - Falla H4: es 8–28 % más suave que el río y tiene 1.5–6 veces más memoria.
  - Solo es aceptable a escala mensual.
- **Anticipación (correlación de anomalías de log Q):** San Regis y Requena no muestran anticipación clara a escala diaria (máxima asociación sin desfase); el modelamiento la reexamina con variaciones diarias preblanqueadas (ver abajo).

## Uso en el modelamiento

Tamshiyacu es la estación objetivo en los cuadernos de `modelos/` (01–09); se excluyen las ventanas que cruzan un escalón de nivel y los errores eliminados aquí. San Regis y Requena se evalúan como entradas en los cuadernos 05 y 08: con la correlación preblanqueada de las variaciones diarias, San Regis se adelanta 1 día a Tamshiyacu y reduce su error de pronóstico 33–45 % a 1–3 días; Requena no lo reduce.

## Limitaciones

- La causa de los escalones, el error de Requena en 2017 y el mapeo de cuantiles son inferencias a partir de los datos. Deben confirmarse con SENAMHI o con el autor de CAMELS-PE.
- No se puede saber qué bloque de cada escalón es el correcto, por eso no se corrigió ninguno.
- Requena termina en 2020-03. Después, el balance solo puede aproximarse con el simulado, y cae a 0.83–0.84 en los estiajes de 2023–2024 sin que pueda atribuirse.
- El atributo `perimeter` es incoherente y no se usa.
- No hay ETP después de 2016 ni temperatura después de 2020.

## Autoría

- Luis Angel Cupe Espinoza (UTEC, Ingeniería Ambiental), autor de los cuadernos
- Equipo: Luis Angel Cupe Espinoza, Yely Lanasca Justiniano, Lia Kim Alcantara Tineo, Mayra Madelyn Marzano Mejia y María Fernanda Torres Carbajal
- Curso: Ciencia de Datos Ambientales, UTEC (2026).
