# Manifiestos de datos

Esta carpeta **no contiene datos crudos**. Contiene las instrucciones exactas
para reconstruirlos desde sus fuentes oficiales:

- `era5_request_manifest.csv`: 136 solicitudes ERA5-Land (4 variables × 34 años),
  con periodo, estadístico diario, zona horaria, frecuencia y caja espacial.
- `cmip6_source_manifest.csv`: 215 subconjuntos de los 12 modelos canónicos,
  con experimento, variable, miembro, rejilla, versión, licencia y `zstore` exacto.

Los manifiestos se extrajeron de los archivos usados en el análisis con:

```bash
python scripts/build_source_manifests.py
```

No es necesario ejecutar ese comando después de clonar: los dos CSV ya están
versionados. Consulte [docs/DATOS.md](../docs/DATOS.md) para descargar y citar.
