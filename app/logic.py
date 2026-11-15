"""Plain-language rules for the AgriResilience dashboard (no Streamlit imports, so it can be tested on its own).

Everything here turns numbers already produced by the pipeline into simple statuses.
THRESHOLDS ARE DESIGN ASSUMPTIONS (marked below), not official drought categories.
"""
import numpy as np
import pandas as pd

# ------------------------------------------------------------------ assumptions (shown on the Methodology page)
RAIN_BANDS = [  # (upper bound of anomaly %, label); first band whose bound the value is <= (strictly < for the last three)
    (-20, "Well below usual"),
    (-10, "Below usual"),
    (10, "About usual"),
    (20, "Above usual"),
    (np.inf, "Well above usual"),
]
RAIN_COLORS = {"Well below usual": "#e34a33", "Below usual": "#fdae61", "About usual": "#a6d96a",
               "Above usual": "#9ecae1", "Well above usual": "#6baed6", "No data": "#bdbdbd"}
ICON = {}   # icons intentionally not used (plain professional layout)
VEG_Z_LOW, VEG_Z_HIGH = -1.0, 1.0          # in units of the block's own year-to-year variation (standard deviation)
VEG_COLORS = {"Less green than usual": "#e34a33", "About usual": "#a6d96a", "Greener than usual": "#66c2a4",
              "Not reliable (few satellite images)": "#bdbdbd", "No data": "#e0e0e0"}
LEVELS = ["Needs attention", "Keep watching", "No major concern"]
LEVEL_COLORS = {"Needs attention": "#e34a33", "Keep watching": "#fdbf3b", "No major concern": "#7fc97f",
                "Not enough data": "#bdbdbd"}
HLS_RATIO_WARN = 0.5                        # same threshold as the pipeline (config.HLS_IMAGE_RATIO_WARN)
MIN_BASELINE_YEARS = 5

