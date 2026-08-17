# Bangalore Tech Corridor Traffic

A continuously running data platform that measures travel time across Bangalore's
tech corridors every 15 minutes, joins it with weather, and answers three questions:

- How bad is this corridor **right now** compared to its own normal?
- **When should I leave** in the next few hours?
- Is today unusual, and **does rain explain it**?

Status: **Phase 1 - ingestion.**

## Why fixed corridors

Predicting "best time to leave" requires weeks of history on a specific route.
An arbitrary origin/destination has none. So a fixed set of tech corridors is
monitored continuously, and user routes are mapped onto those corridors at query
time. See [docs/decisions.md](docs/decisions.md).

## Architecture

```
Mapbox driving-traffic  ─┐
Open-Meteo current      ─┼──▶  raw JSONL        (7-day retention)
                         ┘         │
                                   ▼
                            bronze Parquet      (daily, deduped)
                                   │
                                   ▼
                            silver / gold       (Phase 2-3)
                                   │
                                   ▼
                            web app             (Phase 5)
```

Scheduled by GitHub Actions cron. Storage is Parquet committed to this repo.
Running cost: **$0/month.**

## Layout

```
config/corridors.yml     corridor definitions
src/providers/           upstream clients, one module per provider
src/ingest.py            poll all corridors + weather, append raw
src/compact.py           raw -> bronze Parquet, enforce retention
data/raw/                short-lived provider responses
data/bronze/             derived measures, retained
data/status.json         last run health
docs/decisions.md        why the design looks like this
```

## Running locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

$env:MAPBOX_TOKEN = "your_token"
python -m src.ingest
python -m src.compact
pytest -q
```

## Deploying

1. Create a free Mapbox account and generate a token with the Directions scope.
2. Add it as the repository secret `MAPBOX_TOKEN`.
3. Enable Actions. The `ingest` workflow polls every 15 minutes and commits results.

Budget: 16 corridors x 96 polls/day is roughly 46k requests/month, inside
Mapbox's free tier. Verify current limits before scaling the corridor list.

## Data licence

Raw provider responses are deleted after 7 days. Only derived measures are
retained and published. Weather data is from Open-Meteo (CC BY 4.0).

## Roadmap

| Phase | Scope |
|---|---|
| 1 | Ingestion, bronze Parquet, retention, CI |
| 2 | Streaming silver layer with checkpoints and watermarking |
| 3 | Gold star schema, SCD2 corridor dimension, PySpark backfill |
| 4 | Quality gates, freshness alerts, public status page |
| 5 | Web app: route input, live vs baseline, best time to leave |
