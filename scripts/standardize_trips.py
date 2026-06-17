"""
First-step cleaning and standardization for NYC TLC Yellow Taxi and HVFHV trips.

Reads one raw parquet file at a time, applies conservative validity filters,
maps to a shared trip-level schema, and writes monthly standardized parquet files
under data/processed/00_standardized_trips/.

Never modifies files in data/raw/.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# --- Paths (relative to repository root) ---
REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "00_standardized_trips"
QC_DIR = REPO_ROOT / "data" / "processed" / "qc"

# --- Shared output schema ---
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

# QC thresholds (flags only; rows are not dropped for these)
VERY_LONG_DURATION_SECONDS = 24 * 60 * 60  # 24 hours
VERY_LONG_DISTANCE_MILES = 100.0

# Month folder names in data/raw/ -> numeric month for output filenames
MONTH_NAME_TO_NUM = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def identify_service_type(filename: str) -> str | None:
    """Classify a raw parquet file as yellow or hvfhv from its filename."""
    name = filename.lower()
    if "yellow" in name:
        return "yellow"
    if "fhvhv" in name or "hvfhv" in name:
        return "hvfhv"
    return None


def parse_year_month_from_path(file_path: Path) -> tuple[int, int] | None:
    """
    Extract (year, month) from folder structure and/or filename.

    Expected layout: data/raw/{year}/{MonthName}/...
    Filename fallback: *_tripdata_YYYY-MM.parquet
    """
    year_match = re.search(r"(20\d{2})", file_path.as_posix())
    year = int(year_match.group(1)) if year_match else None

    month_num = None
    for part in file_path.parts:
        key = part.lower()
        if key in MONTH_NAME_TO_NUM:
            month_num = MONTH_NAME_TO_NUM[key]
            break

    if month_num is None:
        file_match = re.search(r"20\d{2}-(\d{2})", file_path.name)
        if file_match:
            month_num = int(file_match.group(1))

    if year is None or month_num is None:
        return None
    return year, month_num


def _safe_numeric(series: pd.Series) -> pd.Series:
    """Coerce to numeric; invalid values become NaN."""
    return pd.to_numeric(series, errors="coerce")


def _fill_cbd_fee(series: pd.Series | None, year: int, index: pd.Index) -> pd.Series:
    """
    Handle missing cbd_congestion_fee.

    Pre-policy 2024 files do not include this column; filling with 0 is safe
    because the CBD congestion fee did not apply before January 2025.
    """
    if series is None:
        return pd.Series(0.0, index=index)
    filled = _safe_numeric(series).fillna(0.0 if year < 2025 else pd.NA)
    return filled


def standardize_yellow(
    df: pd.DataFrame, year: int, month: int, source_file: str
) -> pd.DataFrame:
    """Map Yellow Taxi raw columns to the shared standardized schema."""
    out = pd.DataFrame(index=df.index)

    out["service_type"] = "yellow"
    out["year"] = year
    out["month"] = month
    out["pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"], errors="coerce")
    out["dropoff_datetime"] = pd.to_datetime(df["tpep_dropoff_datetime"], errors="coerce")
    out["pickup_date"] = out["pickup_datetime"].dt.date
    out["pickup_hour"] = out["pickup_datetime"].dt.hour
    out["day_of_week"] = out["pickup_datetime"].dt.dayofweek

    out["PULocationID"] = _safe_numeric(df["PULocationID"])
    out["DOLocationID"] = _safe_numeric(df["DOLocationID"])
    out["trip_distance_miles"] = _safe_numeric(df["trip_distance"])

    # Yellow has no trip_time; derive duration from pickup/dropoff timestamps.
    out["trip_duration_seconds"] = (
        out["dropoff_datetime"] - out["pickup_datetime"]
    ).dt.total_seconds()

    cbd_col = df["cbd_congestion_fee"] if "cbd_congestion_fee" in df.columns else None
    out["cbd_congestion_fee"] = _fill_cbd_fee(cbd_col, year, df.index)

    out["congestion_surcharge"] = _safe_numeric(df.get("congestion_surcharge", pd.NA))
    out["tolls"] = _safe_numeric(df.get("tolls_amount", pd.NA))

    # TLC uses Airport_fee (capital A) in yellow files.
    airport_col = df["Airport_fee"] if "Airport_fee" in df.columns else df.get("airport_fee")
    out["airport_fee"] = _safe_numeric(airport_col)

    tip_amount = _safe_numeric(df.get("tip_amount", 0)).fillna(0)
    total_amount = _safe_numeric(df.get("total_amount", pd.NA))
    # Pre-tip passenger cost: total charge minus voluntary tip.
    out["passenger_cost_pretip"] = total_amount - tip_amount

    out["source_file"] = source_file

    # Optional Yellow-specific helper columns
    for col in YELLOW_OPTIONAL_COLUMNS:
        if col in df.columns:
            out[col] = df[col]

    return out


def standardize_hvfhv(
    df: pd.DataFrame, year: int, month: int, source_file: str
) -> pd.DataFrame:
    """Map HVFHV raw columns to the shared standardized schema."""
    out = pd.DataFrame(index=df.index)

    out["service_type"] = "hvfhv"
    out["year"] = year
    out["month"] = month
    out["pickup_datetime"] = pd.to_datetime(df["pickup_datetime"], errors="coerce")
    out["dropoff_datetime"] = pd.to_datetime(df["dropoff_datetime"], errors="coerce")
    out["pickup_date"] = out["pickup_datetime"].dt.date
    out["pickup_hour"] = out["pickup_datetime"].dt.hour
    out["day_of_week"] = out["pickup_datetime"].dt.dayofweek

    out["PULocationID"] = _safe_numeric(df["PULocationID"])
    out["DOLocationID"] = _safe_numeric(df["DOLocationID"])
    out["trip_distance_miles"] = _safe_numeric(df["trip_miles"])
    out["trip_duration_seconds"] = _safe_numeric(df["trip_time"])

    cbd_col = df["cbd_congestion_fee"] if "cbd_congestion_fee" in df.columns else None
    out["cbd_congestion_fee"] = _fill_cbd_fee(cbd_col, year, df.index)

    out["congestion_surcharge"] = _safe_numeric(df.get("congestion_surcharge", pd.NA))
    out["tolls"] = _safe_numeric(df.get("tolls", pd.NA))
    out["airport_fee"] = _safe_numeric(df.get("airport_fee", pd.NA))

    base_fare = _safe_numeric(df.get("base_passenger_fare", 0)).fillna(0)
    tolls = _safe_numeric(df.get("tolls", 0)).fillna(0)
    bcf = _safe_numeric(df.get("bcf", 0)).fillna(0)
    sales_tax = _safe_numeric(df.get("sales_tax", 0)).fillna(0)
    congestion_surcharge = _safe_numeric(df.get("congestion_surcharge", 0)).fillna(0)
    airport_fee = _safe_numeric(df.get("airport_fee", 0)).fillna(0)
    cbd_fee = _safe_numeric(out["cbd_congestion_fee"]).fillna(0)

    # Pre-tip passenger cost: base fare plus mandatory fees/taxes, excluding tips.
    out["passenger_cost_pretip"] = (
        base_fare
        + tolls
        + bcf
        + sales_tax
        + congestion_surcharge
        + airport_fee
        + cbd_fee
    )

    out["source_file"] = source_file

    for col in HVFHV_OPTIONAL_COLUMNS:
        if col in df.columns:
            out[col] = df[col]

    return out


def add_derived_and_qc_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Compute burden fields and basic QC flags (informational, not filters)."""
    df = df.copy()

    df["charged_cbd_flag"] = df["cbd_congestion_fee"] > 0

    # Relative burden only when pre-tip cost is strictly positive.
    df["relative_cbd_burden"] = pd.NA
    valid_cost = df["passenger_cost_pretip"] > 0
    df.loc[valid_cost, "relative_cbd_burden"] = (
        df.loc[valid_cost, "cbd_congestion_fee"] / df.loc[valid_cost, "passenger_cost_pretip"]
    )

    df["zero_distance_flag"] = df["trip_distance_miles"] == 0
    df["very_long_duration_flag"] = df["trip_duration_seconds"] > VERY_LONG_DURATION_SECONDS
    df["very_long_distance_flag"] = df["trip_distance_miles"] > VERY_LONG_DISTANCE_MILES
    df["negative_cost_flag"] = df["passenger_cost_pretip"] <= 0

    return df


