"""Why does HLS image count per month swing from ~200 to ~20? Prints facts only; no changes made."""
import ee, pandas as pd
import config
from common import init_ee, get_units_fc

init_ee()
geom = get_units_fc().geometry()
col = ee.ImageCollection("NASA/HLS/HLSS30/v002").filterBounds(geom)
props = col.first().propertyNames().getInfo()
print("Image properties:", props)
hist_props = [p for p in ["MGRS_TILE", "SPACECRAFT_NAME", "SENSOR", "PROCESSING_BASELINE"] if p in props]
for ym in ["2019-07", "2021-07", "2024-07", "2025-07", "2026-07"]:
    s = ee.Date(ym + "-01"); e = s.advance(1, "month")
    c = col.filterDate(s, e)
    t = pd.to_datetime(pd.Series(c.aggregate_array("system:time_start").getInfo()), unit="ms")
    print(f"\n{ym}: images={len(t)}, distinct acquisition days={t.dt.date.nunique()}")
    for p in hist_props:
        print("   ", p, c.aggregate_histogram(p).getInfo())
    if "CLOUD_COVERAGE" in props:
        print("    mean CLOUD_COVERAGE:", c.aggregate_mean("CLOUD_COVERAGE").getInfo())
