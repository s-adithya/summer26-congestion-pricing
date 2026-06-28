**Inference Validity and Constructed Leakage**

*A sanity-check section on what relationships in this analysis are
genuinely discovered v/s structurally guaranteed by construction.*

*NYC HVFHV CBD Congestion Fee Analysis*

# Overview

In traditional machine learning, feature leakage refers to training data
containing information about the future or the target label that would
not be available at prediction time. That definition does not cleanly
apply to a descriptive inference problem like ours as we are not
building a prediction system, and there is no train/test split in the
conventional sense.

However, there is an analogous concern that is equally important for
inference: **manufactured correlation**. If two metrics appear to be
correlated, but their mathematical construction guarantees that
correlation regardless of any real-world relationship, then we have
discovered nothing, as we have merely confirmed an algebraic identity.
The question this section addresses is the following:

**Which relationships in this analysis are genuinely discovered from the
data, and which are structurally guaranteed by how the metrics were
defined?**

We identify three distinct concerns, each requiring a different
response.

# Concern 1 : Circular construction between DSₐ and volume change

## The risk

If DSₐ (Zone Disruption Score) and pct_volume_change were derived from
the same underlying formula or the same set of trips, their correlation
would be algebraically guaranteed. Finding r = −0.61 between them would
not be a discovery; it would be an artifact of definition.

## Why this concern does not apply here

DSₐ and pct_volume_change are computed from genuinely separate data:

  ------------------ -------------------------- --------------------------
                     **DSₐ**                    **pct_volume_change**

  Source trips       2025 fee-charged trips     All trips, both years (no
                     only (charged_cbd_flag =   fee filter)
                     1)                         

  What is measured   Average ratio: fee /       Count ratio: n_2025 /
                     (total cost − fee)         n_2024 − 1

  Years used         2025 only                  2024 and 2025

  Mathematical form  Arithmetic mean of a       Ratio of two aggregate
                     per-trip ratio             counts
  ------------------ -------------------------- --------------------------

Different populations (fee-charged vs. all trips), different years,
different mathematical operations. A zone with high DSₐ is not, by
construction, guaranteed to have a negative pct_volume_change. The
correlation between them is a real empirical finding.

# Concern 2 --- Endogeneity between DSₐ and volume change

## The risk

This is the subtlest concern. DSₐ is computed from 2025 trips. The
volume of 2025 trips is partly what pct_volume_change measures. If the
policy caused some zones to lose trips, the remaining 2025 trips in
those zones might be systematically different from the full pre-policy
trip population --- which means DSₐ was computed on a self-selected
sample of trips, shaped partly by the outcome we are trying to explain.

Concretely: if high-fee trips were disproportionately abandoned by
riders after January 5, then the 2025 fee-charged trips that survive
into the DSₐ calculation are a selected sample --- biased toward trips
where riders accepted the fee burden. This would tend to compress DSₐ
downward in zones where the policy had the most bite, attenuating the
observed correlation.

## Direction of the bias

If this endogeneity exists, it biases the DSₐ -- volume correlation
toward zero (attenuation bias), not away from zero. The true
relationship, if the policy caused trip abandonment, is likely stronger
than r = −0.61, not weaker. Our reported correlation is therefore a
conservative estimate of the association, not an inflated one.

## Why we cannot fully resolve this

Resolving this rigorously would require a counterfactual: the DSₐ that
would have been observed had the policy not changed trip volumes. This
is not computable from the available data. We note it here as a known
limitation rather than a solved problem.

# Concern 3 --- Feature contamination in downstream models

## The risk

If DSₐ is used as a predictor (e.g., in a classification or regression
model predicting disruption), including post-policy variables as
covariates alongside it would manufacture a false sense of explanatory
power. Post-policy variables (average fare in 2025, trip count in 2025,
base fare in 2025) are consequences of the same policy shock as DSₐ
itself. Including them as independent predictors of an outcome that is
also driven by the policy creates circular reasoning: we would be
explaining the policy\'s effects using other effects of the same policy.

## The rule

The cleanest operational statement of this constraint is:

