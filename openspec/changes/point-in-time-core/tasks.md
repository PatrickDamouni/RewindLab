# Tasks: point-in-time core

## 1. Local package and revision store

- [x] 1.1 Create a runnable Python 3.14 CLI, SQLite schema, and documented local setup. Verify a fresh checkout runs without network access or secrets.
- [x] 1.2 Parse required revision fields and normalize timezone-aware timestamps. Verify missing fields and naive timestamps fail clearly.
- [x] 1.3 Enforce immutable rows, unique revision IDs, and one revision per event/knowledge time. Verify direct update/delete attempts and conflicting IDs fail.
- [x] 1.4 Make an identical single-revision retry a no-op. Verify history retains one copy.

## 2. Snapshots and demo

- [x] 2.1 Select the latest known revision per event before applying the valid cutoff. Verify correction, late-arrival, moved-valid-time, and no-match cases.
- [x] 2.2 Return revision provenance and expose a clearly identifiable latest-only comparison path. Verify output contains IDs and both timestamps.
- [x] 2.3 Add a fixed synthetic fixture and a short side-by-side demo. Verify repeated JSON demo output is identical and the expected signal sums are 300 and 1400.

## 3. User test gate

- [x] 3.1 Document exact demo and test commands, expected output, and fixture semantics in the README.
- [ ] 3.2 Run focused tests from a clean checkout. The user runs the demo and confirms the historical versus latest-only result before Phase 2 begins. Local checks passed (9 core tests, 5 integration tests); user gate pending.
