"""
QC validation pass for standardized trip parquet files.

Reads all files under data/processed/00_standardized_trips/, checks schema,
row counts, fee distributions, and sample coverage. Writes reports to
data/processed/qc/. Does not perform EDA, plotting, or modeling.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDIZED_DIR = REPO_ROOT / "data" / "processed" / "00_standardized_trips"
QC_DIR = REPO_ROOT / "data" / "processed" / "qc"
SAMPLE_PATH = REPO_ROOT / "data" / "processed" / "samples" / "trip_level_sample.csv"
ROW_COUNTS_PATH = QC_DIR / "standardization_row_counts.csv"

# Expected columns (aligned with scripts/standardize_trips.py)
STANDARD_COLUMNS = [
    "service_type",
    "year",
    "month",
    "pickup_datetime",
    "dropoff_datetime",
    "pickup_date",
    "pickup_hour",
    "day_of_week",
    "PULocationID",
    "DOLocationID",
    "trip_distance_miles",
    "trip_duration_seconds",
    "cbd_congestion_fee",
    "charged_cbd_flag",
    "congestion_surcharge",
    "tolls",
    "airport_fee",
    "passenger_cost_pretip",
    "relative_cbd_burden",
    "source_file",
]

YELLOW_OPTIONAL_COLUMNS = [
    "payment_type",
    "passenger_count",
    "fare_amount",
    "tip_amount",
    "total_amount",
    "RatecodeID",
]

HVFHV_OPTIONAL_COLUMNS = [
    "hvfhs_license_num",
    "base_passenger_fare",
    "bcf",
    "sales_tax",
    "tips",
    "driver_pay",
    "shared_request_flag",
    "shared_match_flag",
]

QC_FLAG_COLUMNS = [
    "zero_distance_flag",
    "very_long_duration_flag",
    "very_long_distance_flag",
    "negative_cost_flag",
]

DROP_REASON_COLUMNS = [
    "dropoff_not_after_pickup",
    "pickup_year_month_mismatch",
    "invalid_pickup_datetime",
    "invalid_dropoff_datetime",
    "missing_zone_id",
    "negative_distance",
    "non_positive_duration",
    "missing_cbd_congestion_fee",
    "negative_cbd_congestion_fee",
    "non_positive_passenger_cost_pretip",
]

EXAMPLE_COLUMNS = [
    "service_type",
    "year",
    "month",
    "pickup_datetime",
    "dropoff_datetime",
    "trip_distance_miles",
    "trip_duration_seconds",
    "cbd_congestion_fee",
    "passenger_cost_pretip",
    "relative_cbd_burden",
    "charged_cbd_flag",
    "source_file",
]

MAX_EXAMPLES_PER_ISSUE = 5


def discover_standardized_files() -> list[Path]:
    """Return all monthly standardized parquet files."""
    return sorted(STANDARDIZED_DIR.rglob("*.parquet"))


def parse_file_meta(path: Path) -> dict:
    """Extract service_type, year, month from a standardized file path."""
    parts = path.parts
    service_type = parts[-3]
    year = int(parts[-2])
    month = int(path.stem)
    return {
        "file_path": path,
        "relative_path": path.relative_to(REPO_ROOT).as_posix(),
        "service_type": service_type,
        "year": year,
        "month": month,
    }


def expected_columns(service_type: str) -> list[str]:
    """Columns required for a given service type."""
    optional = (
        YELLOW_OPTIONAL_COLUMNS if service_type == "yellow" else HVFHV_OPTIONAL_COLUMNS
    )
    return STANDARD_COLUMNS + optional + QC_FLAG_COLUMNS


def validate_schema(path: Path, service_type: str) -> dict:
    """Check that a parquet file contains the expected columns."""
    schema_cols = {f.name for f in pq.read_schema(path)}
    required = set(expected_columns(service_type))
    missing = sorted(required - schema_cols)
    unexpected = sorted(schema_cols - required)
    return {
        "file": path.relative_to(REPO_ROOT).as_posix(),
        "service_type": service_type,
        "schema_ok": len(missing) == 0,
        "missing_columns": ", ".join(missing) if missing else "",
        "unexpected_columns": ", ".join(unexpected) if unexpected else "",
    }


def parquet_row_count(path: Path) -> int:
    """Row count from parquet metadata (no full read)."""
    return pq.ParquetFile(path).metadata.num_rows


def quantile_summary(series: pd.Series) -> dict:
    """Min, p1, median, mean, p99, max for a numeric series."""
    if series.empty:
        return {k: np.nan for k in ["min", "p1", "median", "mean", "p99", "max"]}
    return {
        "min": series.min(),
        "p1": series.quantile(0.01),
        "median": series.median(),
        "mean": series.mean(),
        "p99": series.quantile(0.99),
        "max": series.max(),
    }


def analyze_file(path: Path, meta: dict) -> tuple[dict, dict, list[dict]]:
    """
    Analyze one standardized file.

    Returns (file_summary, cbd_2025_values, example_rows).
    """
    service = meta["service_type"]
    year = meta["year"]
    month = meta["month"]

    # Read columns needed for stats and example extraction (one pass per file).
    stat_cols = [
        "cbd_congestion_fee",
        "charged_cbd_flag",
        "passenger_cost_pretip",
        "relative_cbd_burden",
        "trip_distance_miles",
        "trip_duration_seconds",
        "zero_distance_flag",
        "very_long_duration_flag",
        "very_long_distance_flag",
    ]
    example_extra = [c for c in EXAMPLE_COLUMNS if c not in stat_cols]
    schema_cols = {f.name for f in pq.read_schema(path)}
    read_cols = list(dict.fromkeys([c for c in stat_cols + example_extra if c in schema_cols]))
    df = pd.read_parquet(path, columns=read_cols)

    row_count = len(df)
    key = {**meta, "rows_in_file": row_count}

    # --- 2024 CBD fee check ---
    cbd = df["cbd_congestion_fee"]
    nonzero_cbd_2024 = int((cbd != 0).sum()) if year == 2024 else 0
    key["nonzero_cbd_2024_count"] = nonzero_cbd_2024

    # --- charged_cbd_flag share ---
    if "charged_cbd_flag" in df.columns:
        charged_n = int(df["charged_cbd_flag"].sum())
        key["charged_cbd_count"] = charged_n
        key["charged_cbd_share"] = charged_n / row_count if row_count else np.nan
    else:
        key["charged_cbd_count"] = np.nan
        key["charged_cbd_share"] = np.nan

    # --- passenger_cost_pretip stats ---
    cost_stats = quantile_summary(df["passenger_cost_pretip"])
    for stat_name, val in cost_stats.items():
        key[f"passenger_cost_pretip_{stat_name}"] = val

    # --- relative_cbd_burden stats (non-null only) ---
    burden_stats = quantile_summary(df["relative_cbd_burden"].dropna())
    for stat_name, val in burden_stats.items():
        key[f"relative_cbd_burden_{stat_name}"] = val

    # --- 2025 CBD fee value distribution ---
    cbd_value_rows: list[dict] = []
    if year == 2025:
        counts = (
            df["cbd_congestion_fee"]
            .value_counts(dropna=False)
            .sort_index()
            .reset_index()
        )
        counts.columns = ["cbd_congestion_fee", "trip_count"]
        for _, r in counts.iterrows():
            cbd_value_rows.append(
                {
                    "service_type": service,
                    "year": year,
                    "month": month,
                    "cbd_congestion_fee": r["cbd_congestion_fee"],
                    "trip_count": int(r["trip_count"]),
                    "share_of_month": r["trip_count"] / row_count if row_count else np.nan,
                }
            )

    # --- Example rows for QC categories ---
    examples: list[dict] = []
    ex_df = df

    issue_filters = [
        ("negative_cbd_congestion_fee", ex_df["cbd_congestion_fee"] < 0),
        (
            "non_positive_passenger_cost_pretip",
            ex_df["passenger_cost_pretip"] <= 0,
        ),
        ("zero_distance", ex_df.get("zero_distance_flag", pd.Series(False, index=ex_df.index)) == True),
        (
            "very_long_duration",
            ex_df.get("very_long_duration_flag", pd.Series(False, index=ex_df.index)) == True,
        ),
        (
            "very_long_distance",
            ex_df.get("very_long_distance_flag", pd.Series(False, index=ex_df.index)) == True,
        ),
    ]

    for issue_type, mask in issue_filters:
        subset = ex_df.loc[mask]
        n_found = len(subset)
        if n_found == 0:
            examples.append(
                {
                    "issue_type": issue_type,
                    "service_type": service,
                    "year": year,
                    "month": month,
                    "rows_found": 0,
                    "note": (
                        "No rows in standardized output (expected for dropped issues)."
                        if issue_type
                        in ("negative_cbd_congestion_fee", "non_positive_passenger_cost_pretip")
                        else "No rows matching this QC flag."
                    ),
                }
            )
        else:
            sample = subset.head(MAX_EXAMPLES_PER_ISSUE)
            for i, (_, row) in enumerate(sample.iterrows()):
                ex = {
                    "issue_type": issue_type,
                    "service_type": service,
                    "year": year,
                    "month": month,
                    "rows_found": n_found,
                    "example_rank": i + 1,
                    "note": "",
                }
                for col in EXAMPLE_COLUMNS:
                    if col in row.index:
                        ex[col] = row[col]
                examples.append(ex)

    return key, cbd_value_rows, examples


def validate_row_counts(
    file_summaries: list[dict], row_counts_df: pd.DataFrame
) -> pd.DataFrame:
    """Compare parquet row counts to standardization_row_counts.csv."""
    records = []
    expected = row_counts_df.set_index("output_file")["rows_after"].to_dict()

    for summary in file_summaries:
        rel_path = summary["relative_path"]
        actual = summary["rows_in_file"]
        expected_count = expected.get(rel_path)
        records.append(
            {
                "file": rel_path,
                "service_type": summary["service_type"],
                "year": summary["year"],
                "month": summary["month"],
                "expected_rows": expected_count,
                "actual_rows": actual,
                "match": actual == expected_count if expected_count is not None else False,
                "note": (
                    "missing from standardization_row_counts.csv"
                    if expected_count is None
                    else ""
                ),
            }
        )
    return pd.DataFrame(records)


def build_drop_reason_summary(row_counts_df: pd.DataFrame) -> pd.DataFrame:
    """Melt drop-reason columns from standardization_row_counts.csv."""
    id_cols = ["service_type", "year", "month", "source_file"]
    reason_cols = [c for c in DROP_REASON_COLUMNS if c in row_counts_df.columns]

    melted = row_counts_df[id_cols + reason_cols].melt(
        id_vars=id_cols,
        value_vars=reason_cols,
        var_name="drop_reason",
        value_name="rows_dropped",
    )
    melted = melted.dropna(subset=["rows_dropped"])
    melted = melted[melted["rows_dropped"] > 0]
    melted["rows_dropped"] = melted["rows_dropped"].astype(int)
    return melted.sort_values(
        ["service_type", "year", "month", "drop_reason"]
    ).reset_index(drop=True)


def validate_sample_csv() -> pd.DataFrame:
    """Check coverage of the 100-row teammate sample."""
    if not SAMPLE_PATH.exists():
        return pd.DataFrame(
            [{"check": "sample_file_exists", "passed": False, "detail": "File not found."}]
        )

    sample = pd.read_csv(SAMPLE_PATH)
    checks = []

    def add_check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    add_check("row_count_100", len(sample) == 100, f"rows={len(sample)}")

    for service in ["yellow", "hvfhv"]:
        n = int((sample["service_type"] == service).sum())
        add_check(f"includes_{service}", n > 0, f"count={n}")

    for yr in [2024, 2025]:
        n = int((sample["year"] == yr).sum())
        add_check(f"includes_{yr}", n > 0, f"count={n}")

    months_present = sorted(sample["month"].unique().tolist())
    all_months = [2, 3, 4, 5, 6]
    missing_months = [m for m in all_months if m not in months_present]
    add_check(
        "all_months_feb_jun",
        len(missing_months) == 0,
        f"present={months_present}; missing={missing_months or 'none'}",
    )

    sample_2025 = sample[sample["year"] == 2025]
    if "charged_cbd_flag" in sample_2025.columns:
        charged = sample_2025["charged_cbd_flag"].astype(str).str.lower()
        has_true = (charged == "true").any()
        has_false = (charged == "false").any()
        add_check(
            "2025_charged_cbd_true",
            has_true,
            f"count={int((charged == 'true').sum())}",
        )
        add_check(
            "2025_charged_cbd_false",
            has_false,
            f"count={int((charged == 'false').sum())}",
        )
    else:
        add_check("2025_charged_cbd_flag_column", False, "column missing")

    return pd.DataFrame(checks)


def main() -> None:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    files = discover_standardized_files()

    if not files:
        raise FileNotFoundError(
            f"No standardized parquet files found under {STANDARDIZED_DIR}. "
            "Run scripts/standardize_trips.py first."
        )

    if not ROW_COUNTS_PATH.exists():
        raise FileNotFoundError(
            f"Missing {ROW_COUNTS_PATH}. Run scripts/standardize_trips.py first."
        )

    row_counts_df = pd.read_csv(ROW_COUNTS_PATH)
    print(f"Validating {len(files)} standardized parquet file(s)...\n")

    # --- 1. Schema validation ---
    schema_records = []
    for path in files:
        meta = parse_file_meta(path)
        schema_records.append(validate_schema(path, meta["service_type"]))
    schema_df = pd.DataFrame(schema_records)
    schema_df.to_csv(QC_DIR / "validation_schema.csv", index=False)

    # --- Per-file analysis ---
    file_summaries: list[dict] = []
    cbd_2025_all: list[dict] = []
    example_rows_all: list[dict] = []

    for path in files:
        meta = parse_file_meta(path)
        print(f"  Analyzing {meta['relative_path']} ...")
        summary, cbd_vals, examples = analyze_file(path, meta)
        file_summaries.append(summary)
        cbd_2025_all.extend(cbd_vals)
        example_rows_all.extend(examples)

    summary_df = pd.DataFrame(file_summaries)

    # --- 2. Row count match ---
    row_match_df = validate_row_counts(file_summaries, row_counts_df)
    row_match_df.to_csv(QC_DIR / "validation_row_counts.csv", index=False)

    # --- 3. 2024 CBD fee check ---
    cbd_2024_df = summary_df[summary_df["year"] == 2024][
        ["relative_path", "service_type", "year", "month", "rows_in_file", "nonzero_cbd_2024_count"]
    ].copy()
    cbd_2024_df["cbd_2024_ok"] = cbd_2024_df["nonzero_cbd_2024_count"] == 0
    cbd_2024_df.to_csv(QC_DIR / "validation_cbd_2024.csv", index=False)

    # --- 4. 2025 CBD fee values ---
    cbd_2025_df = pd.DataFrame(cbd_2025_all)
    if len(cbd_2025_df):
        cbd_2025_df.to_csv(QC_DIR / "validation_cbd_2025_values.csv", index=False)
        # Service-level rollup of distinct values
        service_cbd = (
            cbd_2025_df.groupby(["service_type", "cbd_congestion_fee"])["trip_count"]
            .sum()
            .reset_index()
            .sort_values(["service_type", "cbd_congestion_fee"])
        )
        service_cbd.to_csv(QC_DIR / "validation_cbd_2025_by_service.csv", index=False)

    # --- 5. charged_cbd_flag share ---
    charged_df = summary_df[
        [
            "service_type",
            "year",
            "month",
            "rows_in_file",
            "charged_cbd_count",
            "charged_cbd_share",
        ]
    ].copy()
    charged_df.to_csv(QC_DIR / "validation_charged_cbd_share.csv", index=False)

    # --- 6. passenger_cost_pretip stats ---
    cost_cols = ["service_type", "year", "month", "rows_in_file"] + [
        f"passenger_cost_pretip_{s}" for s in ["min", "p1", "median", "mean", "p99", "max"]
    ]
    summary_df[cost_cols].to_csv(
        QC_DIR / "validation_passenger_cost_pretip.csv", index=False
    )

    # --- 7. relative_cbd_burden stats ---
    burden_cols = ["service_type", "year", "month", "rows_in_file"] + [
        f"relative_cbd_burden_{s}" for s in ["min", "p1", "median", "mean", "p99", "max"]
    ]
    summary_df[burden_cols].to_csv(
        QC_DIR / "validation_relative_cbd_burden.csv", index=False
    )

    # --- 8. Drop reason summary ---
    drop_df = build_drop_reason_summary(row_counts_df)
    drop_df.to_csv(QC_DIR / "validation_drop_reasons.csv", index=False)

    # --- 9. Example rows ---
    examples_df = pd.DataFrame(example_rows_all)
    examples_df.to_csv(QC_DIR / "validation_example_rows.csv", index=False)

    # --- 10. Sample CSV validation ---
    sample_checks_df = validate_sample_csv()
    sample_checks_df.to_csv(QC_DIR / "validation_sample_checks.csv", index=False)

    # --- Console summary ---
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    schema_ok = schema_df["schema_ok"].all()
    print(f"1. Schema check: {'PASS' if schema_ok else 'FAIL'} ({len(schema_df)} files)")
    if not schema_ok:
        print(schema_df[~schema_df["schema_ok"]].to_string(index=False))

    row_ok = row_match_df["match"].all()
    print(f"2. Row count match: {'PASS' if row_ok else 'FAIL'}")
    if not row_ok:
        print(row_match_df[~row_match_df["match"]].to_string(index=False))

    cbd_2024_ok = cbd_2024_df["cbd_2024_ok"].all()
    print(f"3. 2024 cbd_congestion_fee all zero: {'PASS' if cbd_2024_ok else 'FAIL'}")
    if not cbd_2024_ok:
        bad = cbd_2024_df[~cbd_2024_df["cbd_2024_ok"]]
        print(bad.to_string(index=False))

    print("\n4. 2025 cbd_congestion_fee values by service:")
    if len(cbd_2025_df):
        print(
            service_cbd.groupby("service_type")["cbd_congestion_fee"]
            .apply(lambda s: sorted(s.unique().tolist()))
            .to_string()
        )

    print("\n5. charged_cbd_flag share (sample):")
    print(
        charged_df.groupby(["service_type", "year"])["charged_cbd_share"]
        .mean()
        .round(4)
        .to_string()
    )

    print("\n8. Drop reasons (top by rows dropped):")
    if len(drop_df):
        top_drops = (
            drop_df.groupby("drop_reason")["rows_dropped"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        print(top_drops.to_string())

    print("\n10. Sample CSV checks:")
    print(sample_checks_df.to_string(index=False))

    print(f"\nQC reports written to: {QC_DIR.relative_to(REPO_ROOT).as_posix()}/")


if __name__ == "__main__":
    main()
