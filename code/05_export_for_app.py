"""Copy the results the dashboard needs into app\\data (so the app runs without Earth Engine)."""
import json, shutil
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
import config

out = Path(__file__).resolve().parent.parent / "app" / "data"
out.mkdir(parents=True, exist_ok=True)
A, P, R = config.ANALYSIS_DIR, config.PREP_DIR, config.RAW_DIR
for src in [A / "acsi_all_seasons.csv", A / "acsi_target_season.csv", A / "sensitivity_target_season.csv",
            A / "analysis_report.md", P / "qc_report.txt",
            A / "exposure_target_season.csv", A / "exposure_district_summary.csv",
            A / "validation_report.md", A / "validation_metrics.csv", A / "validation_baseline_sensitivity.csv",
            R / "soil_by_unit.csv",
            R / "latest_window_summary.csv", R / "latest_rainfall_daily.csv"]:
    if src.exists():
        shutil.copy(src, out / src.name); print("copied", src.name)
    else:
        print("not found (skipped):", src.name)

# small extras used by the dashboard (cropland area per block; HLS image count per month)
crop_src = R / "cropland_pixels_by_unit.csv"
if crop_src.exists():
    shutil.copy(crop_src, out / crop_src.name); print("copied", crop_src.name)
hls_src = P / "hls_monthly_clean.csv"
if hls_src.exists():
    pd.read_csv(hls_src).groupby("month", as_index=False)["n_images"].max().to_csv(out / "hls_images_per_month.csv", index=False)
    print("wrote hls_images_per_month.csv")

def polys(g):
    if not isinstance(g, dict): return
    t = g.get("type")
    if t == "Polygon" and "coordinates" in g: yield g["coordinates"]
    elif t == "MultiPolygon" and "coordinates" in g: yield from g["coordinates"]
    elif "geometries" in g:
        for s in g["geometries"]: yield from polys(s)

gj = json.load(open(R / "units.geojson"))
feats = []
for f in gj["features"]:
    pl = [[[[round(x, 4), round(y, 4)] for x, y in ring] for ring in poly] for poly in polys(f["geometry"])]
    if pl:
        feats.append({"type": "Feature", "properties": {"unit": f["properties"]["unit"]},
                      "geometry": {"type": "MultiPolygon", "coordinates": pl}})
    else:
        print("WARNING: no polygon for", f["properties"].get("unit"))
json.dump({"type": "FeatureCollection", "features": feats}, open(out / "units.geojson", "w"))

tgt = pd.read_csv(A / "acsi_target_season.csv")
master = pd.read_csv(P / "master_seasonal_by_unit.csv")
ty, ts = int(tgt["year"].iloc[0]), tgt["season"].iloc[0]
b = master[(master["season"] == ts) & master["veg_ok"] & master["year"].between(*config.VEG_BASELINE)]
t = master[(master["season"] == ts) & (master["year"] == ty)]
meta = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "target_year": ty, "target_season": ts, "weights": config.WEIGHTS, "seasons": config.SEASONS,
        "clim_baseline": config.CLIM_BASELINE, "veg_baseline": config.VEG_BASELINE,
        "gpm_mode": config.GPM_MODE, "min_distinct": config.MIN_DISTINCT_VALUES,
        "hls_images_target": float(t["veg_mean_images"].mean()), "hls_images_baseline": float(b["veg_mean_images"].mean()),
        "rain_deficit_pct": config.RAIN_DEFICIT_PCT, "stress_z": config.STRESS_Z,
        "dry_day_mm": config.DRY_DAY_MM, "ha_per_pixel": config.HA_PER_PIXEL,
        "temp_distinct_values": int(tgt["t2m_mean_anom"].round(3).nunique())}
json.dump(meta, open(out / "meta.json", "w"), indent=1)
print("Exported to", out, "| target:", ts, ty)
