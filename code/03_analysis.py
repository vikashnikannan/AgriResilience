"""Anomalies -> stress indicators -> provisional ACSI -> sensitivity -> charts + report.
Reads PREPROCESSED\\, writes ANALYSIS\\. Screening tool only: not a validated risk model."""
import json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from matplotlib.path import Path
from matplotlib.patches import PathPatch
import config

PREP, OUT, RAW = config.PREP_DIR, config.ANALYSIS_DIR, config.RAW_DIR
W = config.WEIGHTS
STRESS = list(W)
season_start = {s: min(ms) for s, ms in config.SEASONS.items()}
log = []

master = pd.read_csv(PREP / "master_seasonal_by_unit.csv")
for c in ["rain_ok", "temp_ok", "veg_ok"]:
    master[c] = master[c].astype(bool)
n_units = master["unit"].nunique()

# ---------------- 1. Anomalies vs same-season baseline ----------------
VARS = {"rain_mm": ("rain_ok", config.CLIM_BASELINE),
        "t2m_mean": ("temp_ok", config.CLIM_BASELINE),
        "tmax_mean": ("temp_ok", config.CLIM_BASELINE),
        "ndvi": ("veg_ok", config.VEG_BASELINE),
        "ndmi": ("veg_ok", config.VEG_BASELINE),
        "dry_spell_max_d": ("temp_ok", config.CLIM_BASELINE)}   # longest dry spell, from POWER daily precipitation
m = master.copy()
for var, (flag, (y0, y1)) in VARS.items():
    if var not in m.columns:
        m[var] = np.nan
    ok = m[flag] & m[var].notna()
    b = (m[ok & m["year"].between(y0, y1)].groupby(["unit", "season"])[var]
         .agg(["mean", "std", "count"]).reset_index())
    b.columns = ["unit", "season", f"{var}_bmean", f"{var}_bstd", f"{var}_bn"]
    m = m.merge(b, on=["unit", "season"], how="left")
    ok = m[flag] & m[var].notna()
    good = ok & (m[f"{var}_bn"] >= config.MIN_BASELINE_YEARS)
    m[f"{var}_anom"] = np.where(good, m[var] - m[f"{var}_bmean"], np.nan)
    if var == "rain_mm":
        pct_ok = good & (m["rain_mm_bmean"] >= config.RAIN_BASELINE_MIN_MM)
        m["rain_anom_pct"] = np.where(pct_ok, 100 * m["rain_mm_anom"] / m["rain_mm_bmean"], np.nan)
        z_ok = good & (m["rain_mm_bstd"] > 0)
        m["rain_anom_z"] = np.where(z_ok, m["rain_mm_anom"] / m["rain_mm_bstd"], np.nan)

# ---------------- 2. Stress indicators (0-1, 1 = more stress; relative across blocks) ----------------
def minmax(s, min_range):
    s = s.astype(float)
    if s.notna().sum() < 2:
        return pd.Series(np.nan, index=s.index)
    if s.round(3).nunique() < config.MIN_DISTINCT_VALUES:
        return pd.Series(np.nan, index=s.index)       # too few distinct values: no real block-level contrast
    lo, hi = s.min(), s.max()
    if not np.isfinite(lo) or (hi - lo) < min_range:
        return pd.Series(np.nan, index=s.index)       # no usable spatial contrast
    return (s - lo) / (hi - lo)

if config.RAIN_STRESS_METRIC == "pct":
    rain_col, rain_rng = "rain_anom_pct", config.MIN_RANGE["rain_pct"]
else:
    rain_col, rain_rng = "rain_anom_z", config.MIN_RANGE["rain_z"]

parts = []
for _, g in m.groupby(["year", "season"]):
    g = g.copy()
    g["rainfall_stress"]    = minmax(-g[rain_col], rain_rng)
    g["temperature_stress"] = minmax(g["t2m_mean_anom"], config.MIN_RANGE["temp"])
    g["vegetation_stress"]  = minmax(-g["ndvi_anom"], config.MIN_RANGE["ndvi"])
    g["moisture_stress"]    = minmax(-g["ndmi_anom"], config.MIN_RANGE["ndmi"])
    parts.append(g)
