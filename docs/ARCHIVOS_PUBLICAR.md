# Lista de control de archivos públicos

Esta lista sirve para revisar la pestaña **Changes** de GitHub Desktop antes del
primer commit. No sustituye `.gitignore`: describe qué debe verse y qué no.

## Carpetas que sí deben aparecer

| Carpeta | Contenido público | Razón |
|---|---|---|
| `.github/workflows/` | `ci.yml` | Ejecuta los controles automáticos |
| `bankability/` | código y configuración de ejemplo | Separa el análisis académico del P90 financiero |
| `CMIP6_Guajira/` | scripts funcionales, notebooks y CSV pequeños | Conserva trazabilidad sin publicar código sustituido |
| `data/` | dos manifiestos CSV y README | Permite volver a descargar las fuentes |
| `Datos_Era5/` | scripts, notebook y README | Reconstruye y explica ERA5-Land |
| `docs/` | guías técnicas y de publicación | Evita sobrecargar el README principal |
| `reproducibilidad/` | auditoría y percentiles | Es la capa científica canónica |
| `resultados_reproducibles/` | tablas y cuatro figuras curadas | Muestra resultados verificables |
| `scripts/` | descarga y validación | Automatiza fuentes y controles |
| `tests/` | pruebas automáticas | Demuestra calidad del código |

## Archivos de la raíz que sí deben aparecer

- `.dockerignore`
- `.gitattributes`
- `.gitignore`
- `CHANGELOG.md`
- `CITATION.cff`
- `CONTRIBUTING.md`
- `Dockerfile`
- `INFORME_AUDITORIA.md`
- `README.md`
- `environment.yml`
- `pyproject.toml`
- `requirements.txt`
- `requirements-download.txt`
- `run_bankability.py`
- `run_full_rebuild.py`
- `run_portfolio.py`
- `run_reproducible.py`

## Únicas figuras públicas

1. `resultados_reproducibles/legado/figuras/01_cambio_cf_percentiles.png`
2. `resultados_reproducibles/sensibilidad_sin_recentrado/figuras/01_cambio_cf_percentiles.png`
3. `resultados_reproducibles/sensibilidad_sin_recentrado/figuras/03_energia_p50_p90.png`
4. `resultados_reproducibles/sensibilidad_sin_recentrado/figuras/04_cf_mensual_percentiles.png`

No son repeticiones: muestran respectivamente el resultado legado, la
sensibilidad metodológica, los percentiles académicos de energía y el ciclo
mensual.

## Contenido que no debe aparecer

- cualquier `*.nc`, `*.nc4`, GRIB, Zarr o archivo comprimido de datos;
- `.venv`, `__pycache__`, `.pytest_cache` y `*.pyc`;
- `.env`, `.cdsapirc`, claves o certificados;
- `bankability/private_*`;
- las figuras PNG originales de `CMIP6_Guajira`;
- `resultados_reproducibles/figuras_legacy_reparadas`;
- figuras 02 redundantes y figuras legadas de energía/estacionalidad;
- CSV detallados de inventario local bajo `resultados_reproducibles/auditoria`;
- `tmp_view.txt`.
- `Datos_Era5/descargar_era5land_diario.py`, sustituido por `scripts/download_era5.py`;
- `CMIP6_Guajira/cmip6_pangeo_guajira.py`, sustituido por `scripts/download_cmip6.py`;
- `CMIP6_Guajira/model_validation.py`, que no forma parte del flujo validado;
- `CMIP6_Guajira/plots_future.py`, asociado a las figuras legadas vacías.

Los elementos excluidos permanecen en el computador. No se borran y no son
necesarios para revisar los resultados públicos porque las fuentes y los pasos
de reconstrucción están documentados.
