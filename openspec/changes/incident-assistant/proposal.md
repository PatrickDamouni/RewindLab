# Proposal: read-only incident assistant

## Why

The corpus can establish whether a run is correct, but a reader still needs a
clear explanation of what failed and which evidence supports that conclusion.
An assistant is useful only if it cannot alter the authoritative dataset and
its claims can be checked against the fault oracle.

## What Changes

- Export a compact, immutable evidence bundle from a corpus run.
- Provide an offline dry-run report path with no provider credentials.
- Add an optional Hermes Agent analysis path routed through OmniRoute after
  verifying the supported integration in the checked-out versions.
- Evaluate reports against expected fault categories and evidence IDs.

## Capabilities

### New Capabilities

- `incident-analysis`: evidence-grounded, read-only incident reports.

### Modified Capabilities

None. Core ingestion, query, replay, and oracle behavior remain authoritative.

## Impact

Adds an adapter around generated evidence and optional external model calls.
The project still runs locally without network access or secrets. No automatic
remediation, data mutation, trading decision, or guaranteed diagnosis is in
scope. The user tests offline behavior before configuring any live provider.
