"""Run a sourced, three-vintage BLS point-in-time example without network access."""

from __future__ import annotations

import json
from pathlib import Path

from rewindlab.store import Revision, RevisionStore


DATA_FILE = Path(__file__).with_name("revisions.jsonl")
VALID_THROUGH = "2025-05-31T23:59:59Z"
CHECKPOINTS = (
    ("2025-06-20T00:00:00Z", 139_000),
    ("2025-07-15T00:00:00Z", 144_000),
    ("2025-09-01T00:00:00Z", 19_000),
)


def main() -> None:
    with RevisionStore() as store:
        for line_number, line in enumerate(DATA_FILE.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                revision = Revision.from_dict(json.loads(line))
                store.append(revision)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid BLS fixture on line {line_number}: {exc}") from exc

        print("BLS CES total nonfarm monthly employment change, May 2025")
        print("Seasonally adjusted; values are changes in payroll jobs, not levels.")
        for cutoff, expected in CHECKPOINTS:
            rows = store.snapshot(valid_through=VALID_THROUGH, known_through=cutoff)
            if len(rows) != 1 or rows[0].signal_value != expected:
                raise AssertionError(
                    f"As of {cutoff}: expected one value of {expected}, got {rows!r}"
                )
            print(f"As of {cutoff[:10]}: {rows[0].signal_value:+,}  ({rows[0].source})")

    print("Self-check passed: 139,000 → 144,000 → 19,000.")
    print("Known times are official release-time proxies, not researcher receipt times.")


if __name__ == "__main__":
    main()
