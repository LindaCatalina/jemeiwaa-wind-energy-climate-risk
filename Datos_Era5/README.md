# Preparación de ERA5-Land

Los NetCDF locales se conservan en la estación de trabajo y `.gitignore`
impide publicarlos. El repositorio contiene el descargador portable y los pasos
de consolidación:

```bash
python scripts/download_era5.py --dry-run
python scripts/download_era5.py
python Datos_Era5/unificar_era5_guajira.py
python Datos_Era5/era5_altura_densidad.py
```

El descargador usa `data/era5_request_manifest.csv` y requiere una cuenta CDS
configurada fuera del repositorio. Fuente, DOI y variables:
[docs/DATOS.md](../docs/DATOS.md).
