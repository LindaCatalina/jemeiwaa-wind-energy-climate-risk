# Informe de auditoría técnica y científica

Fecha de auditoría: 30 de agosto de 2026. Carpeta: `E:\Climatologia\Trabajo_Final`.

## Alcance y preservación

Se revisaron scripts, notebooks, CSV, PNG y los 575 NetCDF. Los archivos originales se conservaron. Todo lo añadido está en `reproducibilidad/`, `tests/`, los archivos de entorno/documentación y `resultados_reproducibles/`.

La auditoría profunda final produjo un manifiesto SHA-256 de 712 archivos científicos/documentales (5.737 GiB) en `resultados_reproducibles/auditoria/inventario_archivos.csv`. El inventario excluye `.git`, cachés, entornos y el propio directorio de salidas.

## Comprobaciones que pasan

- 575/575 NetCDF abren correctamente por cabecera.
- Los 136 archivos ERA5 anuales reconstruyen exactamente el consolidado de 12 418 días (1981-01-01 a 2014-12-31), sin huecos ni NaN.
- `wind10`, `v150_power`, `v150_log` y `rho` coinciden exactamente con sus fórmulas.
- Las 48 series `sfcWind` de los 12 modelos canónicos cubren los periodos requeridos y no contienen NaN.
- Las 48 series corregidas reproducen exactamente `v150`, potencia, potencia de planta y CF con las fórmulas del código actual.
- Las 48 series sintéticas (5.6 GiB) fueron leídas completas: no tienen NaN; potencia 0–6.12 MW; CF 0–0.90.
- Las siete pruebas automáticas actuales pasan: cuatro científicas originales, dos livianas para CI y una integración pre-bancable con datos sintéticos temporales.

## Hallazgos

### Críticos

1. **Las figuras originales de ΔCF y Δenergía están vacías.** `plots_future.py` pivota por `(model, exp)`; el histórico tiene `exp=historical` y el futuro `exp=ssp...`, por lo que no se forma ninguna pareja. Había 72 parejas válidas por modelo y escenario, pero el código creó 0. Las figuras reparadas están en `resultados_reproducibles/figuras_legacy_reparadas/`.

2. **La síntesis Weibull no conserva la media diaria.** El código usa `lambda = media/2^(1/k)` con k=2. La media resultante esperada es `Gamma(1.5)/sqrt(2)=0.626657` de la entrada; la razón observada es 0.626497. Esto reduce artificialmente el viento medio de 10.27 a 6.43 m/s en la comprobación NorESM2-MM histórica y baja el CF sintético aproximadamente de 0.63 a 0.28. Las cifras absolutas de energía sintética no deben usarse para decisión empresarial.

3. **La corrección original elimina la mediana futura mensual.** Tras el quantile mapping, `bias_correct_qm` calcula la mediana de cada serie futura completa y la desplaza a la P50 histórica de ERA5. En las 36 series futuras canónicas, la diferencia máxima respecto a esa P50 es `8.88e-16 m/s`. La neutralidad de la mediana no es una validación independiente: está impuesta por el algoritmo. Se añadió una sensibilidad sin ese recentrado.

4. **El validador actual no corre.** `model_validation.py` usa `w_al` y `e_al` sin definir y termina con `NameError`. El CSV existente fue generado por una versión anterior, no por el archivo actual.

### Altos

5. **P90 estaba invertido para la convención empresarial.** Los scripts usan `quantile(0.9)` y lo llaman P90. En energía, P90 de excedencia corresponde al cuantil bajo q10. Las nuevas tablas conservan ambos nombres explícitos.

6. **La definición de métricas cambia entre scripts.** `postproc_future_power.py`, `rebuild_metrics_future.py` y `plots_future.py` calculan P50/P90 sobre resoluciones distintas (10 minutos, diaria o anual) y algunas columnas llamadas “energía anual” contienen el total de 30 o 34 años. Esto impide comparar tablas sin conocer el script que las produjo.

7. **Falta densidad en 3 de las 48 combinaciones canónicas:** ACCESS-CM2 SSP5-8.5, CanESM5 SSP1-2.6 y MIROC6 histórico. Comparar un histórico sin densidad con un futuro con densidad mezcla cambio climático con disponibilidad de variables. La sensibilidad nueva usa densidad de referencia constante para aislar el efecto del viento.

8. **Hay viento corregido negativo en 13 series.** La potencia queda en cero bajo cut-in, por lo que no produce NaN, pero un módulo de viento negativo no es físico. La sensibilidad limita el viento a cero.

9. **La turbina del texto y la curva del código no son la misma.** La presentación indica V172-7.2 MW en modo 6.8 MW; el código usa una curva V164-8 MW escalada y comprimida. Es una aproximación académica válida si se declara, pero no una curva certificada V172.

10. **El número de modelos no es único.** `apply_bias_and_power.py` procesa los 14 mejores por RMSE; la presentación y las figuras principales usan 12; `postproc_future_power.py` actualmente sólo deja 4 modelos activos aunque existen salidas para 12. La nueva configuración fija explícitamente los 12 de la presentación.

### Medios

11. **Descargas no portables.** Los dos scripts de descarga tienen rutas absolutas de otra unidad/equipo. El descargador CMIP6 abre Zarr con `decode_times=False` y después recorta con fechas de texto, lo que produjo archivos parciales en modelos descartados. El análisis nuevo no depende de volver a descargar.

12. **63 NetCDF CMIP6 crudos no canónicos tienen cobertura incompleta**, principalmente HadGEM3-GC31-LL, KACE-1-0-G y UKESM1-0-LL. No afectan el ensamble final de 12, pero deben redescargarse antes de ampliar el estudio.

