# Arquitectura y trazabilidad

| Capa | Contenido público | Propósito |
|---|---|---|
| Fuentes | `data/*.csv`, descargadores | Fijar procedencia sin subir datos crudos |
| Código original | `Datos_Era5/`, `CMIP6_Guajira/` | Conservar cómo se desarrolló el análisis |
| Capa auditada | `reproducibilidad/`, `run_reproducible.py` | Controles, percentiles y sensibilidad |
| Portafolio | `run_portfolio.py`, tablas y 4 PNG | Reproducir resultados visibles sin 5,7 GiB |
| Reconstrucción | `run_full_rebuild.py` | Volver a crear derivados desde CDS/Pangeo |
| Bancabilidad | `bankability/`, `run_bankability.py` | Bloquear un P90 si faltan insumos reales |
| Calidad | `tests/`, `scripts/`, `.github/` | Impedir regresiones y publicaciones accidentales |

## Linaje

```text
manifiestos ERA5-Land + CMIP6
             │
             ├── descarga completa ──> datos locales ignorados por Git
             │                              │
             │                              ▼
             │                    run_reproducible.py
             │                              │
             ▼                              ▼
     tablas auditadas versionadas ──> resultados_reproducibles/
             │
             ▼
       run_portfolio.py ──> 4 figuras públicas verificadas
```

`run_bankability.py` está fuera de esa cadena. Requiere mediciones y documentos
de ingeniería distintos; no convierte los percentiles climáticos en un P90
financiero.

## Código legado

Los scripts originales con rutas absolutas, modelos comentados o decisiones
exploratorias permanecen para preservar la historia del trabajo. Sus resultados
no se presentan como flujo canónico. Cada carpeta contiene un README que dirige
a los puntos de entrada portables.

## Regla de no sobrescritura

Las correcciones metodológicas se publican como sensibilidades separadas. El
resultado legado no se reescribe. `run_full_rebuild.py` se detiene si detecta
derivados existentes, salvo autorización explícita con `--force`.
