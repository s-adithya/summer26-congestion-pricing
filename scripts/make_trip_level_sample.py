"""
Build a balanced 100-row trip-level CSV sample for manual teammate inspection.

Reads standardized parquet files from data/processed/00_standardized_trips/ one file
at a time (memory-safe) and writes data/processed/samples/trip_level_sample.csv plus
a QC note when quota groups could not be fully filled.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDIZED_DIR = REPO_ROOT / "data" / "processed" / "00_standardized_trips"
SAMPLE_PATH = REPO_ROOT / "data" / "processed" / "samples" / "trip_level_sample.csv"
QC_DIR = REPO_ROOT / "data" / "processed" / "qc"

SAMPLE_COLUMNS = [
    "service_type",
    "year",
    "month",
    "pickup_datetime",
    "dropoff_datetime",
    "pickup_hour",
    "day_of_week",
    "PULocationID",
    "DOLocationID",
    "trip_distance_miles",
    "trip_duration_seconds",
    "cbd_congestion_fee",
    "charged_cbd_flag",
    "passenger_cost_pretip",
    "relative_cbd_burden",
    "congestion_surcharge",
    "tolls",
    "airport_fee",
    "source_file",
]

# Target counts per group (service_type, year)
GROUP_TARGETS = {
    ("yellow", 2024): 25,
    ("yellow", 2025): 25,
    ("hvfhv", 2024): 25,
    ("hvfhv", 2025): 25,
}

RANDOM_STATE = 42


def quality_mask(df: pd.DataFrame) -> pd.Series:
    """Rows preferred for manual inspection."""
    return (
        (df["passenger_cost_pretip"] > 0)
        & df["relative_cbd_burden"].notna()
        & (df["trip_duration_seconds"] > 0)
        & (df["trip_distance_miles"] >= 0)
    )


def _read_sample_pool(parquet_path: Path, seed: int) -> pd.DataFrame:
    """
    Load a manageable random slice from a large monthly parquet file.

    Reads one randomly chosen row group instead of the entire file so we can
    sample from 15M+ row HVFHV months without exhausting memory.
    """
    pf = pq.ParquetFile(parquet_path)
    if pf.num_row_groups == 0:
        return pd.DataFrame()

    rng = np.random.default_rng(seed)
    row_group = int(rng.integers(0, pf.num_row_groups))
    return pf.read_row_group(row_group).to_pandas()


def sample_from_file(
    parquet_path: Path,
    n: int,
    seed: int,
    *,
    charged_cbd: bool | None = None,
) -> pd.DataFrame:
    """Draw up to n rows from a single monthly parquet file."""
    if n <= 0:
        return pd.DataFrame()

    df = _read_sample_pool(parquet_path, seed)
    if charged_cbd is not None and "charged_cbd_flag" in df.columns:
        df = df[df["charged_cbd_flag"] == charged_cbd]

    preferred = df[quality_mask(df)] if len(df) else df
    pool = preferred if len(preferred) >= n else df

    take = min(n, len(pool))
    if take == 0:
        return pd.DataFrame()
    return pool.sample(n=take, random_state=seed)


def build_balanced_sample() -> tuple[pd.DataFrame, list[dict]]:
    """
    Build a 100-row sample balanced across service types and years.

    Samples directly from monthly parquet files to avoid loading the full dataset.
    """
    notes: list[dict] = []
    parts: list[pd.DataFrame] = []
    collected: dict[tuple[str, int], int] = {k: 0 for k in GROUP_TARGETS}

    seed_offsets = {
        ("yellow", 2024): 1,
        ("yellow", 2025): 2,
        ("hvfhv", 2024): 3,
        ("hvfhv", 2025): 4,
    }

    # First pass: sample from matching service/year monthly files.
    for (service, year), target in GROUP_TARGETS.items():
        service_dir = STANDARDIZED_DIR / service / str(year)
        if not service_dir.exists():
            notes.append({"group": f"{service}_{year}", "note": "No standardized files found."})
            continue

        month_files = sorted(service_dir.glob("*.parquet"))
        if not month_files:
            notes.append({"group": f"{service}_{year}", "note": "No monthly parquet files."})
            continue

        seed = RANDOM_STATE + seed_offsets[(service, year)]
        need = target

        if year == 2025:
            # Try to split 2025 groups between charged and uncharged CBD trips.
            half = target // 2
            remainder = target - half
            for charged_flag, n_req in [(True, half), (False, remainder)]:
                per_file = max(1, n_req // len(month_files) + 1)
                chunks: list[pd.DataFrame] = []
                for i, fpath in enumerate(month_files):
                    chunk = sample_from_file(
                        fpath,
                        per_file,
                        seed + i + (10 if charged_flag else 0),
                        charged_cbd=charged_flag,
                    )
                    if len(chunk):
                        chunks.append(chunk)
                if chunks:
                    combined = pd.concat(chunks, ignore_index=True)
                    take = min(n_req, len(combined))
                    drawn = combined.sample(n=take, random_state=seed + (1 if charged_flag else 2))
                    parts.append(drawn)
                    need -= take
                    if take < n_req:
                        notes.append(
                            {
                                "group": f"{service}_{year}",
                                "charged_cbd_flag": charged_flag,
                                "note": f"Requested {n_req}, got {take} for charged_cbd={charged_flag}.",
                            }
                        )
        else:
            per_file = max(1, target // len(month_files) + 1)
            chunks = []
            for i, fpath in enumerate(month_files):
                chunk = sample_from_file(fpath, per_file, seed + i)
                if len(chunk):
                    chunks.append(chunk)
            if chunks:
                combined = pd.concat(chunks, ignore_index=True)
                take = min(target, len(combined))
                drawn = combined.sample(n=take, random_state=seed)
                parts.append(drawn)
                need -= take

        collected[(service, year)] = target - need

    sample = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    # Second pass: fill shortfalls from any available standardized file.
    total = len(sample)
    if total < 100:
        shortfall = 100 - total
        filler_parts: list[pd.DataFrame] = []
        all_files = sorted(STANDARDIZED_DIR.rglob("*.parquet"))
        for i, fpath in enumerate(all_files):
            if shortfall <= 0:
                break
            chunk = sample_from_file(fpath, max(1, shortfall // 2), RANDOM_STATE + 200 + i)
            if len(chunk):
                filler_parts.append(chunk)
                shortfall -= len(chunk)

        if filler_parts:
            filler = pd.concat(filler_parts, ignore_index=True)
            take = min(100 - len(sample), len(filler))
            sample = pd.concat(
                [sample, filler.sample(n=take, random_state=RANDOM_STATE + 300)],
                ignore_index=True,
            )
            notes.append(
                {
                    "group": "global",
                    "note": f"Filled {take} row(s) from closest available monthly files.",
                }
            )

    # Trim to exactly 100 if oversampled.
    if len(sample) > 100:
        sample = sample.sample(n=100, random_state=RANDOM_STATE).reset_index(drop=True)
    else:
        sample = sample.reset_index(drop=True)

    # Spread months when possible.
    if len(sample) and "month" in sample.columns:
        sample = sample.sort_values(
            ["service_type", "year", "month", "pickup_datetime"]
        ).reset_index(drop=True)

    for (service, year), got in collected.items():
        target = GROUP_TARGETS[(service, year)]
        if got < target:
            notes.append(
                {
                    "group": f"{service}_{year}",
                    "note": f"Final count {got}/{target} after fill pass.",
                }
            )

    return sample, notes


def main() -> None:
    if not STANDARDIZED_DIR.exists():
        raise FileNotFoundError(
            f"{STANDARDIZED_DIR} not found. Run scripts/standardize_trips.py first."
        )

    sample, notes = build_balanced_sample()

    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_cols = [c for c in SAMPLE_COLUMNS if c in sample.columns]
    sample[out_cols].to_csv(SAMPLE_PATH, index=False)

    QC_DIR.mkdir(parents=True, exist_ok=True)
    notes_path = QC_DIR / "trip_level_sample_notes.csv"
    pd.DataFrame(notes).to_csv(notes_path, index=False)

    print(f"Wrote {len(sample)}-row sample to: {SAMPLE_PATH.relative_to(REPO_ROOT).as_posix()}")
    print("\nSample composition:")
    if len(sample):
        comp = (
            sample.groupby(["service_type", "year"], dropna=False)
            .size()
            .reset_index(name="count")
        )
        print(comp.to_string(index=False))
        if "charged_cbd_flag" in sample.columns:
            charged_2025 = sample[sample["year"] == 2025].groupby(
                ["service_type", "charged_cbd_flag"]
            ).size()
            print("\n2025 charged_cbd_flag breakdown:")
            print(charged_2025.to_string())
        if "month" in sample.columns:
            months = sample.groupby(["service_type", "year", "month"]).size()
            print("\nMonth coverage:")
            print(months.to_string())

    if notes:
        print(f"\nSampling notes written to: {notes_path.relative_to(REPO_ROOT).as_posix()}")
        for n in notes:
            print(f"  - {n}")


if __name__ == "__main__":
    main()
