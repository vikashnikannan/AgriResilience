# Dashboard and pipeline summary (current version)

## Dashboard (app/app.py, app/logic.py)
Six sections: Overview, Climate Hazard, Crop Condition, Integrated Assessment, Adaptation Options, Methodology and Data.
- Every sentence is generated from files in app/data or is a fixed, documented statement about method.
- Explainability: rule-based decision trace for each block, exact indicator contributions to ACSI (weight x scaled value / sum of available weights), ranking stability under changed weights, and a plain statement of the rainfall-vegetation correlation with its sample size. No black-box model is used.
- Vegetation signals are withheld when NASA HLS image availability is below 50% of the usual level for the season.
- Adaptation Options lists general planning considerations only; the dashboard holds no crop, irrigation, cost or soil-suitability data and does not recommend a crop.
- Branding: GeoCosmic banner and wordmark taken from the team's own poster.

## Limits that remain (also stated in the dashboard)
- Season months are an assumed monsoon convention; thresholds and weights are design choices and are not calibrated.
- Cropland is a single-year ESA WorldCover map; hectares assume 30 m pixels.
- Temperature and dry spells come from a coarse grid shared by blocks; they are district-wide.
- No independent validation unless IMD or official reference files are placed in DATA/reference/.
- The shipped HLS series predates the water-bit mask; re-download to apply it.
- Earth Engine scripts (00, 01, 01c, 04) were edited and syntax-checked but could not be run without a Google login.

See METHODOLOGY_COMPLIANCE.md for the item-by-item check against the methodology.
