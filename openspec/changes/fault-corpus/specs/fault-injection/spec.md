# Spec Delta: fault injection

## Purpose

The fault corpus makes data and process failures repeatable so recovery and
historical query correctness can be checked against explicit expected results.

## ADDED Requirements

### Requirement: Reproducible seeded cases
The corpus SHALL produce the same event payloads and expected results for the
same case ID and seed, and SHALL label every event as synthetic.

#### Scenario: Repeat generation
- **WHEN** a user generates the same case with the same seed twice
- **THEN** the two event sets and oracle outputs have matching digests

### Requirement: Delivery perturbations
The corpus SHALL include duplicate and out-of-order delivery cases with
expected query answers and logical record counts.

#### Scenario: Duplicate events
- **WHEN** the duplicate-delivery case is replayed
- **THEN** the final query answers and logical record count match the clean case

#### Scenario: Out-of-order events
- **WHEN** the out-of-order case is replayed
- **THEN** the final answers and dataset digest match the clean case

### Requirement: Invalid input and late corrections
The corpus SHALL include a malformed-schema case that reports a failed import
without partial writes and a late-correction case that checks both sides of the
knowledge cutoff.

#### Scenario: Malformed schema
- **WHEN** the malformed input case is imported
- **THEN** it fails clearly and the pre-import dataset remains unchanged

#### Scenario: Correction after cutoff
- **WHEN** the late-correction case is queried before and after the correction's `known_at`
- **THEN** the answers match the original and corrected oracle values respectively

### Requirement: Interrupted import recovery
The corpus SHALL reproduce an interrupted import and SHALL verify that replay
recovers the expected logical dataset without duplicates.

#### Scenario: Process interruption
- **WHEN** a worker exits during a controlled import before commit
- **THEN** the incomplete import does not become visible and a retry reaches the oracle state
