# EDA del Chancay-Lambayeque con CAMELS-PE: calidad del caudal observado y utilidad del simulado

Diagnóstico de datos (análisis exploratorio) del Proyecto Integrador de **Ciencia de Datos Ambientales** (UTEC, 2026), primera parte del estudio *«¿Cuánto aviso nos da un río?»*. Esta carpeta caracteriza la **cuenca andina del río Chancay-Lambayeque** (vertiente del Pacífico; Cajamarca y Lambayeque), una de las dos cuencas seleccionadas para el modelamiento.

**Pregunta del diagnóstico:** ¿qué calidad tienen los registros observados de Racarumi y Cirato, y puede el caudal simulado PISCO-ARNOVIC sustituir al observado?

| Estación | `gauge_id` CAMELS-PE | Área (km²) | Caudal observado en el archivo | Periodo utilizable |
|---|---|---|---|---|
| Racarumi | PE_200907 | 2 363.3 | 1981-01-01 a 2023-08-31 | 1981–2023 completo |
| Cirato | PE_4724D566 | 1 611.9 | 2008-11-28 a 2025-12-31 | **2022-08-01 a 2025-12-31** (error de fechas antes; ver abajo) |

Cirato drena hacia Puente San Carlos y esta hacia Racarumi, la salida del grupo anidado. El área intermedia es el 31.8 % del área de Racarumi.

## Estructura de carpetas

```
Proyecto-CDA/                                # raíz del repositorio
├── CAMELS-PE_v1.0.1/CAMELS-PE/       # ÚNICA fuente de datos (carpeta o CAMELS-PE_v1.0.1.zip; no se sube)
└── chancay_eda/                                 # ← esta carpeta
    ├── EDA_Chancay-Lambayeque_CAMELS-PE.ipynb   # cuaderno ejecutado (secciones 0–10)
    ├── README.md
    ├── requirements.txt
    └── salidas/
        ├── figuras/                             # fig01 … fig14 (PNG)
        ├── tablas/                              # 10 tablas CSV
        └── mapa_estaciones_chancay.html
```

## Datos y origen

