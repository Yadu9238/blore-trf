"""Compact raw JSONL into daily Parquet and enforce raw retention.

Raw provider responses are licensed content and are deleted after
RAW_RETENTION_DAYS. The Parquet bronze layer holds only fields we derive or are
permitted to retain, and is what every downstream layer reads.
"""
from __future__ import annotations

import logging
import shutil
import sys
from datetime import UTC, datetime, timedelta

import pandas as pd

from src.config import BRONZE_DIR, RAW_DIR, RAW_RETENTION_DAYS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("compact")

NUMERIC_COLUMNS = [
    "duration_live_s",
    "duration_typical_s",
    "distance_m",
    "congestion_ratio",
    "temperature_c",
    "precipitation_mm",
    "rain_mm",
    "wind_speed_kmh",
    "cloud_cover_pct",
]


def compact_partition(partition) -> int:
    source = partition / "records.jsonl"
    if not source.exists():
        return 0

    frame = pd.read_json(source, lines=True)
    if frame.empty:
        return 0

    frame["captured_at_utc"] = pd.to_datetime(frame["captured_at_utc"], utc=True)
    # Reruns and retries can replay a run, so the natural key is deduplicated here
    # rather than relying on the scheduler firing exactly once.
    frame = frame.drop_duplicates(subset=["run_id", "corridor_id"], keep="last")
    frame = frame.sort_values(["captured_at_utc", "corridor_id"])

    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    target = BRONZE_DIR / partition.name
    target.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(target / "part-000.parquet", index=False, compression="snappy")

    return len(frame)


def prune_raw(cutoff) -> list[str]:
    removed = []
    for partition in sorted(RAW_DIR.glob("dt=*")):
        partition_date = datetime.strptime(partition.name[3:], "%Y-%m-%d").date()
        if partition_date < cutoff:
            shutil.rmtree(partition)
            removed.append(partition.name)
    return removed


def main() -> int:
    if not RAW_DIR.exists():
        log.info("No raw data yet")
        return 0

    total = 0
    for partition in sorted(RAW_DIR.glob("dt=*")):
        rows = compact_partition(partition)
        total += rows
        log.info("%s -> %s rows", partition.name, rows)

    cutoff = (datetime.now(UTC) - timedelta(days=RAW_RETENTION_DAYS)).date()
    removed = prune_raw(cutoff)
    if removed:
        log.info("Pruned raw partitions past retention: %s", ", ".join(removed))

    log.info("Compacted %s rows", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
