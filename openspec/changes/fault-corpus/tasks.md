# Tasks: fault corpus and measurements

## 1. Batch replay foundation

- [x] 1.1 Add atomic multi-record import. Verify a bad later row or conflicting revision leaves the previous dataset unchanged.
- [x] 1.2 Add a canonical SHA-256 dataset digest. Verify reversed input order and duplicate retries preserve snapshots and digest.

## 2. Deterministic corpus

- [x] 2.1 Add seeded case generation and a checked-in oracle manifest independent of production query code. Verify rerunning a case and seed produces matching event and oracle digests.
- [x] 2.2 Add duplicate, out-of-order, malformed-schema, and late-correction cases. Verify all query probes, row counts, and digests match the oracle.
- [x] 2.3 Add a controlled pre-commit interruption in a child process and replay recovery test. Verify no partial rows are visible and retry reaches the oracle state.

## 3. Measurement

- [x] 3.1 Add a repeatable benchmark command with monotonic raw timing samples and documented metric definitions. Verify report generation on a fresh checkout.
- [x] 3.2 Publish one actual run with the exact command, seed, input size, machine details, raw samples, and summary. Check that no metric is calculated from simulated historical time.

## 4. User test gate

- [ ] 4.1 Run every fault case twice from clean stores and compare reports. The corpus reports match byte for byte; user inspection remains available in `docs/corpus/seed-1729.json`.
