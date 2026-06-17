# Data Structure and Standardized Schema

This document describes how raw TLC trip data are organized locally, what the first-step
cleaning pipeline produces, and how each standardized column is derived from Yellow Taxi
and HVFHV (high-volume for-hire vehicle) source fields.

## Scope (current first step)

- **Included:** Yellow Taxi and HVFHV monthly trip records for **February–June 2024** and
  **February–June 2025**.
- **Excluded for now:** Green Taxi (deferred to later robustness checks).
- **Policy context:** NYC congestion pricing in the Central Business District (CBD) took
  effect on **January 5, 2025**. We treat **January 2025 as a transition month** and do
  not include it in the primary Feb–Jun comparison windows.

## Folder layout

### Raw data (`data/raw/`)

Raw TLC parquet files are stored locally and are **not** committed to git. Files are
organized by calendar year and month:

```
data/raw/
  2024/
    Feb/   yellow_tripdata_2024-02.parquet, fhvhv_tripdata_2024-02.parquet
    Mar/
    Apr/
    May/
    June/
  2025/
    Feb/
    Mar/
    Apr/
    May/
    June/
```

**Never modify files in `data/raw/`.** All cleaning writes to `data/processed/`.

### Processed data (`data/processed/`)

| Path | Purpose |
|------|---------|
| `00_standardized_trips/` | Month-by-month, service-specific trip-level parquet files after conservative cleaning and schema alignment |
| `samples/trip_level_sample.csv` | 100-row CSV for manual teammate inspection |
| `qc/` | Row-count and issue reports from standardization and sampling |

#### Standardized trip output structure

```
data/processed/00_standardized_trips/
  yellow/
    2024/02.parquet ... 06.parquet
    2025/02.parquet ... 06.parquet
  hvfhv/
    2024/02.parquet ... 06.parquet
    2025/02.parquet ... 06.parquet
```

