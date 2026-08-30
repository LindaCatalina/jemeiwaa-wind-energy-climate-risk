# ERA5-Land: código original y reconstrucción

Los NetCDF locales se conservan en la estación de trabajo, pero `.gitignore`
impide publicarlos. El descargador histórico con ruta personal también permanece
local y está documentado en la auditoría; el repositorio publica únicamente el
descargador portable.

Para reconstruir los datos en cualquier máquina:

```bash
python scripts/download_era5.py
python Datos_Era5/unificar_era5_guajira.py
python Datos_Era5/era5_altura_densidad.py
```

El primer comando usa `data/era5_request_manifest.csv`, escribe directamente en
esta carpeta y requiere una cuenta CDS configurada. Detalles y fuente oficial:
[docs/DATOS.md](../docs/DATOS.md).
