# Local synthetic workload measurement

The [saved raw report](local-synthetic-seed-1729.json) was produced with:

```bash
PYTHONPATH=src python3 -m rewindlab benchmark --seed 1729 --events 1000 \
  --batch-size 100 --repetitions 5 --warmup 1 \
  --report docs/benchmarks/local-synthetic-seed-1729.json
```

Each measured repetition imports 1,000 unique synthetic revisions into a new
SQLite database in batches of 100. One warmup repetition is discarded. Ingest
elapsed time starts before the first batch call and stops after the last call
returns. Throughput divides 5,000 accepted inputs by the sum of those five
elapsed times. Batch processing latency is measured around each batch import
call; the reported p95 is the nearest-rank percentile across 50 batches, not
per-event latency. The recovery sample starts when a new Python process is
launched after a controlled pre-commit exit, and stops after its digest is
checked against the independent oracle. It excludes fault setup and has one
sample, so it should not be read as a latency distribution. Recovery uses the
separate `interrupted_import` corpus case with two preloaded revisions and a
two-revision retry. It does not replay the 1,000-event ingest workload, and
changing `--events` does not change the recovery workload.

The JSON report contains the observed values, all raw nanosecond samples,
Python and SQLite versions, OS, CPU count, and journal mode. These numbers
vary with the machine and load. They establish a reproducible local baseline,
not production throughput, distributed recovery, or live market-data lag.
