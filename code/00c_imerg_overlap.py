"""Compare IMERG monthly (gauge-adjusted) vs 30-min sums, Jan 2023 - Sep 2025."""
import calendar
import ee, pandas as pd
import config
from common import init_ee, get_units_fc, month_range, retry

init_ee()
geom = get_units_fc().geometry()
rows = []
for m in month_range("2023-01-01", "2025-10-01"):
    s = ee.Date(m.strftime("%Y-%m-%d")); e = s.advance(1, "month")
    days = calendar.monthrange(m.year, m.month)[1]
    mon = (ee.ImageCollection("NASA/GPM_L3/IMERG_MONTHLY_V07").filterDate(s, e)
           .select("precipitation").first().multiply(24 * days).rename("monthly"))
    half = (ee.ImageCollection("NASA/GPM_L3/IMERG_V07").filterDate(s, e)
            .select("precipitation").map(lambda i: i.multiply(0.5)).sum().rename("halfhr"))
    r = retry(lambda: mon.addBands(half).reduceRegion(
        ee.Reducer.mean(), geom, 11132, tileScale=4).getInfo())
    rows.append({"month": m.strftime("%Y-%m"), **r}); print(rows[-1])
df = pd.DataFrame(rows)
df["ratio_half_over_monthly"] = df["halfhr"] / df["monthly"]
df.to_csv(config.RAW_DIR / "imerg_overlap_check.csv", index=False)
print(df.to_string())
print("Overall ratio:", df["halfhr"].sum() / df["monthly"].sum())
