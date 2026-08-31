# Procesamiento CMIP6

Esta carpeta contiene el código que corrige y transforma los modelos CMIP6,
además de factores de sesgo y tablas intermedias pequeñas. Los NetCDF y las
figuras exploratorias no se publican; la galería final está en
`../results/figures/`.

Puntos de entrada:

- `bias_eval_cmip6.py`: calcula cuantiles mensuales ERA5–CMIP6;
- `prepare_bias_corrected_inputs.py`: prepara viento y densidad diarios del
  método con recentrado, sin calcular CF directamente;
- `../scripts/rebuild_figures.py`: regenera la galería desde CSV públicos;
- `../scripts/run_analysis.py`: recalcula resultados con los NetCDF locales;
- `../scripts/run_full_rebuild.py`: reconstruye todo desde las fuentes.

Consulte [Metodología](../docs/METODOLOGIA.md),
[Datos](../docs/DATOS.md) y [Limitaciones](../docs/LIMITACIONES.md).
