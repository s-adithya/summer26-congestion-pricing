# Methodology Notes: NYC CBD Congestion Fee — HVFHV Disruption Analysis

**Last updated:** 2026-06-19
**Dataset:** NYC TLC High-Volume For-Hire Vehicle (HVFHV) trip records
**Comparison window:** Feb–Jun 2024 (pre-policy) vs. Feb–Jun 2025 (post-policy)
**Excluded:** January 2025 (policy transition month, ~20M rows/month, both years)

---

## 1. Policy background

On **January 5, 2025**, NYC's Central Business District (CBD) congestion pricing program went into effect. For HVFHV trips (e.g. Uber/Lyft), the relevant charge is:

> **$1.50 per trip to, from, or within the Congestion Relief Zone (CRZ)**, added on top of other FHV surcharges and taxes, billed to the HVFHV base/plate and passed to the rider.

This is distinct from two other, unrelated charges present in the same schema:
- `congestion_surcharge` — a legacy, pre-existing Manhattan congestion surcharge in effect since Feb 2019, **not** related to the 2025 CBD program.
- An earlier, separate 2024 CBD pricing plan that was paused by Gov. Hochul on June 5, 2024 before taking effect — **not** the policy this analysis measures. (Confirmed via web search; ruled out early in the project after initial date confusion — see §6.)

The fee actually analyzed here uses the **`cbd_congestion_fee`** column, confirmed present only in 2025 data, with `charged_cbd_flag = 1` indicating a trip was charged it.

## 2. Zone Disruption Score (DS_z) — final formula

For a given TLC zone *z*, computed separately for `PULocationID` (pickup) and `DOLocationID` (dropoff):

```
DS_z = (1 / N_z) * Σ [ cbd_congestion_fee_i / (passenger_cost_pretip_i - cbd_congestion_fee_i) ]
```

i.e. **fee as a proportion of the base cost the rider would have paid without the CBD fee** — not as a proportion of total cost, and not as a proportion of `base_passenger_fare` alone. See §3 for why each alternative was rejected.

**Confirmed cost identity** (per data dictionary, HVFHV):
```
passenger_cost_pretip = base_passenger_fare + tolls + bcf + sales_tax
                       + congestion_surcharge + airport_fee + cbd_congestion_fee
```

So `passenger_cost_pretip - cbd_congestion_fee` correctly retains tolls, BCF, sales tax, the legacy congestion surcharge, and airport fees in the denominator — every cost component the rider would have paid *regardless* of the CBD policy — and nets out only the one fee under study.

### Filters applied to the trip-level data before aggregating:**

```sql
WHERE charged_cbd_flag = 1
  AND ROUND(passenger_cost_pretip - cbd_congestion_fee, 2) >= 1.00
```

- `charged_cbd_flag = 1`: per project decision, DS_z is computed **only over trips that were actually charged the fee** (not all trips, with non-charged trips contributing 0). This means DS_z answers "among trips that paid the fee, how burdensome was it relative to zone," not "what fraction of all zone trips were burdened."
- `ROUND(..., 2) >= 1.00`: a $1 floor on the base cost, applied **after rounding to the cent**. See §4 for why the rounding step is essential, not cosmetic.

### Scope: pooled, not monthly

DS_z is computed as a **single pooled value per zone per direction across all of Feb–Jun 2025** (not month-by-month). This was a deliberate scope decision — a monthly time series within 2025 was considered but not built, since the primary research question is cross-zone comparison, not within-2025 trend.

## 3. Why earlier formula candidates were rejected

Three other denominators were tested/considered during development and explicitly rejected:

| Candidate denominator | Why rejected |
|---|---|
| `base_passenger_fare` alone | Excludes tolls, BCF, sales tax, airport fee, and legacy congestion surcharge — average gap vs. correct denominator was **$8.65/trip**, confirmed by direct query. Was mistakenly used in an intermediate script version; caught via a trip-level audit (§5) before being used for any real output. |
| `passenger_cost_pretip` (full total cost, not netting out the fee) | This is what the pre-existing `relative_cbd_burden` column in the source data measures. It's a *different and also legitimate* metric ("fee as % of total cost paid") but answers a different question than the DS_z spec ("fee as % of cost *without* this fee"). Kept in source data as a secondary reference column, not used as DS_z. |
| Unfloored `passenger_cost_pretip - cbd_congestion_fee` | Technically matches the spec, but a small number of trips have this denominator equal to floating-point noise (~1e-16) instead of true zero, due to summing 6 double-precision columns that cancel to zero. This produces fee_burden ratios in the **billions**, which silently dominate a naive `AVG()`. See §4. |

## 4. Critical bug: floating-point cancellation in the denominator

**Symptom:** Initial DS_z results showed means in the range of 10^9–10^11 for several zones, while the median for the same zones was a sane ~0.03–0.06.

**Root cause:** For a small number of trips, every cost component except `cbd_congestion_fee` is exactly zero (e.g. a fully comped/free ride that was still charged the regulatory CBD fee). The true `base_cost` for these trips is `0`. But because `passenger_cost_pretip` is computed upstream as a sum of 6 double-precision floats, the result is not exactly `1.5` but `1.5000000000000009` — so `base_cost = passenger_cost_pretip - cbd_congestion_fee` evaluates to `8.88e-16` instead of `0`. Dividing `1.5 / 8.88e-16` produces a ratio around `1.69e15`, and a single such row is enough to dominate a zone's average across hundreds of thousands of legitimate trips.

