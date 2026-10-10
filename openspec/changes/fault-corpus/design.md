# Design: fault corpus and measurements

## Corpus shape

First add a batch import transaction and SHA-256 over canonical serialization
of sorted logical revisions. The digest excludes SQLite row IDs, file paths,
import order, and machine-generated timestamps. Validate input inside one
transaction and roll back the entire batch on any parse or conflict error.

Build each case from a fixed base fixture and a named perturbation. Save or
generate an independent expected result manifest with case ID, seed, event-set
digest, query probes, expected logical row count, and expected dataset digest.
The oracle must not call the production query function to compute expected
answers; otherwise the same bug can affect both sides of the comparison.

Run duplicate and out-of-order cases against fresh stores. Use a deliberately
bad row for schema drift, and assert the prior store digest is unchanged after
the failed import. For interrupted import, run the import in a child process
with a controlled pre-commit exit point, then retry the same batch. Keep the
injection point confined to test harness code.

## Metrics

Time a defined event ingest workload with a monotonic clock. Throughput is
accepted input events divided by ingest elapsed seconds. Processing latency is
time from harness submission to import acknowledgement for each measured
batch/event; state the granularity and calculate p95 from raw samples. Recovery
time is measured from process restart command to the first confirmed oracle
state. Save raw samples and report the CPU/OS/Python version, case seed, event
count, warmup, repetitions, and SQLite mode.

The fixture's `known_at` is a simulated historical timestamp and must not be
subtracted from wall-clock test time to claim live data lag. A future real
dataset can support a separate publication-lag metric only if timestamps are
verifiable.

## Scope decision

Keep the local SQLite architecture until benchmark results show a specific
limitation. If a queue or Postgres is added, make it a separate OpenSpec
change with the baseline and reason for the migration.