SEASON_NAMES = {"SWM": "Southwest monsoon", "NEM": "Northeast monsoon", "Winter": "Winter", "Summer": "Summer"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def season_label(season, seasons):
    ms = sorted(seasons[season])
    return f"{SEASON_NAMES.get(season, season)} ({MONTHS[ms[0] - 1]}–{MONTHS[ms[-1] - 1]})"


# ------------------------------------------------------------------ rainfall
def rain_status(pct):
    if pct is None or pd.isna(pct):
        return "No data"
    for bound, label in RAIN_BANDS:
        if (pct <= bound) if bound <= -10 else (pct < bound):
            return label
    return "Well above usual"


# ------------------------------------------------------------------ vegetation
def veg_baseline_std(allres, veg_baseline):
    b = allres[allres["veg_ok"].astype(bool) & allres["ndvi"].notna() & allres["year"].between(*veg_baseline)]
    g = b.groupby(["unit", "season"])["ndvi"].agg(["std", "count"]).reset_index()
    g.columns = ["unit", "season", "ndvi_bstd", "ndvi_bn"]
    return g


def hls_confidence(hlsn, seasons, year, season, veg_baseline):
    """Return (mean images/month in this season, usual images/month for the same season, ratio, 'OK'|'Low'|'Unknown')."""
    if hlsn is None or hlsn.empty:
        return np.nan, np.nan, np.nan, "Unknown"
    h = hlsn.copy()
    h["y"] = h["month"].str[:4].astype(int)
    h["m"] = h["month"].str[5:7].astype(int)
    ms = seasons[season]
    cur = h[(h["y"] == year) & h["m"].isin(ms)]["n_images"]
    base = h[h["y"].between(*veg_baseline) & h["m"].isin(ms)]["n_images"]
    if cur.empty or base.empty or base.mean() == 0:
        return np.nan, np.nan, np.nan, "Unknown"
    ratio = cur.mean() / base.mean()
    return float(cur.mean()), float(base.mean()), float(ratio), ("Low" if ratio < HLS_RATIO_WARN else "OK")


def veg_status(z, confidence):
    if z is None or pd.isna(z):
        return "No data"
    if confidence == "Low":
        return "Not reliable (few satellite images)"
    if z <= VEG_Z_LOW:
        return "Less green than usual"
    if z >= VEG_Z_HIGH:
        return "Greener than usual"
    return "About usual"


# ------------------------------------------------------------------ overall level
def overall_level(rain, veg):
    """Dry-side concern only: this tool screens for water/vegetation stress, not for flooding."""
    if rain == "No data":
        return "Not enough data"
    if rain == "Well below usual":
        return "Needs attention"
    if rain == "Below usual":
        return "Needs attention" if veg == "Less green than usual" else "Keep watching"
    if veg == "Less green than usual":
        return "Keep watching"
    return "No major concern"


def reason_text(row):
    parts = []
    r, v = row["rain_status"], row["veg_status"]
    pct = row["rain_anom_pct"]
    if r != "No data":
        if r == "About usual":
            parts.append(f"Rain was about usual ({pct:+.0f}%)")
        else:
            parts.append(f"Rain was {abs(pct):.0f}% {'below' if pct < 0 else 'above'} usual for this season")
    if v == "Less green than usual":
        parts.append("crops/vegetation looked less green than usual")
    elif v.startswith("Not reliable"):
        parts.append("crop greenness could not be checked reliably")
    elif v == "Greener than usual":
        parts.append("crops/vegetation looked greener than usual")
    if r in ("Above usual", "Well above usual"):
        parts.append("check field drainage")
    return "; ".join(parts).capitalize() + "."


def status_table(allres, seasons, veg_baseline, hlsn, year, season, crop=None):
    d = allres[(allres["year"] == year) & (allres["season"] == season)].copy()
    d = d.merge(veg_baseline_std(allres, veg_baseline), on=["unit", "season"], how="left")
    d["ndvi_z"] = np.where(d["ndvi_bn"].fillna(0) >= MIN_BASELINE_YEARS, d["ndvi_anom"] / d["ndvi_bstd"], np.nan)
    _, _, ratio, conf = hls_confidence(hlsn, seasons, year, season, veg_baseline)
    d["rain_status"] = d["rain_anom_pct"].map(rain_status)
    d["veg_status"] = [veg_status(z, conf) for z in d["ndvi_z"]]
    d["level"] = [overall_level(r, v) for r, v in zip(d["rain_status"], d["veg_status"])]
    d["why"] = d.apply(reason_text, axis=1)
    if crop is not None:
        c = crop.copy()
        c["cropland_ha"] = c["crop_px_30m"] * 0.09    # ASSUMPTION: crop_px_30m counts 30 m x 30 m pixels
        d = d.merge(c[["unit", "cropland_ha"]], on="unit", how="left")
    d.attrs["hls_conf"] = conf
    d.attrs["hls_ratio"] = ratio
    return d


# ------------------------------------------------------------------ plain-English summary
def summary_sentences(d, label, year):
    n = len(d)
    below = d[d["rain_status"].isin(["Below usual", "Well below usual"])]
    above = d[d["rain_status"].isin(["Above usual", "Well above usual"])]
    out = [f"**{label} {year}:** {n - len(below) - len(above) - int((d['rain_status'] == 'No data').sum())} of {n} blocks "
           f"had about the usual rainfall, {len(below)} had less than usual and {len(above)} had more than usual."]
    if len(below):
        names = ", ".join(f"{u} ({p:+.0f}%)" for u, p in zip(below["unit"], below["rain_anom_pct"]))
        out.append(f"Drier than usual: {names}.")
    if len(above):
        names = ", ".join(f"{u} ({p:+.0f}%)" for u, p in zip(above["unit"], above["rain_anom_pct"]))
        out.append(f"Wetter than usual: {names}.")
    conf = d.attrs.get("hls_conf")
    if conf == "Low":
        out.append("Crop greenness from satellites could not be judged reliably this season because too few usable images were available.")
    else:
        lessg = d[d["veg_status"] == "Less green than usual"]
        out.append("No block looked unusually less green than normal." if lessg.empty
                   else "Less green than usual: " + ", ".join(lessg["unit"]) + ".")
    return out


# ------------------------------------------------------------------ latest 30 days
def latest_table(latest):
    if latest is None:
        return None
    t = latest.copy()
    t["status"] = t["anomaly_pct"].map(rain_status)
    return t


# ------------------------------------------------------------------ actions (GENERAL guidance, not crop-specific)
def advice(rain, veg):
    """General, non-numeric options to discuss with local agriculture officers. No crop data or figures are invented."""
    a = {"do_now": [], "plan_next": [], "check": []}
    if rain in ("Well below usual", "Below usual"):
        a["do_now"] += [
            "Give irrigation priority to the growth stages most sensitive to water shortage (ask your agriculture officer which stages apply to your crop).",
            "Cut avoidable water loss: mulch, keep weeds down, and irrigate in cooler parts of the day where possible.",
            "Check how much water is left in tanks, canals and wells before deciding on the next sowing.",
        ]
        a["plan_next"] += [
            "Ask about shorter-duration or less water-demanding crop options recommended locally for the coming season.",
            "Consider adding pulses/legumes to the rotation where soil and local practice suit.",
            "Look at water-saving irrigation (for example drip or sprinkler) where it is available and affordable.",
            "Check crop-insurance enrolment and deadlines with the local agriculture office.",
        ]
        if rain == "Well below usual":
            a["do_now"].insert(0, "Report dry conditions early to the block agriculture office and ask about contingency crop plans.")
    elif rain in ("Above usual", "Well above usual"):
        a["do_now"] += [
            "Keep field drains and channels clear to avoid waterlogging.",
            "Watch for pests and fungal diseases, which can increase in wet, humid weather.",
        ]
        a["plan_next"] += [
            "Use the extra water: refill tanks and ponds and support well recharge where possible.",
            "Plan storage and harvest timing so that wet spells do not damage produce.",
        ]
    elif rain == "About usual":
        a["do_now"] += ["Continue normal practice and keep checking rainfall each month."]
        a["plan_next"] += ["Use this time to plan water storage and contingency options for drier years."]
    if veg == "Less green than usual":
        a["check"].append("Satellites show less green vegetation than usual: do a field visit to check for water stress, pests, disease or nutrient problems.")
    elif veg.startswith("Not reliable"):
        a["check"].append("Satellite crop-greenness is not reliable this season: rely on field observation rather than the map.")
    a["check"].append("Confirm every action with local agriculture officers, the Krishi Vigyan Kendra (KVK) or Tamil Nadu Agricultural University (TNAU) before acting. This dashboard does not know your crop, soil or irrigation source.")
    return a


SCENARIOS = [
    {"Option": "Keep the existing crop sequence",
     "Idea": "Continue the crops currently grown. This is the reference point for any comparison.",
     "Worth discussing when": "Rainfall is about usual or above usual.",
     "Check first": "Current crops and sowing dates; water availability for the season."},
    {"Option": "Add pulses / legumes to the sequence",
     "Idea": "Include a pulse or other legume crop in the rotation. Legumes are generally known to add nitrogen to the soil.",
     "Worth discussing when": "Rainfall was below usual, or when planning the next season.",
     "Check first": "Soil suitability, crop duration, seed availability, market and local advice."},
    {"Option": "Switch to a lower-water-demand option",
     "Idea": "Choose crops or varieties that need less water or have a shorter duration.",
     "Worth discussing when": "Rainfall was well below usual and irrigation is limited.",
     "Check first": "Documented water requirement from an official source, irrigation supply, market and farmer preference."},
]


def scenario_flags(rain):
    dry = rain in ("Well below usual", "Below usual")
    very_dry = rain == "Well below usual"
    return {SCENARIOS[0]["Option"]: "Yes" if not very_dry else "Compare",
            SCENARIOS[1]["Option"]: "Yes" if dry else "Optional",
            SCENARIOS[2]["Option"]: "Yes" if very_dry else ("Consider" if dry else "Optional")}


# ------------------------------------------------------------------ map helpers
def rewind_geojson(gj):
    """Plotly needs exterior rings clockwise, holes counter-clockwise. Idempotent."""
    def area(r):
        return sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2

    def fix(poly):
        out = []
        for k, ring in enumerate(poly):
            a = area(ring)
            want_ccw = k > 0
            out.append(ring[::-1] if (a != 0 and (a > 0) != want_ccw) else ring)
        return out
    for f in gj["features"]:
        g = f["geometry"]
        if g["type"] == "Polygon":
            g["coordinates"] = fix(g["coordinates"])
        elif g["type"] == "MultiPolygon":
            g["coordinates"] = [fix(p) for p in g["coordinates"]]
    return gj


def centroids(gj):
    """Label position = centre of the bounding box of the largest polygon of each block."""
    rows = []
    for f in gj["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        best = max(polys, key=lambda p: abs(sum(p[0][i][0] * p[0][i + 1][1] - p[0][i + 1][0] * p[0][i][1]
                                                for i in range(len(p[0]) - 1))))
        xs = [c[0] for c in best[0]]
        ys = [c[1] for c in best[0]]
        rows.append({"unit": f["properties"]["unit"], "lon": (min(xs) + max(xs)) / 2, "lat": (min(ys) + max(ys)) / 2})
    return pd.DataFrame(rows)
