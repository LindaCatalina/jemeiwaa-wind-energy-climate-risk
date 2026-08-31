"""Resultados coherentes de CF, energía académica e incertidumbre CMIP6."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from .config import (
    CANONICAL_MODELS,
    CORRECTED_DIR,
    ERA5_DIR,
    HORIZONS,
    PLANT_CAPACITY_MW,
    RHO_REF,
    SCENARIOS,
)
from .core import (
    as_time_series,
    daily_cf_from_mean_hub_wind,
    extrapolate_to_hub,
    load_quantiles,
    load_raw_wind,
    month_values,
    trend_preserving_qm,
    year_values,
)


BG = "#032738"
FG = "#f4f7f8"
LEGACY_METHOD = "qm_recentrado"
PRIMARY_METHOD = "qm_sin_recentrado"
METHODS = (PRIMARY_METHOD, LEGACY_METHOD)
METHOD_LABELS = {
    LEGACY_METHOD: "QM original con recentrado futuro",
    PRIMARY_METHOD: "Método principal: sin recentrado y colas aditivas",
}
SCENARIO_COLORS = {"ssp126": "#65c6e8", "ssp245": "#f1c40f", "ssp585": "#e67e22"}
SCENARIO_LABELS = {"ssp126": "SSP1-2.6", "ssp245": "SSP2-4.5", "ssp585": "SSP5-8.5"}
Q = (0.10, 0.25, 0.50, 0.75, 0.90)
EQUIVALENT_HOURS_PER_YEAR = 8760.0


def _quantiles(values: pd.Series | np.ndarray) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {name: np.nan for name in ("q10", "q25", "q50", "q75", "q90")}
    quantiles = np.quantile(arr, Q)
    return dict(zip(("q10", "q25", "q50", "q75", "q90"), map(float, quantiles)))


def _monthly_wind_quantiles(
    wind: xr.DataArray,
    *,
    source: str,
    model: str,
    correction_method: str,
) -> list[dict]:
    """Resume la distribución diaria por mes sin alinear años entre fuentes."""
    series = as_time_series(wind)
    values = np.asarray(series.values, dtype=float)
    months = month_values(series)
    rows: list[dict] = []
    for month in range(1, 13):
        selected = values[(months == month) & np.isfinite(values)]
        if selected.size == 0:
            raise ValueError(f"Mes vacío en validación: {source} {model} {month}")
        q10, q50, q90 = np.quantile(selected, (0.10, 0.50, 0.90))
        rows.append(
            {
                "source": source,
                "model": model,
                "correction_method": correction_method,
                "month": month,
                "n_days": int(selected.size),
                "q10": float(q10),
                "q50": float(q50),
                "q90": float(q90),
            }
        )
    return rows


def collect_bias_validation() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Diagnóstico histórico de cuantiles mensuales antes/después del QM.

    El error se calcula sobre 36 estadísticas climatológicas por modelo
    (P10/P50/P90 × 12 meses). No se emparejan días ni años ERA5–GCM.
    """
    era5_path = ERA5_DIR / "era5_guajira_daily_1981_2014.nc"
    with xr.open_dataset(era5_path) as dataset:
        era5 = as_time_series(dataset["wind10"]).load()

    rows = _monthly_wind_quantiles(
        era5,
        source="era5",
        model="ERA5-Land",
        correction_method="reference",
    )
    for model in CANONICAL_MODELS:
        raw = load_raw_wind(model, "historical")
        corrected = trend_preserving_qm(raw, load_quantiles(model))
        rows.extend(
            _monthly_wind_quantiles(
                raw,
                source="cmip6_crudo",
                model=model,
                correction_method="none",
            )
        )
        rows.extend(
            _monthly_wind_quantiles(
                corrected,
                source="cmip6_corregido",
                model=model,
                correction_method=PRIMARY_METHOD,
            )
        )

    quantiles = pd.DataFrame(rows)
    era_reference = (
        quantiles[quantiles["source"] == "era5"]
        .set_index("month")[["q10", "q50", "q90"]]
        .sort_index()
    )
    error_rows: list[dict] = []
    for model in CANONICAL_MODELS:
        row = {"model": model, "n_month_quantiles": 36}
        for source, label in (
            ("cmip6_crudo", "raw"),
            ("cmip6_corregido", "corrected"),
        ):
            model_values = (
                quantiles[
                    (quantiles["source"] == source) & (quantiles["model"] == model)
                ]
                .set_index("month")[["q10", "q50", "q90"]]
                .sort_index()
            )
            difference = model_values.to_numpy() - era_reference.to_numpy()
            row[f"rmse_{label}_m_s"] = float(np.sqrt(np.mean(difference**2)))
            row[f"mae_{label}_m_s"] = float(np.mean(np.abs(difference)))
        row["rmse_reduction_pct"] = 100.0 * (
            1.0 - row["rmse_corrected_m_s"] / row["rmse_raw_m_s"]
        )
        error_rows.append(row)
    errors = pd.DataFrame(error_rows).sort_values("rmse_raw_m_s", ascending=False)
    return quantiles, errors


