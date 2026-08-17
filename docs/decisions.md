# Architecture decisions

## 1. Fixed corridors, not arbitrary routes

"When should I leave?" needs weeks of history for a specific route. A user's
route is unknown until they type it, so arbitrary origin/destination pairs can
never have a baseline.

Instead a fixed set of tech corridors is polled continuously. User-entered routes
are decomposed onto the monitored corridors at query time, and historical context
is served for the segments they cross.

## 2. Raw responses expire, derived aggregates persist

Routing providers restrict long-term storage of their responses. Raw JSONL is
deleted after `RAW_RETENTION_DAYS` (default 7). The bronze Parquet layer and
everything downstream hold only derived measures, which is both licence-safe and
smaller.

## 3. No Spark in the 15-minute job

At ~16 corridors x 96 polls/day the working set is roughly 1,500 rows/day.
Spark would add minutes of JVM startup to process kilobytes. The routine job uses
pandas and pyarrow.

PySpark is introduced in Phase 3 for full-history backfill and aggregation, where
the volume justifies it. Choosing per workload rather than defaulting to the
biggest tool is deliberate.

## 4. Micro-batch, not a long-running stream

There is no free way to run an always-on process. The scheduler triggers a job
that processes everything pending and exits - the same model as Auto Loader with
`Trigger.AvailableNow`, which is how most production Databricks pipelines run.
Checkpointing is introduced with the streaming silver layer in Phase 2.

## 5. Git as the storage layer

Repo-committed Parquet costs nothing, needs no cloud account, and makes the data
publicly inspectable. At ~50 KB/day it stays under 20 MB/year.

Trade-off: no object-store lifecycle rules, no Terraform in Phase 1, and commit
noise from the scheduled job (mitigated with `[skip ci]`). If the dataset outgrows
this, the storage layer moves to Cloudflare R2 and IaC arrives with it.

## 6. Partial failure is tolerated

One corridor failing must not discard the other fifteen. Failures are recorded
per corridor in `data/status.json`; the job only fails when nothing was captured.

## 7. Median baselines, not a forecasting model

The baseline is the median travel time per corridor, per day-of-week, per 15-minute
bucket, with anomalies expressed as deviation from it. It is explainable, robust to
outliers, and honest about what the data supports. A black-box model on a few weeks
of data would be neither.
