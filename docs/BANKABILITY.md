# De resultados académicos a una evaluación pre-bancable

## Distinción obligatoria

Los percentiles climáticos existentes describen la dispersión del ensamble CMIP6 y la variabilidad interanual simulada. Sirven para evaluar robustez frente al cambio climático, pero no son una distribución financiera de incertidumbre.

Las cifras absolutas de energía deben seguir rotuladas como **académicas, no bancables**. Un P90 financiero requiere, como mínimo:

- viento observado horario o de 10 minutos, con control de calidad, campaña y correlación de largo plazo documentadas;
- curva certificada de la V172 para el modo exacto de 6.8 MW y densidad de referencia;
- disposición real del parque y modelación de estelas;
- disponibilidad contractual y técnica;
- pérdidas eléctricas;
- pérdidas por desempeño, ambiente y restricciones/curtailment;
- incertidumbres de medición, corrección de largo plazo, extrapolación vertical y modelo de potencia;
- revisión independiente de hipótesis, correlaciones y contratos.

## Uso de la puerta de calidad

1. Copie `bankability/config.example.json` como `bankability/config.local.json`.
2. Guarde insumos autorizados bajo las carpetas privadas ignoradas por Git.
3. Complete todas las fracciones como valores entre 0 y 1; por ejemplo, 2 % se escribe `0.02`.
4. Ejecute:

   ```bash
   python run_bankability.py --config bankability/config.local.json
   ```

Si falta algo, el proceso termina sin un P90 y actualiza `estado_bancabilidad.json`. La opción `--status-only` permite usar la configuración pública para comprobar ese bloqueo esperado sin marcar error en automatización.

Con `config.local.json`, la salida predeterminada es `bankability/private_outputs/`, también ignorada por Git, para no filtrar información contractual. Use `--output` sólo si ha revisado qué metadatos puede publicar.

## Esquema de viento

El CSV configurado en `wind_resource.time_series_csv` debe incluir:

| Columna | Unidad/forma | Uso |
|---|---|---|
| `timestamp_utc` | ISO-8601 UTC | Orden, cadencia y agrupación anual |
| `wind_speed_hub_m_s` | m/s | Curva de potencia a altura de buje |
| `wind_direction_deg` | grados [0,360) | Trazabilidad direccional/estelas |
| `air_density_kg_m3` | kg/m³ | Normalización de densidad |

La validación exige timestamps únicos, cadencia mediana de 10 minutos, al menos 90 % de intervalos regulares/completos y cerca de diez años en la serie MCP de largo plazo. La campaña observada declarada debe ser de al menos 12 meses y la referencia de largo plazo de al menos diez años.

## Esquema de curva certificada

El CSV debe contener `wind_speed_m_s` y `power_kw`, con velocidades estrictamente crecientes, al menos 20 puntos y cobertura 3–25 m/s. `certificate_document` debe identificar la fuente certificada y `reference_air_density_kg_m3` su densidad.

La curva proxy V164 escalada del análisis académico nunca se reutiliza en este módulo.

## Pérdidas e incertidumbres

Cada pérdida contiene `mean_fraction`, `std_fraction` y `evidence`. Se separan estelas, disponibilidad, pérdidas eléctricas, desempeño de turbina, ambiente y restricciones. Las incertidumbres se expresan como desviaciones estándar fraccionales.

Si todos los controles pasan, la simulación remuestrea los años de recurso, muestrea pérdidas y propaga las incertidumbres declaradas. Reporta P90 de excedencia como el cuantil 10, P50 como el cuantil 50 y genera una curva de excedencia. Por diseño el estado final sigue siendo `PRELIMINARY_REQUIRES_INDEPENDENT_ENGINEER_REVIEW`, nunca `BANKABLE`.

## Referencias metodológicas

- [IEC 61400-12-1:2022 — medición del desempeño de potencia](https://webstore.iec.ch/en/publication/68499).
- [NREL — Wind Plant Preconstruction Energy Estimates](https://docs.nrel.gov/docs/fy16osti/64735.pdf): categorías de pérdidas y tablas P50/P90.
- [NREL — Wind Plant Performance Prediction](https://www.nrel.gov/docs/fy22osti/78715.pdf).
- [Vestas — V172-7.2 MW](https://www.vestas.com/en/energy-solutions/onshore-wind-turbines/enventus-platform/V172-7-2-MW).
