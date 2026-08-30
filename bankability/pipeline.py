"""Puerta de calidad para estimaciones P50/P90 de un parque eólico.

El código climático original usa datos diarios y una curva proxy. Es adecuado
para comparar escenarios, pero no para una estimación financiera de energía.
Este módulo mantiene ambos propósitos separados y se niega a calcular un P90
si faltan insumos mínimos documentados.
"""

from __future__ import annotations

import hashlib
import json
from calendar import isleap
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


DISCLAIMER = (
    "Las cifras absolutas de energía del análisis climático son académicas, no "
    "bancables. Un P90 financiero requiere datos observados horarios/10-min, "
    "curva V172 certificada, estelas, disponibilidad, pérdidas eléctricas y "
    "cuantificación trazable de incertidumbres. Incluso una ejecución completa "
    "de este módulo es preliminar y requiere revisión de un ingeniero independiente."
)

LOSS_CATEGORIES = (
    "wake",
    "availability",
    "electrical",
    "turbine_performance",
    "environmental",
    "curtailment",
)

UNCERTAINTY_CATEGORIES = (
    "resource_measurement",
    "long_term_correction",
    "vertical_extrapolation",
    "power_curve_model",
)

WIND_COLUMNS = (
    "timestamp_utc",
    "wind_speed_hub_m_s",
    "wind_direction_deg",
    "air_density_kg_m3",
)

POWER_CURVE_COLUMNS = ("wind_speed_m_s", "power_kw")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("La configuración debe ser un objeto JSON.")
    return data


def _config_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _resolve_input(raw: Any, config_dir: Path) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = config_dir / path
    return path.resolve()


