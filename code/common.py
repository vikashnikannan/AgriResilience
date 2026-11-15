import time
import ee, pandas as pd
import config

def init_ee():
    ee.Initialize(project=config.PROJECT_ID)

def get_units_fc():
    """Block FeatureCollection from the asset, reduced to a single 'unit' property."""
    fc = ee.FeatureCollection(config.ASSET_ID)
    props = fc.first().propertyNames().getInfo()
    if config.UNIT_COL not in props:
        raise SystemExit(f"UNIT_COL '{config.UNIT_COL}' not in {props}. Edit config.py.")
    return fc.map(lambda f: ee.Feature(f.geometry(), {"unit": f.get(config.UNIT_COL)}))

def fc_to_df(fc):
    return pd.DataFrame([f["properties"] for f in fc.getInfo()["features"]])

def month_range(start, end):
    return pd.date_range(start, end, freq="MS", inclusive="left")

def retry(fn, tries=3, wait=15):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as ex:          # network / quota hiccups
            last = ex
            time.sleep(wait * (i + 1))
    raise last
