"""Command-line entry point for the point-in-time data demo."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sqlite3
import sys
from importlib.resources import files
from pathlib import Path
from typing import Sequence

from .store import Revision, RevisionStore, normalize_time
from .corpus import CASE_IDS, DEFAULT_SEED, run_all, run_case
from .benchmark import run_benchmark


DEMO_VALID_THROUGH = "2025-01-03T23:59:59Z"
DEMO_KNOWN_THROUGH = "2025-01-04T00:00:00Z"


def load_seed(store: RevisionStore) -> tuple[int, int]:
    """Load a packaged synthetic fixture; exact retries do not add rows."""
    fixture = files("rewindlab").joinpath("data/seed_events.jsonl")
    revisions = []
    for line_number, line in enumerate(fixture.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            revision = Revision.from_dict(json.loads(line))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid seed fixture line {line_number}: {exc}") from exc
        revisions.append(revision)
    return store.import_batch(revisions)


def summarize(records: list[Revision]) -> dict[str, object]:
    return {
        "record_count": len(records),
        "signal_sum": sum(record.signal_value for record in records),
        "records": [record.to_dict() for record in records],
    }


def build_demo_report(store: RevisionStore) -> dict[str, object]:
    valid_cutoff = normalize_time(DEMO_VALID_THROUGH)
    knowledge_cutoff = normalize_time(DEMO_KNOWN_THROUGH)
    late = store.late_revisions(DEMO_VALID_THROUGH, DEMO_KNOWN_THROUGH)
    return {
        "run_id": "synthetic-signals-2025-01-04",
        "dataset": "synthetic-signals-v1",
        "valid_through": valid_cutoff,
        "known_through": knowledge_cutoff,
        "source_events": [revision.to_dict() for revision in store.all_revisions()],
        "as_known": summarize(store.snapshot(DEMO_VALID_THROUGH, DEMO_KNOWN_THROUGH)),
        "latest": summarize(store.snapshot(DEMO_VALID_THROUGH)),
        "corrected_records": [entry for entry in late if entry["change_type"] == "correction"],
        "late_arrivals": [entry for entry in late if entry["change_type"] == "late_arrival"],
    }


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rewindlab", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="Show how later knowledge changes a naive historical query")
    demo.add_argument("--json", action="store_true", help="Emit a machine-readable incident report")

    seed = commands.add_parser("seed", help="Load the deterministic synthetic fixture into a SQLite file")
    seed.add_argument("--database", type=Path, required=True)

    query = commands.add_parser("query", help="Query the SQLite file at a valid-time cutoff")
    query.add_argument("--database", type=Path, required=True)
    query.add_argument("--valid-through", required=True, help="ISO 8601 timestamp with timezone")
    query.add_argument("--known-through", help="ISO 8601 knowledge cutoff; omit for naive latest")

    corpus = commands.add_parser("corpus", help="Run deterministic synthetic failure cases")
    corpus.add_argument("--case", choices=CASE_IDS, help="One case; default runs all")
    corpus.add_argument("--seed", type=int, default=DEFAULT_SEED)
    corpus.add_argument("--json", action="store_true", help="Print full oracle and observed evidence")
    corpus.add_argument("--report", type=Path, help="Save the full JSON report")

    benchmark = commands.add_parser("benchmark", help="Measure a defined local SQLite workload")
    benchmark.add_argument("--seed", type=int, default=DEFAULT_SEED)
    benchmark.add_argument("--events", type=int, default=1000)
    benchmark.add_argument("--batch-size", type=int, default=100)
    benchmark.add_argument("--repetitions", type=int, default=5)
    benchmark.add_argument("--warmup", type=int, default=1)
    benchmark.add_argument("--report", type=Path, required=True, help="Save raw timings and summary as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            with RevisionStore() as store:
                load_seed(store)
                report = build_demo_report(store)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                as_known = report["as_known"]
                latest = report["latest"]
                assert isinstance(as_known, dict) and isinstance(latest, dict)
                print("Synthetic signal data, valid through 2025-01-03")
                print("Knowledge cutoff: 2025-01-04")
                print(f"As known then: {as_known['record_count']} records, signal sum {as_known['signal_sum']}")
                print(f"Naive latest:  {latest['record_count']} records, signal sum {latest['signal_sum']}")
                print("A correction on Jan 9 and a late arrival on Jan 10 changed the naive answer.")
                print("Run `rewindlab demo --json` for the immutable revisions and query outcomes.")
            return 0

        if args.command == "seed":
            with RevisionStore(args.database) as store:
                inserted, duplicate = load_seed(store)
            print(json.dumps({"inserted": inserted, "duplicate_retries": duplicate}))
            return 0

        if args.command == "query":
            if not args.database.is_file():
                raise FileNotFoundError(f"Database file does not exist: {args.database}")
            with RevisionStore(args.database) as store:
                records = store.snapshot(args.valid_through, args.known_through)
            result = {
                "valid_through": normalize_time(args.valid_through),
                "known_through": normalize_time(args.known_through) if args.known_through else None,
                **summarize(records),
            }
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "corpus":
            report = run_case(args.case, args.seed) if args.case else run_all(args.seed)
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            if args.json:
                print(json.dumps(report, indent=2))
            elif args.case:
                print(f"{args.case}: {'PASS' if report['passed'] else 'FAIL'}")
                if report["import_error"]:
                    print(f"Rejected import: {report['import_error']}")
                if report["recovery_evidence"]:
                    print(f"Recovery: {json.dumps(report['recovery_evidence'], sort_keys=True)}")
                if report["first_mismatch"]:
                    print(report["first_mismatch"])
            else:
                for case in report["cases"]:
                    print(f"{case['case_id']}: {'PASS' if case['passed'] else 'FAIL'}")
                    if case["first_mismatch"]:
                        print(f"  {case['first_mismatch']}")
            return 0 if report["passed"] else 1
        if args.command == "benchmark":
            invocation = [sys.executable, "-m", "rewindlab", *(argv if argv is not None else sys.argv[1:])]
            command = shlex.join(invocation)
            if "PYTHONPATH" in os.environ:
                command = f"PYTHONPATH={shlex.quote(os.environ['PYTHONPATH'])} {command}"
            report = run_benchmark(seed=args.seed, event_count=args.events,
                                   batch_size=args.batch_size, repetitions=args.repetitions,
                                   warmup=args.warmup, command=command)
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"report": str(args.report), "summary": report["summary"]}, indent=2))
            return 0
    except (OSError, ValueError, sqlite3.DatabaseError, RuntimeError) as exc:
        print(f"rewindlab: {exc}", file=sys.stderr)
        return 2
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