def _display_path(path: Path) -> str:
    """Evita grabar rutas personales absolutas en resultados publicables."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return f"<external>/{path.name}"


def _finite_fraction(value: Any, lower: float, upper: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and np.isfinite(value)
        and lower <= float(value) <= upper
    )


def _add_check(
    checks: list[dict[str, Any]], check_id: str, passed: bool, detail: str
) -> None:
    checks.append({"id": check_id, "required": True, "passed": bool(passed), "detail": detail})


def _validate_wind_file(path: Path, checks: list[dict[str, Any]]) -> dict[str, Any]:
    quality: dict[str, Any] = {}
    try:
        wind = pd.read_csv(path)
    except Exception as exc:
        _add_check(checks, "wind.csv_readable", False, f"{type(exc).__name__}: {exc}")
        return quality

    _add_check(checks, "wind.csv_readable", True, f"{len(wind):,} filas")
    missing = sorted(set(WIND_COLUMNS).difference(wind.columns))
    _add_check(
        checks,
        "wind.required_columns",
        not missing,
        "Columnas completas" if not missing else f"Faltan: {', '.join(missing)}",
    )
    if missing:
        return quality

    timestamp = pd.to_datetime(wind["timestamp_utc"], utc=True, errors="coerce")
    numeric = wind[list(WIND_COLUMNS[1:])].apply(pd.to_numeric, errors="coerce")
    valid = timestamp.notna() & numeric.notna().all(axis=1)
    _add_check(
        checks,
        "wind.valid_values",
        bool(valid.all()),
        f"Filas válidas: {int(valid.sum()):,}/{len(wind):,}",
    )
    if valid.sum() < 2:
        return quality

    timestamp = timestamp[valid].sort_values()
    duplicate_count = int(timestamp.duplicated().sum())
    _add_check(
        checks,
        "wind.unique_timestamps",
        duplicate_count == 0,
        f"Duplicados: {duplicate_count}",
    )
    unique_time = pd.DatetimeIndex(timestamp.drop_duplicates())
    deltas_s = np.diff(unique_time.asi8) / 1e9
    median_delta = float(np.median(deltas_s))
    cadence_share = float(np.mean(np.isclose(deltas_s, 600.0)))
    _add_check(
        checks,
        "wind.ten_minute_cadence",
        bool(np.isclose(median_delta, 600.0) and cadence_share >= 0.90),
        f"Intervalo mediano={median_delta:.1f} s; intervalos de 10 min={cadence_share:.1%}",
    )

    expected = int(round((unique_time[-1] - unique_time[0]).total_seconds() / 600.0)) + 1
    completeness = min(1.0, len(unique_time) / expected) if expected else 0.0
    span_years = (unique_time[-1] - unique_time[0]).total_seconds() / (365.2425 * 86400)
    _add_check(
        checks,
        "wind.temporal_completeness",
        completeness >= 0.90,
        f"Completitud temporal={completeness:.2%}",
    )
    _add_check(
        checks,
        "wind.long_term_span",
        span_years >= 9.9,
        f"Cobertura={span_years:.2f} años; se requieren ~10 años o más tras MCP",
    )

    speed = numeric.loc[valid, "wind_speed_hub_m_s"].to_numpy(float)
    direction = numeric.loc[valid, "wind_direction_deg"].to_numpy(float)
    density = numeric.loc[valid, "air_density_kg_m3"].to_numpy(float)
    physical = (
        np.all((speed >= 0.0) & (speed <= 75.0))
        and np.all((direction >= 0.0) & (direction < 360.0))
        and np.all((density >= 0.7) & (density <= 1.5))
    )
    _add_check(
        checks,
        "wind.physical_ranges",
        bool(physical),
        "Rangos plausibles" if physical else "Hay viento, dirección o densidad fuera de rango",
    )
    quality.update(
        {
            "rows": int(len(wind)),
            "valid_rows": int(valid.sum()),
            "start": unique_time[0].isoformat(),
            "end": unique_time[-1].isoformat(),
            "span_years": span_years,
            "completeness": completeness,
            "median_cadence_seconds": median_delta,
        }
    )
    return quality


def _validate_power_curve(
    path: Path, rated_power_kw: float, checks: list[dict[str, Any]]
) -> dict[str, Any]:
    quality: dict[str, Any] = {}
    try:
        curve = pd.read_csv(path)
    except Exception as exc:
        _add_check(checks, "curve.csv_readable", False, f"{type(exc).__name__}: {exc}")
        return quality
    _add_check(checks, "curve.csv_readable", True, f"{len(curve)} puntos")
    missing = sorted(set(POWER_CURVE_COLUMNS).difference(curve.columns))
    _add_check(
        checks,
        "curve.required_columns",
        not missing,
        "Columnas completas" if not missing else f"Faltan: {', '.join(missing)}",
    )
    if missing:
        return quality

    numeric = curve[list(POWER_CURVE_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    valid = numeric.notna().all(axis=1)
    speed = numeric.loc[valid, "wind_speed_m_s"].to_numpy(float)
    power = numeric.loc[valid, "power_kw"].to_numpy(float)
    ordered = len(speed) >= 20 and np.all(np.diff(speed) > 0)
    bounded = (
        len(power) > 0
        and np.all(power >= 0)
        and np.max(power) <= rated_power_kw * 1.05
        and np.max(power) >= rated_power_kw * 0.95
    )
    coverage = len(speed) > 0 and np.min(speed) <= 3.0 and np.max(speed) >= 25.0
    _add_check(checks, "curve.numeric_and_ordered", bool(valid.all() and ordered), "Velocidades estrictamente crecientes y ≥20 puntos")
    _add_check(checks, "curve.rated_power", bool(bounded), f"Potencia máxima={np.max(power) if len(power) else float('nan'):.1f} kW")
    _add_check(checks, "curve.wind_range", bool(coverage), "La tabla debe cubrir al menos 3–25 m/s")
    quality.update(
        {
            "points": int(len(curve)),
            "min_wind_m_s": float(np.min(speed)) if len(speed) else None,
            "max_wind_m_s": float(np.max(speed)) if len(speed) else None,
            "max_power_kw": float(np.max(power)) if len(power) else None,
        }
    )
    return quality


def evaluate_readiness(config_path: Path | str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Valida insumos y retorna ``(config, estado)`` sin calcular energía."""
    path = Path(config_path).resolve()
    config = _load_json(path)
    checks: list[dict[str, Any]] = []
    quality: dict[str, Any] = {}

    project = config.get("project", {})
    turbine_count = project.get("turbine_count")
    rated_power_kw = project.get("rated_power_kw")
    _add_check(
        checks,
        "project.turbine_count",
        isinstance(turbine_count, int) and not isinstance(turbine_count, bool) and turbine_count > 0,
        f"Valor={turbine_count!r}",
    )
    _add_check(
        checks,
        "project.rated_power_kw",
        isinstance(rated_power_kw, (int, float)) and not isinstance(rated_power_kw, bool) and float(rated_power_kw) > 0,
        f"Valor={rated_power_kw!r}",
    )

    wind_cfg = config.get("wind_resource", {})
    wind_path = _resolve_input(wind_cfg.get("time_series_csv"), path.parent)
    _add_check(
        checks,
        "wind.file_exists",
        bool(wind_path and wind_path.is_file()),
        _display_path(wind_path) if wind_path else "No configurado",
    )
    _add_check(
        checks,
        "wind.source_documented",
        isinstance(wind_cfg.get("source_document"), str) and bool(wind_cfg.get("source_document", "").strip()),
        "Fuente declarada" if wind_cfg.get("source_document") else "Falta fuente/campaña/MCP",
    )
    _add_check(
        checks,
        "wind.measurement_campaign",
        isinstance(wind_cfg.get("measurement_campaign_months"), (int, float))
        and not isinstance(wind_cfg.get("measurement_campaign_months"), bool)
        and float(wind_cfg["measurement_campaign_months"]) >= 12,
        f"Meses={wind_cfg.get('measurement_campaign_months')!r}",
    )
    _add_check(
        checks,
        "wind.long_term_reference",
        isinstance(wind_cfg.get("long_term_reference_years"), (int, float))
        and not isinstance(wind_cfg.get("long_term_reference_years"), bool)
        and float(wind_cfg["long_term_reference_years"]) >= 10,
        f"Años={wind_cfg.get('long_term_reference_years')!r}",
    )
    if wind_path and wind_path.is_file():
        quality["wind"] = _validate_wind_file(wind_path, checks)

    curve_cfg = config.get("certified_power_curve", {})
    curve_path = _resolve_input(curve_cfg.get("csv"), path.parent)
    _add_check(
        checks,
        "curve.file_exists",
        bool(curve_path and curve_path.is_file()),
        _display_path(curve_path) if curve_path else "No configurado",
    )
    _add_check(
        checks,
        "curve.certificate_documented",
        isinstance(curve_cfg.get("certificate_document"), str)
        and bool(curve_cfg.get("certificate_document", "").strip()),
        "Certificado declarado" if curve_cfg.get("certificate_document") else "Falta certificado V172/mode 6.8 MW",
    )
    rho_ref = curve_cfg.get("reference_air_density_kg_m3")
    _add_check(
        checks,
        "curve.reference_density",
        isinstance(rho_ref, (int, float)) and not isinstance(rho_ref, bool) and 0.7 <= float(rho_ref) <= 1.5,
        f"Valor={rho_ref!r}",
    )
    if curve_path and curve_path.is_file() and isinstance(rated_power_kw, (int, float)):
        quality["power_curve"] = _validate_power_curve(curve_path, float(rated_power_kw), checks)

    losses = config.get("losses", {})
    for category in LOSS_CATEGORIES:
        item = losses.get(category, {})
        valid_numbers = _finite_fraction(item.get("mean_fraction"), 0.0, 0.50) and _finite_fraction(
            item.get("std_fraction"), 0.0, 0.30
        )
        _add_check(
            checks,
            f"loss.{category}.values",
            valid_numbers,
            f"media={item.get('mean_fraction')!r}; sigma={item.get('std_fraction')!r}",
        )
        evidence = item.get("evidence")
        _add_check(
            checks,
            f"loss.{category}.evidence",
            isinstance(evidence, str) and bool(evidence.strip()),
            "Evidencia declarada" if evidence else "Falta estudio, contrato o hipótesis trazable",
        )

    uncertainties = config.get("uncertainties", {})
    for category in UNCERTAINTY_CATEGORIES:
        value = uncertainties.get(category)
        _add_check(
            checks,
            f"uncertainty.{category}",
            _finite_fraction(value, 0.0, 0.50),
            f"Sigma fraccional={value!r}",
        )

    simulation = config.get("simulation", {})
    n_samples = simulation.get("n_samples")
    seed = simulation.get("seed")
    _add_check(
        checks,
        "simulation.n_samples",
        isinstance(n_samples, int) and not isinstance(n_samples, bool) and 10_000 <= n_samples <= 2_000_000,
        f"Valor={n_samples!r}",
    )
    _add_check(
        checks,
        "simulation.seed",
        isinstance(seed, int) and not isinstance(seed, bool),
        f"Valor={seed!r}",
    )

    blockers = [check for check in checks if check["required"] and not check["passed"]]
    ready = not blockers
    status = {
        "schema_version": "1.0",
        "status": "READY_FOR_PRELIMINARY_CALCULATION" if ready else "BLOCKED_MISSING_OR_INVALID_INPUTS",
        "ready_for_preliminary_p90": ready,
        "financial_p90_calculated": False,
        "bankable": False,
        "disclaimer": DISCLAIMER,
        "config_file": _display_path(path),
        "config_sha256": _config_hash(config),
        "checks": checks,
        "blockers": blockers,
        "quality": quality,
        "warnings": [
            "El ensamble CMIP6 no es una distribución probabilística financiera.",
            "La simulación asume independencia entre categorías de pérdidas e incertidumbre.",
            "La aceptación final requiere revisión contractual y de un ingeniero independiente.",
        ],
    }
    return config, status