m = pd.concat(parts, ignore_index=True)

# ---------------- 3. ACSI with transparent handling of missing indicators ----------------
def acsi(df, weights):
    cols = list(weights)
    w = np.array([weights[c] for c in cols], float)
    X = df[cols].to_numpy(float)
    avail = ~np.isnan(X)
    num = np.nansum(X * w, axis=1)
    den = (avail * w).sum(axis=1)
    enough = avail.sum(axis=1) >= config.MIN_INDICATORS
    with np.errstate(divide="ignore", invalid="ignore"):
        val = np.where(enough & (den > 0), num / den, np.nan)
    return pd.Series(val, index=df.index)

m["ACSI"] = acsi(m, W)
m["n_indicators"] = m[STRESS].notna().sum(axis=1)

def classify(s):
    out = pd.Series("Insufficient data", index=s.index, dtype=object)
    v = s.dropna()
    if len(v) >= 3:
        lo, hi = v.quantile([1 / 3, 2 / 3])
        out.loc[v.index] = np.where(v <= lo, "Lower", np.where(v > hi, "Higher", "Moderate"))
    return out

m["ACSI_class"] = ""
for _, idx in m.groupby(["year", "season"]).groups.items():
    m.loc[idx, "ACSI_class"] = classify(m.loc[idx, "ACSI"])


# ---------------- 3b. VCI, observation reliability, stress flags, concurrent screening ----------------
# VCI = (NDVI - NDVImin) / (NDVImax - NDVImin) x 100, using the same-season baseline range of each block (0-100, clipped).
vb = (m[m["veg_ok"] & m["ndvi"].notna() & m["year"].between(*config.VEG_BASELINE)]
      .groupby(["unit", "season"])["ndvi"].agg(ndvi_min="min", ndvi_max="max").reset_index())
m = m.merge(vb, on=["unit", "season"], how="left")
_rng = m["ndvi_max"] - m["ndvi_min"]
_vci_ok = m["veg_ok"] & m["ndvi"].notna() & (m["ndvi_bn"] >= config.MIN_BASELINE_YEARS) & (_rng > config.MIN_RANGE["ndvi"])
m["vci"] = np.where(_vci_ok, ((m["ndvi"] - m["ndvi_min"]) / _rng * 100).clip(0, 100), np.nan)

# Vegetation observations are only trusted if enough HLS images exist compared with the same-season baseline.
_bi = (m[m["veg_ok"] & m["year"].between(*config.VEG_BASELINE)]
       .groupby(["unit", "season"])["veg_mean_images"].mean().rename("veg_images_baseline").reset_index())
m = m.merge(_bi, on=["unit", "season"], how="left")
m["veg_reliable"] = m["veg_ok"] & (m["veg_mean_images"] >= config.HLS_IMAGE_RATIO_WARN * m["veg_images_baseline"])
m.loc[~m["veg_reliable"], "vci"] = np.nan      # no VCI when too few HLS images were available

def _z(var):
    sd = m[f"{var}_bstd"].where(m[f"{var}_bstd"] > 0)
    return m[f"{var}_anom"] / sd
def _flag(cond, valid):
    return pd.Series(np.where(valid, cond.astype(float), np.nan), index=m.index)

Z = config.STRESS_Z
m["flag_rain"] = _flag(m["rain_anom_pct"] <= -config.RAIN_DEFICIT_PCT, m["rain_anom_pct"].notna())
_zt, _zd, _zn, _zm = _z("t2m_mean"), _z("dry_spell_max_d"), _z("ndvi"), _z("ndmi")
m["flag_heat"] = _flag(_zt >= Z, _zt.notna())
m["flag_dry"] = _flag(_zd >= Z, _zd.notna())
m["flag_veg"] = _flag((_zn <= -Z) | (_zm <= -Z), m["veg_reliable"] & (_zn.notna() | _zm.notna()))

