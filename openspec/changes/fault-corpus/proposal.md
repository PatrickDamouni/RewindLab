# Proposal: fault corpus and measurements

## Why

A correct happy-path demo is not enough to show reliability engineering. A
seeded fault corpus can make failure behavior inspectable, reproducible, and
measurable without claims based on a single hand-picked run.

## What Changes

- Add atomic multi-record import and a canonical, order-independent dataset
  digest for replay verification.
- Add a deterministic suite for duplicate delivery, out-of-order delivery,
  malformed schema, late corrections, and interrupted import.
- Check actual query results and dataset digests against an independent oracle.
- Publish a reproducible metrics command and raw report with precise definitions,
  workload size, machine details, and observed numbers.

## Capabilities

### New Capabilities

- `fault-injection`: reproducible perturbations and expected outcomes.
- `batch-replay`: atomic batch import and order-independent reconstruction.
- `measurement`: transparent timing and correctness reporting.

### Modified Capabilities

None. Phase 1's two-time query and replay contracts remain in force.

## Impact

Adds batch replay, local corpus generation, tests, and benchmarking to the
Python CLI. Any
durable queue or Postgres migration is a later design decision justified by
measurement, not a prerequisite. No external account or model provider is
needed. The user tests this phase before incident analysis is added.
