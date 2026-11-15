"""Offline logic test using SYNTHETIC data in a temp folder (never touches D:\\internship\\NASA).
Verifies that scripts 02 and 03 run end to end. Numbers it prints are NOT real results.
Usage: python code\\selftest.py"""
import calendar, os, subprocess, sys, tempfile, json
from pathlib import Path
import numpy as np, pandas as pd

here = Path(__file__).parent
tmp = Path(tempfile.mkdtemp(prefix="agri_selftest_"))
env = dict(os.environ, NASA_BASE=str(tmp))
raw = tmp / "DATA"; raw.mkdir()
rng = np.random.default_rng(1)
units = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9"]
months = pd.date_range("2015-01-01", "2026-11-01", freq="MS", inclusive="left")

pd.DataFrame({"unit": units, "crop_px_30m": rng.integers(50000, 200000, 9)}).to_csv(raw / "cropland_pixels_by_unit.csv", index=False)
crop = pd.read_csv(raw / "cropland_pixels_by_unit.csv").set_index("unit")["crop_px_30m"]

rows = []
for m in months[months >= "2018-01-01"]:
    for i, u in enumerate(units):
        ndvi = 0.5 + 0.1 * np.sin(m.month / 12 * 6.28) + rng.normal(0, 0.03) - (0.08 if (m.year == 2026 and m.month in (6, 7, 8, 9) and i < 3) else 0)
        cov = rng.uniform(0.05, 0.9)
        rows.append({"unit": u, "NDVI_mean": ndvi, "NDVI_median": ndvi, "NDVI_count": cov * crop[u],
                     "NDMI_mean": ndvi * 0.5, "NDMI_median": ndvi * 0.5, "NDMI_count": cov * crop[u],
                     "month": m.strftime("%Y-%m"), "n_images": 20 if m.year >= 2025 and m.month >= 6 else 200})
pd.DataFrame(rows).to_csv(raw / "hls_monthly_by_unit_raw.csv", index=False)

rows = []
for m in months:
    d = calendar.monthrange(m.year, m.month)[1]
    for i, u in enumerate(units):
        base = 80 + 60 * np.sin((m.month - 3) / 12 * 6.28) ** 2
        r = max(0, base * rng.uniform(0.6, 1.4) * (0.5 if (m.year == 2026 and m.month in (6, 7, 8, 9) and i % 2 == 0) else 1))
        rows.append({"unit": u, "rain_mm": r, "month": m.strftime("%Y-%m"), "n_images": d * 48 - (2 if (m.year == 2026 and m.month == 6) else 0),
                     "expected_images": d * 48, "source": "IMERG_V07_30min"})
pd.DataFrame(rows).to_csv(raw / "gpm_monthly_by_unit_raw.csv", index=False)

dates = pd.date_range("2015-01-01", "2026-10-31")
frames = []
cell_noise = [rng.normal(0, 0.5, len(dates)) for _ in range(3)]   # blocks in one cell share one series (like POWER)
for i, u in enumerate(units):
    cell = i // 3
    t = 28 + 3 * np.sin((dates.day_of_year - 90) / 365 * 6.28) + cell * 0.2 + cell_noise[cell]
    df = pd.DataFrame({"date": dates, "T2M": t, "T2M_MAX": t + 4, "T2M_MIN": t - 4,
                       "PRECTOTCORR": rng.exponential(2, len(dates)), "unit": u, "lat": 8.7 + cell * 0.5, "lon": 77.7})
    df.loc[df.sample(20, random_state=i).index, "T2M"] = -999
    frames.append(df)
pd.concat(frames).to_csv(raw / "power_daily_by_unit_raw.csv", index=False)

feats = []
for i, u in enumerate(units):
    x, y = 77 + (i % 3) * 0.3, 8 + (i // 3) * 0.3
    poly = {"type": "Polygon", "coordinates": [[[x, y], [x + .28, y], [x + .28, y + .28], [x, y + .28], [x, y]]]}
    if i == 2:   # exercise GeometryCollection handling (the case that crashed the real run)
        poly = {"type": "GeometryCollection", "geometries": [poly]}
    if i == 3:   # a geometry with no coordinates at all
        poly = {"type": "GeometryCollection", "geometries": []}
    feats.append({"type": "Feature", "properties": {"unit": u}, "geometry": poly})
(raw / "units.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))

for s in ("02_preprocess.py", "03_analysis.py"):
    r = subprocess.run([sys.executable, str(here / s)], cwd=here, env=env, capture_output=True, text=True)
    print(f"--- {s}: exit {r.returncode}")
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-3000:]); sys.exit(1)
out = tmp / "ANALYSIS"
need = ["acsi_all_seasons.csv", "acsi_target_season.csv", "sensitivity_target_season.csv",
        "acsi_by_block.png", "maps_target_season.png", "season_timeseries.png", "analysis_report.md"]
missing = [f for f in need if not (out / f).exists()]
print("Outputs missing:", missing or "none")
print("Synthetic test folder:", tmp)
sys.exit(1 if missing else 0)
