# RewindLab roadmap

## Thesis

RewindLab answers: **What could a researcher have known at a particular time?**
A later correction may change today's view of an observation, but it must not
silently change an earlier point-in-time result. The portfolio proof is a
repeatable late-correction demo plus a public failure corpus and measured
recovery results. Its fault corpus uses labeled synthetic data, and a separate
curated BLS example shows a published three-vintage revision. It is not a
trading system or investment advice.

## Phase gates

| Phase | Deliverable | Acceptance gate |
| --- | --- | --- |
| 1. Point-in-time core | Local Python/SQLite CLI; immutable per-event revisions, later correction, late arrival, two-time snapshots | Run the 90-second demo and focused tests. The historical snapshot keeps the original signal and excludes the late arrival; the latest-only view includes both. Repeating an identical revision changes nothing. |
| 2. Fault corpus | Atomic batch replay, canonical digest, seeded duplicate, out-of-order, malformed-schema, late-correction, and interrupted-import cases; metrics report | Run the corpus twice. Outcomes match the checked-in oracle, and the report includes method, machine, workload, throughput, p95 processing latency, and recovery time where applicable. No invented benchmark numbers. |
| 3. Incident assistant | Read-only evidence bundle and offline dry run; optional Hermes Agent through OmniRoute | Inspect one incident report and its cited input events. The offline path works without credentials. A live provider call is optional and uses environment variables; its diagnosis is evaluated against the corpus oracle. |

At each gate, run and save the acceptance evidence before broadening the next
phase. The user's latest instruction authorizes continuous work across these
gates; user review remains available. A failed gate becomes a fix in the same
phase. Each phase is an OpenSpec change under `openspec/changes/`; archive it
only after its requirements ship.

## What makes the repository compelling

1. A short terminal capture shows the false historical answer from a latest-only
   query beside the correct point-in-time answer.
2. The source includes a small, readable event fixture and expected outputs.
3. Fault cases are reproducible by seed and have a machine-checkable oracle.
4. Benchmark claims include the exact command, dataset size, machine, and raw
   results. Comparisons use the same workload and disclose limitations.
5. The core correctness tests run locally without network access, accounts, or
   model providers. The optional AI report cites evidence instead of deciding
   which records are correct.

## Dataset progression

The deterministic synthetic fault corpus has exact expected answers. A separate
[BLS example](../examples/bls/README.md) traces the May 2025 monthly change in
seasonally adjusted total nonfarm **payroll jobs** across three archived
releases. Its `known_at` timestamps use the official embargo-lift time as a
release-time proxy, not observed researcher receipt times. The example records
source links, public domain status, verification date, and transformation
limits. Keep real release claims separate from simulated corpus timing and
measured benchmarks.

## Planning workflow

Review `proposal.md`, `specs/*/spec.md`, `design.md`, then `tasks.md` for the
current change. OpenSpec's CLI can validate the change after local installation;
the Markdown artifacts remain readable without it. See the
[OpenSpec change format](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md).
