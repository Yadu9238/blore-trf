"""Poll every corridor plus current weather and append to the raw landing zone.

A single corridor failure must not lose the whole run, so failures are recorded
per corridor and the job only exits non-zero if nothing at all was captured.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from src.config import RAW_DIR, STATUS_PATH, load_settings
from src.providers import mapbox, weather
from src.providers.base import ProviderError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest")


def main() -> int:
    settings = load_settings()
    if not settings.mapbox_token:
        log.error("MAPBOX_TOKEN is not set")
        return 1

    captured_at = datetime.now(UTC)
    run_id = captured_at.strftime("%Y%m%dT%H%M%SZ")

    try:
        conditions = weather.fetch_weather(settings.city_centre)
    except ProviderError as exc:
        log.warning("Weather unavailable, continuing without it: %s", exc)
        conditions = {}

    records: list[dict] = []
    failures: list[dict] = []

    for corridor in settings.corridors:
        try:
            result = mapbox.fetch_corridor(corridor, settings.mapbox_token)
        except ProviderError as exc:
            log.error("Corridor %s failed: %s", corridor.id, exc)
            failures.append({"corridor_id": corridor.id, "error": str(exc)})
            continue

        records.append(
            {
                "run_id": run_id,
                "corridor_id": corridor.id,
                "corridor_name": corridor.name,
                "captured_at_utc": captured_at.isoformat(),
                **result,
                **conditions,
            }
        )

    if records:
        partition = RAW_DIR / f"dt={captured_at:%Y-%m-%d}"
        partition.mkdir(parents=True, exist_ok=True)
        with (partition / "records.jsonl").open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")

    write_status(run_id, captured_at, len(records), failures, len(settings.corridors))
    log.info("Captured %s/%s corridors", len(records), len(settings.corridors))

    return 0 if records else 1


def write_status(run_id, captured_at, captured, failures, total) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        json.dumps(
            {
                "last_run_id": run_id,
                "last_run_utc": captured_at.isoformat(),
                "corridors_total": total,
                "corridors_captured": captured,
                "failures": failures,
                "healthy": not failures,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    sys.exit(main())