| Dato | Fuente |
|---|---|
| Caudal observado `flow_obs` (mm/d) | SENAMHI, distribuido en **CAMELS-PE v1.0.1** (Llauca et al., 2026; https://doi.org/10.5194/essd-2026-386) |
| Caudal simulado `flow_sim` (mm/d) | **PISCO-ARNOVIC v1.1** (Llauca et al., 2023; https://doi.org/10.1016/j.ejrh.2023.101381; https://www.hydroshare.org/resource/f723d6c762ca45b6936dd9489bc44842) |
| Forzantes y atributos | CAMELS-PE (PISCOp v2.1, PISCOt, PISCOeo_pm, ERA5-Land; `02_attributes/`, `04_geospatial/`) |

## Requisitos y ejecución

Python 3.13.16 con las versiones de `requirements.txt` (pandas 3.0.5, numpy 2.5.3, scipy 1.18.1, statsmodels 0.15.0, matplotlib 3.11.2, seaborn 0.13.2, geopandas 1.2.0, folium 0.20.0).

```bash
pip install -r requirements.txt
cd chancay_eda
jupyter nbconvert --to notebook --execute --inplace "EDA_Chancay-Lambayeque_CAMELS-PE.ipynb"
```

Detalles de la ejecución:
- **Rutas relativas:** el cuaderno se ejecuta desde `chancay_eda/`. Lee solo `../CAMELS-PE_v1.0.1/CAMELS-PE`; si esa carpeta no existe y está `../CAMELS-PE_v1.0.1.zip`, la extrae.
- **Duración:** unos 3–4 minutos, con bootstrap de 1 000 réplicas y semilla 42.

## Métodos (resumen)

1. **Inspección:** control de índice y tipos, coherencia de IDs, unidades y áreas.
2. **Independencia del simulado e integridad temporal (2.6–2.7):** coincidencias exactas de valores, desfase anual obs–sim y entre estaciones, ventanas móviles de 120 días y regla automática para el inicio del periodo con fechas confiables.
3. **Balance entre estaciones (2.8):** en el periodo confiable.
4. **Faltantes y outliers:**
   - Las métricas usan solo días pareados y nunca se rellena el observado.
   - La detección usa IQR y z robusto (MAD) sobre log(Q + ε), con ε = media/100.
   - Solo se eliminan puntos con corroboración física: caída aislada, pico aislado sin lluvia o nivel bajo extremo.
5. **Obs vs sim:** NSE, KGE (r, α, β), PBIAS, RMSE, NSE-log, BE frente a la climatología mensual y FHV/FMS, con IC 95 % por bootstrap de bloques mensuales. Además: sensibilidad, homogeneidad, régimen y época.
6. **Hipótesis H1–H4:** criterios fijados a priori y una regla de decisión sobre el uso del simulado.

## Resultados principales

**Racarumi es una serie de alta calidad:**
- 42.5 años de dato válido y 0.32 % de vacíos;
- homogénea en 1981–2023;
- bien fechada: desfase observado–simulado estable de −1 día en todo el registro.

**Cirato tiene un error de fechas en 2009–2022:**
- su desfase crece ~1 día por año, hasta 12 días;
- fechas confiables solo desde 2022-08-01;
- la lluvia lo confirma sin usar el simulado: antes de esa fecha, el caudal responde a la lluvia con 12 días de retraso; después, con 2.

| Indicador | Cirato (2022-08 → 2025) | Racarumi (1981–2023) |
|---|---|---|
| % vacíos | 1.04 | 0.32 |
| Errores eliminados | 0 | 15 |
| NSE diario | 0.73 | 0.73 |
| KGE diario (IC 95 %) | 0.77 [0.61, 0.88] | 0.87 [0.83, 0.88] |
| BE vs climatología mensual | 0.45 | 0.52 |
| PBIAS mensual | +16.9 % | +0.6 % |
| RB_sim / RB_obs (IC 95 %) | 0.72 [0.63, 0.81] | 0.58 [0.55, 0.60] |
| Clasificación | apta con reservas (solo periodo confiable) | apta |

- **Decisión:** el simulado **no puede sustituir** al observado.
  - Cirato falla H1 (sesgo de +17 %) y H4.
  - Racarumi cumple H1, pero falla H4: es 42 % más suave que el río.
- **Mapeo de cuantiles:** el máximo simulado es idéntico al máximo observado, pero ocurre en otra fecha (2023-03 frente a 2022-03).
- **Balance entre estaciones:** Racarumi lleva apenas 7 % más agua que Cirato, aunque drena 47 % más área. Hay captaciones o pérdidas entre ambas.
- **Anticipación:** Cirato no anticipa a Racarumi a escala diaria. La lluvia anticipa ~2 días.

## Uso en el modelamiento

Racarumi es la estación objetivo de la cuenca en los cuadernos de `modelos/` (01–09). Cirato se evalúa solo de forma exploratoria (cuadernos 05 y 07): con 13 meses de fechas confiables en común con Racarumi no admite entrenamiento ni validación. Los errores eliminados aquí (`salidas/tablas/tabla_outliers_eliminados.csv`) son los que usa el modelamiento.

## Limitaciones

- La causa del error de Cirato y el mapeo de cuantiles son inferencias a partir de los datos. Deben confirmarse con SENAMHI o con el autor de CAMELS-PE.
- El periodo común confiable en CAMELS-PE es de solo 13 meses, porque Racarumi termina el 2023-08-31.
- No se puede atribuir a una causa la diferencia de caudal entre estaciones, porque no se registra la operación de captaciones ni presas.
- El atributo `perimeter` de Racarumi (7 422 km) es incoherente y no se usa.

## Autoría

- Luis Angel Cupe Espinoza (UTEC, Ingeniería Ambiental), autor de los cuadernos
- Equipo: Luis Angel Cupe Espinoza, Yely Lanasca Justiniano, Lia Kim Alcantara Tineo, Mayra Madelyn Marzano Mejia y María Fernanda Torres Carbajal
- Curso: Ciencia de Datos Ambientales, UTEC (2026).
