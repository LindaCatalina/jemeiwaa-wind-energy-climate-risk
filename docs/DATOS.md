# Fuentes de datos y reconstrucción

## Política del repositorio

Los datos crudos y derivados permanecen intactos en la copia de trabajo local,
pero no entran a GitHub. `.gitignore` excluye NetCDF, GRIB, Zarr y archivos
comprimidos. El repositorio público conserva:

- todo el código científico y de auditoría;
- tablas CSV necesarias para revisar los números;
- cuatro figuras seleccionadas y verificadas;
- manifiestos exactos para volver a descargar los insumos.

Inventario local auditado: 575 NetCDF y aproximadamente 5,74 GiB. El control de
publicación se ejecuta con `python scripts/check_publication.py`.

## ERA5-Land

| Campo | Valor usado |
|---|---|
| Fuente | Copernicus Climate Data Store |
| Dataset | `derived-era5-land-daily-statistics` |
| DOI | `10.24381/cds.e9c9c792` |
| Periodo | 1981–2014 |
| Estadístico | media diaria a partir de frecuencia horaria |
| Variables | viento U/V a 10 m, temperatura a 2 m, presión superficial |
| Área | N 12,125; O −71,9583; S 12,1166667; E −71,95 |
| Zona horaria | UTC+00:00 |

Fuente oficial: [ERA5-Land daily statistics](https://cds.climate.copernicus.eu/datasets/derived-era5-land-daily-statistics?tab=documentation).
El producto se distribuye bajo CC BY 4.0; deben revisarse y aceptarse los
términos vigentes en CDS.

Antes de descargar:

1. Cree una cuenta en [CDS](https://cds.climate.copernicus.eu/).
2. Abra la página del dataset y acepte sus términos.
3. En su perfil CDS, copie la configuración de API a `.cdsapirc` en su carpeta
   de usuario. **Nunca copie ese archivo dentro del repositorio.**
4. Instale las dependencias y pruebe el plan:

```bash
python -m pip install -r requirements-download.txt
python scripts/download_era5.py --dry-run
python scripts/download_era5.py
python Datos_Era5/unificar_era5_guajira.py
python Datos_Era5/era5_altura_densidad.py
```

`data/era5_request_manifest.csv` contiene las 136 solicitudes exactas.

## CMIP6

Los subconjuntos se obtuvieron del archivo público CMIP6 en Google Cloud
gestionado por Pangeo/ESGF. Se fijan 12 modelos, `historical`, SSP1-2.6,
SSP2-4.5 y SSP5-8.5, variables `sfcWind`, `uas`, `vas`, `tas` y `ps`, y el
miembro/rejilla disponible registrado para cada combinación.

- Catálogo: `https://storage.googleapis.com/cmip6/pangeo-cmip6.json`
- Acceso oficial: [Pangeo CMIP6 Cloud](https://pangeo-data.github.io/pangeo-cmip6-cloud/accessing_data.html)
- Licencias y citación: [Pangeo CMIP6 licensing & citation](https://pangeo-data.github.io/pangeo-cmip6-cloud/licensing_citation.html)

`data/cmip6_source_manifest.csv` fija para cada uno de los 215 archivos lógicos:
modelo, institución, actividad, experimento, variable, tabla, miembro, rejilla,
versión, `zstore` y texto de licencia del productor. Esto evita que una nueva
búsqueda en el catálogo elija otro miembro o versión.

```bash
python scripts/download_cmip6.py --dry-run
python scripts/download_cmip6.py
```

Las licencias CMIP6 varían por institución; el campo `license_from_source` del
manifiesto debe acompañar cualquier redistribución. Este repositorio no
redistribuye los datos.

## Reconstrucción completa

En un clon limpio:

```bash
python -m pip install -r requirements-download.txt
python run_full_rebuild.py --dry-run
python run_full_rebuild.py
```

El proceso descarga las fuentes, consolida ERA5-Land, obtiene factores de sesgo,
genera las 48 series corregidas y las 48 series sintéticas de 10 minutos, ejecuta
la auditoría y valida la galería. Puede tardar horas y producir unos 5,7 GiB.

La igualdad científica se verifica mediante dimensiones, periodos, variables,
modelos, fórmulas y métricas. No se exige igualdad byte a byte: el empaquetado
NetCDF, la compresión y metadatos de escritura pueden variar entre versiones.

## Datos que nunca deben publicarse

Mediciones de campaña, curvas certificadas, contratos de disponibilidad y
estudios de estelas pueden estar sujetos a confidencialidad. Deben mantenerse en
`bankability/private_data/` o `bankability/private_documents/`, ambos ignorados.
