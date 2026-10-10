# RewindLab: portfolio guide

**The question:** What could a researcher have known at a historical cutoff? RewindLab keeps an observation's `valid_at` separate from the time its revision became available, `known_at`. Its synthetic demo returns **300 as known on January 4, 2025**, versus **1400** when a later correction and late arrival leak into the same query. The difference is a data correctness example, not an investment result.

## 90-second walkthrough

From the repository root, run these in order:

```bash
PYTHONPATH=src python3 -m rewindlab demo
PYTHONPATH=src python3 -m rewindlab corpus
PYTHONPATH=src python3 examples/bls/demo.py
PYTHONPATH=src python3 integrations/review_incident.py docs/examples/malformed-schema-evidence.json | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r["mode"], r["model_called"], r["proposal"]["fault_category"], r["proposal"]["citation_ids"])'
```

Narrate the first result as a **synthetic point-in-time bug**. The corpus then prints six `PASS` outcomes: baseline, duplicate, out-of-order delivery, malformed schema, late correction, and interrupted import. A pass means the engine matched the expected result, including rejection or recovery where appropriate; it does **not** mean the engine had six defects. The BLS example shows the May 2025 seasonally adjusted total nonfarm payroll **jobs change** as published across three archived releases: **+139,000 → +144,000 → +19,000**. Its `known_at` values are official release-time proxies, not observed receipt times. The last command prints an offline `schema_rejection` proposal and cited evidence IDs with `model_called: false`.

## Evidence to open when asked

| Claim | Artifact | Boundary |
| --- | --- | --- |
| Historical snapshots differ from latest-only queries | [Core implementation](../src/rewindlab/store.py), [demo fixture](../src/rewindlab/data/seed_events.jsonl) | Toy signal values; no trading strategy |
| Six replay cases match expected state | [Saved corpus report](corpus/seed-1729.json), [independent oracle](../src/rewindlab/data/oracle_seed_1729.json) | Oracle uses Python lists and timestamp comparisons, separate from the SQLite query; fresh seeded reports compare byte for byte |
| Local performance has a reproducible method | [Raw benchmark](benchmarks/local-synthetic-seed-1729.json), [method](benchmarks/README.md) | One macOS arm64 machine; Python 3.14.3, SQLite 3.50.4; 1,000 synthetic revisions per run, batches of 100, five measured runs after one warmup. Observed 89,016 accepted events/s and 1.261 ms p95 **batch acknowledgement**, not per-event latency. Recovery is one separate two-revision retry, not the ingest workload |
| A real revision follows the same query model | [BLS source notes](../examples/bls/README.md) | Curated three-vintage fixture; no live feed or measured publication lag |
| Incident review cannot change the truth source | [Offline report](examples/malformed-schema-report.json), [integration design](../integrations/README.md) | Template knows the injected case; evidence IDs are checked, free-text meaning is not semantically verified |
| Hermes can reach OmniRoute in a local test | [Transport smoke](transport-smoke/README.md) | Canned loopback mock returned the response; no model inference or real-provider accuracy measured |

The [OpenSpec roadmap](roadmap.md) and [change specifications](../openspec/changes/) show the acceptance gates and design decisions.

## Interview framing

Explain the two clocks first: `valid_at` identifies the observation period, while `known_at` prevents later information from appearing in a historical answer. Then show how the independent oracle, atomic batch import, canonical digests, and forced pre-commit exit test correctness and retry behavior. SQLite and the Python standard library keep the experiment easy to reproduce; they do not establish distributed scale. The assistant only reviews a copy of evidence, while the store and oracle decide correctness.

**Resume bullets you can adapt:**

- Built a Python/SQLite point-in-time revision store with immutable valid/known timestamps; demonstrated a 300-versus-1400 historical query error caused by a synthetic late correction and arrival.
- Developed six seeded replay scenarios with an independent oracle, cutoff probes, digests, and interrupted-import recovery; documented the benchmark workload and a sourced BLS revision example.

**Do not claim** trading returns, live market-data latency, production-scale throughput, autonomous defect discovery, or LLM diagnostic accuracy. The Hermes → OmniRoute check establishes mocked transport and report parsing only. A real provider and labeled live evaluation would be needed for any model-quality claim.
