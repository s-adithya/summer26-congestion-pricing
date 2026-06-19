**NYC HVFHV CBD Congestion Fee: Zone Disruption Analysis**

*Methodology, results, and conclusions --- Feb--Jun 2024 vs. Feb--Jun
2025*

*High-Volume For-Hire Vehicle (HVFHV) trip records, NYC Taxi & Limousine
Commission*

Executive summary

On January 5, 2025, NYC\'s Central Business District (CBD) congestion
pricing program introduced a \$1.50 per-trip fee on High-Volume For-Hire
Vehicle (HVFHV) trips to, from, or within the Congestion Relief Zone
(CRZ). This analysis quantifies the fee\'s relative burden across NYC
TLC zones and tests whether that burden is associated with changes in
trip volume.

Two metrics were developed:

-   Zone Disruption Score (DSₐ) --- the CBD fee as a proportion of the
    base trip cost, averaged per zone, computed separately for pickup
    and dropoff directions, using only fee-charged trips in Feb--Jun
    2025.

-   Behavioral shift metrics --- trip volume and average fare per zone,
    compared year-over-year (Feb--Jun 2024 vs. Feb--Jun 2025).

Key finding: zones with a higher Zone Disruption Score saw significantly
larger declines in trip volume. The correlation between DSₐ and
year-over-year volume change is −0.61 (Pearson r, n=519 zone×direction
pairs), and the relationship is monotonic across DSₐ quartiles --- not
driven by a handful of outliers. Zones in the lowest fee-burden quartile
grew volume by \~4--5% on average; zones in the highest fee-burden
quartile shrank by \~5%. The zones bearing the highest relative fee
burden are concentrated in Manhattan\'s historic Yellow Zone core (East
Village, West Village, Greenwich Village, Gramercy, Stuy Town,
Chinatown), and these are largely the same zones exhibiting the steepest
volume declines.

*This relationship is correlational, not causal. High-DSₐ zones share
other characteristics --- dense, low-base-fare, short-trip Manhattan
neighborhoods --- that could independently affect 2024→2025 ridership
trends. See §6 (Limitations) for a full discussion.*

1\. Background and research design

1.1 Policy context

NYC\'s CBD congestion pricing program took effect January 5, 2025. For
HVFHV trips (e.g., Uber, Lyft), the policy adds a \$1.50 fee per trip
to, from, or within the CRZ, on top of existing FHV surcharges and
taxes, billed to the HVFHV base/plate and passed to the rider.

This is distinct from two other charges present in the same data: the
legacy congestion_surcharge (a separate Manhattan-area charge in effect
since February 2019) and an earlier, unrelated 2024 CBD pricing proposal
that was paused before taking effect. Both were identified and ruled out
early in this project to avoid conflating them with the policy under
study.

1.2 Study design

The analysis compares the same five months across two years:

-   Pre-policy baseline: February--June 2024 (no CBD fee in effect)

-   Post-policy period: February--June 2025 (CBD fee in effect
    throughout)

-   Excluded: January 2025, treated as a policy transition month

This year-over-year, same-months design controls for seasonality (e.g.,
weather, tourism patterns) that a simple before/after-within-2025
comparison would not.

1.3 Data

HVFHV trip records, NYC TLC, approximately 20 million rows per month, 10
months total (\~100M+ rows for 2025 alone). Each month supplied as a
separate cleaned parquet file.

2\. Zone Disruption Score (DSₐ) --- definition and derivation

2.1 Final formula

For a given TLC zone z, computed separately for PULocationID (pickup)
and DOLocationID (dropoff):

DSₐ = (1/Nₐ) × Σ \[ cbd_congestion_feeᵢ / (passenger_cost_pretipᵢ −
cbd_congestion_feeᵢ) \]

i.e., the CBD fee as a proportion of the base cost the rider would have
paid without the fee --- not as a proportion of total cost, and not as a
proportion of base_passenger_fare alone (see §2.3 for why each
alternative was rejected).

2.2 Confirmed cost identity

Per the project\'s data dictionary, for HVFHV trips:

