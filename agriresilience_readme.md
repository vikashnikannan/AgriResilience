# AgriResilience: Agricultural Climate Stress Screening for Tirunelveli

**GeoCosmic | NASA International Space Apps Challenge 2026 — From Space to Sustainable Farms**

AgriResilience combines NASA Earth observation data to screen the nine blocks of Tirunelveli District, Tamil Nadu, for climate-related stress on farmland. It reports where rainfall is below normal, whether vegetation shows a matching response, and how much cropland lies in the affected blocks. Every result can be traced to its data source, period, and processing rule.

> **Disclaimer:** It is a screening product. It is not a yield forecast and not an official drought declaration.

---

## Data

| Dataset | Used for | Native resolution |
| :--- | :--- | :--- |
| **NASA HLS Sentinel-2 (HLSS30 v2)** | Vegetation greenness (NDVI), vegetation moisture (NDMI), Vegetation Condition Index | 30 m |
| **NASA GPM IMERG V07** | Rainfall totals and anomalies | ~11 km |
| **NASA POWER** | Temperature and daily rainfall (dry spells) | ~0.5 degree |
| **ESA WorldCover** | Preliminary cropland mask | 10 m |
| **SoilGrids (optional)** | Soil properties | 250 m |

---

## Method in Brief

1. **Cropland isolation:** Cropland is isolated with a land-cover mask so forests and scrub do not count as farmland.
2. **Quality masking & compositing:** HLS images are quality-masked (cloud, adjacent cloud, shadow, snow, and optionally water and aerosol) and composited by season.
3. **Baseline comparison:** Each season is compared with the same season in earlier years (anomalies, VCI).
4. **Threshold flagging:** Rainfall, vegetation, and moisture signals are flagged against documented thresholds. Heat and dry-spell signals are reported as district context because their grids are coarse.
5. **Concurrent-stress screening:** Blocks are classified by concurrent-stress screening. Vegetation is withheld when satellite image availability is too low.
6. **Exposure calculation:** Cropland area in flagged blocks is reported as exposure.
7. **Exploratory stress index (ACSI):** Provided with exact indicator contributions and a sensitivity analysis. Its weights are design choices and are not calibrated.

---

## Dashboard (Streamlit)

A Streamlit application with six sections: **Overview**, **Climate Hazard**, **Crop Condition**, **Integrated Assessment**, **Adaptation Options**, and **Methodology and Data**.

It runs offline from the exported files in `app/data`. Results are explainable—providing a rule-based decision trace for each block, indicator contributions, and ranking stability. No black-box model is used.

### Running Streamlit Directly (Without Re-running the Pipeline)

If `app/data/` already contains exported results, you can launch the dashboard directly:

```bash
pip install -r requirements.txt
streamlit run app/app.py
```

The app will open in your browser at `http://localhost:8501`.

### Deploying on Streamlit Community Cloud

1. Push this repository (including `app/data/`) to GitHub.
2. Sign in to [share.streamlit.io](https://share.streamlit.io) and click **New app**.
3. Select your repository (`vikashnikannan/AgriResilience`), branch (`main`), and set the **Main file path** to:
   ```text
   app/app.py
   ```
4. Click **Deploy**.

---

## Quick Start (Full Pipeline)

Requires Python 3.10 or newer.

```bash
python run_all.py          # Windows: double-click run_all.bat
```

The first run creates a project-only environment (`.venv`), re-processes the data in `DATA/`, runs the checks, and opens the Streamlit dashboard at `http://localhost:8501`.

- **Options:** `--no-app`, `--ee` (refresh data from Google Earth Engine, login required), `--selftest`.
- Full instructions are in `HOW_TO_RUN.txt`.

---

## Repository Layout

```text
run_all.py       One-command pipeline, tests, and dashboard
code/            Pipeline scripts 00-06 and config.py (all settings)
app/             Streamlit dashboard (app/app.py) and exported data (app/data/)
DATA/            Raw downloads (DATA/reference/ for optional IMD and official data)
PREPROCESSED/    Cleaned tables and QC report
ANALYSIS/        Results, validation report, and run manifest
docs/            Methodology compliance and limitations
tests/           Dashboard tests
```

---

## Limitations

- Season months follow an assumed monsoon convention until a local crop calendar is supplied.
- Thresholds and index weights are design choices, not calibrated values.
- The cropland mask is a single-year, preliminary land-cover map.
- Temperature and dry spells come from a coarse grid shared by several blocks.
- Without IMD or official reference data (`DATA/reference/`), results are unvalidated satellite and model estimates.
- No irrigation, crop-type, cost, or soil-suitability data are included, so no crop recommendations are made.
- The Earth Engine download scripts require a Google login.

See `docs/METHODOLOGY_COMPLIANCE.md` for the item-by-item check against the methodology.

---

## Acknowledgements

NASA LP DAAC and GSFC (HLS), NASA GES DISC (GPM IMERG), NASA LaRC (POWER), ESA (WorldCover), ISRIC (SoilGrids), Google Earth Engine, and Streamlit.