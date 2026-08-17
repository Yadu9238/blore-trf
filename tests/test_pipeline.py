from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from src import compact
from src.config import load_settings


def test_corridors_config_is_valid():
    settings = load_settings()
    assert len(settings.corridors) >= 10
    assert all(c.origin != c.destination for c in settings.corridors)


def test_coordinates_outside_bangalore_are_rejected():
    from src.config import _point

    with pytest.raises(ValueError):
        _point({"lat": 28.6139, "lon": 77.2090})  # Delhi


def test_compact_deduplicates_replayed_runs(tmp_path, monkeypatch):
    partition = tmp_path / "raw" / "dt=2026-08-17"
    partition.mkdir(parents=True)

    row = {
        "run_id": "20260817T101500Z",
        "corridor_id": "silkboard_ecity",
        "corridor_name": "Silk Board to Electronic City",
        "captured_at_utc": "2026-08-17T10:15:00+00:00",
        "duration_live_s": 2340.0,
        "duration_typical_s": 1800.0,
        "distance_m": 18200.0,
        "congestion_ratio": 1.3,
    }
    pd.DataFrame([row, row]).to_json(partition / "records.jsonl", orient="records", lines=True)

    bronze = tmp_path / "bronze"
    monkeypatch.setattr(compact, "BRONZE_DIR", bronze)

    assert compact.compact_partition(partition) == 1

    written = pd.read_parquet(bronze / "dt=2026-08-17" / "part-000.parquet")
    assert len(written) == 1
    assert written.loc[0, "corridor_id"] == "silkboard_ecity"


def test_prune_raw_removes_only_expired_partitions(tmp_path, monkeypatch):
    monkeypatch.setattr(compact, "RAW_DIR", tmp_path)
    today = datetime.now(UTC).date()

    fresh = tmp_path / f"dt={today}"
    stale = tmp_path / f"dt={today - timedelta(days=30)}"
    fresh.mkdir()
    stale.mkdir()

    removed = compact.prune_raw(today - timedelta(days=7))

    assert removed == [stale.name]
    assert fresh.exists()
    assert not stale.exists()
