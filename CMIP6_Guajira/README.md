# Código climático original y productos intermedios

Esta carpeta conserva el código funcional con el que se corrigieron y
transformaron los modelos CMIP6, además de las tablas pequeñas de trazabilidad.
Los NetCDF y las figuras legadas no se publican: se reconstruyen o se sustituyen
por la galería auditada.

El descargador antiguo con ruta absoluta, el script de validación no canónico y
el generador de las figuras vacías se conservan localmente, pero están excluidos
de GitHub. Sus hallazgos quedan registrados en la auditoría. Use:

- `../run_portfolio.py` para validar/regenerar las figuras publicadas sin datos crudos;
- `../run_full_rebuild.py` para una reconstrucción completa en un clon limpio;
- `../run_reproducible.py` para la auditoría científica cuando los datos existen.

La revisión detallada de supuestos y limitaciones está en
[INFORME_AUDITORIA.md](../INFORME_AUDITORIA.md).
