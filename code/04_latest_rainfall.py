"""OPTIONAL: latest 30 days of IMERG rainfall per block vs the same calendar window in 2015-2024.
Writes DATA\\latest_window_summary.csv and DATA\\latest_rainfall_daily.csv. Re-run any day to refresh.
Recent IMERG data is provisional (near real time); see the app's Methodology page."""
from datetime import date, timedelta
import ee, numpy as np, pandas as pd
import config
from common import init_ee, get_units_fc, fc_to_df, retry

WINDOW_DAYS, DAILY_DAYS = 30, 60
init_ee()
units = get_units_fc()
col = ee.ImageCollection("NASA/GPM_L3/IMERG_V07")

last = pd.to_datetime(retry(lambda: col.aggregate_max("system:time_start").getInfo()), unit="ms")
end_day = last.normalize() if (last.hour == 23 and last.minute >= 30) else last.normalize() - pd.Timedelta(days=1)
end_day = end_day.date()
print("Latest IMERG 30-min timestamp:", last, "-> last complete day used:", end_day)

def rain_by_unit(s, e_excl):
    c = col.filterDate(s.isoformat(), e_excl.isoformat()).select("precipitation")
    img = c.map(lambda i: i.multiply(0.5)).sum().rename("rain_mm")
    df = retry(lambda: fc_to_df(img.reduceRegions(collection=units, reducer=ee.Reducer.mean(),
                                                  scale=11132, tileScale=4)))
    return df.rename(columns={"mean": "rain_mm"}), c

# ---- current window
w_start = end_day - timedelta(days=WINDOW_DAYS - 1)
cur, c_cur = rain_by_unit(w_start, end_day + timedelta(days=1))
n_img = retry(lambda: c_cur.size().getInfo())
try:
    n_prov = retry(lambda: c_cur.filter(ee.Filter.eq("status", "provisional")).size().getInfo())
except Exception as ex:
    n_prov = np.nan; print("status property not readable:", str(ex)[:100])

# ---- baseline: same calendar window, each year 2015-2024
base = []
for y in range(config.CLIM_BASELINE[0], config.CLIM_BASELINE[1] + 1):
    try:
        s = date(y, w_start.month, w_start.day)
    except ValueError:
        s = date(y, w_start.month, 28)
    b, _ = rain_by_unit(s, s + timedelta(days=WINDOW_DAYS))
    b["year"] = y; base.append(b)
    print("baseline", y, "ok")
base = pd.concat(base).groupby("unit")["rain_mm"].agg(baseline_mean_mm="mean", baseline_years="count").reset_index()
summ = cur.rename(columns={"rain_mm": "rain_mm_last30d"}).merge(base, on="unit")
summ["anomaly_pct"] = np.where(summ["baseline_mean_mm"] >= 10,
                               100 * (summ["rain_mm_last30d"] - summ["baseline_mean_mm"]) / summ["baseline_mean_mm"], np.nan)
summ["window_start"], summ["window_end"] = w_start.isoformat(), end_day.isoformat()
summ["n_images"], summ["n_provisional_images"] = n_img, n_prov
summ.to_csv(config.RAW_DIR / "latest_window_summary.csv", index=False)

# ---- daily series
rows = []
for k in range(DAILY_DAYS):
    d = end_day - timedelta(days=DAILY_DAYS - 1 - k)
    df, _ = rain_by_unit(d, d + timedelta(days=1))
    df["date"] = d.isoformat(); rows.append(df)
pd.concat(rows)[["date", "unit", "rain_mm"]].to_csv(config.RAW_DIR / "latest_rainfall_daily.csv", index=False)
print(summ.round(1).to_string(index=False))
print("Saved latest_window_summary.csv and latest_rainfall_daily.csv in", config.RAW_DIR)
