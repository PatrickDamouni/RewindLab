"""Offline behavior and live-process isolation checks for incident reviews."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import review_incident


PROJECT = Path(__file__).resolve().parent.parent
SCRIPT = Path(review_incident.__file__).resolve()


class ReviewIncidentTests(unittest.TestCase):
    def test_core_demo_json_pipes_into_offline_packet(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT / "src")
        env.pop("OMNIROUTE_API_KEY", None)
        demo = subprocess.run(
            [sys.executable, "-m", "rewindlab", "demo", "--json"],
            cwd=PROJECT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        review = subprocess.run(
            [sys.executable, str(SCRIPT), "-"],
            input=demo.stdout,
            cwd=PROJECT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("synthetic-signals-2025-01-04", review.stdout)
        self.assertIn('"late_arrivals"', review.stdout)
        self.assertIn("What is still unknown", review.stdout)

    def test_bad_json_and_non_object_fail_cleanly(self) -> None:
        for payload, message in (("{", "UTF-8 JSON"), ("[]", "JSON object")):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "incident.json"
                path.write_text(payload, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), str(path)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)

    def test_oversized_snapshot_is_rejected_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            path.write_text('{"text":"' + "x" * review_incident.MAX_SNAPSHOT_BYTES + '"}', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Snapshot exceeds", result.stderr)

    def test_live_requires_key(self) -> None:
        with mock.patch.dict(os.environ, {"OMNIROUTE_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "OMNIROUTE_API_KEY"):
                review_incident.run_live("test prompt")

    def test_live_child_gets_only_scoped_key_and_tool_free_config(self) -> None:
        inspected = False

        def fake_run(args, **kwargs):
            nonlocal inspected
            inspected = True
            self.assertEqual(args[1:], ["chat", "--query-file", "-", "--oneshot", "-Q"])
            self.assertEqual(kwargs["input"], "test prompt")
            child_env = kwargs["env"]
            self.assertEqual(child_env["OMNIROUTE_API_KEY"], "test-local-key")
            self.assertNotIn("OPENAI_API_KEY", child_env)
            self.assertNotIn("HERMES_CONFIG", child_env)
            home = Path(child_env["HERMES_HOME"])
            self.assertEqual(kwargs["cwd"], str(home))
            config = (home / "config.yaml").read_text(encoding="utf-8")
            self.assertIn("provider: custom", config)
            self.assertIn("cli: []", config)
            self.assertIn("key_env: OMNIROUTE_API_KEY", config)
            return SimpleNamespace(returncode=0)

        with mock.patch.dict(
            os.environ,
            {
                "OMNIROUTE_API_KEY": "test-local-key",
                "HERMES_BIN": "/fake/hermes",
                "OPENAI_API_KEY": "unrelated-key",
                "HERMES_CONFIG": "/unrelated/config.yaml",
            },
        ):
            with mock.patch.object(review_incident, "check_omniroute") as check:
                with mock.patch.object(review_incident.subprocess, "run", side_effect=fake_run):
                    self.assertEqual(review_incident.run_live("test prompt"), 0)
                check.assert_called_once_with("test-local-key")
        self.assertTrue(inspected)


if __name__ == "__main__":
    unittest.main()
