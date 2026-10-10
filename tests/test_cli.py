import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from rewindlab.__main__ import main


class DemoCliTests(unittest.TestCase):
    def test_json_demo_exposes_deterministic_replay_gap(self) -> None:
        first = io.StringIO()
        with contextlib.redirect_stdout(first):
            self.assertEqual(main(["demo", "--json"]), 0)
        second = io.StringIO()
        with contextlib.redirect_stdout(second):
            self.assertEqual(main(["demo", "--json"]), 0)

        self.assertEqual(first.getvalue(), second.getvalue())
        report = json.loads(first.getvalue())
        self.assertEqual(report["as_known"]["signal_sum"], 300)
        self.assertEqual(report["latest"]["signal_sum"], 1400)
        self.assertEqual(report["as_known"]["record_count"], 2)
        self.assertEqual(report["latest"]["record_count"], 3)
        self.assertEqual(len(report["corrected_records"]), 1)
        self.assertEqual(len(report["late_arrivals"]), 1)

    def test_query_missing_database_fails_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "missing.sqlite"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = main(
                    ["query", "--database", str(database), "--valid-through", "2025-01-03T00:00:00Z"]
                )
            self.assertEqual(status, 2)
            self.assertIn("does not exist", stderr.getvalue())
            self.assertFalse(database.exists())


if __name__ == "__main__":
    unittest.main()
