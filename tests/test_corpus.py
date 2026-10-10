import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from rewindlab import BatchValidationError, ConflictingRevisionError, Revision, RevisionStore
from rewindlab.__main__ import main
from rewindlab.corpus import CASE_IDS, DEFAULT_SEED, _first_mismatch, generated_case, oracle, run_all, run_case


class BatchReplayTests(unittest.TestCase):
    def test_bad_later_row_rolls_back_entire_batch(self) -> None:
        rows = generated_case("baseline")["deliveries"]
        bad = dict(rows[1])
        del bad["known_at"]
        with RevisionStore() as store:
            original_digest = store.dataset_digest()
            with self.assertRaisesRegex(BatchValidationError, "known_at") as caught:
                store.import_batch([rows[0], bad])
            self.assertEqual(caught.exception.row_index, 1)
            self.assertEqual(caught.exception.detail, "Missing revision fields: known_at")
            self.assertEqual(store.dataset_digest(), original_digest)
            self.assertEqual(store.all_revisions(), [])

    def test_conflict_rolls_back_earlier_row(self) -> None:
        rows = generated_case("baseline")["deliveries"]
        with RevisionStore() as store:
            store.append(Revision.from_dict(rows[0]))
            original_digest = store.dataset_digest()
            conflict = dict(rows[0])
            conflict["signal_value"] += 1
            with self.assertRaises(ConflictingRevisionError):
                store.import_batch([rows[1], conflict])
            self.assertEqual(store.dataset_digest(), original_digest)
            self.assertEqual(len(store.all_revisions()), 1)

    def test_order_and_exact_retries_preserve_digest_and_snapshot(self) -> None:
        rows = generated_case("baseline")["deliveries"]
        with RevisionStore() as first, RevisionStore() as second:
            self.assertEqual(first.import_batch(rows), (4, 0))
            self.assertEqual(second.import_batch(list(reversed(rows))), (4, 0))
            self.assertEqual(first.import_batch([rows[0], rows[0]]), (0, 2))
            self.assertEqual(first.dataset_digest(), second.dataset_digest())
            self.assertEqual(first.snapshot("2025-01-03T23:59:59Z", "2025-01-04T00:00:00Z"),
                             second.snapshot("2025-01-03T23:59:59Z", "2025-01-04T00:00:00Z"))

    def test_successful_batch_does_not_commit_caller_transaction(self) -> None:
        rows = generated_case("baseline")["deliveries"]
        with RevisionStore() as store:
            store.connection.execute("BEGIN")
            store.import_batch(rows[:2])
            self.assertTrue(store.connection.in_transaction)
            self.assertEqual(len(store.all_revisions()), 2)
            store.connection.rollback()
            self.assertEqual(store.all_revisions(), [])

    def test_failed_batch_preserves_uncommitted_outer_write(self) -> None:
        rows = generated_case("baseline")["deliveries"]
        invalid = dict(rows[3])
        del invalid["known_at"]
        with RevisionStore() as store:
            store.connection.execute("BEGIN")
            store.import_batch([rows[0]])
            with self.assertRaisesRegex(BatchValidationError, "known_at") as caught:
                store.import_batch([rows[1], invalid])
            self.assertEqual(caught.exception.row_index, 1)
            self.assertTrue(store.connection.in_transaction)
            self.assertEqual([row.revision_id for row in store.all_revisions()], ["a-original"])
            store.connection.commit()
            self.assertEqual([row.revision_id for row in store.all_revisions()], ["a-original"])

    def test_signal_value_is_bounded_to_sqlite_signed_integer(self) -> None:
        row = generated_case("baseline")["deliveries"][0]
        with RevisionStore() as store:
            for value in (-(1 << 63), (1 << 63) - 1):
                candidate = dict(row)
                candidate["revision_id"] = f"boundary-{value}"
                candidate["event_id"] = f"boundary-event-{value}"
                candidate["signal_value"] = value
                store.import_batch([candidate])
            for value in (-(1 << 63) - 1, 1 << 63):
                candidate = dict(row)
                candidate["signal_value"] = value
                with self.assertRaisesRegex(ValueError, "signed SQLite 64-bit"):
                    store.import_batch([candidate])
            self.assertEqual(len(store.all_revisions()), 2)