# Heat and dry-spell series come from a coarse grid shared by several blocks. They only enter the block-level screening
# when they show real spatial contrast between blocks in that season; otherwise they are district-wide context.
def _contrast(col):
    nu = m.groupby(["year", "season"])[col].transform(lambda x: x.round(3).nunique())
    return nu >= config.MIN_DISTINCT_VALUES
m["scr_rain"] = m["flag_rain"]
m["scr_veg"] = m["flag_veg"]
m["scr_heat"] = m["flag_heat"].where(_contrast("t2m_mean_anom"))
m["scr_dry"] = m["flag_dry"].where(_contrast("dry_spell_max_d_anom"))
_NAMES = {"scr_rain": "Rainfall", "scr_dry": "Dry spell", "scr_heat": "Heat", "scr_veg": "Vegetation"}
def screen_label(r):
    avail = [k for k in _NAMES if pd.notna(r[k])]
    if len(avail) < 1:
        return "Insufficient observations"
    hit = [_NAMES[k] for k in avail if r[k] == 1]
    note = "" if pd.notna(r["scr_veg"]) else " (vegetation not assessed)"
    lab = ("No stress signal" if not hit else f"{hit[0]} stress only" if len(hit) == 1
           else "Concurrent: " + " + ".join(hit))
    return lab + note
m["n_stress_signals"] = m[list(_NAMES)].fillna(0).sum(axis=1).astype(int)
m["screening_class"] = m.apply(screen_label, axis=1)

keep = ["unit", "year", "season", "rain_mm", "rain_mm_bmean", "rain_mm_anom", "rain_anom_pct", "rain_anom_z",
        "t2m_mean", "t2m_mean_bmean", "t2m_mean_anom", "tmax_mean_anom", "ndvi", "ndvi_bmean", "ndvi_anom",
        "ndmi", "ndmi_bmean", "ndmi_anom", "min_valid_cov_pct", "rain_ok", "temp_ok", "veg_ok",
        "rainfall_stress", "temperature_stress", "vegetation_stress", "moisture_stress",
        "n_indicators", "ACSI", "ACSI_class",
        "dry_spell_max_d", "dry_spell_max_d_bmean", "dry_spell_max_d_anom", "dry_spell_max_alt_d",
        "vci", "veg_mean_images", "veg_images_baseline", "veg_reliable",
        "flag_rain", "flag_dry", "flag_heat", "flag_veg", "scr_heat", "scr_dry", "n_stress_signals", "screening_class"]
m[keep].sort_values(["year", "season", "unit"]).to_csv(OUT / "acsi_all_seasons.csv", index=False)

# ---------------- 4. Target season ----------------
if config.TARGET_YEAR and config.TARGET_SEASON:
    ty, ts = int(config.TARGET_YEAR), config.TARGET_SEASON
else:
    cand = (m.groupby(["year", "season"])["ACSI"].apply(lambda s: s.notna().sum())
            .reset_index(name="n_scored"))
    cand = cand[cand["n_scored"] >= max(3, int(np.ceil(0.67 * n_units)))]
    if cand.empty:
        raise SystemExit("No season has enough scored blocks. Check qc_report.txt in PREPROCESSED.")
    cand["start"] = cand["season"].map(season_start)
    last = cand.sort_values(["year", "start"]).iloc[-1]
    ty, ts = int(last["year"]), last["season"]
print(f"Target season: {ts} {ty}")
tgt = m[(m["year"] == ty) & (m["season"] == ts)].copy().sort_values("ACSI", ascending=False)
tgt.to_csv(OUT / "acsi_target_season.csv", index=False)

