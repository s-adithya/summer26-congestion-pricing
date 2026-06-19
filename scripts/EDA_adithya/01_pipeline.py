"""
NYC HVFHV CBD Congestion Fee — Zone Disruption Score (DS_z) Pipeline
======================================================================
Full analysis pipeline: data loading, validation, DS_z computation (Layer A),
behavioral shift analysis (Layer B), and export.

Requires: duckdb (pip install duckdb)
Input: monthly HVFHV parquet files for Feb-Jun 2024 and Feb-Jun 2025
Output: ds_z.parquet, behavioral_shift.parquet, ds_z_vs_volume_change.csv

Run sections top to bottom. Diagnostic sections print output for manual
inspection before downstream steps depend on them.
"""

import duckdb

con = duckdb.connect()

# ============================================================
# STEP 0: Load data
# ============================================================
FILES_2024 = "data/2024-*.parquet"   # Feb-Jun 2024 (pre-policy)
FILES_2025 = "data/2025-*.parquet"   # Feb-Jun 2025 (post-policy), Jan 2025 excluded

con.sql(f"CREATE VIEW trips_2024 AS SELECT *, 2024 AS yr FROM read_parquet('{FILES_2024}')")
con.sql(f"CREATE VIEW trips_2025 AS SELECT *, 2025 AS yr FROM read_parquet('{FILES_2025}')")


# ============================================================
# STEP 1: Schema check
# ============================================================
print(con.sql("DESCRIBE trips_2025"))


# ============================================================
# STEP 2: Fee-charged vs non-charged trip comparison
# (sanity check before computing DS_z)
# ============================================================
print(con.sql("""
    SELECT
        CASE WHEN cbd_congestion_fee > 0 THEN 'fee_charged' ELSE 'no_fee' END AS grp,
        COUNT(*) AS n,
        AVG(passenger_cost_pretip) AS avg_pretip,
        AVG(trip_distance_miles) AS avg_miles
    FROM trips_2025
    GROUP BY grp
"""))


# ============================================================
# STEP 3: Denominator data-quality check
# ============================================================
print(con.sql("""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN cbd_congestion_fee > 0 THEN 1 ELSE 0 END) AS fee_trips,
        SUM(CASE WHEN cbd_congestion_fee > 0
                 AND (passenger_cost_pretip - cbd_congestion_fee) <= 0
            THEN 1 ELSE 0 END) AS excluded_bad_denominator
    FROM trips_2025
"""))


# ============================================================
# STEP 3.5: Floating-point cancellation check
# ------------------------------------------------------------
# A small number of trips have every cost component except
# cbd_congestion_fee equal to exactly zero. Because passenger_cost_pretip
# is a sum of 6 double-precision columns, these trips don't cancel to an
# exact 0.0 -- they land at ~1e-16 due to floating point error, which
# blows up to a billions-scale ratio if used as a divisor unrounded.
# This step quantifies the affected population before any DS_z is computed.
# ============================================================
print(con.sql("""
    SELECT
        COUNT(*) AS total_fee_trips,
        SUM(CASE WHEN ROUND(passenger_cost_pretip - cbd_congestion_fee, 2) <= 0
            THEN 1 ELSE 0 END) AS true_zero_or_negative_base,
        SUM(CASE WHEN ROUND(passenger_cost_pretip - cbd_congestion_fee, 2)
                 BETWEEN 0.01 AND 0.99
            THEN 1 ELSE 0 END) AS genuinely_under_1_dollar
    FROM trips_2025
    WHERE charged_cbd_flag = 1
      AND (passenger_cost_pretip - cbd_congestion_fee) > 0
"""))


