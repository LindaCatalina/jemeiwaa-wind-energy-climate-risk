# Resumen de ejecución reproducible

Los archivos originales no fueron sobrescritos. Todas las tablas y figuras de esta ejecución están dentro de este directorio.

## Integridad

- Archivos inventariados: 712 (5.737 GiB).
- NetCDF abiertos por cabecera: 575; errores: 0.
- ERA5: 12418 días, 1981-01-01 a 2014-12-31; fórmulas exactas: True.
- Series corregidas canónicas: 48; fórmulas reproducidas: True.
- Combinaciones sin densidad: 3.
- Series con viento corregido negativo: 13.
- Conservación de media en síntesis Weibull: False (razón observada 0.626497).
- Fallos fatales de integridad: 0.

## Resultados generados

- `figuras_legacy_reparadas/`: las dos figuras vacías reconstruidas con los mismos datos sintéticos legados.

### legado

- SSP126 lejano: mediana ΔCF=-0.25 %, P10–P90=[-5.73, 3.13] %, 6/12 modelos no negativos.
- SSP245 lejano: mediana ΔCF=0.12 %, P10–P90=[-3.59, 3.68] %, 7/12 modelos no negativos.
- SSP585 lejano: mediana ΔCF=2.32 %, P10–P90=[-4.16, 7.54] %, 9/12 modelos no negativos.
- SSP126 medio: mediana ΔCF=0.28 %, P10–P90=[-0.86, 3.86] %, 6/12 modelos no negativos.
- SSP245 medio: mediana ΔCF=0.15 %, P10–P90=[-2.72, 1.82] %, 6/12 modelos no negativos.
- SSP585 medio: mediana ΔCF=-1.10 %, P10–P90=[-3.52, 2.05] %, 4/12 modelos no negativos.

### sensibilidad_sin_recentrado

- SSP126 lejano: mediana ΔCF=-1.13 %, P10–P90=[-8.49, 4.29] %, 6/12 modelos no negativos.
- SSP245 lejano: mediana ΔCF=4.88 %, P10–P90=[-3.14, 9.25] %, 8/12 modelos no negativos.
- SSP585 lejano: mediana ΔCF=11.09 %, P10–P90=[0.28, 14.96] %, 10/12 modelos no negativos.
- SSP126 medio: mediana ΔCF=-0.21 %, P10–P90=[-2.87, 5.02] %, 6/12 modelos no negativos.
- SSP245 medio: mediana ΔCF=4.64 %, P10–P90=[-5.40, 6.13] %, 8/12 modelos no negativos.
- SSP585 medio: mediana ΔCF=7.13 %, P10–P90=[-0.66, 10.50] %, 10/12 modelos no negativos.

## Lectura correcta de P90

En energía, P90 de excedencia es el cuantil bajo q10: un valor que se supera en aproximadamente 90 % de la muestra empírica. Los modelos CMIP6 no constituyen probabilidades equiprobables; por eso aquí P10/P50/P90 describen *spread* intermodelo y no una garantía financiera.

## Alcance financiero

Las cifras absolutas de energía de este flujo son académicas, no bancables. Para un P90 financiero hacen falta viento observado horario/10-min, curva V172 certificada, estelas, disponibilidad, pérdidas eléctricas y propagación trazable de incertidumbres. `run_bankability.py` valida esos insumos en un flujo separado y se niega a calcular si están incompletos.
