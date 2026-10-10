# RewindLab

**What could a researcher actually have known at a particular time?**

RewindLab is a small, reproducible data engineering project. Its core
stores immutable revisions with two timestamps: `valid_at` says when an
observation applies; `known_at` says when it became available. A historical
query uses both. The core demos and failure corpus use synthetic data with
known answers; a separate BLS example shows a documented real revision.

## Run the first demo

From this directory, with Python 3.10 or newer:

```bash
PYTHONPATH=src python3 -m rewindlab demo
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m unittest discover -s integrations -p 'test_*.py' -v
```

The demo prints a signal sum of **300 as known on January 4, 2025** and
**1400 when queried with later knowledge**. A January 9 correction and a
January 10 late arrival account for the difference. These are toy values,
not trading signals or investment results.

Export one corpus case and produce a cited offline incident report:

```bash
PYTHONPATH=src python3 -m rewindlab evidence --case malformed_schema --report work/malformed-evidence.json
PYTHONPATH=src python3 integrations/review_incident.py work/malformed-evidence.json --report work/malformed-report.json
PYTHONPATH=src python3 integrations/review_incident.py work/malformed-evidence.json --print-prompt
```

The report is labeled `model_called: false`; `--print-prompt` shows the optional
live model input. These commands need no account, network connection, or
provider. Each `--report` path creates a new JSON file and refuses to overwrite
an existing file. The checked-in [malformed-schema example](docs/examples/malformed-schema-report.json)
shows the offline output. See [integration setup](integrations/README.md) for the
optional live Hermes Agent route through OmniRoute. A [local transport smoke](docs/transport-smoke/README.md)
exercised that route against a canned loopback mock; no language model made an
inference, and real-provider behavior remains unmeasured.

## Run the failure corpus

```bash
PYTHONPATH=src python3 -m rewindlab corpus
PYTHONPATH=src python3 -m rewindlab corpus --case malformed_schema --json
PYTHONPATH=src python3 -m rewindlab corpus --case interrupted_import --json
```

The six synthetic cases cover exact duplicate delivery, reversed delivery,
malformed input, a late correction, and an interrupted import. The checked-in
[oracle](src/rewindlab/data/oracle_seed_1729.json) was produced from plain
Python lists and timestamp comparisons; it does not call the SQLite query.
Each run compares all four knowledge-cutoff probes, logical row counts, and
SHA-256 digests. The malformed case **passes** when the bad batch is rejected
and earlier rows remain intact. The interrupted case **passes** when the
pre-commit process exit leaves no partial rows and retry reaches the oracle.
See the [saved corpus report](docs/corpus/seed-1729.json).

To reproduce the local timing report:

```bash
PYTHONPATH=src python3 -m rewindlab benchmark --seed 1729 --events 1000 \
  --batch-size 100 --repetitions 5 --warmup 1 \
  --report work/benchmark-local.json
```

The [benchmark report](docs/benchmarks/local-synthetic-seed-1729.json) includes
raw monotonic timing samples, machine details, workload, and metric definitions.
Results describe this local SQLite workload only. The simulated `known_at`
timestamps do not measure live publication lag.

## Run the real-data example

```bash
PYTHONPATH=src python3 examples/bls/demo.py
```

The [BLS example](examples/bls/README.md) traces the May 2025 change in
seasonally adjusted total nonfarm payroll jobs through three archived releases:
**+139,000 → +144,000 → +19,000**. Its `known_at` values use the official
embargo-lift time as a release-time proxy; they are not evidence of when a
researcher received the figures. The example runs offline from a small,
source-linked fixture.

## Inspect a persistent dataset

```bash
PYTHONPATH=src python3 -m rewindlab seed --database /tmp/rewindlab-demo.db
PYTHONPATH=src python3 -m rewindlab query \
  --database /tmp/rewindlab-demo.db \
  --valid-through 2025-01-03T23:59:59Z \
  --known-through 2025-01-04T00:00:00Z
```

Run `seed` again to see exact duplicate deliveries ignored. Omit
`--known-through` to see the latest-known view. Use a new database path to
repeat the demo from an empty state.

## Plan and phase gates

The [roadmap](docs/roadmap.md) defines three phases. The point-in-time core and
seeded failure corpus run locally. The incident assistant has a deterministic
offline report; a live model route is optional. The requirements and remaining work are
tracked in [OpenSpec changes](openspec/changes/).
The [portfolio guide](docs/portfolio.md) has a short demo path and interview framing.

OpenSpec is installed as a **local development dependency** and initialized
for Codex and Hermes Agent. To validate the planning artifacts:

```bash
npm ci
npm run spec:check
```

Hermes does not load project-local OpenSpec skills automatically. Add this
project's `.hermes/skills` path to `skills.external_dirs` in the Hermes
profile you choose if you want to use those skills inside Hermes. This does
not affect the RewindLab demo.

## Design boundaries

- The revision log and queries own data correctness; AI can only review a
  JSON evidence snapshot.
- The core uses SQLite and the Python standard library so anyone can run it
  locally. It does not claim distributed scale or production reliability.
- Synthetic fixture results are labeled as such. Future performance claims
  will include the workload, test machine, commands, and raw results.

The project direction draws on Two Sigma's public discussion of
[data versioning, replay, lineage, and quality checks](https://www.twosigma.com/articles/treating-data-as-code-at-two-sigma/).
