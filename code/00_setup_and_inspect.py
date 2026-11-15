import ee
import config
from common import init_ee

init_ee()
fc = ee.FeatureCollection(config.ASSET_ID)
print("Feature count:", fc.size().getInfo())
print("Property names:", fc.first().propertyNames().getInfo())
print("Total area (km2):", fc.geometry().area(100).divide(1e6).getInfo())

def info(aid):
    col = ee.ImageCollection(aid)
    t0 = ee.Date(col.aggregate_min("system:time_start")).format("YYYY-MM-dd").getInfo()
    t1 = ee.Date(col.aggregate_max("system:time_start")).format("YYYY-MM-dd").getInfo()
    return t0, t1, col.first().bandNames().getInfo()

for name, aid in {"HLS S30": "NASA/HLS/HLSS30/v002",
                  "IMERG monthly": "NASA/GPM_L3/IMERG_MONTHLY_V07",
                  "IMERG 30-min": "NASA/GPM_L3/IMERG_V07"}.items():
    try:
        print(name, info(aid))
    except Exception as e:
        print(name, "FAILED:", e)

wc = ee.ImageCollection("ESA/WorldCover/v200").first()
print("WorldCover classes:", dict(zip(wc.get("Map_class_values").getInfo(),
                                      wc.get("Map_class_names").getInfo())))
