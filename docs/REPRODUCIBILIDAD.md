# Reproducibilidad

## Nivel 1 — Verificación rápida del portafolio

Recomendado para reclutadores y revisores. Usa los CSV públicos, no necesita
red ni datos crudos y tarda segundos.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/rebuild_figures.py --check-only
python scripts/rebuild_figures.py
python -m unittest discover -s tests -p "test_lightweight.py" -v
```

Activación opcional del entorno:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- Linux/macOS: `source .venv/bin/activate`

El verificador exige:

- 12 modelos en cada resumen de escenario;
- percentiles ordenados y CF dentro de `[0, 0.9]`;
- cinco figuras no vacías con dimensiones válidas;
- manifiestos de fuentes completos;
- ausencia de datos crudos y archivos públicos grandes.

## Nivel 2 — Recálculo con los datos ya descargados

```bash
python scripts/check_repository.py --require-data
python scripts/run_analysis.py
python scripts/rebuild_figures.py --check-only
```

`run_analysis.py` solo escribe dentro de `results/`; no modifica los NetCDF.
Recalcula ambos tratamientos de sesgo con la misma integración subdiaria y
actualiza tablas y figuras.

## Nivel 3 — Reconstrucción desde las fuentes

```bash
python -m pip install -r requirements-download.txt
python scripts/run_full_rebuild.py --dry-run
python scripts/run_full_rebuild.py
```

Úselo en un clon limpio con la API CDS configurada. Si detecta productos
corregidos existentes, el flujo se detiene antes de reemplazarlos. `--force`
solo debe emplearse en una copia controlada.

## Controles automáticos

```bash
python scripts/check_repository.py --ci
python scripts/check_publication.py
python scripts/rebuild_figures.py --check-only
python -m unittest discover -s tests -p "test_lightweight.py" -v
```

GitHub Actions ejecuta estos controles después de cada actualización. Docker
no es necesario: el entorno fijado en `requirements.txt` y la validación en
Ubuntu proporcionan el nivel portable adecuado para este portafolio.

## Semillas y determinismo

La integración subdiaria no utiliza números aleatorios. Emplea 144 puntos
medios de probabilidad de una Weibull y normaliza sus multiplicadores a media
uno. Con las mismas tablas y versiones, las figuras se regeneran de forma
determinista.
