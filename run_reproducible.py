"""Punto de entrada único para auditar y regenerar resultados no destructivos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from reproducibilidad.auditoria import run_audit
from reproducibilidad.config import PROJECT_ROOT
from reproducibilidad.percentiles import repair_legacy_delta_figures, run_percentile_analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita Trabajo_Final y genera figuras/percentiles sin sobrescribir resultados originales."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "resultados_reproducibles",
        help="Directorio nuevo de salida (por defecto: resultados_reproducibles).",
    )
    parser.add_argument(
        "--deep-audit",
        action="store_true",
        help="Calcula SHA-256 de todo y escanea las 48 series sintéticas completas (~5.7 GiB).",
    )
    parser.add_argument("--audit-only", action="store_true", help="Ejecuta sólo controles de integridad.")
    parser.add_argument(
        "--skip-sensitivity",
        action="store_true",
        help="Omite la sensibilidad que elimina el recentrado futuro del QM legado.",
    )
    return parser.parse_args()


def write_execution_summary(output: Path, audit: dict, methods: list[str]) -> Path:
    lines = [
        "# Resumen de ejecución reproducible",
        "",
        "Los archivos originales no fueron sobrescritos. Todas las tablas y figuras de esta ejecución están dentro de este directorio.",
        "",
        "## Integridad",
        "",
        f"- Archivos inventariados: {audit['inventory']['files']} ({audit['inventory']['size_GiB']:.3f} GiB).",
        f"- NetCDF abiertos por cabecera: {audit['netcdf']['files']}; errores: {audit['netcdf']['open_errors']}.",
        f"- ERA5: {audit['era5']['n_days']} días, {audit['era5']['start']} a {audit['era5']['end']}; fórmulas exactas: {audit['era5']['pass']}.",
        f"- Series corregidas canónicas: {audit['corrected']['n_series']}; fórmulas reproducidas: {audit['corrected']['all_formulas_reproduce']}.",
        f"- Combinaciones sin densidad: {audit['corrected']['density_missing_count']}.",
        f"- Series con viento corregido negativo: {audit['corrected']['series_with_negative_corrected_wind']}.",
        f"- Conservación de media en síntesis Weibull: {audit['synthetic']['daily_mean_is_conserved']} (razón observada {audit['synthetic']['observed_daily_mean_ratio_sample']:.6f}).",
        f"- Fallos fatales de integridad: {audit['fatal_integrity_failures']}.",
        "",
        "## Resultados generados",
        "",
        "- `figuras_legacy_reparadas/`: las dos figuras vacías reconstruidas con los mismos datos sintéticos legados.",
    ]
    for method in methods:
        table = pd.read_csv(output / method / "tablas" / "percentiles_cambio_cf_ensemble.csv")
        lines.extend(["", f"### {method}", ""])
        for _, row in table.sort_values(["horizon", "scenario"]).iterrows():
            lines.append(
                f"- {row['scenario'].upper()} {row['horizon']}: mediana ΔCF={row['q50']:.2f} %, "
                f"P10–P90=[{row['q10']:.2f}, {row['q90']:.2f}] %, "
                f"{int(row['models_nonnegative'])}/{int(row['n_models'])} modelos no negativos."
            )
    lines.extend(
        [
            "",
            "## Lectura correcta de P90",
            "",
            "En energía, P90 de excedencia es el cuantil bajo q10: un valor que se supera en aproximadamente 90 % de la muestra empírica. Los modelos CMIP6 no constituyen probabilidades equiprobables; por eso aquí P10/P50/P90 describen *spread* intermodelo y no una garantía financiera.",
            "",
            "## Alcance financiero",
            "",
            "Las cifras absolutas de energía de este flujo son académicas, no bancables. Para un P90 financiero hacen falta viento observado horario/10-min, curva V172 certificada, estelas, disponibilidad, pérdidas eléctricas y propagación trazable de incertidumbres. `run_bankability.py` valida esos insumos en un flujo separado y se niega a calcular si están incompletos.",
            "",
        ]
    )
    path = output / "RESUMEN_EJECUCION.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Proyecto: {PROJECT_ROOT}")
    print(f"[INFO] Salida no destructiva: {output}")

    audit = run_audit(output, deep=args.deep_audit)
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    if audit["fatal_integrity_failures"]:
        print("[ERROR] La auditoría encontró fallos fatales; no se generan análisis derivados.")
        return 2
    if args.audit_only:
        write_execution_summary(output, audit, [])
        return 0

    print("[INFO] Reparando figuras legadas vacías sin sobrescribir originales")
    repair_legacy_delta_figures(output / "figuras_legacy_reparadas")

    methods = ["legado"]
    print("[INFO] Percentiles de reproducción legada")
    run_percentile_analysis(output, "legado")
    if not args.skip_sensitivity:
        print("[INFO] Percentiles de sensibilidad sin recentrado futuro")
        run_percentile_analysis(output, "sensibilidad_sin_recentrado")
        methods.append("sensibilidad_sin_recentrado")

    summary = write_execution_summary(output, audit, methods)
    print(f"[OK] Ejecución completa. Resumen: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
