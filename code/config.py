"""Central configuration. Items marked ASSUMPTION are my choices, not verified standards.
Review them and record whatever you settle on in your methodology."""
import os
from pathlib import Path

PROJECT_ID = "vikashni-anna-univ"
ASSET_ID   = "projects/vikashni-anna-univ/assets/nasa/tirunelveli_block"
UNIT_COL   = "Block_Name"          # confirmed by script 00 output

# NASA_BASE can be overridden by an environment variable (used by selftest.py)
# Default: the package folder itself (works wherever you unzip it). Override with NASA_BASE if needed.
BASE         = Path(os.environ.get("NASA_BASE", Path(__file__).resolve().parents[1]))
RAW_DIR      = BASE / "DATA"            # all raw downloads
PREP_DIR     = BASE / "PREPROCESSED"    # cleaned tables
ANALYSIS_DIR = BASE / "ANALYSIS"        # anomalies, ACSI, charts, report
REF_DIR      = RAW_DIR / "reference"    # OPTIONAL user-supplied reference data (IMD, official crop area, seasons.json)

# ---- Download periods (end dates exclusive) ----
HLS_START, HLS_END     = "2018-01-01", "2026-11-01"   # ASSUMPTION: start 2018 (see VEG_BASELINE)
GPM_START, GPM_END     = "2015-01-01", "2026-11-01"
POWER_START, POWER_END = "20150101", "20261031"
LAST_FULL_MONTH = "2026-10"   # last month fully inside the download window

# ---- Rainfall source ----
# "halfhourly": IMERG 30-min product for every month (consistent series, slower).
# "hybrid": IMERG monthly (gauge-adjusted) up to its last date, 30-min afterwards.
# Your June 2025 check showed 30-min ~14% below monthly for one month. Run
# 00c_imerg_overlap.py before choosing "hybrid".
GPM_MODE = "halfhourly"

# ---- Seasons: ASSUMPTION (general south-Indian monsoon convention), verify locally ----
SEASONS = {"Winter": [1, 2], "Summer": [3, 4, 5], "SWM": [6, 7, 8, 9], "NEM": [10, 11, 12]}

CROP_CLASS = 40               # ESA WorldCover cropland class; confirm with class table

# ---- Quality thresholds (all ASSUMPTIONS) ----
MIN_VALID_COV_PCT   = 20.0    # min % of block cropland pixels valid in a month (HLS)
MIN_VEG_MONTH_FRAC  = 0.5     # share of a season's months that must have valid NDVI
MIN_TEMP_DAY_FRAC   = 0.9     # share of a season's days that must have POWER data
GPM_MIN_COMPLETENESS = 0.98   # a month counts as complete if >=98% of expected 30-min images exist
HLS_IMAGE_RATIO_WARN = 0.5    # warn if target-period HLS images/month < 50% of baseline average

# ---- Baselines ----
CLIM_BASELINE = (2015, 2024)  # rainfall and temperature
VEG_BASELINE  = (2018, 2024)  # NDVI/NDMI (HLS Sentinel-2 record is shorter)
MIN_BASELINE_YEARS = 5
RAIN_BASELINE_MIN_MM = 20.0   # below this, % anomaly is not computed (misleading)
RAIN_STRESS_METRIC = "pct"    # "pct" (guide) or "z" (anomaly / baseline std)

# ---- HLS quality mask (methodology 5.2). HLS V2.0 Fmask: bit1 cloud, bit2 adjacent, bit3 shadow,
# bit4 snow/ice, bit5 water, bits6-7 aerosol level (3 = high). Verify against the official user guide. ----
HLS_MASK_WATER = True
HLS_MASK_HIGH_AEROSOL = False     # set True to also drop high-aerosol observations

# ---- Dry spells (from NASA POWER daily precipitation; coarse 0.5 deg grid) ----
DRY_DAY_MM     = 1.0              # ASSUMPTION: a day with < 1 mm is dry
DRY_DAY_ALT_MM = 2.5              # alternative threshold, reported for sensitivity

# ---- Concurrent-stress screening thresholds (design choices, documented in the dashboard) ----
RAIN_DEFICIT_PCT = 10.0           # rainfall stress if anomaly <= -10 %
STRESS_Z         = 1.0            # temp / NDVI / NDMI / dry-spell flagged at 1 standard deviation of baseline
HA_PER_PIXEL     = 0.09           # one 30 m pixel = 0.09 ha (ASSUMPTION: crop_px_30m counts 30 m pixels)

# ---- ACSI: Agricultural Climate Stress Index (exploratory; provisional weights, NOT calibrated) ----
# Initial design from the methodology. NDVI and NDMI are related, so see the sensitivity analysis.
WEIGHTS = {"rainfall_stress": 0.35, "temperature_stress": 0.20,
           "vegetation_stress": 0.25, "moisture_stress": 0.20}
MIN_INDICATORS = 3            # indicators needed to score a block
# Minimum spread across blocks before min-max scaling is applied; below it the indicator
# is treated as "no usable spatial contrast" (avoids stretching noise to 0-1).
MIN_DISTINCT_VALUES = 4       # ASSUMPTION: an indicator with fewer distinct block values than this is
                              # coarser than the blocks (e.g. shared POWER cells) and is not min-max scaled
MIN_RANGE = {"rain_pct": 1.0, "rain_z": 0.05, "temp": 0.1, "ndvi": 0.005, "ndmi": 0.005}

# ---- Target period for the final screening (None = latest usable season) ----
TARGET_YEAR   = None          # e.g. 2026
TARGET_SEASON = None          # e.g. "SWM"
N_MONTE_CARLO = 1000

# Optional: replace the assumed seasons with a documented local crop calendar
# (DATA/reference/seasons.json, e.g. {"Kharif": [6,7,8,9], "Rabi": [10,11,12,1]}).
_sj = REF_DIR / "seasons.json"
if _sj.exists():
    import json
    SEASONS = {k: sorted(v) for k, v in json.load(open(_sj)).items()}

for d in (RAW_DIR, PREP_DIR, ANALYSIS_DIR, REF_DIR):
    d.mkdir(parents=True, exist_ok=True)
