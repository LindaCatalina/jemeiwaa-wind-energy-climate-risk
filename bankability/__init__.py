"""Controles para una evaluación energética pre-bancable y trazable.

Este paquete está separado del análisis climático académico. Nunca convierte
automáticamente una estimación en "bancable": sólo valida insumos y, cuando
están completos, produce una distribución preliminar para revisión técnica.
"""

from .pipeline import evaluate_readiness, run_preliminary_assessment

__all__ = ["evaluate_readiness", "run_preliminary_assessment"]

