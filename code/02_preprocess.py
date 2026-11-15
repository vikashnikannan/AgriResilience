"""Clean raw tables (DATA\\) -> PREPROCESSED\\. Raw files are never modified."""
import calendar, math
import numpy as np, pandas as pd
import config

RAW, OUT = config.RAW_DIR, config.PREP_DIR
SEAS = config.SEASONS
m2s = {m: s for s, ms in SEAS.items() for m in ms}
n_months_in = {s: len(ms) for s, ms in SEAS.items()}
report = []

def season_days(year, season):
    return sum(calendar.monthrange(int(year), m)[1] for m in SEAS[season])

# ---------------- HLS ----------------
hls = pd.read_csv(RAW / "hls_monthly_by_unit_raw.csv").drop_duplicates(["unit", "month"])
crop = pd.read_csv(RAW / "cropland_pixels_by_unit.csv")
need = {"NDVI_mean", "NDVI_count", "NDMI_mean"}
if need - set(hls.columns):
    raise SystemExit(f"Unexpected HLS columns: {hls.columns.tolist()}")
hls = hls.merge(crop, on="unit", how="left")
hls["valid_cov_pct"] = (100 * hls["NDVI_count"] / hls["crop_px_30m"]).clip(upper=100)
# NaN coverage (no cropland pixels) is treated as low coverage
hls["low_coverage"] = ~(hls["valid_cov_pct"] >= config.MIN_VALID_COV_PCT)
for c in ["NDVI_mean", "NDVI_median", "NDMI_mean", "NDMI_median"]:
    if c in hls.columns:
        hls.loc[hls["low_coverage"], c] = np.nan
hls["year"] = hls["month"].str[:4].astype(int)
hls["mnum"] = hls["month"].str[5:].astype(int)
hls["season"] = hls["mnum"].map(m2s)
hls.to_csv(OUT / "hls_monthly_clean.csv", index=False)
report.append(f"HLS rows: {len(hls)}; low-coverage (<{config.MIN_VALID_COV_PCT}% of cropland) set to NaN: {int(hls['low_coverage'].sum())}")
report.append("Blocks with zero/missing cropland pixels: "
              + str(crop.loc[~(crop["crop_px_30m"] > 0), "unit"].tolist()))
report.append("Median valid coverage % by block:\n" + hls.groupby("unit")["valid_cov_pct"].median().round(1).to_string())

# ---------------- GPM ----------------
gpm = pd.read_csv(RAW / "gpm_monthly_by_unit_raw.csv").drop_duplicates(["unit", "month"])
gpm["completeness"] = gpm["n_images"] / gpm["expected_images"]
gpm["complete"] = gpm["completeness"] >= config.GPM_MIN_COMPLETENESS
gpm["year"] = gpm["month"].str[:4].astype(int)
gpm["mnum"] = gpm["month"].str[5:].astype(int)
gpm["season"] = gpm["mnum"].map(m2s)
gpm.to_csv(OUT / "gpm_monthly_clean.csv", index=False)
report.append(f"GPM rows: {len(gpm)}; months below {config.GPM_MIN_COMPLETENESS:.0%} completeness: {int((~gpm['complete']).sum())}; "
              f"lowest completeness {gpm['completeness'].min():.3f}; sources: {gpm['source'].value_counts().to_dict()}")
inc = gpm.loc[gpm["completeness"] < 1, ["month", "completeness"]].drop_duplicates().sort_values("month")
report.append("Months with any missing 30-min images (rain sums not rescaled):\n" + inc.to_string(index=False))
nimg = hls.drop_duplicates("month").set_index("month")["n_images"]
report.append("HLS images per month (whole study area), summary by year:\n"
              + nimg.groupby(nimg.index.str[:4]).agg(["min", "median", "max"]).to_string())

