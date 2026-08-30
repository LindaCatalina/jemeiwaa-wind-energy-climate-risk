"""
Reconstruye metrics_future.csv a partir de los archivos subdiarios ya generados
en synthetic_10min/*.nc. No vuelve a correr síntesis; solo lee y resume.
"""

from pathlib import Path
import pandas as pd
import xarray as xr

SYN_DIR = Path("CMIP6_Guajira/synthetic_10min")
OUT_CSV = Path("CMIP6_Guajira/metrics_future/tables/metrics_future.csv")
TURBINES = 162

SEASONS = {
    "DJF": [12, 1, 2],
    "MAM": [3, 4, 5],
    "JJA": [6, 7, 8],
    "SON": [9, 10, 11],
}


def season_mean(da, months):
    return float(da.sel(time=da["time.month"].isin(months)).mean())


def main():
    rows = []
    files = sorted(SYN_DIR.glob("*_subdaily.nc"))
    if not files:
        print(f"[WARN] No se encontraron archivos en {SYN_DIR}")
        return

    for f in files:
        stem = f.stem.replace("_subdaily", "")
        try:
            model, exp = stem.split("_", 1)
        except ValueError:
            print(f"[WARN] Nombre inesperado: {f.name}, se omite")
            continue

        ds = xr.open_dataset(f)
        # Variables corregidas
        cf10 = ds["cf_10min"]
        p10 = ds["power_10min"]
        v10 = ds["v150_10min"]

        # Agregaciones diarias
        cf_day = cf10.resample(time="1D").mean()
        p_day = p10.resample(time="1D").mean()

        tag = "hist" if exp == "historical" else "fut"

        row = {"model": model, "exp": exp}
        row[f"cf_mean_{tag}"] = float(cf10.mean())
        row[f"P50_CF_{tag}"] = float(cf10.quantile(0.5))
        row[f"P90_CF_{tag}"] = float(cf10.quantile(0.9))

        # Energía turbina (MWh) y planta
        energy_turb_MWh = float(p10.sum() * (10.0 / 60.0))  # cada muestra 10 min
        row[f"energy_turb_MWh_{tag}"] = energy_turb_MWh
        row[f"energy_plant_MWh_{tag}"] = energy_turb_MWh * TURBINES

        # Días con viento <5 m/s (media diaria) o >25 m/s (al menos un intervalo)
        v_day_mean = v10.resample(time="1D").mean()
        days_lt5 = float((v_day_mean < 5).mean() * 365)
        days_gt25 = float((v10 > 25).resample(time="1D").any().mean() * 365)
        row[f"days_lt5_{tag}"] = days_lt5
        row[f"days_gt25_{tag}"] = days_gt25

        # Medias estacionales de CF diario
        for sea, months in SEASONS.items():
            row[f"cf_{sea}_{tag}"] = season_mean(cf_day, months)

        rows.append(row)

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"[OK] metrics_future.csv regenerado con {len(df)} filas -> {OUT_CSV}")


if __name__ == "__main__":
    main()
