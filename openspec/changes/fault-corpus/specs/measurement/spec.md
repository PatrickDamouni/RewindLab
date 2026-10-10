# Spec Delta: measurement

## Purpose

Measurement reports disclose exactly what was timed and checked, so readers
can reproduce results and understand what the benchmark does and does not prove.

## ADDED Requirements

### Requirement: Correctness summary
Each corpus run SHALL report case ID, seed, pass/fail status, expected and
observed result digests, and any mismatched query or record count.

#### Scenario: A case disagrees with its oracle
- **WHEN** actual output differs from the expected output
- **THEN** the report marks the case failed and identifies the first mismatch

### Requirement: Reproducible timing report
The benchmark SHALL report workload size, command, runtime version, machine
details, elapsed time, throughput, p95 processing latency, and recovery time
for cases where interruption applies. It SHALL define each metric in the report.

#### Scenario: Benchmark completes
- **WHEN** a benchmark run finishes
- **THEN** raw timing samples and a summary with units are saved for inspection

#### Scenario: A metric does not apply
- **WHEN** a case has no interruption or no timing samples for a metric
- **THEN** the report marks that metric as not applicable instead of inventing a value

### Requirement: Evidence scope
The report SHALL state that synthetic fixture timestamps do not measure live
market-data publication lag and that results apply to the documented local
workload and machine.

#### Scenario: Reader inspects report
- **WHEN** a reader opens a benchmark report
- **THEN** the synthetic source and measurement scope are visible near the results