# ---------------- POWER ----------------
pw = pd.read_csv(RAW / "power_daily_by_unit_raw.csv", parse_dates=["date"])
cols = [c for c in ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR"] if c in pw.columns]
pw[cols] = pw[cols].replace(-999, np.nan)          # POWER fill value
pw["year"] = pw["date"].dt.year
pw["season"] = pw["date"].dt.month.map(m2s)
pw.to_csv(OUT / "power_daily_clean.csv", index=False)
report.append("POWER missing fraction:\n" + pw[cols].isna().mean().round(4).to_string())
npts = pw[["lat", "lon"]].round(3).drop_duplicates().shape[0]
sig = pw.dropna(subset=["T2M"]).groupby("unit")["T2M"].apply(lambda x: hash(tuple(x.round(2).iloc[:730])))
report.append(f"POWER: {sig.nunique()} distinct daily T2M series across {pw['unit'].nunique()} blocks")
report.append(f"POWER distinct request points: {npts} for {pw['unit'].nunique()} blocks "
              "(the underlying grid is coarser, so blocks may share a grid cell)")

# ---------------- Dry spells (longest run of consecutive dry days per season) ----------------
def longest_run(is_dry):
    best = cur = 0
    for v in is_dry:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best

if "PRECTOTCORR" in pw.columns:
    pr = pw.dropna(subset=["PRECTOTCORR"]).sort_values(["unit", "date"])
    rows = []
    for (u, y, s_), g in pr.groupby(["unit", "year", "season"]):
        v = g["PRECTOTCORR"].to_numpy()
        rows.append({"unit": u, "year": y, "season": s_,
                     "dry_spell_max_d": longest_run(v < config.DRY_DAY_MM),
                     "dry_spell_max_alt_d": longest_run(v < config.DRY_DAY_ALT_MM),
                     "dry_day_frac": float((v < config.DRY_DAY_MM).mean())})
    dry = pd.DataFrame(rows)
    report.append(f"Dry spells computed from POWER daily PRECTOTCORR (dry day < {config.DRY_DAY_MM} mm; "
                  f"alternative < {config.DRY_DAY_ALT_MM} mm). POWER grid is ~0.5 deg, so blocks may share values.")
else:
    dry = pd.DataFrame(columns=["unit", "year", "season", "dry_spell_max_d", "dry_spell_max_alt_d", "dry_day_frac"])
    report.append("PRECTOTCORR not in POWER file: dry-spell indicator skipped.")

tag_file = RAW / "hls_mask_info.txt"
report.append("HLS quality mask used for the raw download: "
              + (tag_file.read_text().strip() if tag_file.exists()
                 else "bits1-4 only (cloud, adjacent, shadow, snow/ice) - legacy download without water/aerosol masking. "
                      "Re-download HLS with config.HLS_MASK_WATER=True to apply the water bit."))

# ---------------- Seasonal master table ----------------
rain = (gpm.groupby(["unit", "year", "season"])
        .agg(rain_mm=("rain_mm", "sum"), rain_n_months=("month", "count"),
             rain_all_complete=("complete", "all")).reset_index())
rain["rain_ok"] = (rain["rain_n_months"] == rain["season"].map(n_months_in)) & rain["rain_all_complete"]

temp = (pw.groupby(["unit", "year", "season"])
        .agg(t2m_mean=("T2M", "mean"), tmax_mean=("T2M_MAX", "mean"),
             power_rain_mm=("PRECTOTCORR", "sum"), temp_n_days=("T2M", "count")).reset_index())
temp["temp_expected_days"] = [season_days(y, s) for y, s in zip(temp["year"], temp["season"])]
temp["temp_ok"] = temp["temp_n_days"] >= config.MIN_TEMP_DAY_FRAC * temp["temp_expected_days"]

hls["valid_cov_used"] = hls["valid_cov_pct"].where(~hls["low_coverage"])   # months actually used
veg = (hls.groupby(["unit", "year", "season"])
       .agg(ndvi=("NDVI_mean", "mean"), ndmi=("NDMI_mean", "mean"),
            veg_n_valid_months=("NDVI_mean", "count"), veg_mean_images=("n_images", "mean"),
            min_valid_cov_pct=("valid_cov_used", "min")).reset_index())
veg["veg_ok"] = veg["veg_n_valid_months"] >= veg["season"].map(
    lambda s: math.ceil(config.MIN_VEG_MONTH_FRAC * n_months_in[s]))

master = (rain.merge(temp, on=["unit", "year", "season"], how="outer")
              .merge(dry, on=["unit", "year", "season"], how="outer")
              .merge(veg, on=["unit", "year", "season"], how="outer"))
for c in ["rain_ok", "temp_ok", "veg_ok"]:
    master[c] = master[c].fillna(False).astype(bool)
master.to_csv(OUT / "master_seasonal_by_unit.csv", index=False)

report.append(f"Master table: {master.shape}")
report.append("Season-years usable (rain / temp / veg):\n"
              + master.groupby("season")[["rain_ok", "temp_ok", "veg_ok"]].sum().to_string())
(OUT / "qc_report.txt").write_text("\n\n".join(report), encoding="utf-8")
print("\n\n".join(report))
print("\nPreprocessing finished ->", OUT)