def _corrected_inputs(model: str, experiment: str) -> tuple[xr.DataArray, xr.DataArray | float]:
    """Carga viento a buje y densidad de los productos corregidos originales."""
    path = CORRECTED_DIR / f"{model}_{experiment}_wind_bc.nc"
    ds = xr.open_dataset(path)
    try:
        wind_hub = as_time_series(ds["v150"]).load()
        density: xr.DataArray | float
        density = as_time_series(ds["rho"]).load() if "rho" in ds else RHO_REF
    finally:
        ds.close()
    return wind_hub, density


def _load_daily_cf(model: str, experiment: str, method: str) -> xr.DataArray:
    """Calcula CF diario con una única integración subdiaria para ambos métodos."""
    legacy_wind_hub, density = _corrected_inputs(model, experiment)
    if method == LEGACY_METHOD:
        wind_hub = legacy_wind_hub
    elif method == PRIMARY_METHOD:
        raw = load_raw_wind(model, experiment)
        wind_10m = trend_preserving_qm(raw, load_quantiles(model))
        wind_hub = extrapolate_to_hub(wind_10m)
    else:
        raise ValueError(f"Método desconocido: {method}")
    return daily_cf_from_mean_hub_wind(wind_hub, density)


def _append_period(
    annual_rows: list[dict],
    monthly_rows: list[dict],
    method: str,
    model: str,
    scenario: str,
    horizon: str,
    daily_cf: xr.DataArray,
    start_year: int,
    end_year: int,
) -> None:
    years = year_values(daily_cf)
    months = month_values(daily_cf)
    values = np.asarray(daily_cf.values, dtype=float)
    period = (years >= start_year) & (years <= end_year) & np.isfinite(values)
    if not period.any():
        raise ValueError(f"Periodo vacío: {method} {model} {scenario} {horizon}")

    for year in np.unique(years[period]):
        mask = period & (years == year)
        cf_annual = float(np.mean(values[mask]))
        annual_rows.append(
            {
                "method": method,
                "model": model,
                "scenario": scenario,
                "horizon": horizon,
                "year": int(year),
                "n_days": int(mask.sum()),
                "cf_annual": cf_annual,
                "energy_equivalent_GWh": (
                    cf_annual * PLANT_CAPACITY_MW * EQUIVALENT_HOURS_PER_YEAR / 1000.0
                ),
            }
        )

    for month in range(1, 13):
        mask = period & (months == month)
        monthly_rows.append(
            {
                "method": method,
                "model": model,
                "scenario": scenario,
                "horizon": horizon,
                "month": month,
                "cf_monthly_climatology": float(np.mean(values[mask])),
            }
        )