Each file contains trips from **one service**, **one year**, and **one month** that pass
fundamental validity checks (see [Cleaning rules](#conservative-cleaning-rules)).

#### Sample file

`data/processed/samples/trip_level_sample.csv` is a **balanced 100-row** extract
(`random_state=42`) with teammate-friendly columns. It is for manual QA only—not for
modeling or reporting aggregate statistics.

#### QC reports

| File | Contents |
|------|----------|
| `qc/standardization_row_counts.csv` | Per-file row counts before and after cleaning |
| `qc/standardization_issues.csv` | Skipped files and files with notable row loss |
| `qc/trip_level_sample_notes.csv` | Notes when sample quota groups could not be fully filled |

## Scripts

| Script | Role |
|--------|------|
| `scripts/standardize_trips.py` | Discover raw parquets, clean and standardize one file at a time, write monthly outputs and QC reports |
| `scripts/make_trip_level_sample.py` | Build the 100-row balanced CSV sample from standardized parquets |

Run in order:

```bash
python scripts/standardize_trips.py
python scripts/make_trip_level_sample.py
```

---

## Standardized schema

### Core columns (both services)

| Column | Type | Definition |
|--------|------|------------|
| `service_type` | string | `"yellow"` or `"hvfhv"` |
| `year` | int | Calendar year from the source folder/filename (e.g. `2024`, `2025`) |
| `month` | int | Calendar month of the source file (`2`–`6` for Feb–Jun) |
| `pickup_datetime` | timestamp | Trip start time |
| `dropoff_datetime` | timestamp | Trip end time |
| `pickup_date` | date | Date portion of `pickup_datetime` |
| `pickup_hour` | int | Hour of day (0–23) from `pickup_datetime` |
| `day_of_week` | int | Day of week from `pickup_datetime` (Monday = 0, Sunday = 6) |
| `PULocationID` | numeric | TLC taxi zone ID for trip origin |
| `DOLocationID` | numeric | TLC taxi zone ID for trip destination |
| `trip_distance_miles` | float | Trip distance in miles |
| `trip_duration_seconds` | float | Trip duration in seconds |
| `cbd_congestion_fee` | float | CBD congestion pricing fee charged on the trip |
| `charged_cbd_flag` | bool | `True` when `cbd_congestion_fee > 0` |
| `congestion_surcharge` | float | TLC congestion surcharge (distinct from CBD fee) |
| `tolls` | float | Toll amounts passed to the passenger |
| `airport_fee` | float | Airport access fee when applicable |
| `passenger_cost_pretip` | float | Mandatory pre-tip passenger cost (see [Cost definitions](#passenger-cost-definitions)) |
| `relative_cbd_burden` | float | `cbd_congestion_fee / passenger_cost_pretip` when pre-tip cost > 0; otherwise null |
| `source_file` | string | Relative path to the raw parquet file |

### Optional Yellow-specific columns

| Column | Raw source | Notes |
|--------|------------|-------|
| `payment_type` | `payment_type` | TLC payment code; useful for data-quality checks |
| `passenger_count` | `passenger_count` | Reported passenger count |
| `fare_amount` | `fare_amount` | Metered time-and-distance fare only (not total payment) |
| `tip_amount` | `tip_amount` | Tip amount |
| `total_amount` | `total_amount` | Total passenger charge including fare, surcharges, tolls, and tip |
| `RatecodeID` | `RatecodeID` | TLC rate code |

### Optional HVFHV-specific columns

| Column | Raw source | Notes |
|--------|------------|-------|
| `hvfhs_license_num` | `hvfhs_license_num` | Identifies Uber, Lyft, Via, Juno, etc. (not analyzed by company in this step) |
| `base_passenger_fare` | `base_passenger_fare` | Fare before tolls, tips, taxes, and fees |
| `bcf` | `bcf` | Black car fund fee |
| `sales_tax` | `sales_tax` | Sales tax on the trip |
| `tips` | `tips` | Tip amount (excluded from `passenger_cost_pretip`) |
| `driver_pay` | `driver_pay` | Driver pay field from TLC |
| `shared_request_flag` | `shared_request_flag` | Whether passenger requested a shared ride |
| `shared_match_flag` | `shared_match_flag` | Whether trip was matched as shared |

### QC flag columns (informational)

These flags are attached to rows that **pass** fundamental validity filters. They do not
replace outlier removal in later analysis steps.

| Column | Definition |
|--------|------------|
| `zero_distance_flag` | `trip_distance_miles == 0` |
| `very_long_duration_flag` | `trip_duration_seconds > 24 hours` |
| `very_long_distance_flag` | `trip_distance_miles > 100` |
| `negative_cost_flag` | `passenger_cost_pretip <= 0` (such rows are dropped from output) |

---

## Column derivation by service

### Yellow Taxi

| Standardized column | Raw column(s) | Derivation |
|--------------------|---------------|------------|
| `pickup_datetime` | `tpep_pickup_datetime` | Parsed as datetime |
| `dropoff_datetime` | `tpep_dropoff_datetime` | Parsed as datetime |
| `trip_distance_miles` | `trip_distance` | Renamed |
| `trip_duration_seconds` | `tpep_pickup_datetime`, `tpep_dropoff_datetime` | `(dropoff - pickup)` in seconds |
| `cbd_congestion_fee` | `cbd_congestion_fee` | Present in 2025+ files; **filled with 0** in 2024 (pre-policy) |
| `congestion_surcharge` | `congestion_surcharge` | Direct |
| `tolls` | `tolls_amount` | Renamed |
| `airport_fee` | `Airport_fee` | TLC uses capital `A` in yellow files |
| `passenger_cost_pretip` | `total_amount`, `tip_amount` | `total_amount - tip_amount` |

### HVFHV

| Standardized column | Raw column(s) | Derivation |
|--------------------|---------------|------------|
| `pickup_datetime` | `pickup_datetime` | Parsed as datetime |
| `dropoff_datetime` | `dropoff_datetime` | Parsed as datetime |
| `trip_distance_miles` | `trip_miles` | Renamed |
| `trip_duration_seconds` | `trip_time` | TLC reports duration in seconds |
| `cbd_congestion_fee` | `cbd_congestion_fee` | Present in 2025+ files; **filled with 0** in 2024 |
| `congestion_surcharge` | `congestion_surcharge` | Direct |
| `tolls` | `tolls` | Direct |
| `airport_fee` | `airport_fee` | Direct |
| `passenger_cost_pretip` | `base_passenger_fare`, `tolls`, `bcf`, `sales_tax`, `congestion_surcharge`, `airport_fee`, `cbd_congestion_fee` | Sum of mandatory pre-tip charges (tips excluded) |

---

## Passenger cost definitions

### Yellow Taxi

```
passenger_cost_pretip = total_amount - tip_amount
```

- `fare_amount` is **not** total passenger payment—it is only the metered fare.
- `total_amount` is closer to the full passenger charge.
- Tips are subtracted so pre-tip costs are comparable across services.

### HVFHV

```
passenger_cost_pretip =
    base_passenger_fare
  + tolls
  + bcf
  + sales_tax
  + congestion_surcharge
  + airport_fee
  + cbd_congestion_fee
```

- HVFHV records do not include a `total_amount` field.
- Tips are excluded from this sum.

### Relative CBD burden

```
relative_cbd_burden = cbd_congestion_fee / passenger_cost_pretip   (when passenger_cost_pretip > 0)
relative_cbd_burden = null                                           (otherwise)
```

### Charged CBD flag

```
charged_cbd_flag = (cbd_congestion_fee > 0)
```

---

## Conservative cleaning rules

Applied in `scripts/standardize_trips.py` before writing monthly parquet outputs:

1. Parse `pickup_datetime` and `dropoff_datetime`; drop rows with invalid timestamps.
2. Keep only rows where `dropoff_datetime > pickup_datetime`.
3. Keep only rows where pickup year and month match the source folder/file.
4. Keep only rows where `PULocationID` and `DOLocationID` are not missing.
5. Keep only rows where `trip_distance_miles >= 0` (zero-distance trips retained).
6. Keep only rows where `trip_duration_seconds > 0`.
7. `cbd_congestion_fee` must not be missing; for pre-policy **2024** data, missing values
   are filled with **0**. For **2025+**, missing values cause the row to be dropped.
8. Keep only rows where `cbd_congestion_fee >= 0`.
9. Keep only rows where `passenger_cost_pretip > 0` (required for burden metrics).

Outlier trips (very long distance/duration) are **not** removed at this stage; they receive
QC flags instead.

---

## Next steps (not in this document)

EDA, zone-level aggregation, disruption scores, maps, and modeling will use the
standardized trip files as input in later project phases.
