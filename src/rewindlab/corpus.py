"""Deterministic synthetic fault corpus and an independent Python oracle."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any

from .store import BatchValidationError, RevisionStore


DEFAULT_SEED = 1729
CASE_IDS = ("baseline", "duplicate", "out_of_order", "malformed_schema", "late_correction", "interrupted_import")
VALID_CUTOFF = "2025-01-03T23:59:59.000000Z"
KNOWLEDGE_CUTOFFS = (
    "2025-01-04T00:00:00.000000Z",
    "2025-01-09T08:00:00.000000Z",
    "2025-01-09T12:00:00.000000Z",
    "2025-01-10T12:00:00.000000Z",
)


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generated_case(case_id: str, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """Generate only synthetic events; the same seed always yields the same bytes."""
    if case_id not in CASE_IDS:
        raise ValueError(f"Unknown corpus case: {case_id}")
    values = [base + hashlib.sha256(f"{seed}:{index}".encode("ascii")).digest()[0] % 20
              for index, base in enumerate((100, 200, 900, 300))]
    source = f"synthetic:rewindlab-seed-{seed}"

    def event(revision_id: str, event_id: str, valid_at: str, known_at: str, value: int) -> dict[str, str | int]:
        return {"revision_id": revision_id, "event_id": event_id, "valid_at": valid_at,
                "known_at": known_at, "signal_value": value, "source": source}

    rows = [
        event("a-original", "event-a", "2025-01-01T12:00:00.000000Z", "2025-01-02T09:00:00.000000Z", values[0]),
        event("b-original", "event-b", "2025-01-02T12:00:00.000000Z", "2025-01-03T09:00:00.000000Z", values[1]),
        event("a-corrected", "event-a", "2025-01-01T12:00:00.000000Z", "2025-01-09T09:00:00.000000Z", values[2]),
        event("c-late", "event-c", "2025-01-03T12:00:00.000000Z", "2025-01-10T09:00:00.000000Z", values[3]),
    ]
    preload: list[dict[str, Any]] = []
    deliveries: list[dict[str, Any]] = rows[:2]
    if case_id == "duplicate":
        deliveries = [rows[0], rows[0], rows[1]]
    elif case_id == "out_of_order":
        deliveries.reverse()
    elif case_id == "late_correction":
        deliveries = rows[:3]
    elif case_id == "malformed_schema":
        preload = rows[:2]
        invalid = dict(rows[3])
        del invalid["known_at"]
        deliveries = [rows[2], invalid]
    elif case_id == "interrupted_import":
        preload = rows[:2]
        deliveries = rows[2:]
    return {"case_id": case_id, "seed": seed, "source_type": "synthetic",
            "preload": preload, "deliveries": deliveries}


def _logical_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Oracle's final row set, independent of SQLite and production query code."""
    deliveries = [] if case["case_id"] == "malformed_schema" else case["deliveries"]
    by_id = {row["revision_id"]: row for row in case["preload"] + deliveries}
    return sorted(by_id.values(), key=lambda row: row["revision_id"])


def _oracle_probe(rows: list[dict[str, Any]], known_through: str) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["known_at"] <= known_through:
            previous = latest.get(row["event_id"])
            if previous is None or (row["known_at"], row["revision_id"]) > (previous["known_at"], previous["revision_id"]):
                latest[row["event_id"]] = row
    selected = sorted(
        (row for row in latest.values() if row["valid_at"] <= VALID_CUTOFF),
        key=lambda row: (row["valid_at"], row["event_id"]),
    )
    return {"known_through": known_through, "record_count": len(selected),
            "signal_sum": sum(row["signal_value"] for row in selected),
            "revision_ids": [row["revision_id"] for row in selected]}


