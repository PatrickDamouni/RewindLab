"""Measured local SQLite ingest and interrupted-process recovery workload."""

from __future__ import annotations

import json
import os
import platform
import random
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .corpus import DEFAULT_SEED, generated_case, oracle
from .store import RevisionStore


def _workload(seed: int, event_count: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [
        {"revision_id": f"bench-{index:08d}", "event_id": f"event-{index:08d}",
         "valid_at": "2025-01-01T12:00:00.000000Z",
         "known_at": "2025-01-02T12:00:00.000000Z",
         "signal_value": rng.randrange(-1000, 1001),
         "source": f"synthetic:rewindlab-benchmark-seed-{seed}"}
        for index in range(event_count)
    ]


def _p95_ns(samples: list[int]) -> int | None:
    if not samples:
        return None
    ordered = sorted(samples)
    rank = (95 * len(ordered) + 99) // 100
    return ordered[rank - 1]


def _ingest_once(events: list[dict[str, Any]], batch_size: int, database: Path) -> dict[str, Any]:
    samples: list[int] = []
    with RevisionStore(database) as store:
        sqlite_mode = store.connection.execute("PRAGMA journal_mode").fetchone()[0]
        start = time.perf_counter_ns()
        for offset in range(0, len(events), batch_size):
            batch_start = time.perf_counter_ns()
            inserted, duplicate = store.import_batch(events[offset:offset + batch_size])
            samples.append(time.perf_counter_ns() - batch_start)
            if duplicate or inserted != len(events[offset:offset + batch_size]):
                raise RuntimeError("Unexpected duplicate or missing benchmark input")
        elapsed = time.perf_counter_ns() - start
        if len(store.all_revisions()) != len(events):
            raise RuntimeError("Benchmark row count disagrees with accepted inputs")
    return {"elapsed_ns": elapsed, "batch_acknowledgement_ns": samples,
            "accepted_input_events": len(events), "sqlite_journal_mode": sqlite_mode}


def _recovery_once(seed: int, directory: Path) -> int:
    case = generated_case("interrupted_import", seed)
    expected_digest = oracle("interrupted_import", seed)["dataset_digest"]
    database = directory / "recovery.sqlite"
    payload = directory / "recovery.json"
    payload.write_text(json.dumps(case["deliveries"]), encoding="utf-8")
    with RevisionStore(database) as store:
        store.import_batch(case["preload"])
        pre_digest = store.dataset_digest()
    stopped = subprocess.run(
        [sys.executable, "-m", "rewindlab.corpus", "--interrupt-worker", str(database), str(payload)],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if stopped.returncode != 86:
        raise RuntimeError(f"Fault worker exited {stopped.returncode}, expected 86: {stopped.stderr}")
    with RevisionStore(database) as store:
        if store.dataset_digest() != pre_digest:
            raise RuntimeError("Fault worker left partial rows visible")
    start = time.perf_counter_ns()
    recovered = subprocess.run(
        [sys.executable, "-m", "rewindlab.corpus", "--recovery-worker", str(database), str(payload)],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if recovered.returncode != 0:
        raise RuntimeError(f"Recovery worker failed: {recovered.stderr}")
    if recovered.stdout.strip() != expected_digest:
        raise RuntimeError("Recovery worker result disagrees with independent oracle")
    elapsed = time.perf_counter_ns() - start
    return elapsed


def run_benchmark(
    *, seed: int = DEFAULT_SEED, event_count: int = 1000, batch_size: int = 100,
    repetitions: int = 5, warmup: int = 1, command: str = "",
) -> dict[str, Any]:
    if event_count <= 0 or batch_size <= 0 or repetitions <= 0 or warmup < 0:
        raise ValueError("event_count, batch_size, repetitions must be positive; warmup must be nonnegative")
    events = _workload(seed, event_count)
    recovery_case = generated_case("interrupted_import", seed)
    measured: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="rewindlab-bench-") as directory:
        root = Path(directory)
        for index in range(warmup + repetitions):
            sample = _ingest_once(events, batch_size, root / f"ingest-{index}.sqlite")
            if index >= warmup:
                measured.append(sample)
        recovery_ns = _recovery_once(seed, root)
    all_batch_ns = [value for run in measured for value in run["batch_acknowledgement_ns"]]
    total_elapsed_ns = sum(run["elapsed_ns"] for run in measured)
    total_accepted = sum(run["accepted_input_events"] for run in measured)
    return {
        "source_type": "synthetic", "scope": (
            "Local single-process SQLite ingest on this machine. Fixture known_at values are simulated "
            "historical timestamps; they are not live market-data publication lag. "
            "No distributed reliability or trading performance is measured."
        ),
        "command": command,
        "workload": {"seed": seed, "events_per_repetition": event_count, "batch_size": batch_size,
                     "warmup_repetitions_discarded": warmup, "measured_repetitions": repetitions,
                     "sqlite_journal_mode": measured[0]["sqlite_journal_mode"]},
        "recovery_workload": {"case_id": "interrupted_import", "source_type": "synthetic",
                              "preloaded_revisions": len(recovery_case["preload"]),
                              "retried_revisions": len(recovery_case["deliveries"]),
                              "independent_of_ingest_event_count": True},
        "machine": {"os": platform.platform(), "architecture": platform.machine(),
                    "processor": platform.processor() or "unavailable", "cpu_count": os.cpu_count(),
                    "python": platform.python_version(), "sqlite": sqlite3.sqlite_version},
        "definitions": {
            "ingest_elapsed_ns": "Monotonic wall time from just before first measured batch import to just after last batch acknowledgement, per fresh SQLite database; excludes fixture generation, database creation, and post-run row-count check.",
            "throughput_events_per_second": "Accepted input events across measured repetitions divided by their summed ingest elapsed seconds.",
            "p95_batch_acknowledgement_ms": "Nearest-rank 95th percentile of batch import call durations from harness submission to return, across all measured batches. Not per-event latency.",
            "recovery_time_ms": "Monotonic time from launching a new Python recovery process after a controlled pre-commit exit to receiving and confirming its final dataset digest against the independent oracle. Uses a separate two-row retry from the interrupted_import corpus case, independent of --events. Excludes fault creation and pre-restart checks. One sample.",
        },
        "raw_samples": {"ingest_repetitions": measured, "recovery_ns": [recovery_ns]},
        "summary": {"accepted_input_events": total_accepted, "ingest_elapsed_seconds": total_elapsed_ns / 1e9,
                    "throughput_events_per_second": total_accepted / (total_elapsed_ns / 1e9),
                    "p95_batch_acknowledgement_ms": _p95_ns(all_batch_ns) / 1e6 if all_batch_ns else None,
                    "recovery_time_ms": recovery_ns / 1e6},
    }
