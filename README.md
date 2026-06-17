# Who Bears the Congestion Price?
Fare Burden and Trip Pattern Shifts in NYC Taxi/FHV Trips

Erdős Institute Data Science Project — Summer 2026

## Team

- Yunpeng Niu
- Dionel Jaime
- Yue Qiu
- Yiding Tian
- Adithya Sathyanarayana

## Introduction

On January 5th, 2025, a congestion fee went into effect in the downtown area of New York City. While the general effects of this policy on traffic in Manhattan are being studied, less is known about the policy’s effect on ride-sharing services (e.g., Uber and taxis). For these services, the policy is:

- **Yellow and green taxis:** a $0.75 surcharge for trips within the congestion pricing zone (CRZ).
- **For-hire vehicles (FHV)** — standard/app/livery, not high-volume: $1.50 per trip to, from, or within the CRZ; added on top of other FHV surcharges and taxes.
- **High-volume for-hire vehicles (HVFHV)** — e.g., trips from large app fleets like Uber/Lyft: $1.50 per trip to, from, or within the CRZ (same HVFHV rate); billed to the HVFHV base/plate and passed to the rider as required by regulation.

We seek to understand the impacts of the congestion fee on the different zones marked by the New York City Taxi and Limousine Commission (TLC). For each zone, we will compute a **disruption score** that measures the impact of the fee.

### Research Questions

- How did trip volumes and fare patterns change across TLC zones after the congestion fee took effect?
- Who bears the congestion surcharge — riders, drivers, or both — across vehicle types (yellow/green taxi, FHV, HVFHV)?
- Which zones show the largest disruption, and what trip-pattern shifts (origins, destinations, timing) explain those scores?
- Do high-volume app fleets respond differently than traditional taxis and smaller FHV operators?

## Dataset

The dataset used in this project is sourced from the [TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). It contains historical trip records for yellow and green taxis, for-hire vehicles (FHV), and high-volume for-hire vehicles (HVFHV).

| Source | Description | Current project use |
|--------|-------------|---------------------|
| Yellow taxi trips | Monthly trip records with pickup/dropoff times, locations, fares, and surcharges | **Included** (first-step cleaning complete) |
| HVFHV trips | High-volume for-hire vehicle (Uber/Lyft-scale) trip records | **Included** (first-step cleaning complete) |
| Green taxi trips | Boro taxi trip records (outer boroughs) | Deferred for later robustness checks |
| FHV trips | Smaller for-hire vehicle trip records | Not used in current scope |
| TLC taxi zone lookup | Zone IDs and geographic definitions for aggregation | Planned for zone-level work |

### Study window and policy timing

- **Primary comparison:** February–June **2024** (pre-policy) vs. February–June **2025** (post-policy).
- **Transition month:** January 2025 is treated as a policy transition period and is **not** in the primary Feb–Jun panels.
- **Congestion pricing start:** January 5, 2025 (CBD congestion fee on qualifying trips).

Raw TLC parquet files are stored locally under `data/raw/` (by year and month) and are not committed to this repository due to size. See [Reproducing the analysis](#reproducing-the-analysis) and [`docs/data_structure_and_schema.md`](docs/data_structure_and_schema.md) for folder layout and column definitions.

### Passenger cost definitions (standardized)

Pre-tip passenger cost is defined consistently across services for burden comparisons:

| Service | `passenger_cost_pretip` |
|---------|-------------------------|
| **Yellow Taxi** | `total_amount - tip_amount` |
| **HVFHV** | `base_passenger_fare + tolls + bcf + sales_tax + congestion_surcharge + airport_fee + cbd_congestion_fee` |

`relative_cbd_burden = cbd_congestion_fee / passenger_cost_pretip` when pre-tip cost is positive.

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| **Businesses in affected zones** | Plan operations, staffing, and customer access around changing trip volumes and congestion costs |
| **Elected officials / city planners** | Set policy, approve interventions, and evaluate whether the fee meets congestion and equity goals |
| **Taxi and rideshare companies** (e.g., Uber, Lyft, yellow/green taxi fleets) | Adjust pricing, fleet deployment, and driver incentives based on post-policy demand and fare burden |

## Key Performance Indicators

KPIs are tracked in [`kpis.md`](kpis.md). Planned metrics for this project include:

| KPI | Definition |
|-----|------------|
| **Zone disruption score** | Composite measure of how strongly the congestion fee shifted trips and fares in each TLC zone (primary outcome) |
| **Trip volume change** | Pre- vs. post-policy percent change in trips by zone, vehicle type, and time of day |
| **Fare burden** | Share of congestion surcharges borne by riders vs. absorbed elsewhere (by vehicle class) |
| **OD pattern shift** | Change in origin–destination flows across and within the CRZ |
| **Peak-hour redistribution** | Shift in trip timing (e.g., away from peak congestion windows) after January 5, 2025 |

## Deliverables

Our intended deliverables include:

- **`README.md`** — project description, research questions, data sources, and instructions for reproducing the analysis (this file)
- **`kpis.md`** — KPI definitions, targets, and tracking updates
- **Analysis notebooks** — exploratory and modeling work in `notebooks/`
- **Source code** — data processing, feature engineering, models, and visualization in `src/`
- **Presentation** — stakeholder summary in `presentation/`

## Reproducing the analysis

### Environment

```bash
conda env create -f environment.yml
conda activate congestion-pricing
```

*(Dependencies: `pandas`, `pyarrow`, `numpy` — see `environment.yml`.)*

### Data

1. Download monthly TLC trip record files from the [TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) page.
2. Place raw parquet files in `data/raw/{year}/{Month}/` (e.g. `data/raw/2024/Feb/yellow_tripdata_2024-02.parquet`).
3. Run first-step standardization (one raw file at a time; does not modify `data/raw/`):

```bash
python scripts/standardize_trips.py
python scripts/make_trip_level_sample.py
python scripts/validate_standardized_trips.py
```

**Outputs:**

| Output | Description | Committed to git? |
|--------|-------------|-------------------|
| `data/processed/00_standardized_trips/` | Monthly cleaned parquet files by service (`yellow/`, `hvfhv/`) | No (too large; regenerate locally) |
| `data/processed/samples/trip_level_sample.csv` | 100-row balanced CSV for manual inspection | Yes |
| `data/processed/qc/` | Standardization, validation, and sample QC reports | Yes |

See [`docs/data_structure_and_schema.md`](docs/data_structure_and_schema.md) for the full standardized schema and cleaning rules.

### Analysis

1. Open and run notebooks in `notebooks/` as they are added.
2. Further feature engineering, EDA, zone disruption scores, and stakeholder outputs will build on the standardized trip files.

## Project Status

**Current phase: first-step data cleaning and standardization (Yellow Taxi + HVFHV).**

| Area | Status |
|------|--------|
| Raw data download (Feb–Jun 2024 & 2025, Yellow + HVFHV) | Complete locally |
| `scripts/standardize_trips.py` | Implemented |
| `scripts/make_trip_level_sample.py` | Implemented |
| `scripts/validate_standardized_trips.py` | Implemented |
| `data/processed/00_standardized_trips/` | Produced locally by standardization script |
| `data/processed/samples/trip_level_sample.csv` | Produced by sample script |
| `data/processed/qc/` | Standardization + validation QC reports |
| EDA, maps, modeling, disruption scores | **Not started** — next phase |

Green Taxi integration and January 2025 transition analysis are planned for later robustness work.