def oracle(case_id: str, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """Expected results use plain lists/dicts, never RevisionStore.snapshot."""
    case = generated_case(case_id, seed)
    rows = _logical_rows(case)
    probes = [_oracle_probe(rows, cutoff) for cutoff in KNOWLEDGE_CUTOFFS]
    return {"case_id": case_id, "seed": seed, "source_type": "synthetic",
            "delivery_digest": _digest(case["deliveries"]),
            "event_set_digest": _digest(rows),
            "dataset_digest": _digest(rows),
            "result_digest": _digest(probes),
            "row_count": len(rows),
            "import_status": "rejected" if case_id == "malformed_schema" else
                             "interrupted_then_recovered" if case_id == "interrupted_import" else "accepted",
            "probes": probes}


def checked_oracle(case_id: str, seed: int) -> dict[str, Any]:
    if seed != DEFAULT_SEED:
        return oracle(case_id, seed)
    fixture = files("rewindlab").joinpath("data/oracle_seed_1729.json")
    manifest = json.loads(fixture.read_text(encoding="utf-8"))
    return manifest[case_id]


def _interrupt_worker(database: Path, payload: Path) -> None:
    """Test harness only: terminate after SQLite has reached pre-commit."""
    deliveries = json.loads(payload.read_text(encoding="utf-8"))
    with RevisionStore(database) as store:
        def interrupt_on_commit(statement: str) -> None:
            if statement.strip().upper() == "RELEASE SAVEPOINT REWINDLAB_IMPORT_BATCH":
                os._exit(86)
        store.connection.set_trace_callback(interrupt_on_commit)
        store.import_batch(deliveries)
    os._exit(87)


def _recovery_worker(database: Path, payload: Path) -> None:
    deliveries = json.loads(payload.read_text(encoding="utf-8"))
    with RevisionStore(database) as store:
        store.import_batch(deliveries)
        print(store.dataset_digest(), flush=True)


def _interrupted_replay(database: Path, deliveries: list[dict[str, Any]], previous_digest: str) -> dict[str, Any]:
    payload = database.with_suffix(".json")
    payload.write_text(json.dumps(deliveries), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "rewindlab.corpus", "--interrupt-worker", str(database), str(payload)],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if result.returncode != 86:
        raise RuntimeError(f"Interruption worker exited {result.returncode}, expected 86: {result.stderr}")
    with RevisionStore(database) as store:
        after_interrupt = store.dataset_digest()
        if after_interrupt != previous_digest:
            raise RuntimeError("Interrupted import left partial rows visible")
        store.import_batch(deliveries)
        return {"exit_code": result.returncode, "before_digest": previous_digest,
                "after_interrupt_digest": after_interrupt,
                "recovered_digest": store.dataset_digest()}


def _first_mismatch(expected: dict[str, Any], observed: dict[str, Any]) -> str | None:
    for key in ("delivery_digest", "event_set_digest", "dataset_digest", "row_count", "import_status"):
        if expected[key] != observed[key]:
            return f"{key}: expected {expected[key]!r}, observed {observed[key]!r}"
    for index, (left, right) in enumerate(zip(expected["probes"], observed["probes"])):
        for key in ("known_through", "record_count", "signal_sum", "revision_ids"):
            if left[key] != right[key]:
                return f"probe[{index}].{key}: expected {left[key]!r}, observed {right[key]!r}"
    if len(expected["probes"]) != len(observed["probes"]):
        return "probe count differs"
    if expected["result_digest"] != observed["result_digest"]:
        return f"result_digest: expected {expected['result_digest']!r}, observed {observed['result_digest']!r}"
    return None


def run_case(case_id: str, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    case = generated_case(case_id, seed)
    expected = checked_oracle(case_id, seed)
    with tempfile.TemporaryDirectory(prefix="rewindlab-corpus-") as directory:
        database = Path(directory) / "case.sqlite"
        with RevisionStore(database) as store:
            store.import_batch(case["preload"])
            previous_digest = store.dataset_digest()
        import_error = None
        recovery_evidence = None
        if case_id == "interrupted_import":
            recovery_evidence = _interrupted_replay(database, case["deliveries"], previous_digest)
            final_digest = recovery_evidence["recovered_digest"]
            import_status = "interrupted_then_recovered"
        else:
            with RevisionStore(database) as store:
                try:
                    store.import_batch(case["deliveries"])
                    import_status = "accepted"
                except ValueError as exc:
                    import_status = (
                        "rejected" if case_id == "malformed_schema"
                        and type(exc) is BatchValidationError
                        and exc.row_index == 1
                        and exc.detail == "Missing revision fields: known_at"
                        else "unexpected_rejection"
                    )
                    import_error = str(exc)
                final_digest = store.dataset_digest()
        with RevisionStore(database) as store:
            rows = [row.to_dict() for row in store.all_revisions()]
            probes = []
            for cutoff in KNOWLEDGE_CUTOFFS:
                selection = store.snapshot(VALID_CUTOFF, cutoff)
                probes.append({"known_through": cutoff, "record_count": len(selection),
                               "signal_sum": sum(row.signal_value for row in selection),
                               "revision_ids": [row.revision_id for row in selection]})
    observed = {"case_id": case_id, "seed": seed, "source_type": "synthetic",
                "delivery_digest": _digest(case["deliveries"]),
                "event_set_digest": _digest(sorted(rows, key=lambda row: row["revision_id"])),
                "dataset_digest": final_digest, "result_digest": _digest(probes),
                "row_count": len(rows), "import_status": import_status, "probes": probes}
    mismatch = _first_mismatch(expected, observed)
    return {"case_id": case_id, "seed": seed, "source_type": "synthetic",
            "passed": mismatch is None, "first_mismatch": mismatch,
            "import_error": import_error, "recovery_evidence": recovery_evidence,
            "input_evidence": {"preload_events": case["preload"],
                               "delivery_events": case["deliveries"]},
            "expected": expected, "observed": observed}


def run_all(seed: int = DEFAULT_SEED) -> dict[str, Any]:
    cases = [run_case(case_id, seed) for case_id in CASE_IDS]
    return {"seed": seed, "source_type": "synthetic",
            "passed": all(case["passed"] for case in cases), "cases": cases}


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--interrupt-worker":
        _interrupt_worker(Path(sys.argv[2]), Path(sys.argv[3]))
    if len(sys.argv) == 4 and sys.argv[1] == "--recovery-worker":
        _recovery_worker(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise SystemExit("corpus worker is internal")