def collect_metrics(method: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    annual_rows: list[dict] = []
    monthly_rows: list[dict] = []
    for model in CANONICAL_MODELS:
        print(f"[CF] {METHOD_LABELS[method]} · {model} · historical", flush=True)
        historical = _load_daily_cf(model, "historical", method)
        _append_period(
            annual_rows,
            monthly_rows,
            method,
            model,
            "historical",
            "historico",
            historical,
            *HORIZONS["historico"],
        )
        for scenario in SCENARIOS:
            print(f"[CF] {METHOD_LABELS[method]} · {model} · {scenario}", flush=True)
            future = _load_daily_cf(model, scenario, method)
            for horizon in ("medio", "lejano"):
                _append_period(
                    annual_rows,
                    monthly_rows,
                    method,
                    model,
                    scenario,
                    horizon,
                    future,
                    *HORIZONS[horizon],
                )
    return pd.DataFrame(annual_rows), pd.DataFrame(monthly_rows)


def summarize_changes(annual: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows_by_model: list[dict] = []
    for method, method_group in annual.groupby("method", sort=False):
        historical = (
            method_group[
                (method_group["scenario"] == "historical")
                & (method_group["horizon"] == "historico")
            ]
            .groupby("model", as_index=False)["cf_annual"]
            .mean()
            .rename(columns={"cf_annual": "cf_historical"})
        )
        future = (
            method_group[method_group["scenario"].isin(SCENARIOS)]
            .groupby(["model", "scenario", "horizon"], as_index=False)["cf_annual"]
            .mean()
            .rename(columns={"cf_annual": "cf_future"})
        )
        paired = future.merge(historical, on="model", validate="many_to_one")
        paired.insert(0, "method", method)
        paired["delta_cf_pp"] = 100.0 * (paired["cf_future"] - paired["cf_historical"])
        paired["delta_cf_pct"] = 100.0 * (
            paired["cf_future"] / paired["cf_historical"] - 1.0
        )
        rows_by_model.extend(paired.to_dict("records"))

    per_model = pd.DataFrame(rows_by_model)
    summary_rows: list[dict] = []
    for keys, group in per_model.groupby(["method", "scenario", "horizon"], sort=False):
        method, scenario, horizon = keys
        values = group["delta_cf_pct"]
        row = {
            "method": method,
            "scenario": scenario,
            "horizon": horizon,
            "n_models": int(group["model"].nunique()),
            "models_nonnegative": int((values >= 0).sum()),
            "fraction_models_nonnegative": float((values >= 0).mean()),
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": float(values.mean()),
        }
        row.update(_quantiles(values))
        summary_rows.append(row)
    return per_model, pd.DataFrame(summary_rows)


def summarize_energy(annual: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    energy_column = (
        "energy_equivalent_GWh"
        if "energy_equivalent_GWh" in annual.columns
        else "energy_plant_GWh"
    )
    group_columns = [
        column for column in ("method", "scenario", "horizon") if column in annual.columns
    ]
    ensemble_rows: list[dict] = []
    for keys, group in annual.groupby(group_columns, sort=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(group_columns, keys))
        row.update(
            {
                "n_models": int(group["model"].nunique()),
                "n_model_years": int(len(group)),
                "mean_GWh": float(group[energy_column].mean()),
            }
        )
        row.update(_quantiles(group[energy_column]))
        row["P90_exceedance_GWh"] = row["q10"]
        row["P50_exceedance_GWh"] = row["q50"]
        row["P10_exceedance_GWh"] = row["q90"]
        ensemble_rows.append(row)

    interannual_rows: list[dict] = []
    per_model_columns = [*group_columns, "model"]
    for keys, group in annual.groupby(per_model_columns, sort=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(per_model_columns, keys))
        row.update({"n_years": int(len(group)), "mean_GWh": float(group[energy_column].mean())})
        row.update(_quantiles(group[energy_column]))
        row["P90_exceedance_GWh"] = row["q10"]
        row["P50_exceedance_GWh"] = row["q50"]
        row["P10_exceedance_GWh"] = row["q90"]
        interannual_rows.append(row)
    return pd.DataFrame(ensemble_rows), pd.DataFrame(interannual_rows)


def summarize_monthly(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for keys, group in monthly.groupby(
        ["method", "scenario", "horizon", "month"], sort=False
    ):
        method, scenario, horizon, month = keys
        row = {
            "method": method,
            "scenario": scenario,
            "horizon": horizon,
            "month": int(month),
            "n_models": int(group["model"].nunique()),
        }
        row.update(_quantiles(group["cf_monthly_climatology"]))
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_historical_models(annual: pd.DataFrame) -> pd.DataFrame:
    historical = annual[
        (annual["scenario"] == "historical") & (annual["horizon"] == "historico")
    ]
    return (
        historical.groupby(["method", "model"], as_index=False)
        .agg(
            years=("year", "nunique"),
            cf_historical_mean=("cf_annual", "mean"),
            cf_historical_std=("cf_annual", "std"),
            energy_equivalent_mean_GWh=("energy_equivalent_GWh", "mean"),
        )
        .sort_values(["method", "cf_historical_mean"])
    )


def _setup_plot() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "axes.edgecolor": FG,
            "axes.labelcolor": FG,
            "xtick.color": FG,
            "ytick.color": FG,
            "text.color": FG,
            "font.size": 11,
            "axes.titleweight": "bold",
            "savefig.bbox": "tight",
        }
    )


def _save(fig: plt.Figure, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, facecolor=BG)
    plt.close(fig)


def plot_historical_baseline(
    historical_models: pd.DataFrame,
    monthly_summary: pd.DataFrame,
    output: Path,
) -> None:
    _setup_plot()
    models = historical_models[historical_models["method"] == PRIMARY_METHOD].sort_values(
        "cf_historical_mean"
    )
    monthly = monthly_summary[
        (monthly_summary["method"] == PRIMARY_METHOD)
        & (monthly_summary["scenario"] == "historical")
        & (monthly_summary["horizon"] == "historico")
    ].sort_values("month")
    median = float(models["cf_historical_mean"].median())

    fig, axes = plt.subplots(1, 2, figsize=(16, 6.5), gridspec_kw={"width_ratios": [1.05, 1.2]})
    axes[0].barh(models["model"], models["cf_historical_mean"], color="#65c6e8", alpha=0.9)
    axes[0].axvline(median, color="#f1c40f", lw=2, ls="--", label=f"Mediana: {median:.3f}")
    axes[0].set_xlabel("CF medio 1981–2014")
    axes[0].set_title("Línea base por modelo")
    axes[0].grid(axis="x", alpha=0.25)
    axes[0].legend(frameon=False)

    axes[1].fill_between(
        monthly["month"], monthly["q10"], monthly["q90"], color="#65c6e8", alpha=0.24,
        label="P10–P90 intermodelo",
    )
    axes[1].plot(monthly["month"], monthly["q50"], color="#f1c40f", lw=2.5, label="P50")
    axes[1].set_xticks(range(1, 13))
    axes[1].set_xlabel("Mes")
    axes[1].set_ylabel("Factor de planta")
    axes[1].set_title("Estacionalidad histórica")
    axes[1].grid(alpha=0.25)
    axes[1].legend(frameon=False)
    fig.suptitle(
        "Potencial eólico histórico con integración subdiaria consistente\n"
        "144 estados Weibull/día; la media diaria de viento se conserva exactamente"
    )
    fig.tight_layout()
    _save(fig, output)


def plot_change_percentiles(changes: pd.DataFrame, output: Path) -> None:
    _setup_plot()
    data = changes[changes["method"] == PRIMARY_METHOD].copy()
    horizon_order = {"medio": 0, "lejano": 1}
    scenario_order = {scenario: index for index, scenario in enumerate(SCENARIOS)}
    data["order"] = data["horizon"].map(horizon_order) * 3 + data["scenario"].map(scenario_order)
    data = data.sort_values("order")
    x = np.arange(len(data))
    colors = [SCENARIO_COLORS[value] for value in data["scenario"]]
    yerr = np.vstack((data["q50"] - data["q10"], data["q90"] - data["q50"]))

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.axhline(0, color=FG, lw=1.2, ls="--", alpha=0.75)
    ax.bar(x, data["q50"], color=colors, alpha=0.85)
    ax.errorbar(x, data["q50"], yerr=yerr, fmt="none", ecolor=FG, capsize=8, lw=2)
    for index, (_, row) in enumerate(data.iterrows()):
        ax.text(index, row["q90"] + 0.35, f"{int(row['models_nonnegative'])}/12 ≥ 0", ha="center")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{SCENARIO_LABELS[s]}\n{h}" for s, h in zip(data["scenario"], data["horizon"])]
    )
    ax.set_ylabel("Cambio relativo del CF (%)")
    ax.set_title(
        "Cambio del factor de planta: mediana y P10–P90 entre modelos\n"
        "Método que conserva la señal futura · barras de incertidumbre, no probabilidades"
    )
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    _save(fig, output)


def plot_method_sensitivity(changes: pd.DataFrame, output: Path) -> None:
    _setup_plot()
    labels = [(scenario, horizon) for horizon in ("medio", "lejano") for scenario in SCENARIOS]
    x = np.arange(len(labels), dtype=float)
    offsets = {PRIMARY_METHOD: -0.13, LEGACY_METHOD: 0.13}
    colors = {PRIMARY_METHOD: "#e67e22", LEGACY_METHOD: "#65c6e8"}

    fig, ax = plt.subplots(figsize=(15, 7))
    ax.axhline(0, color=FG, lw=1.2, ls="--", alpha=0.75)
    for method in METHODS:
        selected = []
        for scenario, horizon in labels:
            row = changes[
                (changes["method"] == method)
                & (changes["scenario"] == scenario)
                & (changes["horizon"] == horizon)
            ]
            if len(row) != 1:
                raise ValueError(f"Resumen ambiguo: {method} {scenario} {horizon}")
            selected.append(row.iloc[0])
        frame = pd.DataFrame(selected)
        yerr = np.vstack((frame["q50"] - frame["q10"], frame["q90"] - frame["q50"]))
        ax.errorbar(
            x + offsets[method], frame["q50"], yerr=yerr, fmt="o", ms=8, capsize=7,
            lw=2, color=colors[method], label=METHOD_LABELS[method],
        )
    ax.set_xticks(x)
    ax.set_xticklabels([f"{SCENARIO_LABELS[s]}\n{h}" for s, h in labels])
    ax.set_ylabel("Cambio relativo del CF (%)")
    ax.set_title(
        "Sensibilidad de la señal al tratamiento del sesgo futuro\n"
        "Puntos P50 y barras P10–P90 entre 12 modelos"
    )
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    _save(fig, output)


def plot_monthly_percentiles(monthly: pd.DataFrame, output: Path) -> None:
    _setup_plot()
    data = monthly[monthly["method"] == PRIMARY_METHOD]
    historical = data[
        (data["scenario"] == "historical") & (data["horizon"] == "historico")
    ].sort_values("month")
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.6), sharey=True)
    for ax, scenario in zip(axes, SCENARIOS):
        ax.plot(
            historical["month"], historical["q50"], color="#65c6e8", lw=2.4,
            label="Histórico P50",
        )
        for horizon, color, linestyle in (
            ("medio", "#f1c40f", "-"),
            ("lejano", "#e67e22", "--"),
        ):
            part = data[
                (data["scenario"] == scenario) & (data["horizon"] == horizon)
            ].sort_values("month")
            ax.plot(part["month"], part["q50"], color=color, ls=linestyle, lw=2, label=f"{horizon} P50")
            ax.fill_between(part["month"], part["q10"], part["q90"], color=color, alpha=0.13)
        ax.set_title(SCENARIO_LABELS[scenario])
        ax.set_xticks(range(1, 13))
        ax.set_xlabel("Mes")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Factor de planta")
    axes[-1].legend(frameon=False, fontsize=9)
    fig.suptitle(
        "Estacionalidad del CF: P50 y banda P10–P90 intermodelo\n"
        "Histórico 1981–2014 · medio 2040–2069 · lejano 2070–2099"
    )
    fig.tight_layout()
    _save(fig, output)


