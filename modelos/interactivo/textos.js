// Textos de lectura: frases cortas y concretas con los resultados del estudio.
// Si cambian los resultados, actualizar aquí las cifras (las tarjetas, KPI y gráficos se leen de los datos).
window.TX = {
  // ── Visión general
  s_respuestas: [
    '<b>P1 · Horizonte útil:</b> Racarumi 6 días; Tamshiyacu 30 días o más. El río pesa más que el modelo.',
    '<b>P2 · Avisos:</b> Racarumi no alcanza el criterio (12 de 32 crecidas, 54 % de falsas alarmas). Tamshiyacu avisa 3 de 3 con 3 días, pero son muy pocos eventos.',
    '<b>P3 · Aguas arriba:</b> San Regis reduce el error 33–45 % a 1–3 días. Requena y Cirato no muestran mejora.',
    '<b>P4 · Lluvia:</b> reduce el error 12–27 % a 1–3 días en Racarumi, solo si se conoce la del mismo día.',
    '<b>P5 · Chronos-2:</b> gana en validación en Racarumi, pero no se sostiene en la prueba.',
    '<b>P6 · Selección final:</b> Q · Chronos-2 en Racarumi y Q · KNN en Tamshiyacu. Ninguna coincide con la mejor de la prueba.'],
  s_mensaje: [
    'Tamshiyacu da cerca de <b>un mes</b> de pronóstico útil; Racarumi, alrededor de <b>una semana</b>.',
    'Agregar información (San Regis, lluvia del mismo día) mejora la <b>primera semana</b>.',
    'Con la validación disponible no se logra elegir esas mejoras de forma confiable.',
    'Para avisar con más tiempo harían falta <b>pronósticos de lluvia</b>, estaciones más lejanas y <b>más eventos</b>.'],
  s_magnitud: [
    'En los seis casos, lo elegido en validación <b>no es lo mejor</b> en la prueba.',
    'Racarumi: Q · Chronos-2 (0.490) frente a Q+P+IA · LSTM (0.541), que usa la lluvia del mismo día.',
    'Tamshiyacu: Q · KNN (0.906) frente a Q+P+SR · MLP, apenas mejor (+0.016).',
    'Muchos candidatos quedan empatados o sin diferencia clara: la elección es poco nítida.'],
  s_avisos: [
    'Racarumi: se eligen Q+P · KNN (mismo día) y Q · Random Forest (un día de retraso). <b>Ninguno cumple</b> en la prueba.',
    'Tamshiyacu: no se elige un sistema de avisos; los eventos no alcanzan para decidir.',
    'Estimar bien el caudal <b>no basta</b> para avisar una crecida.'],
  limites: [
    '<b>Pocos eventos:</b> Tamshiyacu tiene 3 crecidas en la prueba; Cirato, 13 meses de datos confiables.',
    '<b>Prueba ya consultada:</b> no decide nada, pero no es totalmente independiente.',
    '<b>P95 ≠ inundación:</b> es un umbral estadístico de caudal alto, no un daño.',
    '<b>Datos del mismo día:</b> se supone que la lluvia y San Regis estarían disponibles; no está demostrado.',
    '<b>No es un sistema de alerta:</b> es una evaluación retrospectiva con datos depurados.'],

  // ── P1 · comparación entre ríos
  p1_rios: [
    'En las mismas fechas: <b>6 días</b> en Racarumi y <b>22 días</b> en Tamshiyacu.',
    'Probabilidad de que Tamshiyacu tenga mayor horizonte: <b>0.87</b>.',
    'Con cualquier modelo: 4–6 días en Racarumi y 17–27 días en Tamshiyacu.',
    'Después de la primera semana Racarumi apenas supera a la climatología: de ahí la incertidumbre.'],
  p1_crecidas: [
    'El desempeño cae con el horizonte en los dos ríos.',
    'Racarumi <b>subestima</b> los caudales altos, y más cuanto mayor es el plazo (−11 % a 1 día, −39 % a 7).',
    'Tamshiyacu: error relativo pequeño, pero de cientos a miles de m³/s; solo 3 crecidas.'],
  p1_estabilidad: [
    'Tamshiyacu es estable: 30 días o más en todos los periodos evaluables.',
    'Racarumi varía de 6 a 19 días según el periodo; 2016–2023 fue el más difícil.'],
  p1_seleccion: [
    'Se elige el mayor NSE medio en 2012–2015, o el más simple si otro es equivalente.',
    'Racarumi: <b>LSTM</b>, sin ventaja demostrada sobre regresión lineal, MLP, Random Forest ni KNN.',
    'Tamshiyacu: <b>XGBoost</b>; Random Forest y KNN quedan muy cerca; la regresión lineal es peor.'],
  p1_historia: [
    'Racarumi: el caudal de hoy y la fecha bastan; más días de historia no ayudan.',
    'Tamshiyacu: la tendencia de los últimos 3 días multiplica por 4 la habilidad a 1 día.',
    'A largo plazo, la época del año aporta gran parte de la información.'],
  p1_tabla: [
    'Entre modelos las diferencias son pequeñas: a 7 días, NSE 0.44–0.52 en Racarumi y 0.96–0.97 en Tamshiyacu.',
    'En Tamshiyacu el horizonte sí separa modelos: 27 días con LSTM, 20–22 con la mayoría, 17 con regresión lineal.',
    'Entre ríos la diferencia es de otro orden: <b>el río pesa más que el modelo</b>.'],
  p1_familias: [
    'No linealidad: no ayuda en Racarumi; sí en Tamshiyacu.',
    'Análogos (KNN): débiles en Racarumi, buenos en Tamshiyacu por su ciclo anual regular.',
    'Random Forest y XGBoost rinden casi igual. Ninguna red neuronal domina.'],
  p1_conclusiones: [
    'Con solo el caudal, Racarumi permite <b>una semana</b> y Tamshiyacu <b>un mes</b> de pronóstico útil.',
    'Cambiar de modelo mueve el resultado pocos días; cambiar de río, semanas.',
    'Los caudales altos son el punto débil en Racarumi.'],

  // ── Estaciones
  Racarumi: {
    prueba: ['A 1 día NSE 0.85–0.86, apenas sobre la persistencia (0.84).', 'A 7 días (0.44–0.52) queda cerca de la climatología.', 'A 30 días ningún modelo supera a la climatología.', 'Sesgo total pequeño.'],
    seleccion: ['La LSTM tiene el mayor NSE medio (0.560).', 'Regresión lineal, MLP, Random Forest y KNN: diferencia no demostrada.', 'Solo XGBoost es claramente peor.', 'La regresión lineal es una alternativa más simple y estable.'],
    ajuste: ['NSE medio en validación: de 0.531 (XGBoost) a 0.561 (LSTM).', 'Las diferencias pequeñas no se atribuyen solo al algoritmo.'],
    horizonte: ['<b>6 días</b> con la LSTM; 4–6 según el modelo.', 'Calidad suficiente (NSE ≥ 0.5) hasta 5–7 días.', 'Después de una semana, la ventaja sobre la climatología es pequeña.'],
    comun: ['En las 2 373 fechas comunes con Tamshiyacu el resultado se mantiene: 6 días.'],
    crecidas: ['Los días altos se pronostican peor y se <b>subestiman</b> (−11 % a 1 día, −39 % a 7).', 'Error medio a 1 día: 42 m³/s en días altos frente a 6 en días normales.', 'Mejora pequeña sobre la persistencia.'],
    picos: ['2022 y 2023: el pico se pronosticó ~45 % por debajo y el máximo llegó un día tarde.', 'Causa probable: el caudal de hoy aún no refleja la lluvia que inicia la crecida.'],
    eventos: ['Todos los picos quedan subestimados (≈ −43 % a 1 día).', 'El modelo repite el pico <b>h días después</b> de ocurrido.'],
    estabilidad: ['LSTM: 19, 10, 11 y 6 días según el periodo.', '2016–2023 es el periodo más difícil: 6 días no es un valor fijo de la estación.'],
    sensibilidad: ['Esta estación no tiene escalones de nivel: el análisis no aplica.'],
    memoria: ['Con el caudal de hoy y la fecha ya alcanza su habilidad.', 'Sin calendario, el NSE a 30 días cae de 0.45 a 0.19.'],
    importancia: ['Lo más usado: el <b>nivel de hoy</b>.', 'La época del año gana peso con el plazo.', 'Mide el uso del modelo, no causas.'],
    conclusiones: ['Pronóstico útil de la magnitud: <b>unos 6 días</b> (4–6 según el modelo).', 'Calidad suficiente hasta 5–7 días.', 'Los picos se <b>subestiman</b> y llegan tarde.', 'Usa sobre todo el nivel de hoy y la época del año.', 'Río rápido: sin conocer la lluvia, el aviso es corto.']
  },
  Tamshiyacu: {
    prueba: ['A 1 día NSE 0.999; en m³/s la mejora sobre la persistencia es clara.', 'A 7 días NSE 0.96–0.97.', 'A 30 días todos superan a la climatología, salvo la regresión lineal.'],
    seleccion: ['XGBoost tiene el mayor NSE medio (0.935).', 'Random Forest y KNN, muy cerca: diferencia no demostrada.', 'MLP, LSTM y regresión lineal son peores: aquí los no lineales sí ganan.'],
    ajuste: ['Configuraciones elegidas en validación; el detalle está en las tablas.'],
    horizonte: ['<b>30 días o más</b> con todos los modelos no lineales; 21 con la regresión lineal.', 'NSE ≥ 0.5 los 30 días.', '«≥ 30» significa que el límite no se encontró.'],
    comun: ['En las fechas comunes con Racarumi: 22 días.'],
    crecidas: ['Error relativo muy pequeño en días altos (menos de 1 % hasta 15 días).', 'En m³/s sí es grande: 500–800 a 7–15 días.', 'Solo 3 crecidas: cifras indicativas.'],
    picos: ['Los picos del Amazonas son mesetas de semanas.', 'El máximo se estima con un error de pocos por ciento.'],
    eventos: ['Pico estimado con un error de ~0.4 %.', 'El día exacto del máximo importa poco: el pico dura de 1 a 7 semanas.'],
    estabilidad: ['30 días o más en los tres periodos evaluables (XGBoost y LSTM).'],
    sensibilidad: ['Solo con años sin escalones: 23 días (con menos datos).', 'Con años al azar del mismo tamaño: 13–29 días. Pesa la cantidad de datos.'],
    memoria: ['La tendencia de los últimos 3 días es clave: la habilidad a 1 día pasa de 0.15 a 0.65.', 'Más historia no ayuda.'],
    importancia: ['Hasta 7 días: la <b>tendencia reciente</b>.', 'Después: el nivel de hoy y la época del año.'],
    conclusiones: ['Pronóstico útil de la magnitud: <b>30 días o más</b>.', 'Calidad suficiente en los 30 días.', 'Los modelos no lineales superan al lineal.', 'Bastan el caudal reciente y la época del año.', 'Río lento: el caudal de hoy anticipa el de semanas.']
  },

  // ── P2 · avisos
  p2_prueba: [
    'Racarumi: ningún modelo alcanza el criterio. El más cercano, Random Forest: 16 de 32, pero 60 % de falsas alarmas.',
    'Los modelos no superan con claridad a reglas simples (persistencia, tendencia de 3 días).',
    'Tamshiyacu: KNN avisa 3 de 3 sin falsas alarmas, con 3–4 días. La tendencia de 3 días logra lo mismo.'],
  p2_eventos_prueba: [
    'Racarumi: los aciertos se avisan con 1–7 días (mediana 2).',
    'El aviso indica «río alto», no la magnitud de la crecida.',
    'Tamshiyacu: crecidas de 2019, 2022 y 2025 avisadas con 3–4 días.'],
  p2_eventos: ['Racarumi: 32 crecidas nuevas evaluables en la prueba.', 'Tamshiyacu: solo 3; resultados exploratorios.'],
  p2_calibracion: [
    'La regla se ajusta en 2009–2011: en Racarumi conviene avisar al 80 % del P95.',
    'Modelo para avisos: MLP en Racarumi, KNN en Tamshiyacu.',
    'El mejor modelo para la magnitud no es el mejor para avisar.'],
  p2_sensibilidad: ['Cambiar las reglas de verificación no cambia la conclusión.'],
  p2_comun: ['En las fechas comunes el resultado es el mismo.'],
  p2_limites: ['El P95 es un umbral estadístico, no oficial.', 'Tamshiyacu tiene muy pocas crecidas.', 'Es una evaluación retrospectiva.'],
  p2_conclusiones: [
    'Estimar bien el caudal <b>no basta</b> para avisar una crecida.',
    'Racarumi: señal de «río alto» con 1–2 días; no cumple el criterio.',
    'Tamshiyacu: 3 días de aviso, pero con solo 3 eventos.',
    'Una regla simple (tendencia de 3 días) rinde igual que los modelos.'],

  // ── P3 · aguas arriba
  p3_prueba: [
    'San Regis reduce el error de los seis modelos: <b>33–45 %</b> a 1–3 días y 18–25 % a 4–7.',
    'Con un día de retraso: 7–22 %.',
    'Requena no reduce el error; con Random Forest y KNN lo aumenta.'],
  p3_desfase: ['San Regis va <b>1 día adelante</b>; físicamente plausible (1.5–2.3 m/s).', 'Requena no anticipa a Tamshiyacu.'],
  p3_validacion: ['La validación ya anticipaba el aporte de San Regis (25–37 % a 1–3 días).', 'En el promedio de 30 días la ganancia es pequeña: se mantiene Q · KNN.'],
  p3_crecidas: ['En días normales San Regis reduce el error de todos los modelos.', 'En días altos no hay un patrón claro (3 crecidas).'],
  p3_cruces: ['El efecto en los avisos no se puede evaluar: solo 3 crecidas en la prueba.'],
  p3_cirato: ['Cirato y Racarumi cambian el mismo día: no anticipa.', 'Sin mejora demostrada (13 meses de datos confiables).'],
  p3_conclusiones: [
    'San Regis mejora la <b>primera semana</b> del pronóstico.',
    'Su aporte depende de tener el dato <b>del mismo día</b>.',
    'El horizonte útil casi no cambia: ya era de 30 días o más.',
    'Requena y Cirato no aportan.'],

  // ── P4 · lluvia
  p4_prueba: [
    'Racarumi: <b>12–27 % menos error</b> a 1–3 días con la lluvia del mismo día.',
    'Con un día de retraso el beneficio casi desaparece.',
    'Tamshiyacu: 2–18 % menos error según el modelo y el plazo (salvo KNN).'],
  p4_balance: ['Escorrentía/lluvia: 0.43 en Racarumi y 0.54 en Tamshiyacu.', 'El río responde 1 día después en Racarumi y ~6 días en Tamshiyacu.'],
  p4_crecidas: [
    'Racarumi: menos error en caudales altos a 1 día (de ~42 a ~28 m³/s) y menos subestimación.',
    'A 7 días no cambia.',
    'Tamshiyacu: la lluvia empeora los caudales altos desde 3 días.'],
  p4_avisos: [
    'Con la lluvia del mismo día, varios modelos logran <b>1 día</b> de aviso útil en Racarumi; con su incertidumbre, solo XGBoost.',
    'Con un día de retraso, ninguno.'],
  p4_idealizado: [
    'Conociendo la lluvia futura: <b>62–69 % menos error</b> en Racarumi.',
    'Avisos de alrededor de una semana para parte de las crecidas.',
    'Es un potencial: un pronóstico real de lluvia tiene error.'],
  p4_conclusiones: [
    'La lluvia ayuda solo si llega <b>a tiempo</b> (el mismo día).',
    'Racarumi gana en los primeros días; Tamshiyacu, en las semanas 2–4.',
    'El mayor potencial está en <b>pronosticar la lluvia</b>.'],

  // ── P5 · Chronos-2
  p5_probabilistico: [
    'Bandas P10–P90: cubren 77–79 % en Racarumi (ideal 80 %).',
    'En días sobre el P95, solo 42–57 %: <b>fallan en las crecidas</b>.',
    'En Tamshiyacu las bandas son estrechas a 1 día (62 %).',
    'Su error probabilístico es 31–52 % menor que el de la persistencia.'],
  p5_contexto: ['Racarumi necesita mucha historia: 2 048 días (≈ 5.6 años).', 'Tamshiyacu no distingue contextos en validación: se eligió 512 días.'],
  p5_sensibilidad: ['Con 2 048 días Tamshiyacu mejoraría: NSE medio 0.854 → 0.899 y horizonte 18 → 25 días.', 'En el Amazonas el contexto debe abarcar varios años.'],
  p5_idealizado: ['Con la lluvia futura conocida reduce su error 45–67 % en Racarumi.'],
  p5_conclusiones: [
    'Funciona sin entrenar con estos ríos, pero <b>no supera</b> a los modelos entrenados en la prueba.',
    'Sus bandas sirven en días normales, no en crecidas.',
    'Necesita contextos largos.'],

  // ── P6 · selección final
  p6_validacion: ['Se compararon <b>196 candidatos</b> (28 combinaciones de entradas × 7 familias) en las mismas fechas.', 'Se elige en 2012–2015; muchos quedan empatados o sin diferencia clara.'],
  p6_prueba: [
    'Racarumi: lo elegido (Q · Chronos-2) cae a 0.490; 10 de 20 candidatos son mejores.',
    'Tamshiyacu: Q · KNN (0.906), casi igual al mejor (+0.016).',
    'Con la misma familia, las fuentes externas reducen el error de corto plazo.'],
  p6_avisos: ['Racarumi: Q+P · KNN (mismo día) y Q · Random Forest (retraso); no cumplen en la prueba.', 'Tamshiyacu: muy pocos eventos para elegir.'],
  p6_conclusiones: [
    'Elegir solo con validación es lo correcto, pero <b>no recupera</b> las mejoras que se ven en la prueba.',
    'Ninguna elección coincide con la mejor de la prueba.',
    'Todas las verificaciones de calidad fueron correctas.'],

  // ── Método
  controles: [
    '<b>Sin información futura:</b> todo se ajusta con el pasado de cada emisión.',
    '<b>La prueba no decide:</b> se elige en validación (2012–2015) y la prueba solo confirma.',
    '<b>Verificaciones automáticas</b> antes de cada resultado, incluida una prueba con datos aleatorios.',
    '<b>Mismas fechas</b> para comparar modelos y fuentes.']
};
