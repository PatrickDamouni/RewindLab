# Spec Delta: point-in-time data

## Purpose

Point-in-time snapshots preserve the distinction between when an event was
effective and when its current revision became known, making historical
answers inspectable without retroactive corrections leaking into them.

## ADDED Requirements

### Requirement: Two-time event revisions
Each event revision SHALL contain an event ID, revision ID, effective timestamp
(`valid_at`), knowledge timestamp (`known_at`), source, and integer signal
value. Timestamps SHALL include an offset and be normalized to UTC.

#### Scenario: Valid revision
- **WHEN** a revision has all required fields and timezone-aware timestamps
- **THEN** it is available to snapshots at or after its `known_at`

#### Scenario: Invalid timestamp
- **WHEN** a revision omits a timestamp or supplies a time without an offset
- **THEN** ingestion fails with a clear diagnostic

### Requirement: Historical snapshot
For a target `valid_through` and `known_through`, the system SHALL select the
latest revision known by the knowledge cutoff for each event ID, then include
only selected revisions whose `valid_at` is within the effective-time cutoff.

#### Scenario: Late correction excluded
- **WHEN** an event has a correction known after the cutoff
- **THEN** the historical snapshot contains the earlier revision

#### Scenario: Late correction included
- **WHEN** the cutoff includes the correction's `known_at`
- **THEN** the snapshot contains the corrected revision for that event

#### Scenario: Late arrival excluded
- **WHEN** an event's first revision is known after the cutoff
- **THEN** the historical snapshot omits that event

#### Scenario: Correction moves event out of range
- **WHEN** the latest known revision moves an event's `valid_at` past the effective-time cutoff
- **THEN** the snapshot omits that event rather than reviving its earlier revision

### Requirement: Latest-only comparison
The system SHALL permit a latest-only snapshot for comparison by omitting the
knowledge cutoff, and SHALL make that mode identifiable in output.

#### Scenario: Current knowledge differs
- **WHEN** a correction and late arrival occurred after a historical knowledge cutoff
- **THEN** the latest-only snapshot can differ from the historical snapshot

### Requirement: Snapshot provenance
Every returned record SHALL include its event ID, revision ID, `valid_at`,
`known_at`, source, and value. A query with no qualifying events SHALL return
an explicit empty result.

#### Scenario: Inspect selected revisions
- **WHEN** a snapshot is returned
- **THEN** the selected revision identities and both timestamps are inspectable

### Requirement: Honest comparison demo
The demo SHALL use a fixed, labeled synthetic fixture and display the
historical snapshot beside the latest-only snapshot for the same valid cutoff.

#### Scenario: Demo is run twice
- **WHEN** the supplied demo runs twice without changing code or fixture
- **THEN** its machine-readable reports agree and show the correction and late arrival