def plot_bias_validation(
    monthly_quantiles: pd.DataFrame,
    errors: pd.DataFrame,
    output: Path,
) -> None:
    """Grafica el diagnóstico histórico agregado de la corrección de sesgo."""
    _setup_plot()
    source_styles = {
        "era5": ("ERA5-Land", "#f4f7f8", "-", None, 3.8, 3),
        "cmip6_crudo": ("CMIP6 crudo", "#e67e22", "--", None, 2.5, 2),
        "cmip6_corregido": ("CMIP6 corregido", "#65c6e8", ":", "o", 2.4, 4),
    }
    aggregated_parts: list[pd.DataFrame] = []
    era5 = monthly_quantiles[monthly_quantiles["source"] == "era5"].copy()
    era5["n_models"] = 1
    aggregated_parts.append(era5)
    for source in ("cmip6_crudo", "cmip6_corregido"):
        part = (
            monthly_quantiles[monthly_quantiles["source"] == source]
            .groupby("month", as_index=False)
            .agg(
                q10=("q10", "median"),
                q50=("q50", "median"),
                q90=("q90", "median"),
                n_models=("model", "nunique"),
            )
        )
        part["source"] = source
        aggregated_parts.append(part)
    aggregated = pd.concat(aggregated_parts, ignore_index=True)

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(18, 8),
        gridspec_kw={"width_ratios": [1.15, 1.0]},
    )
    ax = axes[0]
    for source in ("cmip6_crudo", "era5", "cmip6_corregido"):
        label, color, linestyle, marker, linewidth, zorder = source_styles[source]
        part = aggregated[aggregated["source"] == source].sort_values("month")
        ax.fill_between(
            part["month"],
            part["q10"],
            part["q90"],
            color=color,
            alpha={"cmip6_crudo": 0.08, "era5": 0.10, "cmip6_corregido": 0.16}[source],
            zorder=zorder - 1,
        )
        ax.plot(
            part["month"],
            part["q50"],
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            marker=marker,
            markersize=4 if marker else 0,
            label=label,
            zorder=zorder,
        )
    ax.set_xticks(range(1, 13))
    ax.set_xlabel("Mes")
    ax.set_ylabel("Viento diario a 10 m (m/s)")
    ax.set_title(
        "Distribución mensual del viento\n"
        "Líneas: P50 · bandas: P10–P90 · CMIP6: mediana de 12 modelos"
    )
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, ncol=3, fontsize=9, loc="lower left")

    ax = axes[1]
    ordered = errors.sort_values("rmse_raw_m_s", ascending=True).reset_index(drop=True)
    y = np.arange(len(ordered))
    for index, row in ordered.iterrows():
        ax.plot(
            [row["rmse_corrected_m_s"], row["rmse_raw_m_s"]],
            [index, index],
            color=FG,
            alpha=0.35,
            linewidth=1.5,
        )
    ax.scatter(
        ordered["rmse_raw_m_s"],
        y,
        color="#e67e22",
        s=75,
        marker="o",
        label="Antes: CMIP6 crudo",
        zorder=3,
    )
    ax.scatter(
        ordered["rmse_corrected_m_s"],
        y,
        color="#65c6e8",
        s=75,
        marker="D",
        label="Después: CMIP6 corregido",
        zorder=3,
    )
    raw_median = float(errors["rmse_raw_m_s"].median())
    ax.set_yticks(y)
    ax.set_yticklabels(ordered["model"])
    ax.set_xlabel("RMSE de cuantiles mensuales (m/s)")
    ax.set_title(
        "Error por modelo: P10/P50/P90 × 12 meses\n"
        f"Mediana {raw_median:.2f} → <0.01 m/s · ajuste esperado en calibración"
    )
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False, loc="lower right")

    fig.suptitle(
        "Diagnóstico histórico de la corrección de sesgo, 1981–2014\n"
        "Calibración histórica; no es validación predictiva y no se emparejan años ERA5–GCM",
        fontsize=18,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    _save(fig, output)


def write_results(output_root: Path) -> dict[str, Path]:
    """Recalcula tablas y figuras desde los NetCDF locales sin sobrescribirlos."""
    tables_dir = output_root / "tables"
    figures_dir = output_root / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    annual_parts = []
    monthly_parts = []
    for method in METHODS:
        annual, monthly = collect_metrics(method)
        annual_parts.append(annual)
        monthly_parts.append(monthly)
    annual = pd.concat(annual_parts, ignore_index=True)
    monthly = pd.concat(monthly_parts, ignore_index=True)
    per_model, changes = summarize_changes(annual)
    energy, energy_by_model = summarize_energy(annual)
    monthly_summary = summarize_monthly(monthly)
    historical_models = summarize_historical_models(annual)
    validation_quantiles, validation_errors = collect_bias_validation()

    outputs = {
        "annual": tables_dir / "metricas_anuales.csv",
        "monthly_by_model": tables_dir / "climatologia_mensual_por_modelo.csv",
        "historical_models": tables_dir / "linea_base_historica_por_modelo.csv",
        "change_by_model": tables_dir / "cambio_cf_por_modelo.csv",
        "change_percentiles": tables_dir / "percentiles_cambio_cf.csv",
        "monthly_percentiles": tables_dir / "percentiles_cf_mensual.csv",
        "energy_percentiles": tables_dir / "percentiles_energia_academica.csv",
        "energy_by_model": tables_dir / "percentiles_energia_interanual_por_modelo.csv",
        "validation_quantiles": tables_dir / "validacion_cuantiles_mensuales.csv",
        "validation_errors": tables_dir / "validacion_error_cuantiles_por_modelo.csv",
    }
    annual.to_csv(outputs["annual"], index=False)
    monthly.to_csv(outputs["monthly_by_model"], index=False)
    historical_models.to_csv(outputs["historical_models"], index=False)
    per_model.to_csv(outputs["change_by_model"], index=False)
    changes.to_csv(outputs["change_percentiles"], index=False)
    monthly_summary.to_csv(outputs["monthly_percentiles"], index=False)
    energy.to_csv(outputs["energy_percentiles"], index=False)
    energy_by_model.to_csv(outputs["energy_by_model"], index=False)
    validation_quantiles.to_csv(outputs["validation_quantiles"], index=False)
    validation_errors.to_csv(outputs["validation_errors"], index=False)

    plot_historical_baseline(
        historical_models, monthly_summary, figures_dir / "01_linea_base_historica.png"
    )
    plot_change_percentiles(changes, figures_dir / "02_cambio_cf_percentiles.png")
    plot_method_sensitivity(changes, figures_dir / "03_sensibilidad_metodologica.png")
    plot_monthly_percentiles(monthly_summary, figures_dir / "04_estacionalidad_cf.png")
    plot_bias_validation(
        validation_quantiles,
        validation_errors,
        figures_dir / "05_validacion_correccion_sesgo.png",
    )
    return outputs


def regenerate_figures_from_tables(output_root: Path) -> None:
    """Regenera la galería pública únicamente desde los CSV versionados."""
    tables = output_root / "tables"
    figures = output_root / "figures"
    historical_models = pd.read_csv(tables / "linea_base_historica_por_modelo.csv")
    changes = pd.read_csv(tables / "percentiles_cambio_cf.csv")
    monthly = pd.read_csv(tables / "percentiles_cf_mensual.csv")
    validation_quantiles = pd.read_csv(tables / "validacion_cuantiles_mensuales.csv")
    validation_errors = pd.read_csv(
        tables / "validacion_error_cuantiles_por_modelo.csv"
    )
    plot_historical_baseline(historical_models, monthly, figures / "01_linea_base_historica.png")
    plot_change_percentiles(changes, figures / "02_cambio_cf_percentiles.png")
    plot_method_sensitivity(changes, figures / "03_sensibilidad_metodologica.png")
    plot_monthly_percentiles(monthly, figures / "04_estacionalidad_cf.png")
    plot_bias_validation(
        validation_quantiles,
        validation_errors,
        figures / "05_validacion_correccion_sesgo.png",
    )