# ---------------- 4b. Agricultural exposure (cropland in blocks flagged for each hazard) ----------------
crop = pd.read_csv(RAW / "cropland_pixels_by_unit.csv")
crop["cropland_ha"] = crop["crop_px_30m"] * config.HA_PER_PIXEL
crop["share_of_district_cropland_pct"] = 100 * crop["cropland_ha"] / crop["cropland_ha"].sum()
expo = tgt[["unit", "screening_class", "flag_rain", "flag_dry", "flag_heat", "flag_veg", "vci"]].merge(
    crop[["unit", "cropland_ha", "share_of_district_cropland_pct"]], on="unit", how="left")
expo["flag_rain_veg"] = np.where(expo[["flag_rain", "flag_veg"]].notna().all(axis=1),
                                 ((expo["flag_rain"] == 1) & (expo["flag_veg"] == 1)).astype(float), np.nan)
expo.to_csv(OUT / "exposure_target_season.csv", index=False)
tot_ha = crop["cropland_ha"].sum()
rows = []
for f, lab in [("flag_rain", "Rainfall deficit"), ("flag_dry", "Long dry spell"), ("flag_heat", "Heat anomaly"),
               ("flag_veg", "Vegetation / moisture below usual"), ("flag_rain_veg", "Rainfall deficit + vegetation stress")]:
    a = expo[expo[f].notna()]
    rows.append({"indicator": lab, "exposed_ha": float(a.loc[a[f] == 1, "cropland_ha"].sum()),
                 "exposed_pct_of_district_cropland": 100 * float(a.loc[a[f] == 1, "cropland_ha"].sum()) / tot_ha,
                 "assessed_pct_of_district_cropland": 100 * float(a["cropland_ha"].sum()) / tot_ha,
                 "blocks_flagged": int((a[f] == 1).sum()), "blocks_assessed": int(len(a))})
expo_sum = pd.DataFrame(rows)
expo_sum.to_csv(OUT / "exposure_district_summary.csv", index=False)

# ---------------- 5. Sensitivity of block ranking to weights ----------------
avail_cols = [c for c in STRESS if tgt[c].notna().any()]
sens_note = ""
if len(avail_cols) >= config.MIN_INDICATORS and tgt["ACSI"].notna().sum() >= 3:
    scen = {"base": {c: W[c] for c in avail_cols}, "equal": {c: 1.0 for c in avail_cols}}
    for c in avail_cols:
        scen[f"drop_{c}"] = {k: W[k] for k in avail_cols if k != c}
    ranks = pd.DataFrame(index=tgt["unit"])
    for name, w in scen.items():
        if len(w) >= config.MIN_INDICATORS:
            a = acsi(tgt, w); a.index = tgt["unit"]
            ranks[name] = a.rank(ascending=False, method="min")
    rng = np.random.default_rng(0)
    mc = []
    for _ in range(config.N_MONTE_CARLO):
        d = rng.dirichlet(np.ones(len(avail_cols)))
        a = acsi(tgt, dict(zip(avail_cols, d))); a.index = tgt["unit"]
        mc.append(a.rank(ascending=False, method="min"))
    mc = pd.concat(mc, axis=1)
    summ = ranks.join(pd.DataFrame({"mc_rank_mean": mc.mean(axis=1), "mc_rank_min": mc.min(axis=1),
                                    "mc_rank_max": mc.max(axis=1), "mc_share_top3": (mc <= 3).mean(axis=1)})
                      ).sort_values("base")
    summ.to_csv(OUT / "sensitivity_target_season.csv")
else:
    summ = None
    sens_note = "Sensitivity analysis skipped: too few indicators or scored blocks."

# ---------------- 6. Cross-check: GPM vs POWER seasonal rainfall ----------------
ck = master[master["rain_ok"] & master["temp_ok"]][["rain_mm", "power_rain_mm"]].dropna()
corr = ck.corr().iloc[0, 1] if len(ck) > 10 else np.nan

# ---------------- 7. Charts ----------------
def contributions(df):
    cols = [c for c in STRESS if c in df.columns]
    w = np.array([W[c] for c in cols]); X = df[cols].to_numpy(float)
    den = ((~np.isnan(X)) * w).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return pd.DataFrame(np.nan_to_num(X) * w / den[:, None], columns=cols, index=df.index)