# ============================================================
# STEP 4: Layer A — DS_z (Zone Disruption Score)
# ------------------------------------------------------------
# DS_z = mean( cbd_congestion_fee / (passenger_cost_pretip - cbd_congestion_fee) )
# computed per zone, separately for PULocationID (pickup) and
# DOLocationID (dropoff), pooled across Feb-Jun 2025.
#
# Filters:
#   - charged_cbd_flag = 1            -> only trips that paid the fee
#   - ROUND(base_cost, 2) >= 1.00     -> excludes floating-point-zero
#                                         artifacts AND genuinely-sub-$1
#                                         trips (judgment call, see notes)
# ============================================================
con.sql("""
    CREATE OR REPLACE TABLE ds_z AS
    WITH cleaned AS (
        SELECT
            PULocationID,
            DOLocationID,
            cbd_congestion_fee,
            ROUND(passenger_cost_pretip - cbd_congestion_fee, 2) AS base_cost,
            cbd_congestion_fee / ROUND(passenger_cost_pretip - cbd_congestion_fee, 2) AS fee_burden
        FROM trips_2025
        WHERE charged_cbd_flag = 1
          AND ROUND(passenger_cost_pretip - cbd_congestion_fee, 2) >= 1.00
    ),
    pickup AS (
        SELECT PULocationID AS zone, 'pickup' AS direction,
               AVG(fee_burden) AS DS_z,
               MEDIAN(fee_burden) AS DS_z_median,
               COUNT(*) AS N_z
        FROM cleaned GROUP BY PULocationID
    ),
    dropoff AS (
        SELECT DOLocationID AS zone, 'dropoff' AS direction,
               AVG(fee_burden) AS DS_z,
               MEDIAN(fee_burden) AS DS_z_median,
               COUNT(*) AS N_z
        FROM cleaned GROUP BY DOLocationID
    )
    SELECT * FROM pickup
    UNION ALL
    SELECT * FROM dropoff
    ORDER BY zone, direction
""")

print(con.sql("SELECT * FROM ds_z ORDER BY DS_z DESC LIMIT 20"))


# ============================================================
# STEP 4.5: Monotonicity check against relative_cbd_burden
# ------------------------------------------------------------
# relative_cbd_burden (pre-existing column) = fee / total_cost
# fee_burden (this pipeline)               = fee / (total_cost - fee)
# Since the second denominator is always <= the first, fee_burden should
# always be >= relative_cbd_burden for every trip. n_violations should be 0.
# ============================================================
print(con.sql("""
    SELECT COUNT(*) AS n_violations
    FROM trips_2025
    WHERE charged_cbd_flag = 1
      AND (passenger_cost_pretip - cbd_congestion_fee) > 0
      AND (cbd_congestion_fee / (passenger_cost_pretip - cbd_congestion_fee)) < relative_cbd_burden
"""))


# ============================================================
# STEP 5: Layer B — Behavioral shift (2024 vs 2025)
# ------------------------------------------------------------
# Trip volume and average fare by zone x direction, year-over-year.
# Not filtered by charged_cbd_flag (includes all trips). Low-N zones are
# flagged, not dropped, so 2024->2025 "activation" effects remain visible.
# ============================================================
con.sql("""
    CREATE OR REPLACE TABLE behavioral_shift AS
    WITH combined AS (
        SELECT yr, PULocationID, DOLocationID, passenger_cost_pretip, base_passenger_fare
        FROM trips_2024
        UNION ALL
        SELECT yr, PULocationID, DOLocationID, passenger_cost_pretip, base_passenger_fare
        FROM trips_2025
    ),
    pu_stats AS (
        SELECT PULocationID AS zone, 'pickup' AS direction, yr,
               COUNT(*) AS n_trips,
               AVG(passenger_cost_pretip) AS avg_total_cost,
               AVG(base_passenger_fare) AS avg_base_fare
        FROM combined GROUP BY PULocationID, yr
    ),
    do_stats AS (
        SELECT DOLocationID AS zone, 'dropoff' AS direction, yr,
               COUNT(*) AS n_trips,
               AVG(passenger_cost_pretip) AS avg_total_cost,
               AVG(base_passenger_fare) AS avg_base_fare
        FROM combined GROUP BY DOLocationID, yr
    ),
    all_stats AS (
        SELECT * FROM pu_stats UNION ALL SELECT * FROM do_stats
    )
    SELECT
        zone, direction,
        MAX(CASE WHEN yr=2024 THEN n_trips END) AS n_2024,
        MAX(CASE WHEN yr=2025 THEN n_trips END) AS n_2025,
        MAX(CASE WHEN yr=2025 THEN n_trips END)::DOUBLE
            / NULLIF(MAX(CASE WHEN yr=2024 THEN n_trips END), 0) - 1 AS pct_volume_change,
        MAX(CASE WHEN yr=2024 THEN avg_total_cost END) AS avg_total_cost_2024,
        MAX(CASE WHEN yr=2025 THEN avg_total_cost END) AS avg_total_cost_2025,
        MAX(CASE WHEN yr=2024 THEN avg_base_fare END) AS avg_base_fare_2024,
        MAX(CASE WHEN yr=2025 THEN avg_base_fare END) AS avg_base_fare_2025,
        CASE
            WHEN COALESCE(MAX(CASE WHEN yr=2024 THEN n_trips END), 0) < 100
              OR COALESCE(MAX(CASE WHEN yr=2025 THEN n_trips END), 0) < 100
            THEN TRUE ELSE FALSE
        END AS low_n_flag
    FROM all_stats
    GROUP BY zone, direction
    ORDER BY zone, direction
""")

