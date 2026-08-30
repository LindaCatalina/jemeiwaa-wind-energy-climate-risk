# Contribuir sin romper la trazabilidad

1. Cree una rama y no sobrescriba archivos científicos originales ni resultados legados.
2. Publique una corrección metodológica como sensibilidad separada y documente su efecto.
3. No cambie el ensamble canónico de 12 modelos sin justificar y versionar la decisión.
4. No publique `.cdsapirc`, `.env`, datos contractuales ni contenido de `private_*`.
5. Antes de proponer cambios ejecute:

```bash
python scripts/check_repository.py --ci
python run_portfolio.py --check-only
python scripts/check_publication.py
python -m unittest discover -s tests -v
```

6. Si dispone de los datos locales, añada `python run_reproducible.py --audit-only`.
7. No agregue NetCDF a Git ni habilite LFS: las fuentes se reconstruyen con los manifiestos.

La licencia de reutilización sigue pendiente de acuerdo expreso entre ambos autores.