scored = tgt[tgt["ACSI"].notna()].sort_values("ACSI")
if len(scored):
    contrib = contributions(scored)
    fig, ax = plt.subplots(figsize=(9, 5))
    left = np.zeros(len(scored))
    for c in contrib.columns:
        ax.barh(scored["unit"], contrib[c].to_numpy(), left=left, label=c.replace("_", " "))
        left += contrib[c].to_numpy()
    ax.set_xlabel("ACSI (0-1, relative screening score)")
    ax.set_title(f"Provisional ACSI by block: {ts} {ty}\n(stacked = weighted indicator contributions)")
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(OUT / "acsi_by_block.png", dpi=150); plt.close(fig)

geo_path = RAW / "units.geojson"
def iter_polys(g):
    """Yield polygon coordinate lists from Polygon / MultiPolygon / GeometryCollection / Feature."""
    if not isinstance(g, dict):
        return
    t = g.get("type")
    if t == "Polygon" and "coordinates" in g:
        yield g["coordinates"]
    elif t == "MultiPolygon" and "coordinates" in g:
        yield from g["coordinates"]
    elif "geometries" in g:
        for sub in g["geometries"]:
            yield from iter_polys(sub)
    elif t == "Feature":
        yield from iter_polys(g.get("geometry"))

def geom_path(g):
    polys = list(iter_polys(g))
    if not polys:
        return None, None
    verts, codes = [], []
    for poly in polys:
        for ring in poly:
            r = np.asarray(ring)[:, :2]
            verts.extend(r.tolist())
            codes += [Path.MOVETO] + [Path.LINETO] * (len(r) - 2) + [Path.CLOSEPOLY]
    return Path(verts, codes), np.asarray(verts).mean(axis=0)

def draw_map(ax, geoms, values, title, cmap, center=None):
    v = pd.Series(values).astype(float)
    vmin, vmax = np.nanmin(v), np.nanmax(v)
    if center is not None and np.isfinite(vmin):
        lim = max(abs(vmin - center), abs(vmax - center)) or 1
        norm = colors.TwoSlopeNorm(center, center - lim, center + lim)
    else:
        norm = colors.Normalize(vmin if np.isfinite(vmin) else 0, vmax if np.isfinite(vmax) and vmax > vmin else (vmin + 1 if np.isfinite(vmin) else 1))
    cmap = plt.get_cmap(cmap)
    for unit, g in geoms.items():
        p, c = geom_path(g)
        if p is None:
            print('WARNING: no polygon geometry for', unit, '- skipped on map')
            continue
        val = v.get(unit, np.nan)
        ax.add_patch(PathPatch(p, facecolor=cmap(norm(val)) if np.isfinite(val) else "lightgrey",
                               edgecolor="k", lw=0.6))
        ax.text(c[0], c[1], unit, fontsize=6, ha="center")
    ax.autoscale_view(); ax.set_aspect("equal"); ax.set_title(title, fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=0.7)

def make_maps():
    gj = json.load(open(geo_path))
    geoms = {f["properties"]["unit"]: f["geometry"] for f in gj["features"]}
    t = tgt.set_index("unit")
    fig, axs = plt.subplots(2, 2, figsize=(11, 10))
    draw_map(axs[0, 0], geoms, t["ACSI"], f"Provisional ACSI ({ts} {ty})", "YlOrRd")
    draw_map(axs[0, 1], geoms, t["rain_anom_pct"], "Rainfall anomaly (%) - GPM IMERG", "RdBu", 0)
    draw_map(axs[1, 0], geoms, t["ndvi_anom"], "NDVI anomaly (cropland) - HLS", "RdYlGn", 0)
    draw_map(axs[1, 1], geoms, t["t2m_mean_anom"], "Temperature anomaly (C) - NASA POWER", "coolwarm", 0)
    fig.suptitle("Grey = no valid value. Resolutions differ: HLS 30 m, IMERG ~0.1 deg, POWER coarse grid.", fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "maps_target_season.png", dpi=150); plt.close(fig)

