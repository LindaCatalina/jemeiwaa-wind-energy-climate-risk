# Fuentes de datos

## Política pública

El repositorio no redistribuye datos climáticos crudos. Los NetCDF, GRIB, Zarr
y archivos comprimidos están excluidos mediante `.gitignore`. La reproducción
se apoya en código abierto, tablas finales y dos manifiestos que fijan las
solicitudes exactas utilizadas.

## ERA5-Land

| Campo | Configuración usada |
|---|---|
| Proveedor | Copernicus Climate Data Store |
| Dataset | `derived-era5-land-daily-statistics` |
| DOI | `10.24381/cds.e9c9c792` |
| Periodo | 1981–2014 |
| Frecuencia de entrada | horaria |
| Agregación | media diaria |
| Variables | `u10`, `v10`, temperatura a 2 m y presión superficial |
| Punto/caja | entorno de 12,125 N; −71,9583 W |
| Zona horaria | UTC |

Fuente oficial: [ERA5-Land daily statistics](https://cds.climate.copernicus.eu/datasets/derived-era5-land-daily-statistics?tab=documentation).

`data/era5_request_manifest.csv` contiene 136 solicitudes: cuatro variables
por 34 años, además de área, frecuencia, estadístico y archivo de destino.

Para descargar:

1. Cree una cuenta en el [Climate Data Store](https://cds.climate.copernicus.eu/).
2. Acepte los términos vigentes del dataset.
3. Configure la API CDS en `.cdsapirc` fuera del repositorio.
4. Ejecute:

```bash
python -m pip install -r requirements-download.txt
python scripts/download_era5.py --dry-run
python scripts/download_era5.py
python Datos_Era5/unificar_era5_guajira.py
python Datos_Era5/era5_altura_densidad.py
```

## CMIP6

Los datos proceden del archivo CMIP6 en Google Cloud publicado mediante
Pangeo/ESGF. Se fijaron 12 modelos, los experimentos `historical`, `ssp126`,
`ssp245` y `ssp585`, y las variables `sfcWind`, `uas`, `vas`, `tas` y `ps`
cuando estaban disponibles.

- [Acceso a Pangeo CMIP6 Cloud](https://pangeo-data.github.io/pangeo-cmip6-cloud/accessing_data.html)
- [Licencias y citación de CMIP6](https://pangeo-data.github.io/pangeo-cmip6-cloud/licensing_citation.html)
- Catálogo: `https://storage.googleapis.com/cmip6/pangeo-cmip6.json`

`data/cmip6_source_manifest.csv` registra 215 almacenes lógicos con modelo,
institución, experimento, variable, tabla, miembro, rejilla, versión, `zstore`
y licencia informada por el productor. Así se evita que una búsqueda futura
seleccione silenciosamente otra versión o miembro.

```bash
python scripts/download_cmip6.py --dry-run
python scripts/download_cmip6.py
```

Las licencias varían por institución. Debe consultarse el campo
`license_from_source` antes de cualquier redistribución; este repositorio no
redistribuye esas fuentes.

## Reconstrucción integrada

En un clon limpio:

```bash
python -m pip install -r requirements-download.txt
python scripts/run_full_rebuild.py --dry-run
python scripts/run_full_rebuild.py
```

El flujo descarga, prepara ERA5-Land, materializa CMIP6, calcula factores de
sesgo, genera las 48 series diarias corregidas y finalmente reconstruye
`results/`. No crea ni necesita las antiguas series sintéticas de 10 minutos.

La igualdad se comprueba por modelos, periodos, variables, fórmulas, tablas y
figuras; no por identidad byte a byte del empaquetado NetCDF.

## Datos que no deben publicarse

- `.cdsapirc`, tokens o credenciales;
- NetCDF/GRIB/Zarr descargados;
- mediciones privadas de campaña;
- curvas certificadas sujetas a licencia;
- contratos, pérdidas, disponibilidad o estudios de estelas confidenciales.