print(con.sql("SELECT * FROM behavioral_shift ORDER BY pct_volume_change DESC LIMIT 20"))
print(con.sql("SELECT * FROM behavioral_shift WHERE low_n_flag = FALSE ORDER BY pct_volume_change ASC LIMIT 20"))
print(con.sql("SELECT COUNT(*) AS null_pct_change FROM behavioral_shift WHERE pct_volume_change IS NULL"))
print(con.sql("""
    SELECT zone, direction, n_2024, n_2025, avg_total_cost_2025, avg_base_fare_2025, low_n_flag
    FROM behavioral_shift
    WHERE pct_volume_change IS NULL
"""))


# ============================================================
# STEP 6: Correlation between DS_z and pct_volume_change
# ============================================================
print(con.sql("""
    WITH joined AS (
        SELECT d.zone, d.direction, d.DS_z, d.N_z, b.pct_volume_change, b.low_n_flag
        FROM ds_z d
        JOIN behavioral_shift b ON d.zone = b.zone AND d.direction = b.direction
        WHERE b.pct_volume_change IS NOT NULL AND b.low_n_flag = FALSE
    )
    SELECT
        COUNT(*) AS n_zones,
        CORR(DS_z, pct_volume_change) AS pearson_corr,
        CORR(DS_z, pct_volume_change) FILTER (WHERE direction = 'pickup') AS corr_pickup,
        CORR(DS_z, pct_volume_change) FILTER (WHERE direction = 'dropoff') AS corr_dropoff
    FROM joined
"""))

# Quartile breakdown (more robust to outliers than a single Pearson r)
print(con.sql("""
    WITH joined AS (
        SELECT d.zone, d.direction, d.DS_z, b.pct_volume_change
        FROM ds_z d
        JOIN behavioral_shift b ON d.zone = b.zone AND d.direction = b.direction
        WHERE b.pct_volume_change IS NOT NULL AND b.low_n_flag = FALSE
    ),
    quartiled AS (
        SELECT *, NTILE(4) OVER (PARTITION BY direction ORDER BY DS_z) AS ds_z_quartile
        FROM joined
    )
    SELECT direction, ds_z_quartile, COUNT(*) AS n_zones,
           AVG(DS_z) AS avg_DS_z, AVG(pct_volume_change) AS avg_pct_volume_change
    FROM quartiled
    GROUP BY direction, ds_z_quartile
    ORDER BY direction, ds_z_quartile
"""))


# ============================================================
# STEP 7: Export
# ============================================================
con.sql("COPY ds_z TO 'output/ds_z.parquet' (FORMAT PARQUET)")
con.sql("COPY behavioral_shift TO 'output/behavioral_shift.parquet' (FORMAT PARQUET)")
con.sql("""
    COPY (
        SELECT d.zone, d.direction, d.DS_z, d.N_z, b.pct_volume_change, b.n_2024, b.n_2025
        FROM ds_z d
        JOIN behavioral_shift b ON d.zone = b.zone AND d.direction = b.direction
        WHERE b.pct_volume_change IS NOT NULL AND b.low_n_flag = FALSE
    ) TO 'output/ds_z_vs_volume_change.csv' (HEADER, DELIMITER ',')
""")

print("Pipeline complete. Files written to output/")
