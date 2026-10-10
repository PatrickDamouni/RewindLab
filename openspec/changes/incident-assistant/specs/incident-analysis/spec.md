# Spec Delta: incident analysis

## Purpose

Incident analysis turns a reproducible corpus run and its injected condition
into a cited explanation while keeping model output separate from the system's
correctness oracle.

## ADDED Requirements

### Requirement: Read-only evidence bundle
The system SHALL export a versioned incident bundle containing case ID, seed,
observed mismatch, expected result, relevant event IDs, and integrity digest.
Analysis SHALL not modify the source dataset or oracle.

#### Scenario: Bundle generated
- **WHEN** a corpus case is selected for analysis
- **THEN** the bundle identifies the exact run and evidence needed to inspect
  the condition and observed outcome

#### Scenario: Analysis completes
- **WHEN** an offline or live report is produced
- **THEN** the dataset and oracle digests remain unchanged

### Requirement: Offline dry run
The system SHALL produce a clearly labeled deterministic report preview from
an evidence bundle without network access or provider credentials.

#### Scenario: No provider configured
- **WHEN** the user runs the offline path on a fresh checkout
- **THEN** it produces a report preview and explains that no model was called

### Requirement: Optional live analyst
When configured, the system SHALL pass only a selected read-only analyst view
derived from the evidence bundle to Hermes Agent via OmniRoute and SHALL treat
its response as a proposed diagnosis, not an authoritative correction.

#### Scenario: Provider unavailable
- **WHEN** live analysis is requested but configuration or connectivity is unavailable
- **THEN** the command fails clearly without changing data or losing the evidence bundle

#### Scenario: Live diagnosis returned
- **WHEN** live analysis succeeds
- **THEN** the report identifies the provider path, fault hypothesis, cited evidence IDs, and uncertainty

### Requirement: Checkable report
Each report SHALL identify evidence IDs for factual claims and SHALL compare
its fault category with the corpus oracle when an oracle label exists.

#### Scenario: Unsupported claim
- **WHEN** a report cites an ID absent from its evidence bundle
- **THEN** validation flags the citation as unsupported

#### Scenario: Oracle comparison
- **WHEN** a labeled fault case is analyzed
- **THEN** the report records whether its proposed category matches the expected category
