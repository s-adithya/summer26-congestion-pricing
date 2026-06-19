"""
Zone lookup + merge for visualization
======================================================================
Joins the official NYC TLC taxi zone lookup table onto the
ds_z_vs_volume_change.csv export from 01_pipeline.py, producing the
data structure used to build the scatter plot (see 03_build_chart.py).

Requires: pandas (pip install pandas)
Input: ds_z_vs_volume_change.csv (from 01_pipeline.py Step 7)
Output: scatter_data.json
"""

import pandas as pd

# Official TLC taxi zone lookup table
# Source: https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv
ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"

df = pd.read_csv("ds_z_vs_volume_change.csv")
zones = pd.read_csv(ZONE_LOOKUP_URL)  # columns: LocationID, Borough, Zone, service_zone

merged = df.merge(zones, left_on="zone", right_on="LocationID", how="left")
merged["Zone"] = merged["Zone"].fillna("Zone " + merged["zone"].astype(str))
merged["Borough"] = merged["Borough"].fillna("Other")

# Sanity check before export
print(merged[["DS_z", "pct_volume_change"]].describe())
print(merged["Borough"].value_counts())

merged_out = merged[
    ["zone", "direction", "DS_z", "N_z", "pct_volume_change", "n_2024", "n_2025", "Zone", "Borough"]
]
merged_out.to_json("scatter_data.json", orient="records")
print(f"Exported {len(merged_out)} rows to scatter_data.json")
