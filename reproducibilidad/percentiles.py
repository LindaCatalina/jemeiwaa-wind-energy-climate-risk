"""Percentiles, P50/P90 y figuras de incertidumbre intermodelo."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from .config import (
    CANONICAL_MODELS,
    CORRECTED_DIR,
    HORIZONS,
    LEGACY_SPLIT_TABLE,
    PLANT_CAPACITY_MW,
    SCENARIOS,
)
from .core import (
    as_time_series,
    cf_from_wind_reference_density,
    load_quantiles,
    load_raw_wind,
    month_values,
    trend_preserving_qm,
    year_values,
)

BG = "#032738"
FG = "#f4f7f8"
SCENARIO_COLORS = {"ssp126": "#65c6e8", "ssp245": "#f1c40f", "ssp585": "#e67e22"}
Q = (0.10, 0.25, 0.50, 0.75, 0.90)


def _quantiles(values: pd.Series | np.ndarray) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {"q10": np.nan, "q25": np.nan, "q50": np.nan, "q75": np.nan, "q90": np.nan}
    q = np.quantile(arr, Q)
    return dict(zip(("q10", "q25", "q50", "q75", "q90"), map(float, q)))


def _load_cf(model: str, experiment: str, method: str) -> xr.DataArray:
    if method == "legado":
        path = CORRECTED_DIR / f"{model}_{experiment}_wind_bc.nc"
        ds = xr.open_dataset(path)
        try:
            return as_time_series(ds["cf"]).load()
        finally:
            ds.close()
    if method == "sensibilidad_sin_recentrado":
        raw = load_raw_wind(model, experiment)
        corrected = trend_preserving_qm(raw, load_quantiles(model))
        return cf_from_wind_reference_density(corrected)
    raise ValueError(f"Método desconocido: {method}")


def _append_period(
    annual_rows: list[dict],
    monthly_rows: list[dict],
    model: str,
    scenario: str,
    horizon: str,
    da: xr.DataArray,
    start_year: int,
    end_year: int,
) -> None:
    years = year_values(da)
    months = month_values(da)
    values = np.asarray(da.values, dtype=float)
    period = (years >= start_year) & (years <= end_year) & np.isfinite(values)
    if not period.any():
        raise ValueError(f"Periodo vacío: {model} {scenario} {horizon}")

    for year in np.unique(years[period]):
        mask = period & (years == year)
        cf_annual = float(np.mean(values[mask]))
        represented_hours = int(mask.sum()) * 24
        annual_rows.append(
            {
                "model": model,
                "scenario": scenario,
                "horizon": horizon,
                "year": int(year),
                "n_days": int(mask.sum()),
                "cf_annual": cf_annual,
                "energy_plant_GWh": cf_annual * PLANT_CAPACITY_MW * represented_hours / 1000.0,
            }
        )

    for month in range(1, 13):
        mask = period & (months == month)
        monthly_rows.append(
            {
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
        hist = _load_cf(model, "historical", method)
        _append_period(
            annual_rows,
            monthly_rows,
            model,
            "historical",
            "historico",
            hist,
            *HORIZONS["historico"],
        )
        for scenario in SCENARIOS:
            future = _load_cf(model, scenario, method)
            for horizon in ("medio", "lejano"):
                _append_period(
                    annual_rows,
                    monthly_rows,
                    model,
                    scenario,
                    horizon,
                    future,
                    *HORIZONS[horizon],
                )
    return pd.DataFrame(annual_rows), pd.DataFrame(monthly_rows)


def summarize_changes(annual: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    hist = (
        annual[(annual["scenario"] == "historical") & (annual["horizon"] == "historico")]
        .groupby("model", as_index=False)["cf_annual"]
        .mean()
        .rename(columns={"cf_annual": "cf_hist"})
    )
    future = (
        annual[annual["scenario"] != "historical"]
        .groupby(["model", "scenario", "horizon"], as_index=False)["cf_annual"]
        .mean()
        .rename(columns={"cf_annual": "cf_future"})
        .merge(hist, on="model", validate="many_to_one")
    )
    future["delta_cf_pp"] = 100.0 * (future["cf_future"] - future["cf_hist"])
    future["delta_cf_pct"] = 100.0 * (future["cf_future"] / future["cf_hist"] - 1.0)

    summary_rows = []
    for (scenario, horizon), group in future.groupby(["scenario", "horizon"], sort=False):
        row = {
            "scenario": scenario,
            "horizon": horizon,
            "n_models": int(group["model"].nunique()),
            "models_nonnegative": int((group["delta_cf_pct"] >= 0).sum()),
            "fraction_models_nonnegative": float((group["delta_cf_pct"] >= 0).mean()),
            "min": float(group["delta_cf_pct"].min()),
            "max": float(group["delta_cf_pct"].max()),
            "mean": float(group["delta_cf_pct"].mean()),
        }
        row.update(_quantiles(group["delta_cf_pct"]))
        summary_rows.append(row)
    return future.sort_values(["horizon", "scenario", "model"]), pd.DataFrame(summary_rows)


def summarize_energy(annual: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Primero se obtiene una climatología por modelo. Después se cuantifica el
    # spread entre modelos, sin tratar los miembros CMIP6 como probabilidades.
    climatologies = (
        annual.groupby(["model", "scenario", "horizon"], as_index=False)["energy_plant_GWh"]
        .mean()
        .rename(columns={"energy_plant_GWh": "mean_annual_energy_GWh"})
    )
    ensemble_rows = []
    for (scenario, horizon), group in climatologies.groupby(["scenario", "horizon"], sort=False):
        row = {
            "scenario": scenario,
            "horizon": horizon,
            "n_models": int(group["model"].nunique()),
            "mean_GWh": float(group["mean_annual_energy_GWh"].mean()),
        }
        row.update(_quantiles(group["mean_annual_energy_GWh"]))
        # Convención de excedencia: P90 es el cuantil bajo q10; P10 es q90.
        row["P90_exceedance_GWh"] = row["q10"]
        row["P50_exceedance_GWh"] = row["q50"]
        row["P10_exceedance_GWh"] = row["q90"]
        ensemble_rows.append(row)

    interannual_rows = []
    for keys, group in annual.groupby(["model", "scenario", "horizon"], sort=False):
        model, scenario, horizon = keys
        row = {
            "model": model,
            "scenario": scenario,
            "horizon": horizon,
            "n_years": int(group["year"].nunique()),
            "mean_GWh": float(group["energy_plant_GWh"].mean()),
        }
        row.update(_quantiles(group["energy_plant_GWh"]))
        row["P90_exceedance_GWh"] = row["q10"]
        row["P50_exceedance_GWh"] = row["q50"]
        row["P10_exceedance_GWh"] = row["q90"]
        interannual_rows.append(row)
    return pd.DataFrame(ensemble_rows), pd.DataFrame(interannual_rows)


def summarize_monthly(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in monthly.groupby(["scenario", "horizon", "month"], sort=False):
        scenario, horizon, month = keys
        row = {
            "scenario": scenario,
            "horizon": horizon,
            "month": int(month),
            "n_models": int(group["model"].nunique()),
        }
        row.update(_quantiles(group["cf_monthly_climatology"]))
        rows.append(row)
    return pd.DataFrame(rows)


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
            "grid.color": "#52707c",
            "font.size": 10,
        }
    )


def plot_change_percentiles(summary: pd.DataFrame, out: Path, title_suffix: str) -> None:
    _setup_plot()
    order = [(s, h) for h in ("medio", "lejano") for s in SCENARIOS]
    data = summary.set_index(["scenario", "horizon"]).loc[order].reset_index()
    x = np.arange(len(data))
    y = data["q50"].to_numpy()
    yerr = np.vstack((y - data["q10"].to_numpy(), data["q90"].to_numpy() - y))
    colors = [SCENARIO_COLORS[s] for s in data["scenario"]]

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.axhline(0.0, color=FG, lw=1, ls="--", alpha=0.7)
    ax.bar(x, y, color=colors, alpha=0.85, width=0.7)
    ax.errorbar(x, y, yerr=yerr, fmt="none", ecolor=FG, capsize=6, lw=1.5)
    data_span = float(data["q90"].max() - data["q10"].min())
    label_offset = max(0.45, 0.035 * data_span)
    for i, row in data.iterrows():
        ax.text(
            i,
            row["q90"] + label_offset,
            f"{int(row['models_nonnegative'])}/{int(row['n_models'])} ≥ 0",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    lower = float(data["q10"].min()) - max(0.6, 0.05 * data_span)
    upper = float(data["q90"].max()) + max(1.6, 0.14 * data_span)
    ax.set_ylim(lower, upper)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s.upper()}\n{h}" for s, h in order])
    ax.set_ylabel("Cambio relativo del CF (%)")
    ax.set_title(f"Cambio del factor de planta: mediana y P10–P90\n{title_suffix}", pad=16)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(rect=(0.01, 0.01, 0.99, 0.95))
    fig.savefig(out, dpi=200, facecolor=BG)
    plt.close(fig)


def plot_model_changes(per_model: pd.DataFrame, out: Path, title_suffix: str) -> None:
    _setup_plot()
    fig, axes = plt.subplots(1, 2, figsize=(17, 7), sharey=True)
    for ax, horizon in zip(axes, ("medio", "lejano")):
        part = per_model[per_model["horizon"] == horizon]
        positions = np.arange(len(CANONICAL_MODELS))
        offsets = dict(zip(SCENARIOS, (-0.22, 0.0, 0.22)))
        ax.axhline(0.0, color=FG, lw=1, ls="--", alpha=0.7)
        for scenario in SCENARIOS:
            values = (
                part[part["scenario"] == scenario]
                .set_index("model")
                .reindex(CANONICAL_MODELS)["delta_cf_pct"]
            )
            ax.scatter(
                positions + offsets[scenario],
                values,
                s=40,
                color=SCENARIO_COLORS[scenario],
                label=scenario.upper(),
            )
        ax.set_xticks(positions)
        ax.set_xticklabels(CANONICAL_MODELS, rotation=65, ha="right", fontsize=8)
        ax.set_title(horizon.capitalize())
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Cambio relativo del CF (%)")
    axes[1].legend(frameon=False)
    fig.suptitle(f"Dispersión intermodelo por escenario\n{title_suffix}")
    fig.tight_layout()
    fig.savefig(out, dpi=200, facecolor=BG)
    plt.close(fig)


def plot_energy_exceedance(energy: pd.DataFrame, out: Path, title_suffix: str) -> None:
    _setup_plot()
    order = [("historical", "historico")] + [
        (s, h) for h in ("medio", "lejano") for s in SCENARIOS
    ]
    data = energy.set_index(["scenario", "horizon"]).loc[order].reset_index()
    x = np.arange(len(data))
    width = 0.36
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.bar(x - width / 2, data["P90_exceedance_GWh"], width, label="P90 excedencia (q10)", color="#65c6e8")
    ax.bar(x + width / 2, data["P50_exceedance_GWh"], width, label="P50 excedencia (q50)", color="#f1c40f")
    labels = ["Histórico"] + [f"{s.upper()}\n{h}" for s, h in order[1:]]
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Energía anual de planta (GWh/año)")
    ax.set_title(f"Energía anual: P50 y P90 empíricos del spread intermodelo\n{title_suffix}")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=200, facecolor=BG)
    plt.close(fig)


def plot_monthly_percentiles(monthly: pd.DataFrame, out: Path, title_suffix: str) -> None:
    _setup_plot()
    hist = monthly[(monthly["scenario"] == "historical") & (monthly["horizon"] == "historico")]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    for ax, scenario in zip(axes, SCENARIOS):
        ax.plot(hist["month"], hist["q50"], color="#65c6e8", lw=2.2, label="Histórico P50")
        for horizon, color, ls in (("medio", "#f1c40f", "-"), ("lejano", "#e67e22", "--")):
            part = monthly[(monthly["scenario"] == scenario) & (monthly["horizon"] == horizon)]
            ax.plot(part["month"], part["q50"], color=color, ls=ls, lw=2, label=f"{horizon} P50")
            ax.fill_between(part["month"], part["q10"], part["q90"], color=color, alpha=0.14)
        ax.set_title(scenario.upper())
        ax.set_xticks(range(1, 13))
        ax.set_xlabel("Mes")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Factor de planta")
    axes[-1].legend(frameon=False, fontsize=9)
    fig.suptitle(f"Comportamiento mensual: mediana y P10–P90 intermodelo\n{title_suffix}")
    fig.tight_layout()
    fig.savefig(out, dpi=200, facecolor=BG)
    plt.close(fig)


def repair_legacy_delta_figures(output_dir: Path) -> pd.DataFrame:
    """Repara, sin sobrescribir, las dos figuras legadas que quedaron vacías."""
    table = pd.read_csv(LEGACY_SPLIT_TABLE)
    hist = table[(table["exp"] == "historical") & (table["horizon"] == "hist")][
        ["model", "cf_mean", "energy_plant_MWh"]
    ].rename(columns={"cf_mean": "cf_hist", "energy_plant_MWh": "energy_hist_total"})
    future = table[(table["exp"].isin(SCENARIOS)) & (table["horizon"].isin(["mid", "late"]))].copy()
    repaired = future.merge(hist, on="model", validate="many_to_one")
    repaired["delta_cf_pct"] = 100.0 * (repaired["cf_mean"] / repaired["cf_hist"] - 1.0)
    years = {"mid": 30.0, "late": 30.0}
    repaired["energy_future_annual_MWh"] = repaired.apply(
        lambda row: row["energy_plant_MWh"] / years[row["horizon"]], axis=1
    )
    repaired["energy_hist_annual_MWh"] = repaired["energy_hist_total"] / 34.0
    repaired["delta_energy_annual_pct"] = 100.0 * (
        repaired["energy_future_annual_MWh"] / repaired["energy_hist_annual_MWh"] - 1.0
    )
    repaired = repaired.sort_values(["horizon", "exp", "model"])
    output_dir.mkdir(parents=True, exist_ok=True)
    repaired.to_csv(output_dir / "deltas_sinteticos_legados_reparados.csv", index=False)

    _setup_plot()
    for column, ylabel, filename, title in (
        ("delta_cf_pct", "ΔCF (%)", "delta_cf_models_REPARADA.png", "Cambio de CF sintético frente al histórico"),
        (
            "delta_energy_annual_pct",
            "Δ energía anualizada (%)",
            "delta_energy_models_REPARADA.png",
            "Cambio de energía anualizada frente al histórico",
        ),
    ):
        fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharey=True)
        for ax, horizon in zip(axes, ("mid", "late")):
            part = repaired[repaired["horizon"] == horizon]
            labels = [f"{m}\n{s.upper()}" for m, s in zip(part["model"], part["exp"])]
            values = part[column].to_numpy()
            ax.axhline(0.0, color=FG, lw=1, ls="--")
            ax.bar(np.arange(len(part)), values, color=[SCENARIO_COLORS[s] for s in part["exp"]])
            ax.set_xticks(np.arange(len(part)))
            ax.set_xticklabels(labels, rotation=70, ha="right", fontsize=7)
            ax.set_title(horizon)
            ax.set_ylabel(ylabel)
            ax.grid(axis="y", alpha=0.25)
        fig.suptitle(f"{title}\nFigura reparada; mismos datos legados, sin sobrescribir originales")
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=200, facecolor=BG)
        plt.close(fig)
    return repaired


def run_percentile_analysis(output_root: Path, method: str) -> dict[str, Path]:
    method_dir = output_root / method
    tables = method_dir / "tablas"
    figures = method_dir / "figuras"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    annual, monthly = collect_metrics(method)
    per_model, changes = summarize_changes(annual)
    energy_ensemble, energy_interannual = summarize_energy(annual)
    monthly_summary = summarize_monthly(monthly)

    outputs = {
        "annual": tables / "metricas_anuales_modelo.csv",
        "per_model": tables / "cambio_cf_por_modelo.csv",
        "changes": tables / "percentiles_cambio_cf_ensemble.csv",
        "energy_ensemble": tables / "percentiles_energia_ensemble.csv",
        "energy_interannual": tables / "percentiles_energia_interanual_por_modelo.csv",
        "monthly": tables / "percentiles_cf_mensual_ensemble.csv",
    }
    annual.to_csv(outputs["annual"], index=False)
    per_model.to_csv(outputs["per_model"], index=False)
    changes.to_csv(outputs["changes"], index=False)
    energy_ensemble.to_csv(outputs["energy_ensemble"], index=False)
    energy_interannual.to_csv(outputs["energy_interannual"], index=False)
    monthly_summary.to_csv(outputs["monthly"], index=False)

    title_suffix = (
        "resultados originales corregidos (densidad disponible por archivo)"
        if method == "legado"
        else "sensibilidad: QM sin recentrado futuro y densidad de referencia"
    )
    plot_change_percentiles(changes, figures / "01_cambio_cf_percentiles.png", title_suffix)
    plot_model_changes(per_model, figures / "02_cambio_cf_por_modelo.png", title_suffix)
    plot_energy_exceedance(energy_ensemble, figures / "03_energia_p50_p90.png", title_suffix)
    plot_monthly_percentiles(monthly_summary, figures / "04_cf_mensual_percentiles.png", title_suffix)
    return outputs
