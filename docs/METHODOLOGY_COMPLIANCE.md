# Methodology compliance check (code vs AgriResilience methodology)

| Methodology item | Status | Where |
|---|---|---|
| Separate hazard / response / exposure; no single "proof" index | Done: screening page shows signals separately; ACSI is optional and labelled exploratory | 03_analysis.py, app "Stress screening & checks" |
| Cropland mask (not all green pixels), labelled preliminary | Done (ESA WorldCover class 40) | 01_download_raw.py |
| Official crop-area comparison | Hook added; runs when `DATA/reference/official_crop_area_ha.csv` is supplied | 06_validation.py |
| HLS cloud/adjacent/shadow/snow mask | Done | 01_download_raw.py |
| HLS water bit (5) and optional high-aerosol mask | **Added** (config switches). Shipped raw data predates it; re-download HLS to apply | 01_download_raw.py, config.py |
| Mixed-mask protection | **Added** (script refuses to append months with a different mask) | 01_download_raw.py |
| NDVI, NDMI seasonal composites, valid-pixel coverage, image-count check | Done | 02/03 |
| Seasonal anomalies vs same-season baseline, min baseline years | Done | 03_analysis.py |
| VCI | **Added** (same-season baseline range, 0-100) | 03_analysis.py |
| IMERG mm/hr x 0.5 h before summing | Done (verified) | 01_download_raw.py |
| Percentage anomaly guarded for tiny baselines | Done | 03_analysis.py |
| Dry spells with documented threshold + alternative | **Added** (from POWER daily precipitation, <1 mm and <2.5 mm) | 02_preprocess.py, 06_validation.py |
| Temperature anomaly | Done (POWER T2M); heat-day count NOT done (needs a sourced crop-specific threshold) | 03_analysis.py |
| Soil (SoilGrids) | **Added** download script + dashboard panel (needs Earth Engine; not run here) | 01c_download_soil.py |
| SMAP soil moisture | Not implemented (marked optional in the methodology) | - |
| Exposure = % of cropland in hazard zones | **Added** (block-resolved, district totals in ha and %) | 03_analysis.py |
| Adaptive capacity | Information panel with data gaps; **no score** (as required) | app |
| Concurrent-stress screening (rain only / veg only / concurrent / insufficient) | **Added** | 03_analysis.py, app |
| Optional ACSI with documented weights, renormalised for missing indicators, sensitivity analysis | Done; renamed from ACVI; weights set to methodology (0.35/0.20/0.25/0.20) | 03_analysis.py |
| Missing data never set to zero; show coverage and confidence | Done | 03_analysis.py, app |
| Validation: GPM/POWER vs independent reference (MBE, RMSE, r) | Hook added; needs IMD files. Without them the report says "unvalidated". GPM-vs-POWER is a consistency check only | 06_validation.py |
| Sensitivity: baseline years, thresholds, weights, drop-one | Done (baseline + dry-day threshold in 06; weights/drop-one/Monte-Carlo in 03) | 03, 06 |
| Seasons from a local crop calendar | Not obtainable here. Override via `DATA/reference/seasons.json`; default is an assumed convention | config.py |
| Longer rainfall baseline (1991-2020 / 2001+) | Not done: data window starts 2015 | config.py |
| Adaptation scenarios, no invented TOPSIS values | Qualitative scenarios only (correct per methodology) | app "What can be done" |
| Reproducibility record | **Added** run_manifest.json (versions, config, input hashes, step status) | run_all.py |

Not run in this build (no Google login available): scripts 00, 01, 01c, 04. They were edited and syntax-checked only.
