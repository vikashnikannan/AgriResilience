"""OPTIONAL (needs Earth Engine): SoilGrids soil properties averaged over each block's cropland -> DATA/soil_by_unit.csv.
Uses the ISRIC SoilGrids 250 m community assets in Earth Engine (0-5 cm layer). Check the catalogue for units/scale factors:
sand, clay and soc are stored in g/kg-type units (converted /10 here), phh2o as pH x 10 (converted /10)."""
import ee, pandas as pd
import config
from common import init_ee, get_units_fc, fc_to_df, retry

init_ee()
units = get_units_fc()
mask = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(config.CROP_CLASS)
layers = {"sand_pct": ("projects/soilgrids-isric/sand_mean", "sand_0-5cm_mean"),
          "clay_pct": ("projects/soilgrids-isric/clay_mean", "clay_0-5cm_mean"),
          "soc_g_per_kg": ("projects/soilgrids-isric/soc_mean", "soc_0-5cm_mean"),
          "ph": ("projects/soilgrids-isric/phh2o_mean", "phh2o_0-5cm_mean")}
img = ee.Image.cat([ee.Image(a).select(b).divide(10).rename(n) for n, (a, b) in layers.items()]).updateMask(mask)
df = retry(lambda: fc_to_df(img.reduceRegions(collection=units, reducer=ee.Reducer.mean(), scale=250, tileScale=4)))
df.to_csv(config.RAW_DIR / "soil_by_unit.csv", index=False)
print(df)
