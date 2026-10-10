# Spec Delta: batch replay

## Purpose

Batch replay reconstructs the same logical revision history from the same
event set while preventing partial imports after invalid input or interruption.

## ADDED Requirements

### Requirement: Atomic multi-record import
A batch import SHALL either accept every valid revision or leave the prior
dataset unchanged when any revision is invalid or conflicting.

#### Scenario: Malformed later row
- **WHEN** an import contains valid rows followed by a malformed row
- **THEN** no row from that import appears in subsequent snapshots

#### Scenario: Conflicting revision
- **WHEN** a batch includes a revision ID whose existing payload differs
- **THEN** the batch fails and the pre-import dataset remains unchanged

### Requirement: Canonical dataset digest
The system SHALL report a digest of logical revision content that is
independent of import order, SQLite row IDs, and local filesystem paths.

#### Scenario: Input order changes
- **WHEN** two fresh stores ingest the same valid revision set in different orders
- **THEN** their snapshots and reported dataset digests agree

#### Scenario: Exact duplicate delivery
- **WHEN** an identical revision is included twice or retried later
- **THEN** the logical dataset and its digest remain unchanged after the retry

### Requirement: Replay recovery
Retrying a batch after a controlled interruption SHALL reach the same logical
dataset and digest as an uninterrupted import.

#### Scenario: Interrupted before commit
- **WHEN** import stops before its commit and the same batch is retried
- **THEN** the final snapshots and digest match an uninterrupted run