def apply_conservative_filters(
    df: pd.DataFrame, year: int, month: int
) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Apply fundamental validity checks. Returns cleaned DataFrame and drop counts
    by reason (for the cleaning report).
    """
    drops: dict[str, int] = {}
    n_start = len(df)

    def _drop(mask: pd.Series, reason: str) -> None:
        nonlocal df
        n = int(mask.sum())
        if n:
            drops[reason] = drops.get(reason, 0) + n
            df = df.loc[~mask]

    # 1–2. Valid pickup and dropoff datetimes.
    _drop(df["pickup_datetime"].isna(), "invalid_pickup_datetime")
    _drop(df["dropoff_datetime"].isna(), "invalid_dropoff_datetime")

    # 3. Dropoff must be strictly after pickup.
    _drop(df["dropoff_datetime"] <= df["pickup_datetime"], "dropoff_not_after_pickup")

    # 4. Pickup year/month must match the source folder.
    _drop(
        (df["pickup_datetime"].dt.year != year) | (df["pickup_datetime"].dt.month != month),
        "pickup_year_month_mismatch",
    )

    # 5. Zone IDs must be present.
    _drop(df["PULocationID"].isna() | df["DOLocationID"].isna(), "missing_zone_id")

    # 6. Distance cannot be negative (zero-distance trips are kept).
    _drop(df["trip_distance_miles"] < 0, "negative_distance")

    # 7. Duration must be strictly positive.
    _drop(df["trip_duration_seconds"] <= 0, "non_positive_duration")

    # 8–9. CBD fee must be present and non-negative.
    # (2024 missing values were already filled with 0 in standardize_*.)
    _drop(df["cbd_congestion_fee"].isna(), "missing_cbd_congestion_fee")
    _drop(df["cbd_congestion_fee"] < 0, "negative_cbd_congestion_fee")

    # 10. Pre-tip passenger cost must be positive for burden outputs.
    _drop(df["passenger_cost_pretip"] <= 0, "non_positive_passenger_cost_pretip")

    drops["rows_before"] = n_start
    drops["rows_after"] = len(df)
    drops["rows_dropped"] = n_start - len(df)
    return df, drops


def discover_raw_parquet_files() -> list[Path]:
    """Find Yellow and HVFHV parquet files under data/raw/."""
    files = sorted(RAW_DIR.rglob("*.parquet"))
    return [f for f in files if identify_service_type(f.name) is not None]


def output_path_for(service_type: str, year: int, month: int) -> Path:
    """Build processed output path: .../00_standardized_trips/{service}/{year}/{MM}.parquet"""
    return PROCESSED_DIR / service_type / str(year) / f"{month:02d}.parquet"


def order_columns(df: pd.DataFrame, service_type: str) -> pd.DataFrame:
    """Place standard columns first, then service-specific optional columns, then QC flags."""
    optional = YELLOW_OPTIONAL_COLUMNS if service_type == "yellow" else HVFHV_OPTIONAL_COLUMNS
    cols = [c for c in STANDARD_COLUMNS if c in df.columns]
    cols += [c for c in optional if c in df.columns]
    cols += [c for c in QC_FLAG_COLUMNS if c in df.columns]
    return df[cols]


def process_one_file(raw_path: Path) -> dict:
    """Read, standardize, clean, and save one raw parquet file."""
    raw_path = raw_path.resolve()
    service_type = identify_service_type(raw_path.name)
    year_month = parse_year_month_from_path(raw_path)
    rel_source = raw_path.relative_to(REPO_ROOT).as_posix()

    record: dict = {
        "source_file": rel_source,
        "service_type": service_type,
        "status": "ok",
    }

    if service_type is None:
        record["status"] = "skipped"
        record["skip_reason"] = "unrecognized_service_type"
        return record

    if year_month is None:
        record["status"] = "skipped"
        record["skip_reason"] = "could_not_parse_year_month"
        return record

    year, month = year_month
    record["year"] = year
    record["month"] = month

    print(f"Processing {rel_source} ({service_type}, {year}-{month:02d}) ...")

    df_raw = pd.read_parquet(raw_path)
    record["rows_before"] = len(df_raw)

    if service_type == "yellow":
        df = standardize_yellow(df_raw, year, month, rel_source)
    else:
        df = standardize_hvfhv(df_raw, year, month, rel_source)

    df = add_derived_and_qc_flags(df)
    df, drop_detail = apply_conservative_filters(df, year, month)
    record.update(drop_detail)

    df = order_columns(df, service_type)

    out_path = output_path_for(service_type, year, month)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    record["output_file"] = out_path.relative_to(REPO_ROOT).as_posix()

    print(
        f"  {record['rows_before']:,} -> {record['rows_after']:,} rows "
        f"({record['rows_dropped']:,} dropped)"
    )
    return record


def write_qc_reports(row_records: list[dict], issue_records: list[dict]) -> None:
    """Write row-count and issue summaries to data/processed/qc/."""
    QC_DIR.mkdir(parents=True, exist_ok=True)

    counts_df = pd.DataFrame(row_records)
    counts_path = QC_DIR / "standardization_row_counts.csv"
    counts_df.to_csv(counts_path, index=False)

    issues_df = pd.DataFrame(issue_records)
    issues_path = QC_DIR / "standardization_issues.csv"
    issues_df.to_csv(issues_path, index=False)


def main() -> None:
    raw_files = discover_raw_parquet_files()
    row_records: list[dict] = []
    issue_records: list[dict] = []
    created_outputs: list[str] = []

    print(f"Found {len(raw_files)} raw Yellow/HVFHV parquet file(s) under {RAW_DIR}\n")

    for raw_path in raw_files:
        record = process_one_file(raw_path)
        row_records.append(record)

        if record["status"] == "skipped":
            issue_records.append(
                {
                    "source_file": record.get("source_file"),
                    "issue": record.get("skip_reason"),
                }
            )
        elif record.get("rows_dropped", 0) > 0:
            issue_records.append(
                {
                    "source_file": record.get("source_file"),
                    "issue": "rows_dropped_during_cleaning",
                    "rows_before": record.get("rows_before"),
                    "rows_after": record.get("rows_after"),
                    "rows_dropped": record.get("rows_dropped"),
                }
            )

        if record.get("output_file"):
            created_outputs.append(record["output_file"])

    write_qc_reports(row_records, issue_records)

    # --- Summary for teammates ---
    print("\n" + "=" * 60)
    print("STANDARDIZATION SUMMARY")
    print("=" * 60)
    print(f"1. Raw files processed: {sum(1 for r in row_records if r['status'] == 'ok')}")
    print(f"   Raw files found:    {len(raw_files)}")
    print(f"2. Standardized parquet files created: {len(created_outputs)}")

    print("\n3. Row counts before and after cleaning (by service/year/month):")
    ok_records = [r for r in row_records if r["status"] == "ok"]
    if ok_records:
        summary = pd.DataFrame(ok_records)[
            ["service_type", "year", "month", "rows_before", "rows_after", "rows_dropped"]
        ].sort_values(["service_type", "year", "month"])
        print(summary.to_string(index=False))

    print("\n4. 100-row sample CSV: run scripts/make_trip_level_sample.py after this step.")
    print(f"   Target path: data/processed/samples/trip_level_sample.csv")

    skipped = [r for r in row_records if r["status"] == "skipped"]
    print(f"\n5. Files skipped: {len(skipped)}")
    for r in skipped:
        print(f"   - {r.get('source_file')}: {r.get('skip_reason')}")

    print(f"\nQC reports written to: {QC_DIR.relative_to(REPO_ROOT).as_posix()}/")


if __name__ == "__main__":
    main()