passenger_cost_pretip = base_passenger_fare + tolls + bcf + sales_tax +
congestion_surcharge + airport_fee + cbd_congestion_fee

This confirms that passenger_cost_pretip − cbd_congestion_fee retains
every other cost component (tolls, Black Car Fund surcharge, sales tax,
the legacy congestion surcharge, and airport fees) in the denominator
--- i.e., every cost the rider would have paid regardless of the CBD
policy --- and nets out only the fee under study.

2.3 Why alternative denominators were rejected

  ------------------------ ----------------------------------------------------
  **Candidate              **Why rejected**
  denominator**            

  base_passenger_fare      Excludes tolls, BCF, sales tax, airport fee, and
  alone                    legacy congestion surcharge. Average gap vs. the
                           correct denominator was \$8.65/trip, confirmed by
                           direct query. Briefly and mistakenly used in an
                           intermediate script version; caught via trip-level
                           audit before producing any reported output.

  passenger_cost_pretip    This is what the dataset\'s pre-existing
  (full total, not netting relative_cbd_burden column measures --- "fee as % of
  out the fee)             total cost," a different and also legitimate metric,
                           but not the one specified for DSₐ ("fee as % of cost
                           without this fee"). Retained as a secondary
                           reference metric, not used as DSₐ.

  Unfloored                Technically matches the spec, but a small number of
  (passenger_cost_pretip − trips have this denominator equal to floating-point
  cbd_congestion_fee)      noise (\~1e-16) instead of true zero, due to summing
                           six double-precision columns that should cancel
                           exactly to zero. This produced fee_burden ratios in
                           the billions for a handful of trips, which silently
                           dominated a naive AVG(). See §2.4.
  ------------------------ ----------------------------------------------------

2.4 Data quality issue: floating-point cancellation

Initial DSₐ results showed zone-level means in the range of 10⁹--10¹¹,
while the median for the same zones was a sane \~0.03--0.06. Diagnosis
traced this to trips where every cost component except
cbd_congestion_fee was exactly zero (e.g., a fully comped ride still
charged the regulatory CBD fee). The true base cost for these trips is
\$0, but because passenger_cost_pretip is computed upstream as a sum of
six double-precision floats, the result was not exactly 1.5 but
1.5000000000000009 --- so the computed base cost evaluated to
\~8.88×10⁻¹⁶ instead of 0. Dividing the \$1.50 fee by this near-zero
value produced ratios around 1.7×10¹⁵ for a single trip, enough to
dominate a zone\'s average across hundreds of thousands of legitimate
trips.

Of 34,717,550 fee-charged trips, only 19 had a true zero/negative base
cost (after rounding to the cent) and 89 had a genuinely small-but-real
base cost under \$1 --- 108 rows total, 0.0003% of fee-charged trips.

Fix applied: ROUND(passenger_cost_pretip − cbd_congestion_fee, 2) \>=
1.00. Rounding to the cent collapses floating-point noise to a true 0.00
before the floor is applied. The \$1 floor is a deliberate judgment call
(not purely a bug fix) to exclude a small number of extreme-but-real
ratios from disproportionately swinging a zone average; it is not a
principled threshold, and a sensitivity check at \$0.50 / \$5.00 floors
is recommended as a follow-up (see §7).

2.5 Internal consistency check

The pre-existing relative_cbd_burden column (= fee / total cost) was
used as an independent cross-check rather than as the DSₐ metric itself.
Two validations were run:

-   Trip-level comparison across 34.7M trips: 99.6% of rows initially
    appeared to mismatch the from-scratch recalculation by more than
    \$0.001 --- fully explained once the denominator difference (total
    cost vs. cost-minus-fee) was identified, not a data quality issue.

-   Monotonicity check (post floating-point fix): for every qualifying
    trip, recomputed fee_burden ≥ relative_cbd_burden, since the DSₐ
    denominator is always ≤ the relative_cbd_burden denominator. Result:
    0 violations across all qualifying trips.

3\. Layer A results: Zone Disruption Score

DSₐ was computed for 519 zone×direction pairs (pooled across Feb--Jun
2025, filtered to fee-charged trips with base cost ≥ \$1.00). Mean and
median converge across zones after the floating-point fix, confirming
the metric is stable.

3.1 Highest-burden zones

  ----------------- ----------------- ----------------- -----------------
  **Zone**          **Borough**       **Direction**     **DSₐ**

  East Village      Manhattan         Dropoff           6.4%

  Stuy Town / Peter Manhattan         Dropoff           6.3%
  Cooper Village                                        

  Greenwich Village Manhattan         Dropoff           6.1%
  North                                                 

  Kips Bay          Manhattan         Dropoff           6.2%

  Gramercy          Manhattan         Dropoff           6.1%

  Chinatown         Manhattan         Dropoff           6.0%

  Lower East Side   Manhattan         Dropoff           5.9%
  ----------------- ----------------- ----------------- -----------------

Every zone in the top 20 by DSₐ is a Manhattan "Yellow Zone" --- the
dense, historic core service area. This is consistent with the metric\'s
construction: short, low-base-fare trips bear a proportionally larger
burden from the flat \$1.50 fee than longer, higher-fare trips. Dropoffs
dominate the top of the ranking over pickups, suggesting trips ending in
these dense core neighborhoods skew shorter/cheaper than trips starting
there.

4\. Layer B results: behavioral shift, 2024 vs. 2025

Trip volume and average fare (total cost and base fare, reported
separately) were compared year-over-year per zone and direction. Zones
with fewer than 100 trips in either year are flagged rather than
dropped, so 2024→2025 activation effects (near-zero baseline volume)
remain visible rather than being silently excluded.

4.1 Largest volume declines (excluding low-N zones)

  -------------- --------------- -------------- -------------- --------------
  **Zone**       **Direction**   **2024 trips** **2025 trips** **Change**

  Zone 154       Dropoff         16,005         11,287         −29.5%
  (Marine                                                      
  Park/Floyd                                                   
  Bennett Field)                                               

  East Village   Dropoff         1,119,252      990,843        −11.5%

  East Village   Pickup          1,367,384      1,211,105      −11.4%

  Stuy           Dropoff         187,122        163,517        −12.6%
  Town/Peter                                                   
  Cooper Village                                               

  Stuy           Pickup          230,755        201,803        −12.5%
  Town/Peter                                                   
  Cooper Village                                               

  Alphabet City  Dropoff         271,542        242,158        −10.8%
  -------------- --------------- -------------- -------------- --------------

The same Manhattan core zones carrying the highest fee burden (§3) are
also among the zones with the largest volume declines --- East Village
and Stuy Town/Peter Cooper Village appear prominently in both rankings.
Average total trip cost rose 10--13% in these declining zones, outpacing
the \~8--9% rise in average base fare, consistent with a flat per-trip
fee adding a fixed amount on top of fares that changed comparatively
little.

4.2 Largest volume increases

Growth was concentrated in outer-borough, non-CRZ zones --- Astoria
Park, Far Rockaway, Cambria Heights, Charleston/Tottenville, Glen Oaks
--- consistent with either organic ridership growth unrelated to the
policy, or a substitution effect away from CRZ-adjacent demand. The data
does not distinguish between these explanations.

4.3 Zero-baseline (activation) zones

Two zone×direction combinations had zero HVFHV trips in the Feb--Jun
2024 baseline and nonzero activity in 2025, out of approximately 520
possible combinations. This population is too small to analyze as a
trend; it is noted here for completeness rather than treated as a
finding.

5\. Combined finding: DSₐ vs. volume change

5.1 Correlation

Joining DSₐ (Layer A) to behavioral shift (Layer B) on zone × direction
(n = 519 pairs, low-N zones excluded) yields:

  ----------------------- ----------------------- -----------------------
  **Metric**              **Value**               **Interpretation**

  Pearson r (overall)     −0.610                  Moderately strong
                                                  negative linear
                                                  relationship

  Pearson r (pickup only) −0.610                  Nearly identical to
                                                  overall --- directional
                                                  symmetry

  Pearson r (dropoff      −0.611                  Nearly identical to
  only)                                           overall --- directional
                                                  symmetry
  ----------------------- ----------------------- -----------------------

5.2 Quartile breakdown

Zones were split into DSₐ quartiles within each direction; average
volume change was computed per quartile. This view is more robust to
outlier zones than a single Pearson coefficient and confirms the
relationship is monotonic, not driven by a few extreme points.

  ----------------- ----------------- ----------------- -----------------
  **Direction**     **DSₐ quartile**  **Avg. DSₐ**      **Avg. volume
                                                        change**

  Dropoff           1 (lowest burden) 1.8%              +4.4%

  Dropoff           2                 2.6%              +3.1%

  Dropoff           3                 3.6%              +1.2%

  Dropoff           4 (highest        5.3%              −5.3%
                    burden)                             

  Pickup            1 (lowest burden) 1.8%              +4.6%

  Pickup            2                 2.5%              +4.5%

  Pickup            3                 3.5%              +1.1%

  Pickup            4 (highest        5.0%              −4.8%
                    burden)                             
  ----------------- ----------------- ----------------- -----------------

Zones in the lowest fee-burden quartile grew volume by roughly 4--5%;
zones in the highest fee-burden quartile shrank by roughly 5%, in both
directions --- nearly a mirror image, with a steady step pattern between
quartiles rather than a jump driven by one extreme bucket.

6\. Limitations and caveats

-   Correlational, not causal. High-DSₐ zones are disproportionately
    dense, low-base-fare Manhattan core neighborhoods. These zones may
    have experienced other changes between 2024 and 2025 --- broader
    CBD-program effects on traffic generally, subway/bike-share
    competition, post-pandemic ridership normalization --- that also
    suppress HVFHV volume independent of the \$1.50 fee itself.

-   Shared confounder risk. DSₐ and pct_volume_change are not derived
    from the same underlying trips (DSₐ uses 2025 CRZ-charged trips
    only; volume change uses all trips in both years), so the
    correlation is not mechanically tautological --- but both metrics
    share "low base fare / dense Manhattan zone" as a likely common
    driver, which would produce a relationship like this even before
    considering any genuine rider behavior change.

-   The \$1 base-cost floor (§2.4) is a judgment call. A sensitivity
    check across alternate floors (\$0.50, \$5.00) to confirm DSₐ zone
    rankings are stable has not yet been performed.

-   Layer B\'s avg_base_fare is not isolated to CRZ-charged trips --- it
    reflects all trips in a zone, so a zone\'s base-fare change partly
    reflects its mix of CRZ and non-CRZ trips, not pricing behavior
    specifically on fee-charged trips.

-   Two zone×direction pairs with zero 2024 baseline volume were
    excluded from the correlation and quartile analysis
    (pct_volume_change undefined); not separately investigated given the
    small count.

7\. Suggested next steps

-   Sensitivity check on the \$1 base-cost floor: rerun at \$0.50 and
    \$5.00, confirm DSₐ zone rankings remain stable.

-   Address the Manhattan confound directly: restrict the correlation
    analysis to within-Manhattan zones only, to test whether the DSₐ --
    volume relationship holds when borough/density is held roughly
    constant.

-   Build a CRZ-isolated version of Layer B: compare base-fare changes
    specifically for trips charged the fee in 2025 against a
    geographically matched 2024 comparison group (since charged_cbd_flag
    does not exist pre-2025).

-   Identify the two zero-baseline activation zones by name and assess
    whether they are CRZ-adjacent (a notable activation story) or simply
    low-coverage areas (a footnote).

-   Consider a partial-correlation or regression-based control for
    average base fare or trip distance, to separate the fee-burden
    effect from the "dense short-trip zone" confound described in §6.

Appendix A: Pipeline summary

The full analysis was implemented in DuckDB (Python), querying parquet
files directly without loading into pandas, to handle \~100M+ rows
across 10 monthly files within memory constraints. Three scripts
(provided separately): (1) the core DuckDB pipeline computing DSₐ and
behavioral shift metrics with all data-quality filters and diagnostic
checks; (2) a zone-name lookup merge using the official NYC TLC
taxi_zone_lookup.csv; (3) a standalone HTML/Chart.js scatter chart
generator visualizing DSₐ against volume change.