if geo_path.exists() and len(tgt):
    try:
        make_maps()
    except Exception as ex:
        print('WARNING: maps skipped:', repr(ex))

ts_df = master[(master["season"] == ts)]
fig, axs = plt.subplots(1, 2, figsize=(11, 4))
for ax, var, flag, lab, (y0, y1) in [
        (axs[0], "rain_mm", "rain_ok", "Rainfall (mm)", config.CLIM_BASELINE),
        (axs[1], "ndvi", "veg_ok", "Cropland NDVI", config.VEG_BASELINE)]:
    d = ts_df[ts_df[flag]].groupby("year")[var].mean()
    base = d[(d.index >= y0) & (d.index <= y1)]
    if len(d):
        ax.plot(d.index, d.values, marker="o")
        if len(base) > 1:
            ax.axhspan(base.mean() - base.std(), base.mean() + base.std(), alpha=0.2,
                       label=f"baseline {y0}-{y1} mean ± 1 sd")
            ax.legend(fontsize=8)
    ax.set_title(f"{lab}, {ts}: simple mean of blocks (not area-weighted)", fontsize=9)
    ax.set_xlabel("Year")
fig.tight_layout(); fig.savefig(OUT / "season_timeseries.png", dpi=150); plt.close(fig)

# ---------------- 8. Report ----------------
def md_table(df, nd=2):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("NA" if np.isnan(v) else f"{v:.{nd}f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)

tab = tgt[["unit", "rain_mm", "rain_anom_pct", "t2m_mean_anom", "ndvi_anom", "ndmi_anom",
           "min_valid_cov_pct", "n_indicators", "ACSI", "ACSI_class"]].rename(columns={
    "unit": "Block", "rain_mm": "Rain mm", "rain_anom_pct": "Rain anom %", "t2m_mean_anom": "Temp anom C",
    "ndvi_anom": "NDVI anom", "ndmi_anom": "NDMI anom", "min_valid_cov_pct": "Min valid cov %",
    "n_indicators": "N indicators"})
_b = master[(master["season"] == ts) & master["veg_ok"] & master["year"].between(*config.VEG_BASELINE)]
_bi, _ti = _b["veg_mean_images"].mean(), tgt["veg_mean_images"].mean()
img_note = f"- HLS images per month (study area): target period {_ti:.0f} vs baseline average {_bi:.0f}"
if np.isfinite(_bi) and np.isfinite(_ti) and _ti < config.HLS_IMAGE_RATIO_WARN * _bi:
    img_note += (". WARNING: far fewer images in the target period than in the baseline; NDVI/NDMI anomalies may "
                 "reflect composite sampling rather than crop condition. Investigate (00d_hls_diagnostic.py) before relying on them.")
rep = [f"# AgriResilience analysis report: {ts} {ty}", "",
       "Screening and decision-support output. Not a validated crop-yield or drought-risk model.", "",
       "## Settings used",
       f"- Climate baseline (rain, temperature): {config.CLIM_BASELINE[0]}-{config.CLIM_BASELINE[1]}",
       f"- Vegetation baseline (NDVI, NDMI): {config.VEG_BASELINE[0]}-{config.VEG_BASELINE[1]}",
       f"- Minimum baseline years: {config.MIN_BASELINE_YEARS}",
       f"- Rainfall source mode: {config.GPM_MODE}",
       f"- Rainfall stress metric: {config.RAIN_STRESS_METRIC}",
       f"- Weights (provisional, not calibrated): {W}",
       f"- Seasons (assumed convention): {config.SEASONS}", "",
       f"## Block results, {ts} {ty}", md_table(tab), "",
       "Classes (Lower / Moderate / Higher) are terciles of ACSI among scored blocks in this season. "
       "They describe relative position only and are not absolute risk thresholds.", ""]
_scr = tgt[["unit", "screening_class", "rain_anom_pct", "dry_spell_max_d", "dry_spell_max_d_anom", "t2m_mean_anom",
            "ndvi_anom", "ndmi_anom", "vci"]].rename(columns={
    "unit": "Block", "screening_class": "Concurrent-stress screening", "rain_anom_pct": "Rain anom %",
    "dry_spell_max_d": "Longest dry spell (d)", "dry_spell_max_d_anom": "Dry spell anom (d)",
    "t2m_mean_anom": "Temp anom C", "ndvi_anom": "NDVI anom", "ndmi_anom": "NDMI anom", "vci": "VCI (0-100)"})
rep += ["## Concurrent-stress screening (primary integrated output)",
        f"Heat and dry-spell flags enter the block screening only when blocks differ in that season (coarse grid); otherwise they are reported district-wide. Flags: rainfall deficit <= -{config.RAIN_DEFICIT_PCT:.0f}% ; heat / dry spell >= +{config.STRESS_Z:g} sd ; "
        f"vegetation (NDVI or NDMI) <= -{config.STRESS_Z:g} sd of the same-season baseline, only when enough HLS images exist. "
        "Thresholds are design choices, not official categories.",
        md_table(_scr), "",
        "## Agricultural exposure (cropland area in blocks showing each signal)",
        "Indicators are block-level, so exposure is block-resolved: the cropland of a flagged block counts as exposed. "
        "Cropland = ESA WorldCover class 40 (preliminary mask), hectares = 30 m pixels x 0.09.",
        md_table(expo_sum), ""]
if summ is not None:
    rep += ["## Sensitivity of ranking to weights",
            f"Rank 1 = highest stress. Columns: base weights, equal weights, drop-one-indicator, and "
            f"summary over {config.N_MONTE_CARLO} random weight sets.",
            md_table(summ.reset_index().rename(columns={"unit": "Block"})), ""]
else:
    rep += ["## Sensitivity of ranking to weights", sens_note, ""]
unavailable = [c for c in STRESS if not tgt[c].notna().any()]
rep += ["## Data-quality notes",
        f"- Indicators with no usable spatial contrast or no data for this season: {unavailable if unavailable else 'none'}",
        f"- Blocks scored: {int(tgt['ACSI'].notna().sum())} of {len(tgt)}",
        "- Blocks with data per indicator: " + ", ".join(f"{c}={int(tgt[c].notna().sum())}" for c in STRESS),
        img_note,
        f"- Correlation of seasonal rainfall, GPM IMERG vs NASA POWER (all usable block-seasons): "
        f"{'not computed' if np.isnan(corr) else f'{corr:.2f}'} (sanity check only)", "",
        "## Limitations",
        "- Min-max scaling is relative to the blocks and season analysed: a block can score 'Higher' even if absolute stress is mild.",
        "- ACSI weights are design assumptions, not calibrated; see the sensitivity table before interpreting ranks.",
        "- IMERG (~0.1 deg) and NASA POWER (coarse grid) cannot resolve differences inside small blocks; neighbouring blocks may share values.",
        "- Cropland mask is a single-year (2021) ESA WorldCover map applied to all years.",
        "- Low NDVI/NDMI can reflect harvest timing, fallow land or residual cloud, not only stress.",
        "- Seasonal NDVI/NDMI is the mean of monthly median composites over valid months.",
        "- Dry spells come from NASA POWER daily precipitation (~0.5 deg grid), not from IMERG directly; the dry-day threshold is an assumption.",
        "- VCI uses the same-season baseline range (short HLS record), so extremes are poorly constrained.",
        "- The HLS raw download may use the legacy mask without the water bit; see qc_report.txt.",
        "- No crop-yield, irrigation or soil data are used; results do not by themselves indicate any adaptation action."]
(OUT / "analysis_report.md").write_text("\n".join(rep), encoding="utf-8")
print("\n".join(rep))
print("\nAnalysis finished ->", OUT)