def _read_validated_inputs(config: dict[str, Any], config_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    wind_path = _resolve_input(config["wind_resource"]["time_series_csv"], config_path.parent)
    curve_path = _resolve_input(config["certified_power_curve"]["csv"], config_path.parent)
    assert wind_path is not None and curve_path is not None
    wind = pd.read_csv(wind_path)
    wind["timestamp_utc"] = pd.to_datetime(wind["timestamp_utc"], utc=True)
    wind = wind.sort_values("timestamp_utc")
    curve = pd.read_csv(curve_path).sort_values("wind_speed_m_s")
    return wind, curve


def _annual_gross_energy(config: dict[str, Any], wind: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    rho_ref = float(config["certified_power_curve"]["reference_air_density_kg_m3"])
    equivalent_speed = wind["wind_speed_hub_m_s"].to_numpy(float) * (
        wind["air_density_kg_m3"].to_numpy(float) / rho_ref
    ) ** (1.0 / 3.0)
    power_kw = np.interp(
        equivalent_speed,
        curve["wind_speed_m_s"].to_numpy(float),
        curve["power_kw"].to_numpy(float),
        left=0.0,
        right=0.0,
    )
    work = pd.DataFrame({"timestamp_utc": wind["timestamp_utc"], "power_kw": power_kw})
    work["year"] = work["timestamp_utc"].dt.year
    turbine_count = int(config["project"]["turbine_count"])
    rated_power_kw = float(config["project"]["rated_power_kw"])
    rows = []
    for year, group in work.groupby("year"):
        hours = 8784 if isleap(int(year)) else 8760
        mean_power_kw = float(group["power_kw"].mean())
        gross_gwh = mean_power_kw * turbine_count * hours / 1_000_000.0
        rows.append(
            {
                "year": int(year),
                "records": int(len(group)),
                "gross_energy_GWh": gross_gwh,
                "gross_capacity_factor": mean_power_kw / rated_power_kw,
            }
        )
    return pd.DataFrame(rows)


def _sample_energy(config: dict[str, Any], annual: pd.DataFrame) -> np.ndarray:
    simulation = config["simulation"]
    n_samples = int(simulation["n_samples"])
    rng = np.random.default_rng(int(simulation["seed"]))
    gross = rng.choice(annual["gross_energy_GWh"].to_numpy(float), size=n_samples, replace=True)

    net_factor = np.ones(n_samples, dtype=float)
    for category in LOSS_CATEGORIES:
        item = config["losses"][category]
        sampled_loss = rng.normal(float(item["mean_fraction"]), float(item["std_fraction"]), n_samples)
        sampled_loss = np.clip(sampled_loss, 0.0, 0.95)
        net_factor *= 1.0 - sampled_loss

    sigma = float(
        np.sqrt(
            sum(float(config["uncertainties"][name]) ** 2 for name in UNCERTAINTY_CATEGORIES)
        )
    )
    epistemic_multiplier = np.clip(rng.normal(1.0, sigma, n_samples), 0.0, None)
    return gross * net_factor * epistemic_multiplier


def _write_exceedance_figure(samples: np.ndarray, summary: dict[str, Any], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = np.sort(samples)
    exceedance = 1.0 - np.arange(1, len(ordered) + 1) / (len(ordered) + 1)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(ordered, exceedance * 100.0, color="#0B7285", linewidth=2)
    for label, color in (("P90_exceedance_GWh", "#C92A2A"), ("P50_exceedance_GWh", "#5F3DC4")):
        value = float(summary[label])
        probability = 90 if label.startswith("P90") else 50
        ax.axvline(value, color=color, linestyle="--", linewidth=1.5, label=f"{label[:3]} = {value:,.1f} GWh")
        ax.scatter([value], [probability], color=color, zorder=3)
    ax.set_xlabel("Energía neta anual (GWh)")
    ax.set_ylabel("Probabilidad de excedencia (%)")
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.25)
    ax.legend()
    ax.set_title("Curva preliminar de excedencia — requiere revisión independiente")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_preliminary_assessment(
    config_path: Path | str, output_dir: Path | str
) -> dict[str, Any]:
    """Valida y, sólo si todo pasa, calcula percentiles preliminares de energía."""
    config_path = Path(config_path).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config, status = evaluate_readiness(config_path)

    status_path = output / "estado_bancabilidad.json"
    status_path.write_text(
        json.dumps(status, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    if not status["ready_for_preliminary_p90"]:
        return status

    wind, curve = _read_validated_inputs(config, config_path)
    annual = _annual_gross_energy(config, wind, curve)
    samples = _sample_energy(config, annual)
    q10, q25, q50, q75, q90 = np.quantile(samples, [0.10, 0.25, 0.50, 0.75, 0.90])
    summary = {
        "status": "PRELIMINARY_REQUIRES_INDEPENDENT_ENGINEER_REVIEW",
        "bankable": False,
        "P90_exceedance_GWh": float(q10),
        "P75_exceedance_GWh": float(q25),
        "P50_exceedance_GWh": float(q50),
        "P25_exceedance_GWh": float(q75),
        "P10_exceedance_GWh": float(q90),
        "n_samples": int(len(samples)),
        "n_resource_years": int(len(annual)),
        "seed": int(config["simulation"]["seed"]),
        "disclaimer": DISCLAIMER,
        "method_notes": [
            "P90 de excedencia corresponde al cuantil 10 de energía.",
            "Densidad aplicada mediante velocidad equivalente (rho/rho_ref)^(1/3).",
            "Años de recurso remuestreados con reemplazo.",
            "Pérdidas e incertidumbres muestreadas como independientes; validar correlaciones.",
        ],
    }
    annual.to_csv(output / "energia_bruta_anual_preliminar.csv", index=False)
    (output / "resumen_p50_p90_preliminar.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    _write_exceedance_figure(samples, summary, output / "curva_excedencia_preliminar.png")

    status.update(
        {
            "status": summary["status"],
            "financial_p90_calculated": True,
            "bankable": False,
            "preliminary_summary": summary,
        }
    )
    status_path.write_text(
        json.dumps(status, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    return status
