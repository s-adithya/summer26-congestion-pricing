# NYC HVFHV CBD Congestion Fee Analysis — Code Package

Run in order:

1. `01_pipeline.py` — DuckDB pipeline. Loads parquet files, runs data
   quality diagnostics, computes DS_z (Layer A) and behavioral shift
   metrics (Layer B), runs the correlation check, exports parquet/CSV.
   Requires `pip install duckdb`. Edit FILES_2024 / FILES_2025 paths
   at the top to point at your actual data.

2. `02_zone_lookup_merge.py` — Joins the official TLC zone lookup table
   onto the Step 1 CSV export so zones are human-readable.
   Requires `pip install pandas`.

3. `03_build_chart.py` — Builds the standalone HTML scatter chart
   (DS_z vs. trip volume change) from the Step 2 output. No extra
   dependencies; pulls Chart.js from a CDN at render time.

See methodology_notes.md (separate file, already delivered) for the
full reasoning behind each data quality decision in this pipeline.