**Diagnosis process:**
1. Compared `DS_z` (mean) vs `DS_z_median` per zone — large divergence flagged the issue.
2. Pulled the top 20 trips by `fee_burden DESC` directly — all had `base_cost ≈ 8.88e-16`, immediately visible as floating-point noise rather than a real small fare.
3. Quantified scope: of 34,717,550 fee-charged trips, only **19** had a true zero/negative base cost (after rounding) and **89** had a genuinely small-but-real base cost under $1. Combined, 108 rows out of 34.7M (0.0003%).

**Fix:**
```sql
ROUND(passenger_cost_pretip - cbd_congestion_fee, 2) >= 1.00
```
Rounding to the cent before filtering collapses floating-point noise to a true `0.00`, which the `>= 1.00` floor then correctly excludes. The same floor also excludes the 89 genuinely-sub-$1 trips — a separate, deliberate judgment call (not a bug fix) to avoid a tiny number of extreme-but-real ratios (e.g. $1.50 fee on a $0.50 ride) from disproportionately swinging a zone average. **This $1 threshold is a judgment call, not a principled cutoff** — a sensitivity check (rerunning at $0.50 and $5.00 floors, confirming zone *rankings* stay stable) is recommended before treating DS_z rankings as robust, but was not yet performed as of this writing.

**Post-fix validation:** Re-ran top-20 zones by DS_z; mean and median are now in the same range throughout (0.054–0.064), confirming the fix resolved the issue without introducing new distortions.

## 5. Audit method: pre-existing column vs. recomputation

The cleaned dataset already contained a column `relative_cbd_burden`, separately defined (per data dictionary) as:
```
relative_cbd_burden = cbd_congestion_fee / passenger_cost_pretip
```
This was used as an independent cross-check, not as the DS_z metric itself (see §3 for why it's a different quantity). Two checks were run:

1. **Trip-level mismatch audit**: compared `relative_cbd_burden` against a from-scratch recalculation for 34.7M trips. Found 99.6% of rows differed by >0.001 — initially alarming, fully explained once the denominator difference (full cost vs. cost-minus-fee) was identified. Not a data quality issue; two different, both-valid metrics.
2. **Monotonicity check** (post floating-point fix): confirmed that for every trip, `recomputed_fee_burden >= relative_cbd_burden` (since the DS_z denominator is always ≤ the `relative_cbd_burden` denominator). Result: **0 violations** across all qualifying trips — strong internal-consistency confirmation that both formulas are being computed correctly relative to each other, even though they answer different questions.

**Recommendation:** Keep `relative_cbd_burden` (or its zone-aggregated mean) as a secondary reported metric alongside DS_z in any final output — "fee as % of total cost" may be more intuitive to a general audience than "fee as % of base cost," even though DS_z (the latter) is the metric specified for this project.

## 6. Layer B: behavioral shift (2024 vs 2025)

Separate from DS_z, Layer B measures whether trip **volume** and **average fare** changed year-over-year by zone, using:
- `n_trips`: count of trips per zone per direction per year (no fee-related filtering — includes all trips, not just CRZ-charged ones)
- `avg_total_cost`: `AVG(passenger_cost_pretip)` — what riders actually paid, all-in
- `avg_base_fare`: `AVG(base_passenger_fare)` — underlying ride cost, independent of any fee/surcharge

Both fare metrics are reported as separate columns (not collapsed into one "avg fare") per project decision, since they answer different questions: total cost captures the full rider experience including the fee; base fare isolates whether *underlying pricing* (not just the flat fee) shifted.

**Low-N handling:** Zones with fewer than 100 trips in either year are flagged via `low_n_flag` rather than dropped, since a zone with near-zero 2024 volume that grew substantially in 2025 (or vice versa) is a potentially meaningful "activation" signal that a hard volume cutoff would hide. `pct_volume_change` is left as `NULL` (rather than artificially set to 0 or infinity) when `n_2024 = 0`, since the percent change is genuinely undefined in that case — as of this writing, only 2 zone×direction combinations fall into this category.

**Caveat on `avg_base_fare` interpretation:** this query does not filter on `charged_cbd_flag`, so a zone's `avg_base_fare` change reflects *all* trips in that zone (CRZ-charged and not), not isolated CRZ-trip pricing behavior. A narrower "did base pricing shift specifically for CRZ-charged trips" analysis would require a different 2024 comparison group, since `charged_cbd_flag` does not exist pre-2025 (would need geographic CRZ-membership matching instead). Not yet built — flagged as a possible follow-up.

## 7. Early-stage corrections (for project history / transparency)

- **Date range confusion**: initial framing referenced "Feb–Jun 2024" as if it straddled the congestion pricing policy. study design is that of a year-over-year Feb–Jun 2024 vs. Feb–Jun 2025 comparison, with Jan 2025 excluded as a transition month.
- **Column confusion**: `congestion_surcharge` (legacy, since 2019) vs. `cbd_congestion_fee` (new, 2025 CBD policy) are separate columns in the same schema and are easy to conflate. DS_z must use `cbd_congestion_fee` only.

## 8. Open items / possible next steps

- [ ] Sensitivity check on the $1 base-cost floor (try $0.50 and $5.00, confirm zone DS_z *rankings* are stable)
- [ ] Formal correlation between DS_z and `pct_volume_change` across all zones (not just eyeballing top-20 overlap)
- [ ] Identify the 2 zones with `pct_volume_change IS NULL` (zero 2024 baseline) by name
- [ ] Consider CRZ-flag-isolated version of Layer B (trips actually charged the fee, 2025-only, compared against geographically-matched 2024 trips)
- [ ] Join `taxi_zone_lookup.csv` (LocationID → Borough/Zone/service_zone) onto both `ds_z` and `behavioral_shift` outputs for final tables
