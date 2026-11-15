# AgriResilience analysis report: SWM 2026

Screening and decision-support output. Not a validated crop-yield or drought-risk model.

## Settings used
- Climate baseline (rain, temperature): 2015-2024
- Vegetation baseline (NDVI, NDMI): 2018-2024
- Minimum baseline years: 5
- Rainfall source mode: halfhourly
- Rainfall stress metric: pct
- Weights (provisional, not calibrated): {'rainfall_stress': 0.35, 'temperature_stress': 0.2, 'vegetation_stress': 0.25, 'moisture_stress': 0.2}
- Seasons (assumed convention): {'Winter': [1, 2], 'Summer': [3, 4, 5], 'SWM': [6, 7, 8, 9], 'NEM': [10, 11, 12]}

## Block results, SWM 2026
| Block | Rain mm | Rain anom % | Temp anom C | NDVI anom | NDMI anom | Min valid cov % | N indicators | ACSI | ACSI_class |
|---|---|---|---|---|---|---|---|---|---|
| Radhapuram | 192.61 | -19.18 | 0.49 | -0.00 | 0.01 | 100.00 | 3 | 0.89 | Higher |
| Nanguneri | 244.11 | 1.10 | 0.49 | -0.03 | -0.01 | 100.00 | 3 | 0.79 | Higher |
| Manur | 230.54 | -11.84 | 0.77 | 0.01 | 0.02 | 99.60 | 3 | 0.75 | Higher |
| Palayamkottai | 245.17 | 0.06 | 0.49 | 0.00 | 0.01 | 99.97 | 3 | 0.67 | Moderate |
| Pappakudi | 325.71 | 3.06 | 0.77 | 0.01 | 0.03 | 99.23 | 3 | 0.58 | Moderate |
| Valliyoor | 282.94 | 1.38 | 0.49 | 0.02 | 0.04 | 100.00 | 3 | 0.55 | Moderate |
| Kalakadu | 391.08 | 20.36 | 0.49 | -0.02 | 0.00 | 99.91 | 3 | 0.53 | Lower |
| Cheranmahadevi | 322.13 | 6.34 | 0.49 | 0.04 | 0.05 | 99.85 | 3 | 0.41 | Lower |
| Ambasamudram | 581.74 | 22.23 | 0.49 | 0.09 | 0.10 | 73.32 | 3 | 0.00 | Lower |

Classes (Lower / Moderate / Higher) are terciles of ACSI among scored blocks in this season. They describe relative position only and are not absolute risk thresholds.

## Concurrent-stress screening (primary integrated output)
Heat and dry-spell flags enter the block screening only when blocks differ in that season (coarse grid); otherwise they are reported district-wide. Flags: rainfall deficit <= -10% ; heat / dry spell >= +1 sd ; vegetation (NDVI or NDMI) <= -1 sd of the same-season baseline, only when enough HLS images exist. Thresholds are design choices, not official categories.
| Block | Concurrent-stress screening | Rain anom % | Longest dry spell (d) | Dry spell anom (d) | Temp anom C | NDVI anom | NDMI anom | VCI (0-100) |
|---|---|---|---|---|---|---|---|---|
| Radhapuram | Rainfall stress only (vegetation not assessed) | -19.18 | 17 | -2.40 | 0.49 | -0.00 | 0.01 | NA |
| Nanguneri | No stress signal (vegetation not assessed) | 1.10 | 17 | -2.40 | 0.49 | -0.03 | -0.01 | NA |
| Manur | Rainfall stress only (vegetation not assessed) | -11.84 | 10 | -0.40 | 0.77 | 0.01 | 0.02 | NA |
| Palayamkottai | No stress signal (vegetation not assessed) | 0.06 | 17 | -2.40 | 0.49 | 0.00 | 0.01 | NA |
| Pappakudi | No stress signal (vegetation not assessed) | 3.06 | 10 | -0.40 | 0.77 | 0.01 | 0.03 | NA |
| Valliyoor | No stress signal (vegetation not assessed) | 1.38 | 17 | -2.40 | 0.49 | 0.02 | 0.04 | NA |
| Kalakadu | No stress signal (vegetation not assessed) | 20.36 | 17 | -2.40 | 0.49 | -0.02 | 0.00 | NA |
| Cheranmahadevi | No stress signal (vegetation not assessed) | 6.34 | 17 | -2.40 | 0.49 | 0.04 | 0.05 | NA |
| Ambasamudram | No stress signal (vegetation not assessed) | 22.23 | 17 | -2.40 | 0.49 | 0.09 | 0.10 | NA |

