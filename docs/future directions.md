## 1. Strengthening causal claims (addressing the confound from §6)

- **Within-Manhattan comparison**: restrict the DS_z–volume correlation to Manhattan zones only. If the relationship survives, that's much stronger evidence it's the fee and not "being a dense Manhattan zone."
- **Regression with controls**: model volume change as a function of DS_z *plus* controls (avg base fare, avg trip distance, borough fixed effects). The residual DS_z coefficient after controlling for these is a cleaner estimate of the fee's marginal effect.
- **Synthetic control / matched zones**: pair each high-DS_z zone with a similar zone (by density, fare level, trip length) that's NOT in the CRZ, and compare their 2024→2025 trajectories. (This is the closest we can get to a counterfactual without a true natural experiment?)
- **Border discontinuity design**: zones that straddle the CRZ boundary are a near-natural experiment — same neighborhood, one side charged, one side not. Worth identifying if any TLC zones sit right at the boundary.
- **Event-study / monthly granularity**: right now DS_z and volume change are pooled across Feb–Jun. Breaking this into a month-by-month time series could show whether the effect is immediate (Jan 5 shock) and stable, or growing/fading over the five months. That shape itself is informative.

## 2. Extending what's measured

- **Driver-side effects**: this analysis is entirely rider/trip-side. `driver_pay` is already in our schema — did driver earnings change in high-DS_z zones? Did drivers reposition away from CRZ-heavy routes?
- **Substitution patterns**: are riders in high-DS_z zones shifting to yellow/green taxis (different fee structure), subway, or walking/biking instead of just disappearing? Would need to pull in TLC yellow/green taxi data and/or MTA ridership data for the same zones.
- **Trip-purpose proxies**: `shared_request_flag`/`shared_match_flag` are in our schema — did shared-ride usage change differently than solo rides in response to the fee? Shared rides might be more price-sensitive.
- **Time-of-day / day-of-week effects**: commute trips (price-inelastic, employer-paid in some cases) vs. discretionary evening/weekend trips (more elastic) might respond very differently to the same flat fee. `pickup_hour` and `day_of_week` are already in your schema.
- **Trip-length interaction**: does the fee burden effect compound or attenuate for longer trips that cross in/out of the CRZ multiple times, vs. short trips entirely within it?

## 3. Robustness and sensitivity

- **The $1 floor sensitivity check** already flagged as a to-do — rerun at $0.50 and $5.00, confirm DS_z rankings are stable.
- **Outlier-robust correlation**: Spearman rank correlation alongside Pearson, given a few extreme zones (154, 194) sit far from the trend line.
- **Bootstrap confidence intervals** on DS_z and the correlation coefficient, rather than point estimates alone — useful if this is heading toward a more formal write-up.
- **Placebo test**: compute "DS_z" and volume change for Feb–Jun 2023 vs. 2024 (both pre-policy) — if we see a spurious correlation even with no policy in effect, that's a red flag for the whole approach; if not, it strengthens confidence in the 2024-vs-2025 result.

## 4. Different cuts of the existing data

- **Borough-level rollup**: aggregate DS_z and volume change by borough rather than zone, for a higher-level summary that's easier to communicate to a non-technical audience.
- **Income/demographic overlay**: TLC zones can be joined to Census tract or ACS data — does fee burden correlate with neighborhood income, raising an equity question?
- **Airport corridors specifically**: JFK/LaGuardia/Newark are unique high-volume, scheduled-fare zones — worth a dedicated look since they behave very differently from the Manhattan core pattern.

## 5. Presentation / communication

- **Choropleth map** of DS_z or volume change across NYC zones (the chart skill's D3 module supports this with real TLC zone topology) — much more intuitive than a zone-ID table for a non-technical reader.
- **Interactive dashboard** combining the scatter, the map, and the quartile breakdown into one explorable artifact.
