"""Validation and reliability checks (methodology section 9). Reads PREPROCESSED, ANALYSIS and optional reference data.

What this script can and cannot do:
  * ALWAYS: internal consistency (GPM IMERG vs NASA POWER rainfall), baseline-sensitivity of the target-season
    rainfall flag, and a quality checklist. These are consistency checks, NOT independent validation.
  * ONLY IF YOU SUPPLY FILES in DATA/reference/ (see HOW_TO_RUN.txt):
        imd_rainfall_monthly.csv      columns: unit,month(YYYY-MM),rain_mm      -> GPM vs IMD  (MBE, RMSE, r)
        imd_temperature_monthly.csv   columns: unit,month(YYYY-MM),t2m          -> POWER vs IMD
        official_crop_area_ha.csv     columns: unit,area_ha                      -> cropland mask vs official area
"""
import numpy as np, pandas as pd
import config

PREP, OUT, RAW, REF = config.PREP_DIR, config.ANALYSIS_DIR, config.RAW_DIR, config.REF_DIR
rep, rows = ["# Validation and reliability report", "",
             "Consistency checks are not independent validation. Independent comparison runs only when reference files "
             "are placed in DATA/reference/.", ""], []

def metrics(a, b):
    d = pd.concat([a, b], axis=1).dropna()
    d.columns = ["x", "ref"]
    if len(d) < 5:
        return None
    return {"n": len(d), "MBE": float((d.x - d.ref).mean()), "RMSE": float(np.sqrt(((d.x - d.ref) ** 2).mean())),
            "r": float(d.x.corr(d.ref))}

def add(name, m, note=""):
    if m is None:
        rep.append(f"- {name}: not enough matched data."); return
    rows.append({"check": name, **m})
    rep.append(f"- {name}: n={m['n']}, MBE={m['MBE']:.2f}, RMSE={m['RMSE']:.2f}, r={m['r']:.2f}. {note}")

# ---- 1. Internal consistency: GPM monthly vs POWER monthly precipitation ----
gpm = pd.read_csv(PREP / "gpm_monthly_clean.csv")
gpm = gpm[gpm["complete"]].set_index(["unit", "month"])["rain_mm"]
pw = pd.read_csv(PREP / "power_daily_clean.csv", parse_dates=["date"])
pw["month"] = pw["date"].dt.strftime("%Y-%m")
pwm = pw.groupby(["unit", "month"]).agg(rain=("PRECTOTCORR", "sum"), t2m=("T2M", "mean"))
rep.append("## 1. Consistency check: GPM IMERG vs NASA POWER monthly rainfall (mm)")
add("GPM vs POWER (monthly, all blocks)", metrics(gpm, pwm["rain"]),
    "Both are satellite-based and not fully independent; a good match shows the processing is coherent, not that rainfall is correct.")
rep.append("")

# ---- 2. Independent reference data (optional) ----
rep.append("## 2. Independent reference comparison")
found = False
f = REF / "imd_rainfall_monthly.csv"
if f.exists():
    found = True
    ref = pd.read_csv(f).set_index(["unit", "month"])["rain_mm"]
    add("GPM IMERG vs IMD rainfall (monthly)", metrics(gpm, ref), "Check IMD grid/station support matches the block.")
f = REF / "imd_temperature_monthly.csv"
if f.exists():
    found = True
    ref = pd.read_csv(f).set_index(["unit", "month"])["t2m"]
    add("POWER T2M vs IMD temperature (monthly mean, deg C)", metrics(pwm["t2m"], ref))
