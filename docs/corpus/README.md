# Synthetic fault corpus

Run from the repository root:

```bash
PYTHONPATH=src python3 -m rewindlab corpus --report docs/corpus/seed-1729.json
PYTHONPATH=src python3 -m rewindlab corpus --case malformed_schema --json
PYTHONPATH=src python3 -m rewindlab corpus --case interrupted_import --json
```

The checked-in [report](seed-1729.json) is a complete run using seed 1729. The
synthetic source label appears on every generated revision. Duplicate and
out-of-order delivery resolve to the same four logical revisions as baseline.
The late-correction case isolates the correction without the late arrival;
the malformed case must retain only its two preloaded rows. Input delivery
digests preserve delivery order;
logical dataset digests sort unique revisions by ID and ignore delivery order.

The independent oracle constructs expected snapshots with Python dictionaries
and comparisons. It does not call the production SQLite snapshot query. Its
seed 1729 output is frozen in `src/rewindlab/data/oracle_seed_1729.json`; other
seeds are derived at run time. The default corpus report is deterministic, so
two runs from fresh temporary stores should compare byte for byte.

The `malformed_schema` report includes the rejected import error and confirms
that the pre-import dataset digest is still expected. The
`interrupted_import` report includes the worker exit code, digest before and
after interruption, and digest after replay. The harness terminates a child
at SQLite's pre-commit trace callback; the production importer has no fault
hook.
