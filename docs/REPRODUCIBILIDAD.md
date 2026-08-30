# Reproducibilidad en Windows, Linux y macOS

## Nivel 1: resultados visibles sin datos crudos

Recomendado para reclutadores, revisores y evaluación rápida. Requiere Python
3.12, no requiere red y tarda segundos:

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run_portfolio.py --check-only
python run_portfolio.py
python -m unittest discover -s tests -p "test_lightweight.py" -v
```

En PowerShell active con `.venv\Scripts\Activate.ps1`; en Linux/macOS use
`source .venv/bin/activate`.

## Nivel 2: auditoría con los datos ya materializados

```bash
python scripts/check_repository.py --require-data
python run_reproducible.py --audit-only
python run_reproducible.py
```

La auditoría profunda lee y calcula hashes de unos 5,7 GiB:

```bash
python run_reproducible.py --deep-audit
```

## Nivel 3: reconstrucción completa desde fuentes

Úselo en un clon limpio con credenciales CDS configuradas:

```bash
python -m pip install -r requirements-download.txt
python run_full_rebuild.py --dry-run
python run_full_rebuild.py
```

El comando se niega a reemplazar derivados existentes. `--force` existe para una
decisión consciente, pero no es necesario en una reproducción limpia.

## Docker opcional para el nivel 1

```bash
docker build -t jemeiwaa-clima .
docker run --rm -v "${PWD}:/workspace" -w /workspace jemeiwaa-clima python run_portfolio.py --check-only
```

Para descarga completa, configure CDS en el sistema anfitrión y no incorpore
credenciales a la imagen.

## Controles esperados

- `check_repository.py`: `PASS`, reglas de exclusión activas y Python válido.
- `check_publication.py`: cero datos crudos, cero archivos >10 MiB y cuatro PNG válidos.
- `run_portfolio.py --check-only`: cuatro dimensiones válidas y tablas completas.
- GitHub Actions: marca verde después de cada `push`.

El detalle científico y las advertencias metodológicas están en
[INFORME_AUDITORIA.md](../INFORME_AUDITORIA.md).
