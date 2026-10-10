# Tasks: read-only incident assistant

## 1. Evidence and offline path

- [x] 1.1 Export versioned evidence bundles with case ID, seed, expected/actual outputs, relevant event IDs, and a digest. Verified a generated bundle is stable and the oracle fixture digest stays unchanged.
- [x] 1.2 Produce a deterministic offline preview clearly marked as non-AI output. Verified all six corpus cases without network access or credentials.
- [x] 1.3 Validate report citations and compare proposed fault category with the oracle. Tests flag forged and missing evidence IDs and category disagreement.

## 2. Optional Hermes and OmniRoute path

- [x] 2.1 Read checked-out Hermes `3eb7ed08` and OmniRoute `02f2f00e` docs/source for CLI, zero-tool config, and local endpoint. The live adapter passed a canned-mock transport smoke; a real-provider/model smoke remains unrun until an eligible provider exists.
- [x] 2.2 Add an opt-in live adapter that passes only selected evidence and stores no secrets in code or logs. Mocked missing configuration, provider failure, timeout, malformed output, and child environment checks pass; saved evidence survives a missing-key failure.
- [ ] 2.3 Evaluate live reports against labeled corpus cases and publish category agreement and citation-validity counts with the exact model/configuration used.

## 3. User test gate

- [ ] 3.1 User runs the offline preview and checks one report against the underlying events. Optional live setup follows only after credentials are configured outside the repo and a small smoke test succeeds.
