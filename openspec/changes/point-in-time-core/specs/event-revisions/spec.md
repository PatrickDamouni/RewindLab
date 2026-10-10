# Spec Delta: event revisions

## Purpose

Immutable event revisions retain the evidence behind every snapshot, while
allowing safe retries of an individual revision without duplicating it.

## ADDED Requirements

### Requirement: Immutable revision history
Once accepted, a revision SHALL remain available for inspection and SHALL not
be updated or deleted through the revision store.

#### Scenario: Earlier revision remains inspectable
- **WHEN** a correction is appended to an event
- **THEN** the original and corrected revisions remain in history

#### Scenario: Mutation attempted
- **WHEN** a caller tries to update or delete an accepted revision
- **THEN** the store rejects the mutation

### Requirement: Idempotent single-revision retry
Appending an identical revision ID and payload SHALL be a no-op. Reusing an
existing revision ID with different content SHALL fail clearly.

#### Scenario: Identical revision arrives twice
- **WHEN** the same revision is appended again
- **THEN** history still contains one copy of it

#### Scenario: Revision ID collision
- **WHEN** an existing revision ID is reused with a different payload
- **THEN** the append reports a conflict

### Requirement: Unambiguous event knowledge time
One event ID SHALL not have two different revisions with the same `known_at`.

#### Scenario: Equal knowledge timestamps
- **WHEN** a different revision for an event uses an already accepted `known_at`
- **THEN** the append reports a conflict instead of choosing by arrival order
