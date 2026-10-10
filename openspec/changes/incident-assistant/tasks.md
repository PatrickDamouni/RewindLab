# Tasks: read-only incident assistant

## 1. Evidence and offline path

- [ ] 1.1 Export versioned evidence bundles with case ID, seed, expected/actual outputs, relevant event IDs, and a digest. Verify bundle generation leaves database and oracle digests unchanged.
- [ ] 1.2 Produce a deterministic offline preview clearly marked as non-AI output. Verify it works from a fresh checkout without network access or credentials.
- [ ] 1.3 Validate report citations and compare proposed fault category with the oracle. Verify an invented event ID is flagged.

## 2. Optional Hermes and OmniRoute path

- [ ] 2.1 Read current documentation and checked-out source for the actual Hermes invocation, read-only tool controls, and OmniRoute configuration. Record supported versions and a minimal smoke test before implementing the adapter.
- [ ] 2.2 Add an opt-in live adapter that passes only selected evidence and stores no secrets in code or logs. Verify missing configuration and provider failure preserve the dataset and evidence.
- [ ] 2.3 Evaluate live reports against labeled corpus cases and publish category agreement and citation-validity counts with the exact model/configuration used.

## 3. User test gate

- [ ] 3.1 User runs the offline preview and checks one report against the underlying events. Optional live setup follows only after credentials are configured outside the repo and a small smoke test succeeds.
