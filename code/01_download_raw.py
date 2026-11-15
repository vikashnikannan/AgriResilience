"""Download block-level raw extractions into DATA\\. Resumable: re-run to fill gaps.
Usage:  python code\\01_download_raw.py [--only boundary|crop|hls|gpm|power]"""
import argparse, calendar, json, time
import ee, pandas as pd, requests
import config
from common import init_ee, get_units_fc, fc_to_df, month_range, retry

ap = argparse.ArgumentParser()
ap.add_argument("--only", choices=["boundary", "crop", "hls", "gpm", "power"])
args = ap.parse_args()
want = lambda k: args.only in (None, k)

init_ee()
units = get_units_fc()
RAW = config.RAW_DIR

# ---------- 0. Boundary geometry (for maps) ----------
if want("boundary") and not (RAW / "units.geojson").exists():
    simp = units.map(lambda f: f.setGeometry(f.geometry().simplify(100)))
    with open(RAW / "units.geojson", "w") as fh:
        json.dump(retry(lambda: simp.getInfo()), fh)
    print("boundary saved (simplified to 100 m for plotting only)")

# ---------- 1. Cropland mask + pixel counts ----------
crop_mask = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(config.CROP_CLASS)
if want("crop") and not (RAW / "cropland_pixels_by_unit.csv").exists():
    c = (ee.Image.constant(1).updateMask(crop_mask).rename("crop_px")
         .reduceRegions(collection=units, reducer=ee.Reducer.count(), scale=30, tileScale=4))
    df = retry(lambda: fc_to_df(c))
    print("crop count columns:", df.columns.tolist())
    df.rename(columns={"count": "crop_px_30m"})[["unit", "crop_px_30m"]].to_csv(
        RAW / "cropland_pixels_by_unit.csv", index=False)

# ---------- 2. HLS NDVI / NDMI monthly per block ----------
def mask_hls(img):
    """HLS V2.0 Fmask: bit1 cloud, bit2 adjacent to cloud/shadow, bit3 shadow, bit4 snow/ice,
    bit5 water, bits6-7 aerosol level (3 = high). Water/aerosol masking is controlled in config.py."""
    f = img.select("Fmask")
    bad = (f.bitwiseAnd(1 << 1).neq(0).Or(f.bitwiseAnd(1 << 2).neq(0))
           .Or(f.bitwiseAnd(1 << 3).neq(0)).Or(f.bitwiseAnd(1 << 4).neq(0)))
    if config.HLS_MASK_WATER:
        bad = bad.Or(f.bitwiseAnd(1 << 5).neq(0))
    if config.HLS_MASK_HIGH_AEROSOL:
        bad = bad.Or(f.rightShift(6).bitwiseAnd(3).eq(3))
    return img.updateMask(bad.Not())

def add_idx(img):
    return img.addBands([img.normalizedDifference(["B8", "B4"]).rename("NDVI"),
                         img.normalizedDifference(["B8", "B11"]).rename("NDMI")])

HLS_COLS = ["unit", "NDVI_mean", "NDVI_median", "NDVI_count",
            "NDMI_mean", "NDMI_median", "NDMI_count", "month", "n_images"]

if want("hls"):
    p = RAW / "hls_monthly_by_unit_raw.csv"
    # Guard: never mix months downloaded with different quality masks in one file.
    mask_tag = f"bits1-4; water={config.HLS_MASK_WATER}; high_aerosol={config.HLS_MASK_HIGH_AEROSOL}"
    tag_file = RAW / "hls_mask_info.txt"
    if p.exists():
        old_tag = tag_file.read_text().strip() if tag_file.exists() else "bits1-4; water=False; high_aerosol=False (legacy download)"
        if old_tag != mask_tag:
            raise SystemExit(f"Existing HLS file was built with mask [{old_tag}] but config.py asks for [{mask_tag}].\n"
                             f"Move/delete {p.name} to re-download everything with the new mask, or set the config back.")
    tag_file.write_text(mask_tag)
    done = set(pd.read_csv(p)["month"]) if p.exists() else set()
    red = (ee.Reducer.mean().combine(ee.Reducer.median(), sharedInputs=True)
           .combine(ee.Reducer.count(), sharedInputs=True))
    for m in month_range(config.HLS_START, config.HLS_END):
        key = m.strftime("%Y-%m")
        if key in done:
            continue
        s = ee.Date(m.strftime("%Y-%m-%d")); e = s.advance(1, "month")
        col = (ee.ImageCollection("NASA/HLS/HLSS30/v002").filterBounds(units.geometry())
               .filterDate(s, e).map(mask_hls).map(add_idx))
        try:
            n = retry(lambda: col.size().getInfo())
            if n == 0:
                with open(RAW / "hls_months_no_images.txt", "a") as fh: fh.write(key + "\n")
                print(key, "no images"); continue
            comp = col.select(["NDVI", "NDMI"]).median().updateMask(crop_mask)
            df = None
            for ts in (4, 8, 16):               # retry with more tiling on memory errors
                try:
                    df = fc_to_df(comp.reduceRegions(collection=units, reducer=red,
                                                     scale=30, tileScale=ts))
                    break
                except Exception as ex:
                    print(key, f"tileScale {ts} failed: {str(ex)[:120]}")
            if df is None:
                print(key, "HLS FAILED (will retry on next run)"); continue
            if not {"NDVI_mean", "NDVI_count"} <= set(df.columns):
                raise SystemExit(f"Unexpected HLS columns: {df.columns.tolist()}")
            df["month"], df["n_images"] = key, n
            df = df.reindex(columns=HLS_COLS)
            df.to_csv(p, mode="a", header=not p.exists(), index=False)
            print(key, "HLS ok, images:", n)
        except SystemExit:
            raise
        except Exception as ex:
            print(key, "HLS ERROR:", str(ex)[:200])