## Agricultural exposure (cropland area in blocks showing each signal)
Indicators are block-level, so exposure is block-resolved: the cropland of a flagged block counts as exposed. Cropland = ESA WorldCover class 40 (preliminary mask), hectares = 30 m pixels x 0.09.
| indicator | exposed_ha | exposed_pct_of_district_cropland | assessed_pct_of_district_cropland | blocks_flagged | blocks_assessed |
|---|---|---|---|---|---|
| Rainfall deficit | 22518.45 | 26.42 | 100.00 | 2 | 9 |
| Long dry spell | 0.00 | 0.00 | 100.00 | 0 | 9 |
| Heat anomaly | 85223.70 | 100.00 | 100.00 | 9 | 9 |
| Vegetation / moisture below usual | 0.00 | 0.00 | 0.00 | 0 | 0 |
| Rainfall deficit + vegetation stress | 0.00 | 0.00 | 0.00 | 0 | 0 |

## Sensitivity of ranking to weights
Rank 1 = highest stress. Columns: base weights, equal weights, drop-one-indicator, and summary over 1000 random weight sets.
| Block | base | equal | mc_rank_mean | mc_rank_min | mc_rank_max | mc_share_top3 |
|---|---|---|---|---|---|---|
| Radhapuram | 1.00 | 1.00 | 1.70 | 1.00 | 3.00 | 1.00 |
| Nanguneri | 2.00 | 2.00 | 1.76 | 1.00 | 4.00 | 0.99 |
| Manur | 3.00 | 3.00 | 3.58 | 2.00 | 6.00 | 0.60 |
| Palayamkottai | 4.00 | 4.00 | 4.00 | 3.00 | 5.00 | 0.02 |
| Pappakudi | 5.00 | 6.00 | 5.71 | 5.00 | 6.00 | 0.00 |
| Valliyoor | 6.00 | 7.00 | 6.55 | 5.00 | 7.00 | 0.00 |
| Kalakadu | 7.00 | 5.00 | 4.86 | 2.00 | 8.00 | 0.40 |
| Cheranmahadevi | 8.00 | 8.00 | 7.86 | 7.00 | 8.00 | 0.00 |
| Ambasamudram | 9.00 | 9.00 | 9.00 | 9.00 | 9.00 | 0.00 |

## Data-quality notes
- Indicators with no usable spatial contrast or no data for this season: ['temperature_stress']
- Blocks scored: 9 of 9
- Blocks with data per indicator: rainfall_stress=9, temperature_stress=0, vegetation_stress=9, moisture_stress=9
- HLS images per month (study area): target period 21 vs baseline average 177. WARNING: far fewer images in the target period than in the baseline; NDVI/NDMI anomalies may reflect composite sampling rather than crop condition. Investigate (00d_hls_diagnostic.py) before relying on them.
- Correlation of seasonal rainfall, GPM IMERG vs NASA POWER (all usable block-seasons): 0.93 (sanity check only)

## Limitations
- Min-max scaling is relative to the blocks and season analysed: a block can score 'Higher' even if absolute stress is mild.
- ACSI weights are design assumptions, not calibrated; see the sensitivity table before interpreting ranks.
- IMERG (~0.1 deg) and NASA POWER (coarse grid) cannot resolve differences inside small blocks; neighbouring blocks may share values.
- Cropland mask is a single-year (2021) ESA WorldCover map applied to all years.
- Low NDVI/NDMI can reflect harvest timing, fallow land or residual cloud, not only stress.
- Seasonal NDVI/NDMI is the mean of monthly median composites over valid months.
- Dry spells come from NASA POWER daily precipitation (~0.5 deg grid), not from IMERG directly; the dry-day threshold is an assumption.
- VCI uses the same-season baseline range (short HLS record), so extremes are poorly constrained.
- The HLS raw download may use the legacy mask without the water bit; see qc_report.txt.
- No crop-yield, irrigation or soil data are used; results do not by themselves indicate any adaptation action.