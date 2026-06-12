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

The dataset used to train our models is sourced from the [TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). It contains historical trip records for yellow and green taxis, for-hire vehicles (FHV), and high-volume for-hire vehicles (HVFHV), with coverage extending back to February 2019 and including many trips before that date.

| Source | Description |
|--------|-------------|
| Yellow taxi trips | Monthly trip records with pickup/dropoff times, locations, fares, and surcharges |
| Green taxi trips | Boro taxi trip records (outer boroughs) |
| FHV trips | For-hire vehicle trip records |
| HVFHV trips | High-volume for-hire vehicle (Uber/Lyft-scale) trip records |
| TLC taxi zone lookup | Zone IDs and geographic definitions for aggregation |

Raw data files are stored locally under `data/` and are not committed to this repository due to size. See [Reproducing the analysis](#reproducing-the-analysis) for download instructions.

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

*(Environment specification is in progress; update `environment.yml` as dependencies are finalized.)*

### Data

1. Download monthly TLC trip record files from the [TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) page (yellow, green, FHV, and HVFHV as needed).
2. Place raw files in `data/raw/` (create subfolders by trip type if helpful).
3. Run preprocessing scripts from `src/data/` once available.

### Analysis

1. Open and run notebooks in `notebooks/` in order, or execute pipeline scripts from `src/` as they are added.
2. Outputs (tables, figures, disruption scores by zone) will be written to `data/processed/` and `presentation/` as the project matures.

## Project Status

Early setup — repository structure, data sourcing, and KPI definitions. Modeling and disruption-score methodology are in development.