# ---------- 3. IMERG rainfall monthly per block ----------
MONTHLY, HALFHR = "NASA/GPM_L3/IMERG_MONTHLY_V07", "NASA/GPM_L3/IMERG_V07"
GPM_COLS = ["unit", "rain_mm", "month", "n_images", "expected_images", "source"]

if want("gpm"):
    monthly_end = pd.Timestamp(ee.Date(ee.ImageCollection(MONTHLY)
                  .aggregate_max("system:time_start")).format("YYYY-MM-dd").getInfo())
    print("IMERG monthly ends:", monthly_end.date(), "| mode:", config.GPM_MODE)
    p = RAW / "gpm_monthly_by_unit_raw.csv"
    done = set(pd.read_csv(p)["month"]) if p.exists() else set()
    for m in month_range(config.GPM_START, config.GPM_END):
        key = m.strftime("%Y-%m")
        if key in done:
            continue
        try:
            s = ee.Date(m.strftime("%Y-%m-%d")); e = s.advance(1, "month")
            days = calendar.monthrange(m.year, m.month)[1]
            if config.GPM_MODE == "hybrid" and m <= monthly_end:
                # monthly 'precipitation' treated as mean rate mm/hr (consistent with your overlap check)
                img = (ee.ImageCollection(MONTHLY).filterDate(s, e).select("precipitation")
                       .first().multiply(24 * days).rename("rain_mm"))
                n, exp, src = 1, 1, "IMERG_MONTHLY_V07"
            else:
                col = ee.ImageCollection(HALFHR).filterDate(s, e).select("precipitation")
                n = retry(lambda: col.size().getInfo()); exp = days * 48; src = "IMERG_V07_30min"
                img = col.map(lambda i: i.multiply(0.5)).sum().rename("rain_mm")
            df = retry(lambda: fc_to_df(img.reduceRegions(
                collection=units, reducer=ee.Reducer.mean(), scale=11132, tileScale=4)))
            df = df.rename(columns={"mean": "rain_mm"})
            df["month"], df["n_images"], df["expected_images"], df["source"] = key, n, exp, src
            df.reindex(columns=GPM_COLS).to_csv(p, mode="a", header=not p.exists(), index=False)
            print(key, "GPM ok", src, n)
        except Exception as ex:
            print(key, "GPM ERROR:", str(ex)[:200])

# ---------- 4. NASA POWER daily per block centroid ----------
if want("power") and not (RAW / "power_daily_by_unit_raw.csv").exists():
    cents = units.map(lambda f: ee.Feature(None, {"unit": f.get("unit"),
              "lon": f.geometry().centroid(1).coordinates().get(0),
              "lat": f.geometry().centroid(1).coordinates().get(1)}))
    pts = fc_to_df(cents)
    frames = []
    for _, r in pts.iterrows():
        try:
            resp = requests.get("https://power.larc.nasa.gov/api/temporal/daily/point",
                params={"parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR", "community": "AG",
                        "latitude": r["lat"], "longitude": r["lon"],
                        "start": config.POWER_START, "end": config.POWER_END,
                        "format": "JSON", "time-standard": "UTC"}, timeout=180)
            resp.raise_for_status()
            d = pd.DataFrame(resp.json()["properties"]["parameter"])
            d.index = pd.to_datetime(d.index, format="%Y%m%d")
            d = d.rename_axis("date").reset_index()
            d["unit"], d["lat"], d["lon"] = r["unit"], r["lat"], r["lon"]
            frames.append(d); print(r["unit"], "POWER ok", len(d)); time.sleep(1)
        except Exception as ex:
            print(r["unit"], "POWER ERROR:", str(ex)[:200])
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(RAW / "power_daily_by_unit_raw.csv", index=False)
    if len(frames) < len(pts):
        print("WARNING: POWER incomplete; file saved with available blocks only. Delete it and re-run to retry.")

print("Download step finished ->", RAW)