class CorpusTests(unittest.TestCase):
    def test_checked_oracle_matches_independent_generation(self) -> None:
        manifest = json.loads(files("rewindlab").joinpath("data/oracle_seed_1729.json").read_text())
        self.assertEqual(set(manifest), set(CASE_IDS))
        for case_id in CASE_IDS:
            self.assertEqual(manifest[case_id], oracle(case_id, DEFAULT_SEED))
            self.assertEqual(generated_case(case_id), generated_case(case_id))

    def test_query_mismatch_names_the_first_probe_and_field(self) -> None:
        expected = oracle("baseline")
        observed = json.loads(json.dumps(expected))
        observed["probes"][1]["signal_sum"] += 1
        observed["result_digest"] = "incorrect"
        self.assertIn("probe[1].signal_sum", _first_mismatch(expected, observed))

    def test_all_cases_repeat_with_identical_reports(self) -> None:
        first = run_all(DEFAULT_SEED)
        second = run_all(DEFAULT_SEED)
        self.assertEqual(first, second)
        self.assertTrue(first["passed"])
        self.assertEqual(len(first["cases"]), 6)
        baseline = first["cases"][0]["observed"]
        for case in first["cases"]:
            if case["case_id"] in ("duplicate", "out_of_order", "interrupted_import"):
                self.assertEqual(case["observed"]["dataset_digest"], baseline["dataset_digest"])
        late = run_case("late_correction")["observed"]["probes"]
        self.assertNotEqual(late[1]["signal_sum"], late[2]["signal_sum"])
        self.assertEqual(late[2]["signal_sum"], late[3]["signal_sum"])
        malformed = run_case("malformed_schema")
        self.assertIn("known_at", malformed["import_error"])
        self.assertEqual(malformed["observed"]["row_count"], 2)
        recovery = run_case("interrupted_import")
        self.assertEqual(recovery["recovery_evidence"]["exit_code"], 86)
        self.assertEqual(recovery["recovery_evidence"]["before_digest"],
                         recovery["recovery_evidence"]["after_interrupt_digest"])

    def test_unrelated_value_error_cannot_pass_malformed_case(self) -> None:
        original = RevisionStore.import_batch

        def unrelated_error(store: RevisionStore, rows: list[dict[str, object]]) -> tuple[int, int]:
            if any("known_at" not in row for row in rows):
                raise ValueError("unrelated failure")
            return original(store, rows)

        with patch.object(RevisionStore, "import_batch", unrelated_error):
            report = run_case("malformed_schema")
        self.assertFalse(report["passed"])
        self.assertEqual(report["observed"]["import_status"], "unexpected_rejection")
        self.assertIn("import_status", report["first_mismatch"])

    def test_expected_error_text_on_first_valid_row_cannot_pass_malformed_case(self) -> None:
        original = RevisionStore.import_batch

        def early_error(store: RevisionStore, rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
            if any("known_at" not in row for row in rows):
                next(iter(rows))
                raise BatchValidationError(0, "Missing revision fields: known_at")
            return original(store, rows)

        with patch.object(RevisionStore, "import_batch", early_error):
            report = run_case("malformed_schema")
        self.assertFalse(report["passed"])
        self.assertEqual(report["observed"]["import_status"], "unexpected_rejection")
        self.assertIn("import_status", report["first_mismatch"])

    def test_buffered_same_text_value_error_cannot_pass_malformed_case(self) -> None:
        original = RevisionStore.import_batch

        def buffered_error(store: RevisionStore, rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
            if any("known_at" not in row for row in rows):
                list(rows)
                raise ValueError("Missing revision fields: known_at")
            return original(store, rows)

        with patch.object(RevisionStore, "import_batch", buffered_error):
            report = run_case("malformed_schema")
        self.assertFalse(report["passed"])
        self.assertEqual(report["observed"]["import_status"], "unexpected_rejection")

    def test_corpus_cli_report_and_benchmark_raw_samples(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            corpus_path = Path(directory) / "corpus.json"
            benchmark_path = Path(directory) / "benchmark.json"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["corpus", "--case", "malformed_schema", "--report", str(corpus_path)]), 0)
                self.assertEqual(main(["benchmark", "--events", "20", "--batch-size", "5",
                                       "--repetitions", "2", "--warmup", "0",
                                       "--report", str(benchmark_path)]), 0)
            self.assertIn("Rejected import", output.getvalue())
            self.assertTrue(json.loads(corpus_path.read_text())["passed"])
            report = json.loads(benchmark_path.read_text())
            self.assertEqual(report["summary"]["accepted_input_events"], 40)
            self.assertEqual(len(report["raw_samples"]["ingest_repetitions"]), 2)
            self.assertEqual(len(report["raw_samples"]["ingest_repetitions"][0]["batch_acknowledgement_ns"]), 4)
            self.assertGreater(report["summary"]["recovery_time_ms"], 0)
            self.assertEqual(report["recovery_workload"]["preloaded_revisions"], 2)
            self.assertEqual(report["recovery_workload"]["retried_revisions"], 2)
            self.assertTrue(report["recovery_workload"]["independent_of_ingest_event_count"])
            self.assertIn("not live market-data publication lag", report["scope"])


if __name__ == "__main__":
    unittest.main()
