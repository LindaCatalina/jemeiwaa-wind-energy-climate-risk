# Metodología

## 1. Caso de estudio

El análisis representa una planta virtual de 162 turbinas de 6,8 MW
(1.101,6 MW) en el entorno de Jemeiwaa Ka'I, La Guajira. La configuración es
académica y no contractual.

Periodos:

- histórico: 1981–2014;
- futuro medio: 2040–2069;
- futuro lejano: 2070–2099.

Escenarios: SSP1-2.6, SSP2-4.5 y SSP5-8.5.

## 2. Referencia y ensamble

ERA5-Land aporta viento a 10 m, temperatura a 2 m y presión superficial. El
ensamble contiene 12 GCM CMIP6 fijados explícitamente en
`reproducibilidad/config.py`; no se cambia automáticamente cuando aparecen
nuevos archivos.

La validación histórica compara climatología, dispersión y estacionalidad. No
se exige coincidencia año a año: la variabilidad interna de un GCM no está
sincronizada con la meteorología observada por ERA5-Land.

## 3. Corrección de sesgo

Se comparan dos tratamientos:

1. **Método original con recentrado futuro.** Reproduce la lógica en la cual la
   mediana mensual futura se desplaza hacia la P50 histórica de ERA5-Land.
2. **Método principal sin recentrado.** Usa quantile mapping mensual con colas
   aditivas, limita velocidades negativas a cero y conserva la señal de cambio
   de cada simulación.

El segundo se utiliza para las conclusiones. El primero se conserva para medir
sensibilidad metodológica, porque el recentrado reduce parte de la señal
climática por construcción.

## 4. Altura de buje y densidad

El viento se extrapola de 10 a 150 m mediante:

```text
v150 = v10 × (150 / 10)^0,14
```

La densidad se obtiene de presión y temperatura cuando está disponible. En las
combinaciones sin densidad se usa `1,225 kg/m³`, hecho registrado como
limitación.

## 5. Integración subdiaria corregida

La potencia es no lineal, por lo que no debe calcularse directamente a partir
de una velocidad media diaria. La síntesis inicial tampoco era válida: para
una Weibull con `k = 2` usaba una escala que producía una razón esperada

```text
Γ(1 + 1/k) / √2 = Γ(1,5) / √2 ≈ 0,6267
```

respecto a la media objetivo. La auditoría encontró aproximadamente 0,6265.
Esto explica el CF histórico cercano a 0,28 de la presentación inicial.

La corrección actual construye 144 puntos medios de probabilidad:

```text
pᵢ = (i + 0,5) / 144
xᵢ = [−ln(1 − pᵢ)]^(1/k)
mᵢ = xᵢ / promedio(x)
vᵢ,día = viento_medio_día × mᵢ
```

Por definición, `promedio(m) = 1`; por tanto, el promedio de los 144 estados
es exactamente el viento medio diario. No hay semilla ni ruido Monte Carlo.

Estos estados sirven para integrar la curva de potencia; no son una serie
temporal observada ni permiten estudiar rampas, turbulencia o autocorrelación.

## 6. Potencia, CF y energía equivalente

Se conserva la aproximación académica original: curva V164-8 MW escalada a
6,8 MW, comprimida hacia un plateau cercano a 12 m/s, ajuste de densidad y 10 %
de pérdidas genéricas.

```text
CF diario = promedio(potencia de los 144 estados) / 6,8 MW
CF anual = promedio de los CF diarios del año
Energía equivalente = CF anual × 1.101,6 MW × 8.760 h
```

Las 8.760 horas estandarizan calendarios CMIP6 de diferente longitud. La
energía es un equivalente académico y no una producción contractual.

## 7. Incertidumbre

Para cada modelo se calculan medias climatológicas históricas y futuras. El
cambio relativo es:

```text
ΔCF (%) = 100 × (CF_futuro / CF_histórico − 1)
```

Luego se obtienen P10, P50 y P90 entre los 12 modelos, además de la fracción de
modelos con cambio no negativo. Las bandas describen el *spread* del ensamble;
no son intervalos probabilísticos calibrados.

La energía académica incluye cuantiles entre años y modelos para trazabilidad,
pero no se presenta como P90 financiero.

## 8. Resultados de control

- La media diaria del viento se conserva a precisión numérica.
- El CF permanece entre 0 y 0,9 por la pérdida académica del 10 %.
- La mediana histórica del método principal es 0,453.
- El P50 mensual histórico varía aproximadamente de 0,28 a 0,53.
- Las cinco figuras se regeneran desde los CSV sin NetCDF.

## 9. Diagnóstico histórico de la corrección

La figura `05_validacion_correccion_sesgo.png` compara P10, P50 y P90 diarios
por mes. Para CMIP6 se calcula primero cada cuantil en cada modelo y después se
toma la mediana entre los 12 modelos, otorgándoles el mismo peso.

El RMSE por modelo utiliza 36 estadísticas climatológicas
(`12 meses × P10/P50/P90`). No se emparejan días ni años de ERA5-Land con años
de los GCM. El error corregido casi nulo es esperable porque esos cuantiles
históricos son objetivos explícitos de la calibración. Es un diagnóstico del
ajuste histórico, no una prueba fuera de muestra ni validación predictiva.
