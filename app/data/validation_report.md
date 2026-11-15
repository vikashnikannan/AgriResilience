# Validation and reliability report

Consistency checks are not independent validation. Independent comparison runs only when reference files are placed in DATA/reference/.

## 1. Consistency check: GPM IMERG vs NASA POWER monthly rainfall (mm)
- GPM vs POWER (monthly, all blocks): n=1278, MBE=-1.25, RMSE=44.92, r=0.89. Both are satellite-based and not fully independent; a good match shows the processing is coherent, not that rainfall is correct.

## 2. Independent reference comparison
- **No independent reference files supplied.** Rainfall, temperature and the cropland mask are therefore reported as UNVALIDATED satellite/model estimates.

## 3. Sensitivity: does the target-season rainfall flag change with the baseline years?
Rainfall anomaly % for SWM 2026 under alternative baselines (see validation_baseline_sensitivity.csv). Blocks whose rainfall-deficit flag changes: none.

## 4. Dry-spell threshold sensitivity (days)
```
          unit  longest dry spell, <1.0 mm/day  <2.5 mm/day
    Radhapuram                              17           32
     Nanguneri                              17           32
         Manur                              10           17
 Palayamkottai                              17           32
     Pappakudi                              10           17
     Valliyoor                              17           32
      Kalakadu                              17           32
Cheranmahadevi                              17           32
  Ambasamudram                              17           32
```

## 5. Quality checklist (methodology section 13)
- HLS quality mask in raw data: legacy: bits 1-4 only (no water / aerosol bit)
- GPM half-hourly rate (mm/hr) x 0.5 h before summing: implemented in 01_download_raw.py
- Seasonal comparisons use the same season window and baseline: implemented in 03_analysis.py
- Missing indicators are never set to zero; weights are renormalised; blocks need >= 3 indicators: implemented
- Boundary source/year, season months (assumed convention) and crop calendar: **must be confirmed locally**
- Official crop statistics, irrigation, soil moisture (SMAP): not included unless supplied