f = REF / "official_crop_area_ha.csv"
if f.exists():
    found = True
    crop = pd.read_csv(RAW / "cropland_pixels_by_unit.csv")
    crop["mask_ha"] = crop["crop_px_30m"] * config.HA_PER_PIXEL
    c = crop.merge(pd.read_csv(f), on="unit")
    c["diff_pct"] = 100 * (c["mask_ha"] - c["area_ha"]) / c["area_ha"]
    c.to_csv(OUT / "validation_cropland_vs_official.csv", index=False)
    rep.append(f"- Cropland mask vs official area: mean difference {c['diff_pct'].mean():.1f}% "
               f"(range {c['diff_pct'].min():.1f}% to {c['diff_pct'].max():.1f}%) -> validation_cropland_vs_official.csv")
if not found:
    rep.append("- **No independent reference files supplied.** Rainfall, temperature and the cropland mask are therefore "
               "reported as UNVALIDATED satellite/model estimates.")
rep.append("")

# ---- 3. Sensitivity of the rainfall flag to the baseline period ----
rep.append("## 3. Sensitivity: does the target-season rainfall flag change with the baseline years?")
master = pd.read_csv(PREP / "master_seasonal_by_unit.csv")
tgt = pd.read_csv(OUT / "acsi_target_season.csv")
ty, ts = int(tgt["year"].iloc[0]), tgt["season"].iloc[0]
res = {}
for lab, (y0, y1) in {"2015-2024 (default)": config.CLIM_BASELINE, "2018-2024": (2018, 2024), "2015-2022": (2015, 2022)}.items():
    b = master[(master["season"] == ts) & master["rain_ok"] & master["year"].between(y0, y1)].groupby("unit")["rain_mm"].mean()
    cur = master[(master["season"] == ts) & (master["year"] == ty)].set_index("unit")["rain_mm"]
    pct = 100 * (cur - b) / b.where(b >= config.RAIN_BASELINE_MIN_MM)
    res[lab] = pct
sens = pd.DataFrame(res).round(1)
sens["flag_changes"] = (sens.le(-config.RAIN_DEFICIT_PCT).nunique(axis=1) > 1)
sens.to_csv(OUT / "validation_baseline_sensitivity.csv")
unstable = sens.index[sens["flag_changes"]].tolist()
rep.append(f"Rainfall anomaly % for {ts} {ty} under alternative baselines (see validation_baseline_sensitivity.csv). "
           f"Blocks whose rainfall-deficit flag changes: {unstable if unstable else 'none'}.")
rep.append("")

# ---- 4. Dry-day threshold sensitivity ----
if "dry_spell_max_alt_d" in tgt.columns:
    d = tgt[["unit", "dry_spell_max_d", "dry_spell_max_alt_d"]].rename(columns={
        "dry_spell_max_d": f"longest dry spell, <{config.DRY_DAY_MM} mm/day", "dry_spell_max_alt_d": f"<{config.DRY_DAY_ALT_MM} mm/day"})
    rep += ["## 4. Dry-spell threshold sensitivity (days)", "```", d.to_string(index=False), "```", ""]

# ---- 5. Quality checklist ----
tag = RAW / "hls_mask_info.txt"
mask_txt = tag.read_text().strip() if tag.exists() else "legacy: bits 1-4 only (no water / aerosol bit)"
rep += ["## 5. Quality checklist (methodology section 13)",
        f"- HLS quality mask in raw data: {mask_txt}",
        "- GPM half-hourly rate (mm/hr) x 0.5 h before summing: implemented in 01_download_raw.py",
        "- Seasonal comparisons use the same season window and baseline: implemented in 03_analysis.py",
        "- Missing indicators are never set to zero; weights are renormalised; blocks need >= "
        f"{config.MIN_INDICATORS} indicators: implemented",
        "- Boundary source/year, season months (assumed convention) and crop calendar: **must be confirmed locally**",
        "- Official crop statistics, irrigation, soil moisture (SMAP): not included unless supplied", ""]
(OUT / "validation_report.md").write_text("\n".join(rep), encoding="utf-8")
pd.DataFrame(rows).to_csv(OUT / "validation_metrics.csv", index=False)
print("\n".join(rep)); print("Validation finished ->", OUT)
