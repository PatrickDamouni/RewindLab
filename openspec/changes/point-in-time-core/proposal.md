# Proposal: point-in-time core

## Why

A latest-value query can leak a late correction into a historical analysis.
RewindLab needs a small, reproducible demonstration of what was known at a
chosen time before adding distributed failure modes or an AI analyst.

## What Changes

- Store immutable revisions of synthetic observations with event time
  (`valid_at`) and knowledge time (`known_at`).
- Query a snapshot for an event-time cutoff and knowledge-time cutoff, returning
  one latest known revision per event with provenance.
- Make an identical single-revision retry a no-op and reject conflicting IDs.
- Provide a deterministic short demo that contrasts a latest-only snapshot with
  the historical point-in-time snapshot.

## Capabilities

### New Capabilities

- `point-in-time-data`: observable two-time snapshot behavior and provenance.
- `event-revisions`: immutable revisions and idempotent single-revision retries.

### Modified Capabilities

None; this is the first product capability.

## Impact

Phase 1 is a local Python 3.14 standard-library CLI with SQLite persistence,
deterministic synthetic fixtures, and focused tests. It needs no account,
credential, model call, dashboard, live feed, or remote database. Phase 2 owns
atomic multi-record import, order-independent digest, fault corpus, and
benchmark; Phase 3 owns Hermes and OmniRoute.