13. **La validación diaria GCM–ERA5 no mide habilidad de fase.** Un GCM libre no debe reproducir el día meteorológico observado; el RMSE diario de ~2.8 m/s no es una métrica adecuada para selección. La selección original se basó en RMSE de la climatología mensual, que sí es más coherente con el objetivo.

14. **La curva aplicada a medias diarias introduce sesgo no lineal.** La potencia de una media diaria no equivale al promedio de potencia subdiaria. Sin ERA5 horario real y una síntesis calibrada, el CF absoluto debe interpretarse como aproximación.

## Percentiles añadidos

Se generaron:

- cambio de CF por modelo;
- mediana, P10–P90 e IQR intermodelo;
- fracción de modelos con cambio no negativo;
- P50/P90 de excedencia de energía intermodelo;
- P50/P90 interanual por modelo;
- comportamiento mensual con banda P10–P90.

### Reproducción de resultados legados, 2070–2099

| Escenario | Mediana ΔCF | P10 | P90 | Modelos ΔCF ≥ 0 |
|---|---:|---:|---:|---:|
| SSP1-2.6 | −0.25 % | −5.73 % | +3.13 % | 6/12 |
| SSP2-4.5 | +0.12 % | −3.59 % | +3.68 % | 7/12 |
| SSP5-8.5 | +2.32 % | −4.16 % | +7.54 % | 9/12 |

### Sensibilidad sin recentrado futuro, 2070–2099

| Escenario | Mediana ΔCF | P10 | P90 | Modelos ΔCF ≥ 0 |
|---|---:|---:|---:|---:|
| SSP1-2.6 | −1.13 % | −8.49 % | +4.29 % | 6/12 |
| SSP2-4.5 | +4.88 % | −3.14 % | +9.25 % | 8/12 |
| SSP5-8.5 | +11.09 % | +0.28 % | +14.96 % | 10/12 |

La señal positiva de SSP5-8.5 no desaparece al retirar el recentrado; se fortalece. Sin embargo, SSP1-2.6 sigue mostrando desacuerdo fuerte. La conclusión cualitativa de “sin disminución sistemática en todos los escenarios” resiste, pero no la afirmación absoluta de ausencia de riesgo.

## Interpretación de las figuras históricas

- Los percentiles mensuales ERA5/modelo se superponen casi exactamente porque esos cuantiles son los objetivos del quantile mapping. Esa superposición comprueba el ajuste, pero no valida por sí sola proyecciones futuras.
- Las series anuales ERA5/modelo no deben coincidir año a año: los GCM no están sincronizados con la variabilidad meteorológica observada. Conviene comparar climatología, distribución, estacionalidad y tendencia, no correlación diaria/anual de fase.
- La estacionalidad es coherente en todos los productos: máximos principales alrededor de junio–julio y mínimos alrededor de septiembre–noviembre.
- Las figuras originales de cambios futuros no contenían barras. Deben reemplazarse en la presentación por las figuras reparadas o, preferiblemente, por las nuevas bandas P10–P90.

## Conclusión recomendada para la presentación

> El recurso histórico es alto y presenta una estacionalidad marcada. En el ensamble CMIP6 no aparece una degradación sistemática en los tres escenarios; la mediana es aproximadamente neutra bajo SSP1-2.6 y positiva bajo SSP2-4.5/SSP5-8.5 en la sensibilidad que conserva la señal. No obstante, la dispersión entre modelos es amplia y algunas simulaciones proyectan disminuciones. Por tanto, el resultado sugiere resiliencia climática del recurso, no una garantía de aumento.

## Antes de entregar cifras a una empresa

1. Obtener ERA5/observaciones horarias o de 10 minutos y calibrar la distribución subdiaria.
2. Usar la curva certificada V172 en modo 6.8 MW.
3. Incluir estelas, disponibilidad, pérdidas eléctricas, histéresis de cut-out y restricciones de red.
4. Calibrar α o usar perfiles verticales/mesoescala a 150 m.
5. Completar presión/temperatura o usar una estrategia homogénea de densidad.
6. Incorporar incertidumbres de medición, extrapolación, pérdidas y modelo de potencia al P90 financiero.
7. Tratar cada SSP por separado; los modelos CMIP6 no son probabilidades equiprobables.

## Control añadido para cifras empresariales

Se implementó `run_bankability.py` como flujo completamente separado. La configuración pública deja intencionalmente vacíos los insumos que no existen en el proyecto; el diagnóstico resultante es `BLOCKED_MISSING_OR_INVALID_INPUTS`, `financial_p90_calculated=false` y `bankable=false`. Por tanto, no se fabricó ni se renombró ningún percentil académico como P90 financiero.

La puerta exige serie observada/MCP de 10 minutos a altura de buje, curva certificada V172 para el modo 6.8 MW, densidad, estelas, disponibilidad, pérdidas eléctricas, desempeño, ambiente, curtailment e incertidumbres documentadas. Si todos los controles pasan, sólo produce una evaluación marcada como preliminar y pendiente de revisión de un ingeniero independiente.

## Preparación para GitHub

Se añadieron documentación navegable, `CITATION.cff`, historial de cambios, reglas de contribución, dependencias fijadas, Docker opcional, CI liviana, control de secretos/rutas y exclusión verificable de datos crudos. El repositorio local quedó inicializado en la rama `main`, sin commit ni remoto, para que los autores puedan revisar la licencia antes de publicar.

Hay 36 archivos locales mayores de 100 MiB. Los 5,74 GiB no se publican en GitHub ni se movieron o eliminaron: dos manifiestos versionados fijan las 136 solicitudes ERA5-Land y los 215 `zstore` CMIP6 para reconstruirlos desde sus fuentes oficiales. La selección pública pesa menos de 2 MiB y un control automático impide incluir NetCDF o archivos mayores de 10 MiB.