**Pre-policy variables (any feature computed from Feb--Jun 2024 data)
are valid predictors. Post-policy variables (any feature computed from
Feb--Jun 2025 data) are not, unless they are the outcome being
predicted.**

This distinction cleanly separates cause from consequence. The 2024 base
fare reflects what a zone\'s rides inherently cost, independent of the
congestion fee. The 2025 base fare reflects both what rides inherently
cost and how the market responded to the policy. Therefore, the 2025
base fare is partly an outcome, not purely a predictor.

## Feature classification

  --------------------- ------------- ------------------------------------
  **Feature**           **Status**    **Reason**

  n_2024                ✅ Safe       Pre-policy baseline trip volume;
                                      does not encode any 2025 outcome

  avg_total_cost_2024   ✅ Safe       Pre-policy baseline fare;
                                      independent of CBD fee

  avg_base_fare_2024    ✅ Safe       Pre-policy baseline base fare;
                                      independent of CBD fee

  DS_z                  ⚠️ Use with   2025 metric; valid as primary cause
                        care          variable, but cannot be combined
                                      with other 2025 covariates in the
                                      same model (Concern 2)

  DS_z_median           ⚠️ Use with   Near-duplicate of DS_z; including
                        care          both inflates apparent explanatory
                                      power without adding independent
                                      information

  relative_cbd_burden   ⚠️ Redundant  Mathematical near-duplicate of DS_z
                                      (same numerator, slightly larger
                                      denominator); not an independent
                                      feature

  avg_total_cost_2025   ❌            Encodes 2025 outcome; using as a
                        Post-policy   predictor of 2025 disruption is
                                      circular

  avg_base_fare_2025    ❌            Same reason; the 2025 base fare may
                        Post-policy   itself have shifted in response to
                                      the policy

  n_2025                ❌            Directly determines
                        Post-policy   pct_volume_change; using as a
                                      predictor of volume-based disruption
                                      is tautological

  pct_volume_change     ❌ Outcome    This is the target variable in a
                                      behavioral model; cannot
                                      simultaneously be a predictor
  --------------------- ------------- ------------------------------------

# Causal logic summary

The intended causal chain in this analysis is:

CBD policy → cbd_congestion_fee charged per trip → higher relative fare
burden (DSₐ) → rider response → volume decline (pct_volume_change)

Within this chain:

-   DSₐ is the relative burden measure, and it quantifies the size of
    the policy shock as experienced by riders in each zone.

-   pct_volume_change is the behavioral response, and it measures
    whether riders changed their behavior in response.

-   Variables to the left of DSₐ in the chain (the fee itself, the
    policy) are causes. Variables to the right (volume, 2025 fares) are
    consequences.

-   Pre-policy zone characteristics (2024 fare levels, 2024 trip volume)
    are exogenous baseline controls. They describe what a zone was like
    before any treatment, and are safe to use as covariates.

*Including any post-policy variable other than the primary outcome as a
covariate risks controlling away part of the policy effect itself, since
post-policy variables may be mediators (part of the causal path) rather
than confounders (alternative explanations). This is a common and
often-missed form of over-controlling in policy evaluation.*

# Summary: what this analysis claims and does not claim

  ----------------------------------- -----------------------------------
  **What we claim**                   **What we do not claim**

  DSₐ and pct_volume_change are       That the correlation is causal.
  genuinely independent metrics whose High-DSₐ zones share other
  correlation is empirically          characteristics (density, short
  discovered, not algebraically       trips, Manhattan location) that
  guaranteed.                         could independently explain volume
                                      decline.

  The observed r = −0.61 is a         That DSₐ is a clean, uncontaminated
  conservative estimate; endogeneity  measure of policy shock. It was
  from trip self-selection would      computed on the 2025 trips that
  attenuate, not inflate, the true    survived into the post-policy
  association.                        period, not the counterfactual
                                      pre-policy population.

  Pre-policy zone characteristics     That post-policy variables (2025
  (2024 fare, 2024 volume) are valid  fare, 2025 volume, N_z) can be used
  covariates for any downstream       as independent predictors alongside
  model.                              DSₐ in a causal model.
  ----------------------------------- -----------------------------------
