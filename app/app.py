"""AgriResilience dashboard (GeoCosmic, NASA Space Apps Challenge 2026).

Reads only app/data. Every sentence shown to the user is generated from those files or is a fixed, documented
statement about method; nothing is invented. Thresholds and weights are design choices and are labelled as such."""
import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import logic as L

HERE = Path(__file__).parent
DATA = HERE / "data"
ASSETS = HERE / "assets"

try:
    from PIL import Image
    _icon = Image.open(ASSETS / "favicon.png")
except Exception:
    _icon = None
st.set_page_config(page_title="AgriResilience | GeoCosmic", page_icon=_icon, layout="wide")

NAVY, RED, AMBER, GREEN, BLUE, GREY = "#0B3D91", "#C0392B", "#D68910", "#2E7D5B", "#2F6DA3", "#8A96A3"
FONT = "Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"

CSS = f"""
<style>
html, body, [class*="css"], .stMarkdown, .stDataFrame {{ font-family: {FONT}; }}
.block-container {{ max-width: 1240px; padding-top: 0.8rem; padding-bottom: 2rem; }}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
h1 {{ font-size: 1.55rem !important; color: {NAVY}; font-weight: 600; margin: 0.2rem 0 0.1rem 0; }}
h2 {{ font-size: 1.2rem !important; color: {NAVY}; font-weight: 600; border-bottom: 2px solid {NAVY};
      padding-bottom: 0.25rem; margin-top: 1.6rem; }}
h3 {{ font-size: 1.0rem !important; color: #1f2d3d; font-weight: 600; margin-top: 1.1rem; }}
p, li, td, th, label, .stMarkdown {{ font-size: 0.92rem; line-height: 1.5; color: #1f2d3d; }}
[data-testid="stSidebar"] {{ background: #F2F5F9; border-right: 1px solid #D5DDE8; }}
[data-testid="stSidebar"] * {{ font-size: 0.9rem; }}
[data-testid="stSidebar"] {{ min-width: 330px; }}
.sub {{ color: #4a5a6b; font-size: 0.88rem; margin-bottom: 0.6rem; }}
.hero img {{ width: 100%; border-radius: 3px; display: block; }}
.kpis {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 0.6rem 0 0.4rem 0; }}
.kpi {{ flex: 1 1 150px; background: #fff; border: 1px solid #D5DDE8; border-top: 3px solid {NAVY}; padding: 10px 14px; }}
.kpi .l {{ font-size: 0.74rem; text-transform: uppercase; letter-spacing: .04em; color: #5b6b7c; }}
.kpi .v {{ font-size: 1.55rem; font-weight: 600; color: {NAVY}; line-height: 1.2; }}
.kpi .n {{ font-size: 0.78rem; color: #5b6b7c; }}
.panel {{ background: #F7F9FC; border: 1px solid #D5DDE8; border-left: 4px solid {NAVY}; padding: 12px 16px; margin: 0.5rem 0 0.9rem 0; }}
.panel.warn {{ border-left-color: {AMBER}; background: #FFFAF0; }}
table.gt {{ border-collapse: collapse; width: 100%; word-break: break-word; margin: 0.3rem 0 0.7rem 0; }}
table.gt th {{ background: {NAVY}; color: #fff; text-align: left; padding: 6px 9px; font-weight: 600; font-size: 0.82rem; }}
table.gt td {{ padding: 6px 9px; border-bottom: 1px solid #DDE4EC; vertical-align: top; }}
table.gt tr:nth-child(even) td {{ background: #F7F9FC; }}
.b {{ display: inline-block; padding: 1px 8px; border-radius: 3px; font-size: 0.78rem; font-weight: 600; color: #fff; white-space: nowrap; }}
.b-red {{ background: {RED}; }} .b-amber {{ background: {AMBER}; }} .b-green {{ background: {GREEN}; }}
.b-blue {{ background: {BLUE}; }} .b-grey {{ background: {GREY}; }}
.flow {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: stretch; margin: 0.6rem 0; }}
.flow div {{ flex: 1 1 140px; border: 1px solid #C5D0DE; border-top: 3px solid {NAVY}; padding: 8px 10px; background: #fff; font-size: 0.82rem; }}
.flow b {{ display: block; color: {NAVY}; margin-bottom: 2px; }}
.foot {{ color: #6b7a8a; font-size: 0.78rem; border-top: 1px solid #D5DDE8; margin-top: 2rem; padding-top: 0.6rem; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ data
@st.cache_data
def load():
    d = {"all": pd.read_csv(DATA / "acsi_all_seasons.csv"),
         "target": pd.read_csv(DATA / "acsi_target_season.csv"),
         "meta": json.load(open(DATA / "meta.json"))}
    for c in ["rain_ok", "temp_ok", "veg_ok", "veg_reliable"]:
        if c in d["all"].columns:
            d["all"][c] = d["all"][c].fillna(False).astype(bool)
    geo = json.load(open(DATA / "units.geojson")) if (DATA / "units.geojson").exists() else None
    d["geo"] = L.rewind_geojson(geo) if geo else None
    d["cent"] = L.centroids(d["geo"]) if geo else None
    for k, f in {"sens": "sensitivity_target_season.csv", "latest": "latest_window_summary.csv",
                 "daily": "latest_rainfall_daily.csv", "crop": "cropland_pixels_by_unit.csv", "soil": "soil_by_unit.csv",
                 "hlsn": "hls_images_per_month.csv"}.items():
        d[k] = pd.read_csv(DATA / f) if (DATA / f).exists() else None
    for k, f in {"validation": "validation_report.md", "qc": "qc_report.txt"}.items():
        d[k] = (DATA / f).read_text(encoding="utf-8") if (DATA / f).exists() else ""
    return d


@st.cache_data
def b64(name):
    p = ASSETS / name
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


D = load()
meta, allres = D["meta"], D["all"]
SEAS, VB, CB = meta["seasons"], tuple(meta["veg_baseline"]), tuple(meta["clim_baseline"])
sstart = {s: min(m) for s, m in SEAS.items()}
TS, TY = meta["target_season"], meta["target_year"]
RAIN_T = meta.get("rain_deficit_pct", 10.0)
Z_T = meta.get("stress_z", 1.0)
HA = meta.get("ha_per_pixel", 0.09)


# ------------------------------------------------------------------ helpers
def show(fig, key=None):
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key)


def style(fig, h=360, title=None):
    fig.update_layout(template="plotly_white", height=h, title=dict(text=title, font=dict(size=14, color=NAVY)) if title else None,
                      font=dict(family=FONT, size=12, color="#1f2d3d"), margin=dict(l=10, r=10, t=46 if title else 12, b=10),
                      legend=dict(orientation="h", y=-0.2, title_text=""))
    return fig


def badge(text, kind):
    return f'<span class="b b-{kind}">{text}</span>'


def table(headers, rows):
    th = "".join(f"<th>{h}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    st.markdown(f'<table class="gt"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>', unsafe_allow_html=True)


def kpis(items):
    html = "".join(f'<div class="kpi"><div class="l">{l}</div><div class="v">{v}</div><div class="n">{n}</div></div>' for l, v, n in items)
    st.markdown(f'<div class="kpis">{html}</div>', unsafe_allow_html=True)


def panel(text, warn=False):
    st.markdown(f'<div class="panel{" warn" if warn else ""}">{text}</div>', unsafe_allow_html=True)


def num(x, nd=0, signed=False):
    if x is None or pd.isna(x):
        return "n/a"
    return f"{x:+,.{nd}f}" if signed else f"{x:,.{nd}f}"


RAIN_KIND = {"Well below usual": "red", "Below usual": "amber", "About usual": "green", "Above usual": "blue",
             "Well above usual": "blue", "No data": "grey"}
VEG_KIND = {"Less green than usual": "red", "About usual": "green", "Greener than usual": "green",
            "Not reliable (few satellite images)": "grey", "No data": "grey"}
VEG_LABEL = {"Less green than usual": "Below usual", "About usual": "About usual", "Greener than usual": "Above usual",
             "Not reliable (few satellite images)": "Not assessed (low image count)", "No data": "No data"}
CLASS_COLOR = lambda c: (GREY if c.startswith("Insufficient") else GREEN if c.startswith("No stress")
                         else RED if c.startswith("Concurrent") else AMBER)


def _rings(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    return [poly[0] for poly in polys]          # exterior rings


def _poly_trace(unit, geom, color, hover, legend_name=None, show_legend=False):
    xs, ys = [], []
    for ring in _rings(geom):
        xs += [c[0] for c in ring] + [None]
        ys += [c[1] for c in ring] + [None]
    return go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=color, line=dict(color="#FFFFFF", width=1.2),
                      name=legend_name or unit, legendgroup=legend_name or unit, showlegend=show_legend,
                      text=hover, hoverinfo="text", hoveron="fills")


def _finish_map(fig, title, height):
    c = D["cent"]
    fig.add_trace(go.Scatter(x=c["lon"], y=c["lat"], text=c["unit"], mode="text", showlegend=False, hoverinfo="skip",
                             textfont=dict(size=11, color="#111")))
    lat0 = float(c["lat"].mean())
    fig.update_xaxes(visible=False, showgrid=False, zeroline=False)
    fig.update_yaxes(visible=False, showgrid=False, zeroline=False, scaleanchor="x", scaleratio=1 / max(np.cos(np.radians(lat0)), 0.2))
    style(fig, height, title)
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor="#FFFFFF")
    return fig


def _geoms():
    return {f["properties"]["unit"]: f["geometry"] for f in D["geo"]["features"]}


def cat_map(df, col, cmap, title, hover=None, height=420, key=None):
    """Block map coloured by category. Drawn from the block polygons (no web map tiles or CDN files needed)."""
    if D["geo"] is None:
        st.info("Boundary file not available.")
        return
    g, fig, seen = _geoms(), go.Figure(), set()
    for _, r in df.iterrows():
        if r["unit"] not in g:
            continue
        cls = r[col]
        txt = f"<b>{r['unit']}</b><br>{cls}" + "".join(f"<br>{c}: {r[c]:.1f}" for c in (hover or []) if c in df.columns and pd.notna(r[c]))
        fig.add_trace(_poly_trace(r["unit"], g[r["unit"]], cmap.get(cls, GREY), txt, legend_name=cls, show_legend=cls not in seen))
        seen.add(cls)
    show(_finish_map(fig, title, height), key)


def num_map(df, col, title, scale, mid=None, height=420, key=None, label=""):
    if D["geo"] is None:
        return
    vals = df[col].astype(float)
    if vals.notna().sum() == 0:
        st.info("No values to map for this period.")
        return
    if mid is not None:
        lim = max(abs(vals.min() - mid), abs(vals.max() - mid)) or 1
        lo, hi = mid - lim, mid + lim
    else:
        lo, hi = float(vals.min()), float(vals.max())
        hi = hi if hi > lo else lo + 1
    g, fig = _geoms(), go.Figure()
    for _, r in df.iterrows():
        if r["unit"] not in g:
            continue
        v = r[col]
        color = px.colors.sample_colorscale(scale, [(v - lo) / (hi - lo)])[0] if pd.notna(v) else "#D9DEE5"
        fig.add_trace(_poly_trace(r["unit"], g[r["unit"]], color, f"<b>{r['unit']}</b><br>{label or col}: {v:.2f}" if pd.notna(v) else f"<b>{r['unit']}</b><br>no value"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", showlegend=False, hoverinfo="skip",
                             marker=dict(colorscale=scale, cmin=lo, cmax=hi, color=[lo], showscale=True,
                                         colorbar=dict(title=dict(text=label), thickness=14, len=0.8))))
    show(_finish_map(fig, title, height), key)


def periods():
    p = allres[allres["rain_ok"] & allres["rain_anom_pct"].notna()][["year", "season"]].drop_duplicates()
    p["k"] = p["season"].map(sstart)
    p = p.sort_values(["year", "k"], ascending=False)
    return [(int(y), s) for y, s in zip(p["year"], p["season"])]


# ------------------------------------------------------------------ sidebar
SECTIONS = ["Overview", "Climate Hazard", "Crop Condition", "Integrated Assessment", "Adaptation Options", "Methodology and Data"]
st.sidebar.markdown("### Navigation")
page = st.sidebar.radio("Section", SECTIONS, label_visibility="collapsed")
opts = periods()
default = opts.index((TY, TS)) if (TY, TS) in opts else 0
st.sidebar.markdown("### Reporting period")
Y, S = st.sidebar.selectbox("Season", opts, index=default,
                            format_func=lambda o: f"{L.season_label(o[1], SEAS)} {o[0]}", label_visibility="collapsed")
SL = L.season_label(S, SEAS)
st.sidebar.markdown("### Data currency")
st.sidebar.caption(f"Results generated {meta['generated_utc']} UTC\n\nClimate baseline {CB[0]}-{CB[1]}\n\nVegetation baseline {VB[0]}-{VB[1]}")

T = L.status_table(allres, SEAS, VB, D["hlsn"], Y, S, D["crop"])
CONF, RATIO = T.attrs.get("hls_conf"), T.attrs.get("hls_ratio")
N = len(T)
CROP_TOTAL = float(T["cropland_ha"].sum()) if "cropland_ha" in T.columns else np.nan
IS_TARGET = (Y, S) == (TY, TS)

# ------------------------------------------------------------------ header
st.markdown(f'<div class="hero"><img src="data:image/png;base64,{b64("header.png")}" alt="NASA Space Apps Challenge 2026 - GeoCosmic"></div>',
            unsafe_allow_html=True)
st.markdown("# AgriResilience: Agricultural Climate Stress Screening")
st.markdown(f'<div class="sub">Tirunelveli District, Tamil Nadu, India &nbsp;|&nbsp; Reporting period: <b>{SL} {Y}</b> &nbsp;|&nbsp; '
            'Data: NASA HLS, NASA GPM IMERG, NASA POWER &nbsp;|&nbsp; Screening product, not a yield forecast or an official drought declaration.</div>',
            unsafe_allow_html=True)


# ------------------------------------------------------------------ text generated from the data
def flagged(col):
    if col not in T.columns:
        return T.iloc[0:0]
    return T[T[col] == 1]


def executive_summary():
    rain_f = flagged("flag_rain")
    out = [f"{N} blocks were screened for the {SL} {Y}, covering about {num(CROP_TOTAL)} ha of mapped cropland."]
    if T["rain_anom_pct"].notna().sum() == 0:
        out.append("Rainfall comparison is not available for this period.")
    elif rain_f.empty:
        out.append(f"No block recorded rainfall more than {RAIN_T:.0f}% below its {CB[0]}-{CB[1]} average for this season.")
    else:
        names = ", ".join(f"{u} ({p:+.0f}%)" for u, p in zip(rain_f["unit"], rain_f["rain_anom_pct"]))
        share = 100 * rain_f["cropland_ha"].sum() / CROP_TOTAL if CROP_TOTAL else np.nan
        out.append(f"{len(rain_f)} of {N} blocks recorded rainfall at least {RAIN_T:.0f}% below the seasonal average: {names}. "
                   f"These blocks hold about {share:.0f}% of the mapped cropland.")
    wet = T[T["rain_status"].isin(["Above usual", "Well above usual"])]
    if len(wet):
        out.append(f"{len(wet)} blocks recorded rainfall more than 10% above average ({', '.join(wet['unit'])}).")
    if CONF == "Low":
        out.append(f"Vegetation response could not be assessed: only {RATIO:.0%} of the usual number of NASA HLS satellite images "
                   "were available, so vegetation anomalies are withheld from the screening.")
    else:
        veg_f = flagged("flag_veg")
        out.append("No block shows vegetation or moisture response below its seasonal baseline." if veg_f.empty
                   else f"Vegetation or moisture response is below baseline in: {', '.join(veg_f['unit'])}.")
    conc = T[T["screening_class"].str.startswith("Concurrent")]
    out.append(f"{len(conc)} blocks show two or more block-level stress signals at the same time." if len(conc)
               else "No block shows two or more block-level stress signals at the same time.")
    return out


def screening_base(c):
    return c.replace(" (vegetation not assessed)", "")


# ================================================================== OVERVIEW
if page == "Overview":
    st.markdown("## Executive summary")
    panel(" ".join(executive_summary()))
    deficit_ha = flagged("flag_rain")["cropland_ha"].sum() if "cropland_ha" in T.columns else np.nan
    kpis([("Blocks screened", f"{N}", "Tirunelveli district"),
          ("Mapped cropland", f"{num(CROP_TOTAL)} ha", "ESA WorldCover cropland (preliminary mask)"),
          ("Blocks with rainfall deficit", f"{len(flagged('flag_rain'))} of {N}", f"at least {RAIN_T:.0f}% below seasonal average"),
          ("Cropland in deficit blocks", f"{num(deficit_ha)} ha", f"{100 * deficit_ha / CROP_TOTAL:.0f}% of mapped cropland" if CROP_TOTAL else ""),
          ("Satellite image availability", f"{RATIO:.0%}" if pd.notna(RATIO) else "n/a", "NASA HLS images vs usual for the season")])

    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.markdown("## Block-level screening result")
        base = T.assign(result=T["screening_class"].map(screening_base))
        cmap = {c: CLASS_COLOR(c) for c in sorted(base["result"].unique())}
        cat_map(base, "result", cmap, f"Concurrent-stress screening, {SL} {Y}", hover=["rain_anom_pct", "rain_mm"], key="ov_map")
    with c2:
        st.markdown("## Rainfall against seasonal average")
        rows = []
        for _, r in T.sort_values("rain_anom_pct").iterrows():
            rows.append([r["unit"], num(r["rain_mm"]), num(r["rain_mm_bmean"]), num(r["rain_anom_pct"], 0, True) + " %",
                         badge(r["rain_status"], RAIN_KIND.get(r["rain_status"], "grey"))])
        table(["Block", "Season total (mm)", "Average (mm)", "Difference", "Status"], rows)
        st.caption(f"Average = same season, {CB[0]}-{CB[1]}. Source: NASA GPM IMERG V07 (about 11 km grid), summed to season totals.")

    st.markdown("## Data confidence")
    val_done = "No independent reference files supplied" not in D["validation"]
    veg_ok = CONF == "OK"
    rows = [["Rainfall (NASA GPM IMERG)", badge("Available" if T["rain_ok"].all() else "Incomplete", "green" if T["rain_ok"].all() else "amber"),
             "Satellite estimate on a grid of about 11 km; neighbouring blocks can share similar values. Recent months are provisional."],
            ["Vegetation (NASA HLS)", badge("Adequate" if veg_ok else "Low image count" if CONF == "Low" else "Unknown", "green" if veg_ok else "amber"),
             (f"{RATIO:.0%} of the usual number of images for this season." if pd.notna(RATIO) else "Image counts could not be checked.")],
            ["Temperature (NASA POWER)", badge("District-wide only", "amber"),
             f"Coarse grid: the blocks fall on {meta['temp_distinct_values']} distinct temperature series, so block differences cannot be resolved."],
            ["Cropland mask", badge("Preliminary", "amber"), "Single-year land-cover map applied to all years; not a field-level crop map."],
            ["Independent validation", badge("Performed" if val_done else "Not performed", "green" if val_done else "amber"),
             "Comparison with IMD or official statistics was run." if val_done else "No IMD or official reference data were supplied; values are reported as unvalidated estimates."]]
    table(["Component", "Status", "Note"], rows)

    st.markdown("## Reading guide")
    st.markdown("The dashboard compares each block's rainfall and vegetation with what is normal for the same season in earlier years. "
                "A signal is raised only when the difference passes a stated threshold. Blocks are screened on rainfall and vegetation response, "
                "which can be resolved block by block; temperature and dry-spell length come from a coarse grid and are reported for the district as a whole. "
                "The result is a prompt for local investigation, not a measurement of crop loss.")


# ================================================================== CLIMATE HAZARD
elif page == "Climate Hazard":
    st.markdown("This section compares rainfall, temperature and dry-spell length in the selected season with the average of the same season in earlier years. "
                "Rainfall is shown for each block. Temperature and dry spells come from a coarser grid and describe the district as a whole.")
    st.markdown("## Rainfall")
    c1, c2 = st.columns(2)
    with c1:
        num_map(T, "rain_anom_pct", "Rainfall difference from seasonal average (%)", "RdBu", mid=0, key="ch_rmap", label="%")
    with c2:
        d = T.sort_values("rain_anom_pct")
        fig = px.bar(d, x="rain_anom_pct", y="unit", orientation="h", color="rain_status", color_discrete_map=L.RAIN_COLORS,
                     labels={"rain_anom_pct": "Difference from seasonal average (%)", "unit": ""})
        fig.add_vline(x=-RAIN_T, line_dash="dash", line_color=RED, annotation_text=f"-{RAIN_T:.0f}% threshold")
        show(style(fig, 420, "Rainfall anomaly by block"), key="ch_rbar")
    d = T.sort_values("rain_mm", ascending=False)
    fig = go.Figure([go.Bar(name=f"{SL} {Y}", x=d["unit"], y=d["rain_mm"], marker_color=NAVY),
                     go.Bar(name=f"Average {CB[0]}-{CB[1]}", x=d["unit"], y=d["rain_mm_bmean"], marker_color="#9DB4D3")])
    fig.update_layout(barmode="group", yaxis_title="Rainfall (mm)")
    show(style(fig, 340, "Season rainfall total against average (NASA GPM IMERG)"), key="ch_rcmp")

    ts = allres[(allres["season"] == S) & allres["rain_ok"]].groupby("year")["rain_mm"].mean().reset_index()
    if len(ts):
        base = ts[ts["year"].between(*CB)]["rain_mm"]
        fig = go.Figure(go.Scatter(x=ts["year"], y=ts["rain_mm"], mode="lines+markers", line=dict(color=NAVY), name="District mean"))
        if len(base) > 1:
            fig.add_hrect(y0=base.mean() - base.std(), y1=base.mean() + base.std(), fillcolor=BLUE, opacity=0.15, line_width=0,
                          annotation_text=f"baseline mean +/- 1 sd ({CB[0]}-{CB[1]})", annotation_position="top left")
        fig.update_layout(xaxis_title="Year", yaxis_title="Rainfall (mm)", xaxis=dict(dtick=1))
        show(style(fig, 330, f"{SL}: district mean rainfall by year (simple mean of blocks)"), key="ch_ts")

    st.markdown("## Temperature")
    t = allres[(allres["season"] == S) & allres["temp_ok"] & allres["t2m_mean_anom"].notna()].groupby("year", as_index=False)["t2m_mean_anom"].mean()
    if t.empty:
        st.info("No temperature anomaly is available for this season.")
    else:
        t["dir"] = np.where(t["t2m_mean_anom"] >= 0, "Warmer than average", "Cooler than average")
        fig = px.bar(t, x="year", y="t2m_mean_anom", color="dir", color_discrete_map={"Warmer than average": RED, "Cooler than average": BLUE},
                     labels={"t2m_mean_anom": "Difference (deg C)", "year": "Year"})
        show(style(fig, 320, f"{SL}: district temperature difference from average (NASA POWER T2M)"), key="ch_temp")
        cur = t[t["year"] == Y]
        if not cur.empty:
            x = cur["t2m_mean_anom"].iloc[0]
            st.markdown(f"In {Y} the {SL} was {abs(x):.1f} deg C {'warmer' if x >= 0 else 'cooler'} than the {CB[0]}-{CB[1]} average, district-wide.")
        st.caption("NASA POWER is a gridded model product with a coarse resolution; it describes the district, not individual blocks.")

    st.markdown("## Dry spells")
    if "dry_spell_max_d" in T.columns and T["dry_spell_max_d"].notna().any():
        rows = [[r["unit"], num(r["dry_spell_max_d"]), num(r["dry_spell_max_d_bmean"], 1), num(r["dry_spell_max_alt_d"])]
                for _, r in T.sort_values("dry_spell_max_d", ascending=False).iterrows()]
        table(["Block", "Longest dry spell (days)", "Average for season (days)", "Longest, stricter threshold (days)"], rows)
        st.caption(f"A dry day is a day with less than 1 mm of rain (stricter: 2.5 mm). Daily rainfall is from NASA POWER on a coarse grid, "
                   "so blocks that share a grid cell share a value. Thresholds are stated assumptions.")
    else:
        st.info("Dry-spell results are not available for this season.")

    if D["latest"] is not None:
        st.markdown("## Most recent 30 days (provisional)")
        lt = L.latest_table(D["latest"])
        rows = [[r["unit"], num(r["rain_mm_last30d"]), num(r["baseline_mean_mm"]), num(r["anomaly_pct"], 0, True) + " %",
                 badge(r["status"], RAIN_KIND.get(r["status"], "grey"))] for _, r in lt.iterrows()]
        table(["Block", "Last 30 days (mm)", "Usual for window (mm)", "Difference", "Status"], rows)
        st.caption("Near-real-time satellite estimates; they can be revised when final data are released.")


# ================================================================== CROP CONDITION
elif page == "Crop Condition":
    st.markdown("## Vegetation and moisture response")
    st.markdown("Greenness (NDVI), vegetation moisture (NDMI) and the Vegetation Condition Index (VCI) are measured from NASA HLS "
                "at 30 m, on mapped cropland only. They describe the condition of vegetation, not crop yield. Harvested, fallow and newly "
                "sown fields also appear less green.")
    if CONF == "Low":
        panel(f"Image availability for {SL} {Y} is {RATIO:.0%} of the usual level. Vegetation anomalies for this period are shown for "
              "transparency but are excluded from the screening, because a change may reflect missing images rather than crop condition.", warn=True)
    c1, c2 = st.columns(2)
    with c1:
        num_map(T, "ndvi_anom", f"NDVI difference from baseline, {SL} {Y}", "RdYlGn", mid=0, key="cc_ndvi", label="NDVI")
    with c2:
        if T["vci"].notna().any():
            num_map(T, "vci", f"Vegetation Condition Index (0-100), {SL} {Y}", "RdYlGn", key="cc_vci", label="VCI")
        else:
            st.info("VCI is not shown for this period (insufficient baseline or too few HLS images).")
    rows = []
    for _, r in T.sort_values("unit").iterrows():
        st_ = r["veg_status"]
        rows.append([r["unit"], num(r["ndvi"], 3), num(r["ndvi_anom"], 3, True), num(r["ndmi_anom"], 3, True), num(r["vci"], 0),
                     num(r["min_valid_cov_pct"], 0) + " %", badge(VEG_LABEL.get(st_, st_), VEG_KIND.get(st_, "grey"))])
    table(["Block", "NDVI", "NDVI difference", "NDMI difference", "VCI (0-100)", "Valid cropland coverage (min)", "Assessment"], rows)
    st.caption(f"Differences are measured from the same-season mean of {VB[0]}-{VB[1]}. VCI = (NDVI - minimum) / (maximum - minimum) x 100 over the baseline range. "
               "Assessment is withheld when image availability is low.")

    st.markdown("## Time series")
    unit = st.selectbox("Block", sorted(allres["unit"].unique()), key="cc_block")
    v = allres[(allres["unit"] == unit) & (allres["season"] == S) & allres["veg_ok"] & allres["ndvi"].notna()].sort_values("year")
    if v.empty:
        st.info("No vegetation record for this block and season.")
    else:
        fig = go.Figure(go.Scatter(x=v["year"], y=v["ndvi"], mode="lines+markers", line=dict(color=GREEN), name="NDVI"))
        if v["ndvi_bmean"].notna().any():
            fig.add_hline(y=v["ndvi_bmean"].dropna().iloc[0], line_dash="dash", line_color=GREY,
                          annotation_text=f"baseline mean {VB[0]}-{VB[1]}")
        fig.update_layout(xaxis_title="Year", yaxis_title="NDVI", xaxis=dict(dtick=1))
        show(style(fig, 320, f"{unit}: cropland NDVI in the {SL}"), key="cc_line")

    if D["hlsn"] is not None:
        st.markdown("## Satellite image availability")
        hn = D["hlsn"].copy()
        hn["Year"] = hn["month"].str[:4]
        fig = px.bar(hn, x="month", y="n_images", color="Year", labels={"n_images": "HLS images", "month": "Month"})
        show(style(fig, 320, "NASA HLS images available per month (whole district)"), key="cc_hls")
        st.caption("Fewer images give a less dependable vegetation reading. The cause of the lower counts in 2021 and 2025-2026 has not been verified.")


# ================================================================== INTEGRATED ASSESSMENT
elif page == "Integrated Assessment":
    st.markdown("## Concurrent-stress screening")
    st.markdown("Hazard, vegetation response and farmland exposure are kept separate. A block is highlighted when independent signals agree. "
                f"Rainfall stress: rainfall at least {RAIN_T:.0f}% below the seasonal average. Vegetation stress: NDVI or NDMI at least {Z_T:g} standard "
                f"deviation below the {VB[0]}-{VB[1]} baseline, judged only when enough satellite images exist. Thresholds are design choices, not official categories.")

    def cell(v, assessed_text="Not assessed"):
        if pd.isna(v):
            return badge(assessed_text, "grey")
        return badge("Flagged", "red") if v == 1 else badge("Not flagged", "green")
    def ctx(v):
        return badge("No data", "grey") if pd.isna(v) else badge("Above baseline", "amber") if v == 1 else badge("Within baseline", "grey")
    rows = []
    for _, r in T.sort_values("unit").iterrows():
        res = screening_base(r["screening_class"])
        rows.append([r["unit"], num(r["rain_anom_pct"], 0, True) + " %", cell(r["flag_rain"]), cell(r["flag_veg"], "Not assessed"),
                     ctx(r["flag_heat"]), ctx(r["flag_dry"]), badge(res, "red" if res.startswith("Concurrent") else "grey" if res.startswith("Insufficient")
                                                                       else "green" if res.startswith("No stress") else "amber")])
    table(["Block", "Rainfall vs average", "Rainfall signal", "Vegetation signal", "Heat (district context)", "Dry spell (district context)", "Block result"], rows)
    st.caption("Heat and dry-spell columns are district context: they come from a coarse grid shared by several blocks, so they do not separate blocks and are not part of the block result.")

    st.markdown("## Agricultural exposure")
    if D["crop"] is not None and "cropland_ha" in T.columns:
        rows = []
        for f, lab in [("flag_rain", "Rainfall deficit"), ("flag_veg", "Vegetation or moisture below baseline"),
                       ("flag_heat", "Heat anomaly (district-wide)"), ("flag_dry", "Long dry spell (district-wide)")]:
            a = T[T[f].notna()]
            hit = a.loc[a[f] == 1, "cropland_ha"].sum()
            rows.append([lab, num(hit) + " ha", f"{100 * hit / CROP_TOTAL:.1f} %", f"{100 * a['cropland_ha'].sum() / CROP_TOTAL:.0f} %"])
        table(["Signal", "Cropland in flagged blocks", "Share of district cropland", "Cropland assessed"], rows)
        st.caption("Exposure is an overlay: all mapped cropland of a flagged block counts as exposed, because rainfall (about 11 km) is not resolved within blocks. "
                   f"Cropland hectares = 30 m cropland pixels x {HA}.")

    st.markdown("## Decision trace")
    st.markdown("The screening is rule-based, so every block result can be traced. The table lists each rule, the observed value and the outcome. "
                "The block result follows directly from these rows; no other information enters the screening.")
    ub = st.selectbox("Block", sorted(T["unit"]), key="ia_trace")
    rb = T[T["unit"] == ub].iloc[0]

    def outcome(v, na_text):
        return badge(na_text, "grey") if pd.isna(v) else badge("Flagged", "red") if v == 1 else badge("Not flagged", "green")
    veg_na = (f"Not assessed: image availability {RATIO:.0%} of usual" if CONF == "Low" else "Not assessed")
    table(["Signal", "Observed value", "Rule", "Outcome"],
          [["Rainfall", num(rb["rain_anom_pct"], 0, True) + " % vs average", f"At least {RAIN_T:.0f}% below the {CB[0]}-{CB[1]} seasonal average", outcome(rb["flag_rain"], "No data")],
           ["Vegetation (NDVI / NDMI)", f"NDVI {num(rb['ndvi_anom'], 3, True)}, NDMI {num(rb['ndmi_anom'], 3, True)}",
            f"Either at least {Z_T:g} standard deviation below the {VB[0]}-{VB[1]} baseline, with enough images", outcome(rb["flag_veg"], veg_na)],
           ["Heat (district-wide)", num(rb["t2m_mean_anom"], 2, True) + " deg C vs average", f"At least {Z_T:g} standard deviation above baseline", outcome(rb["flag_heat"], "No data")],
           ["Dry spell (district-wide)", num(rb["dry_spell_max_d"]) + " days (average " + num(rb["dry_spell_max_d_bmean"], 1) + ")",
            f"Longest dry spell at least {Z_T:g} standard deviation above baseline", outcome(rb["flag_dry"], "No data")]])
    st.markdown(f"Result for {ub}: **{rb['screening_class']}**. At least two usable signals are required for a result; otherwise the block is reported as having insufficient observations.")

    st.markdown("## Driver analysis of the Agricultural Climate Stress Index (ACSI)")
    st.markdown("ACSI is an exploratory 0-1 score that ranks blocks relative to one another. It is a weighted sum of scaled indicators, so the "
                "contribution of every indicator to every block's score can be computed exactly: contribution = weight x scaled value / sum of the weights available. "
                "No black-box model is used, and missing indicators are never treated as zero.")
    A = allres[(allres["season"] == S) & (allres["year"] == Y)].copy()
    STRESS = ["rainfall_stress", "temperature_stress", "vegetation_stress", "moisture_stress"]
    NAMES = {"rainfall_stress": "Rainfall", "temperature_stress": "Temperature", "vegetation_stress": "Vegetation (NDVI)", "moisture_stress": "Vegetation moisture (NDMI)"}
    if A["ACSI"].notna().any():
        w = np.array([meta["weights"][c] for c in STRESS])
        X = A[STRESS].to_numpy(float)
        den = ((~np.isnan(X)) * w).sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            C = np.nan_to_num(X) * w / den[:, None]
        cd = pd.DataFrame(C, columns=STRESS)
        cd["unit"], cd["ACSI"] = A["unit"].to_numpy(), A["ACSI"].to_numpy()
        cd = cd[cd["ACSI"].notna()].sort_values("ACSI")
        long = cd.melt(id_vars=["unit", "ACSI"], value_vars=STRESS, var_name="Indicator", value_name="Contribution")
        long["Indicator"] = long["Indicator"].map(NAMES)
        fig = px.bar(long, y="unit", x="Contribution", color="Indicator", orientation="h", labels={"unit": "", "Contribution": "Contribution to ACSI"},
                     color_discrete_sequence=[NAVY, RED, GREEN, "#7FB069"])
        show(style(fig, 380, f"Indicator contributions to ACSI, {SL} {Y}"), key="ia_acsi")
        used = [NAMES[c] for c in STRESS if A[c].notna().any()]
        st.caption("Indicators used in this period: " + ", ".join(used) + ". Indicators with no spatial contrast between blocks are left out and the remaining weights are renormalised. "
                   "ACSI is relative: the highest-ranked block can still have mild absolute conditions.")
    else:
        st.info("ACSI is not scored for this period (the vegetation baseline starts in "
                f"{VB[0]} and blocks need at least three usable indicators).")
    if IS_TARGET and D["sens"] is not None:
        st.markdown("### Stability of the ranking")
        s = D["sens"].round(2)
        s = s.rename(columns={"unit": "Block", "base": "Base weights", "equal": "Equal weights", "mc_rank_mean": "Mean rank (random weights)",
                              "mc_rank_min": "Best rank", "mc_rank_max": "Worst rank", "mc_share_top3": "Share of runs in top 3",
                              **{c: "Without " + c[5:].replace("_stress", "").replace("_", " ") for c in s.columns if c.startswith("drop_")}})
        st.markdown("Rank 1 is the highest relative stress. Columns compare the base weights with equal weights, with each indicator removed in turn, and with 1,000 random weight sets.")
        st.dataframe(s, hide_index=True)

    st.markdown("## Observed relationship between rainfall and vegetation")
    ev = allres[allres["rain_ok"] & allres["veg_ok"] & allres["veg_reliable"] & allres["rain_anom_pct"].notna() & allres["ndvi_anom"].notna()]
    if len(ev) >= 8:
        r_ = ev[["rain_anom_pct", "ndvi_anom"]].corr(method="spearman").iloc[0, 1]
        strength = "weak" if abs(r_) < 0.2 else "moderate" if abs(r_) < 0.5 else "strong"
        fig = px.scatter(ev, x="rain_anom_pct", y="ndvi_anom", hover_name="unit", color_discrete_sequence=[NAVY],
                         labels={"rain_anom_pct": "Rainfall difference from average (%)", "ndvi_anom": "NDVI difference from baseline"})
        show(style(fig, 330, "Block-season pairs with reliable vegetation data"), key="ia_scatter")
        st.markdown(f"Across {len(ev)} block-season pairs, the rank correlation between rainfall anomaly and NDVI anomaly is {r_:+.2f} ({strength}). "
                    + ("This is a small sample, so the figure is indicative only. " if len(ev) < 60 else "")
                    + "A correlation describes the district's own record; it does not prove that rainfall caused any vegetation change.")
    else:
        st.info("Too few reliable block-season pairs to describe the rainfall-vegetation relationship.")


# ================================================================== ADAPTATION OPTIONS
elif page == "Adaptation Options":
    st.markdown("## Options to evaluate")
    panel("The options below are general planning considerations linked to the rainfall and vegetation status of a block. "
          "The dashboard holds no crop-type, soil-suitability, irrigation or cost data for the district, so it does not recommend a crop. "
          "Every option requires confirmation with local agriculture officers, the Krishi Vigyan Kendra or Tamil Nadu Agricultural University.", warn=True)
    unit = st.selectbox("Block", sorted(T["unit"]), key="ad_block")
    x = T[T["unit"] == unit].iloc[0]
    st.markdown(f"### {unit}, {SL} {Y}")
    st.markdown(f"Rainfall: {badge(x['rain_status'], RAIN_KIND.get(x['rain_status'], 'grey'))} &nbsp; "
                f"Vegetation: {badge(VEG_LABEL.get(x['veg_status'], x['veg_status']), VEG_KIND.get(x['veg_status'], 'grey'))} &nbsp; "
                f"{x['why']}", unsafe_allow_html=True)
    adv = L.advice(x["rain_status"], x["veg_status"])
    c1, c2, c3 = st.columns(3)
    for col, key, head in [(c1, "do_now", "Immediate considerations"), (c2, "plan_next", "Next-season planning"), (c3, "check", "Verification on the ground")]:
        with col:
            st.markdown(f"**{head}**")
            st.markdown("\n".join(f"- {i}" for i in adv[key]) if adv[key] else "- None for this status.")

    st.markdown("## Scenario comparison")
    flags = L.scenario_flags(x["rain_status"])
    rows = [[s["Option"], s["Idea"], flags[s["Option"]], s["Worth discussing when"], s["Check first"]] for s in L.SCENARIOS]
    table(["Scenario", "Description", f"Relevance for {unit}", "Typically considered when", "Evidence to confirm first"], rows)
    st.caption("Scenarios are qualitative. No scoring (for example TOPSIS) is applied because sourced crop, water and cost data are not loaded.")

    st.markdown("## Evidence required for a quantitative comparison")
    table(["Criterion", "Evidence required", "Status in this dashboard"],
          [["Climate suitability", "Rainfall and temperature during the crop season", badge("Partly available", "amber") + " rainfall and temperature anomalies"],
           ["Soil suitability", "Texture, pH, organic carbon", badge("Available" if D["soil"] is not None else "Not loaded", "green" if D["soil"] is not None else "grey")],
           ["Water requirement", "Documented crop-water requirement", badge("Not loaded", "grey")],
           ["Crop duration", "Official crop calendar", badge("Not loaded", "grey")],
           ["Irrigation feasibility", "Irrigation and water-availability data", badge("Not loaded", "grey")],
           ["Economic feasibility", "Official cultivation cost and return data", badge("Not loaded", "grey")],
           ["Farmer preference", "Survey or documented local evidence", badge("Not loaded", "grey")]])
    if D["soil"] is not None:
        st.markdown("### Soil properties of cropland (SoilGrids, 0-5 cm)")
        st.dataframe(D["soil"].round(1), hide_index=True)
    st.markdown("## Adaptive capacity")
    st.markdown("Irrigation coverage, groundwater dependence, crop diversity, water storage and extension access are not available as loaded data. "
                "No adaptive-capacity score is calculated, because missing information must not be read as low capacity.")


# ================================================================== METHODOLOGY AND DATA
else:
    st.markdown("## Processing chain")
    st.markdown('<div class="flow"><div><b>1. Observe</b>NASA HLS 30 m, GPM IMERG 0.1 deg, POWER daily, ESA WorldCover</div>'
                '<div><b>2. Quality control</b>Cloud, shadow, snow masks; coverage and image-count checks</div>'
                '<div><b>3. Seasonal summary</b>Block values on cropland for fixed seasons</div>'
                '<div><b>4. Anomaly</b>Current season against same-season baseline</div>'
                '<div><b>5. Screening</b>Signals, exposure, exploratory ACSI</div>'
                '<div><b>6. Verification</b>Consistency checks, sensitivity tests, limits</div></div>', unsafe_allow_html=True)

    st.markdown("## Data sources")
    table(["Dataset", "Provider", "Resolution", "Used for", "Period in this run"],
          [["HLS Sentinel-2 S30 v002", "NASA", "30 m", "NDVI, NDMI, VCI on cropland", f"{VB[0]} to {meta['generated_utc'][:4]} (baseline {VB[0]}-{VB[1]})"],
           ["GPM IMERG V07", "NASA", "about 0.1 deg (11 km)", "Rainfall totals and anomalies", f"{CB[0]} onward (baseline {CB[0]}-{CB[1]}); mode: {meta['gpm_mode']}"],
           ["POWER daily", "NASA", "coarse grid (about 0.5 deg)", "Temperature and dry spells", f"{CB[0]} onward"],
           ["WorldCover v200", "ESA", "10 m", "Preliminary cropland mask (class 40)", "2021 map"],
           ["SoilGrids", "ISRIC", "250 m", "Soil properties (optional)", "Current version"],
           ["Administrative blocks", "Project asset", "vector", "Reporting units", "Boundary source and year to be confirmed"]])

    st.markdown("## Method")
    st.markdown("**Season total and anomaly**")
    st.latex(r"P'_{\%}=\frac{P_{\mathrm{season}}-\overline{P}_{\mathrm{baseline}}}{\overline{P}_{\mathrm{baseline}}}\times100")
    st.markdown("Half-hourly IMERG rain rates (mm/hr) are multiplied by 0.5 h before summing. Percentage anomalies are not computed when the baseline is below 20 mm.")
    st.markdown("**Vegetation indices**")
    st.latex(r"NDVI=\frac{B8-B4}{B8+B4},\qquad NDMI=\frac{B8-B11}{B8+B11},\qquad VCI=\frac{NDVI-NDVI_{\min}}{NDVI_{\max}-NDVI_{\min}}\times100")
    st.markdown("**Exploratory index**")
    st.latex(r"ACSI=\sum_i w_i S_i,\qquad S_i=\frac{X_i-X_{\min}}{X_{\max}-X_{\min}},\qquad \sum_i w_i=1")
    w = meta["weights"]
    st.markdown(f"Provisional weights, not calibrated: rainfall {w['rainfall_stress']}, temperature {w['temperature_stress']}, "
                f"NDVI {w['vegetation_stress']}, NDMI {w['moisture_stress']}. Scaling is relative to the blocks in the season analysed.")

    st.markdown("## Thresholds and assumptions")
    table(["Item", "Value", "Nature"],
          [["Season definitions", ", ".join(f"{L.season_label(s, SEAS)}" for s in SEAS), "Assumed monsoon convention; confirm with a local crop calendar"],
           ["Climate baseline", f"{CB[0]}-{CB[1]}", "Short for a climate normal"],
           ["Vegetation baseline", f"{VB[0]}-{VB[1]}", "Limited by the HLS record"],
           ["Rainfall stress", f"{RAIN_T:.0f}% below seasonal average", "Design choice"],
           ["Vegetation, heat, dry-spell stress", f"{Z_T:g} standard deviation beyond baseline", "Design choice"],
           ["Dry day", f"{meta.get('dry_day_mm', 1.0)} mm per day", "Assumption; stricter 2.5 mm also reported"],
           ["Minimum HLS image availability", "50% of the usual season level", "Design choice"],
           ["Cropland area", f"30 m pixels x {HA} ha", "Assumes counts are 30 m pixels"]])

    st.markdown("## Validation and reliability")
    st.markdown(D["validation"] if D["validation"] else "Validation report not found.")
    st.markdown("**Reliability statement.** The outputs are derived from satellite and gridded meteorological datasets and are intended for agricultural "
                "climate-stress screening. Data quality is evaluated through product quality flags, valid-observation coverage, spatial-resolution checks and "
                "comparison with independent reference datasets where available. Results are not a substitute for field-level crop assessment or official drought declarations.")

    st.markdown("## Limitations")
    st.markdown("- Block values from IMERG and POWER cannot resolve differences inside small blocks.\n"
                "- Cropland is a single-year land-cover map, not a crop map; no crop type, irrigation or yield data are used.\n"
                "- Low vegetation indices can reflect harvest timing, fallow land or cloud, not only stress.\n"
                "- The shipped HLS series may use a quality mask without the water bit; see the QC notes below.\n"
                "- Thresholds and weights are design choices and have not been calibrated against observed crop outcomes.\n"
                "- Seasons follow an assumed convention until a local crop calendar is supplied.")
    with st.expander("Quality-control log"):
        st.text(D["qc"])

    st.markdown("## Glossary")
    table(["Term", "Meaning"],
          [["Anomaly", "Difference between the current season and the average of the same season in the baseline years."],
           ["Block", "Administrative sub-division of the district used as the reporting unit."],
           ["NDVI", "Normalised Difference Vegetation Index; higher values indicate greener vegetation."],
           ["NDMI", "Normalised Difference Moisture Index; relates to moisture in vegetation."],
           ["VCI", "Vegetation Condition Index; current NDVI placed within its historical range, 0 (lowest) to 100 (highest)."],
           ["ACSI", "Agricultural Climate Stress Index; exploratory relative score from 0 to 1."],
           ["Exposure", "Area of mapped cropland located in blocks where a signal is raised."],
           ["Provisional", "Near-real-time satellite data that can be revised later."]])

    st.markdown("## References")
    st.markdown("- NASA HLS: https://hls.gsfc.nasa.gov and the HLS V2.0 User Guide (LP DAAC)\n"
                "- NASA GPM IMERG: https://gpm.nasa.gov/data/imerg\n"
                "- NASA POWER: https://power.larc.nasa.gov/docs/\n"
                "- FAO Earth Observation, Agricultural Stress Index System: https://eo.apps.fao.org\n"
                "- ISRIC SoilGrids: https://soilgrids.org")
    gl = b64("geocosmic_logo.png")
    if gl:
        st.markdown(f'<img src="data:image/png;base64,{gl}" style="width:300px; margin-top:12px;" alt="GeoCosmic">', unsafe_allow_html=True)
    st.caption("Reproducibility: parameters, package versions and input-file fingerprints for each run are recorded in ANALYSIS/run_manifest.json.")

st.markdown('<div class="foot">GeoCosmic | NASA International Space Apps Challenge 2026 | AgriResilience screening prototype. '
            'Contains NASA HLS, GPM IMERG and POWER data processed for this project.</div>', unsafe_allow_html=True)
