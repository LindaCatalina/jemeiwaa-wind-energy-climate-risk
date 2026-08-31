# Limitaciones y uso responsable

## Lo que sí responde el estudio

- dirección y magnitud aproximada de cambios relativos del recurso;
- desacuerdo entre 12 modelos CMIP6;
- sensibilidad al tratamiento del sesgo futuro;
- estacionalidad y persistencia cualitativa del recurso;
- coherencia matemática entre CF y energía equivalente.

## Lo que no responde

### No es un estudio bancable

Las cifras absolutas de energía son académicas. Para un P90 financiero se
requieren, como mínimo:

- viento observado horario o de 10 minutos y control de calidad de campaña;
- correlación de largo plazo con una referencia observacional;
- curva V172 certificada para densidad y condiciones del sitio;
- modelo de estelas y pérdidas por disposición del parque;
- disponibilidad, pérdidas eléctricas, curtailment y restricciones;
- incertidumbres de medición, extrapolación y curva de potencia;
- propagación probabilística trazable y revisión independiente.

Por tanto, `P90_exceedance_GWh` en las tablas significa únicamente el q10
empírico del conjunto académico. No es una garantía de financiación.

### Resolución temporal

CMIP6 se procesa a frecuencia diaria. Los 144 estados Weibull/día integran la
no linealidad de la curva, pero no reproducen secuencia temporal, turbulencia,
rampas ni eventos de parada. No sustituyen observaciones subhorarias.

### Curva de potencia

La curva es una aproximación V164-8 MW escalada a 6,8 MW, no la curva oficial
certificada de una V172. El 10 % de pérdidas es genérico.

### Corrección de sesgo

El quantile mapping supone que la relación de sesgo histórica sigue siendo
informativa en el futuro. La comparación con/sin recentrado muestra que el
resultado depende de esa decisión, especialmente en SSP2-4.5 y SSP5-8.5.

### Ensamble CMIP6

- Los 12 modelos no son independientes ni equiprobables.
- P10/P50/P90 describen dispersión, no probabilidades calibradas.
- Los SSP son narrativas separadas, no probabilidades de ocurrencia.
- Un punto de rejilla no representa micrositing ni topografía a escala de parque.
- Los años de un GCM no están sincronizados con ERA5-Land; no debe interpretarse
  la correlación anual como habilidad predictiva meteorológica.

### Densidad

Cuando presión/temperatura no estaban disponibles se utilizó densidad de
referencia. Esto afecta más las cifras absolutas que los cambios relativos.

## Interpretación recomendada

La evidencia sugiere que no existe una señal robusta de degradación común a
todos los escenarios y modelos. SSP5-8.5 tiene una mediana positiva en el
método principal, pero su banda incluye valores negativos. El resultado apoya
una lectura de resiliencia potencial del recurso, no una garantía de mejora.

