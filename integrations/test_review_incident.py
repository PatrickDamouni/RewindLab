"""Offline CLI and live-process isolation checks for incident reviews."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import review_incident
from rewindlab.evidence import build_bundle, offline_proposal


PROJECT = Path(__file__).resolve().parent.parent
SCRIPT = Path(review_incident.__file__).resolve()


class ReviewIncidentTests(unittest.TestCase):
    def test_evidence_cli_pipes_into_non_ai_report(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT / "src")
        env.pop("OMNIROUTE_API_KEY", None)
        export = subprocess.run(
            [sys.executable, "-m", "rewindlab", "evidence", "--case", "malformed_schema"],
            cwd=PROJECT, env=env, text=True, capture_output=True, check=True,
        )
        review = subprocess.run(
            [sys.executable, str(SCRIPT), "-"], input=export.stdout,
            cwd=PROJECT, env=env, text=True, capture_output=True, check=True,
        )
        report = json.loads(review.stdout)
        self.assertEqual(report["mode"], "offline_template")
        self.assertFalse(report["model_called"])
        self.assertIsNone(report["observed_mismatch"])
        self.assertEqual(report["injected_fault_category"], "schema_rejection")
        self.assertIn("attempted:1", report["proposal"]["citation_ids"])
        self.assertTrue(report["validation"]["passed"])

    def test_print_prompt_contains_only_selected_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(build_bundle("duplicate")), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), "--print-prompt"],
                text=True, capture_output=True, check=True,
            )
            self.assertIn("BEGIN ANALYST VIEW JSON", result.stdout)
            self.assertNotIn('"case_id": "duplicate"', result.stdout)
            self.assertNotIn('"category": "duplicate_delivery"', result.stdout)
            self.assertNotIn("OMNIROUTE_API_KEY", result.stdout)
            self.assertIn("Every report must cite run:expected and run:observed", result.stdout)
            self.assertIn("paired delivery IDs", result.stdout)
            self.assertIn("attempted invalid input ID and run:import-error", result.stdout)
            self.assertIn("correction revision ID", result.stdout)
            self.assertIn("run:recovery", result.stdout)

    def test_bad_json_and_non_object_fail_cleanly(self) -> None:
        for payload, message in (("{", "UTF-8 JSON"), ("[]", "JSON object")):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "incident.json"
                path.write_text(payload, encoding="utf-8")
                result = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                                        text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)

    def test_oversized_snapshot_and_edited_bundle_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            path.write_text('{"text":"' + "x" * review_incident.MAX_SNAPSHOT_BYTES + '"}', encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Snapshot exceeds", result.stderr)
            bundle = build_bundle("baseline")
            bundle["observed_mismatch"] = "forged"
            path.write_text(json.dumps(bundle), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                                    text=True, capture_output=True, check=False)
            self.assertIn("integrity digest", result.stderr)

    def test_live_requires_saved_evidence_and_key(self) -> None:
        bundle = build_bundle("baseline")
        with mock.patch.dict(os.environ, {"OMNIROUTE_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "OMNIROUTE_API_KEY"):
                review_incident.run_live(review_incident.build_prompt(bundle))
        result = subprocess.run([sys.executable, str(SCRIPT), "-", "--live"],
                                input=json.dumps(bundle), text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("saved evidence bundle path", result.stderr)

        with tempfile.TemporaryDirectory() as directory:
            evidence_path = Path(directory) / "evidence.json"
            report_path = Path(directory) / "live-report.json"
            evidence_path.write_text(json.dumps(bundle), encoding="utf-8")
            before = evidence_path.read_bytes()
            env = os.environ.copy()
            env.pop("OMNIROUTE_API_KEY", None)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(evidence_path), "--live", "--report", str(report_path)],
                text=True, capture_output=True, check=False, env=env,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("OMNIROUTE_API_KEY", result.stderr)
            self.assertEqual(evidence_path.read_bytes(), before)
            self.assertFalse(report_path.exists())

    def test_live_child_has_only_scoped_key_and_tool_free_config(self) -> None:
        bundle = build_bundle("baseline")
        proposal = offline_proposal(bundle)

        def fake_run(args, **kwargs):
            self.assertEqual(args[1:], ["chat", "--query-file", "-", "--oneshot", "-Q"])
            self.assertEqual(kwargs["timeout"], review_incident.LIVE_TIMEOUT_SECONDS)
            self.assertTrue(kwargs["capture_output"])
            self.assertIn(bundle["run_id"], kwargs["input"])
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
            return SimpleNamespace(returncode=0, stdout=json.dumps(proposal), stderr="")

        with mock.patch.dict(os.environ, {
            "OMNIROUTE_API_KEY": "test-local-key", "HERMES_BIN": "/fake/hermes",
            "OPENAI_API_KEY": "unrelated-key", "HERMES_CONFIG": "/unrelated/config.yaml",
        }):
            with mock.patch.object(review_incident, "check_omniroute") as check:
                with mock.patch.object(review_incident.subprocess, "run", side_effect=fake_run):
                    self.assertEqual(review_incident.run_live(review_incident.build_prompt(bundle)), proposal)
                check.assert_called_once_with("test-local-key")

    def test_malformed_provider_and_timeout_fail_without_report(self) -> None:
        with mock.patch.dict(os.environ, {"OMNIROUTE_API_KEY": "test-key", "HERMES_BIN": "/fake/hermes"}):
            with mock.patch.object(review_incident, "check_omniroute", side_effect=RuntimeError("provider unavailable")):
                with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
                    review_incident.run_live("prompt")
            with mock.patch.object(review_incident, "check_omniroute"):
                with mock.patch.object(review_incident.subprocess, "run", side_effect=subprocess.TimeoutExpired("hermes", 120)):
                    with self.assertRaisesRegex(RuntimeError, "timed out"):
                        review_incident.run_live("prompt")
                with mock.patch.object(review_incident.subprocess, "run", return_value=SimpleNamespace(returncode=7, stdout="", stderr="secret")):
                    with self.assertRaisesRegex(RuntimeError, "status 7") as context:
                        review_incident.run_live("prompt")
                    self.assertNotIn("secret", str(context.exception))
                with mock.patch.object(review_incident.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="not JSON", stderr="")):
                    with self.assertRaisesRegex(ValueError, "malformed JSON"):
                        review_incident.run_live("prompt")

    def test_omniroute_key_rejection_does_not_echo_key(self) -> None:
        denial = urllib.error.HTTPError(
            review_incident.OMNIROUTE_MODELS_URL, 401, "Unauthorized", None, None,
        )
        fake_opener = SimpleNamespace(open=mock.Mock(side_effect=denial))
        with mock.patch.object(review_incident.urllib.request, "build_opener", return_value=fake_opener):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as context:
                review_incident.check_omniroute("private-test-key")
        self.assertNotIn("private-test-key", str(context.exception))

    def test_report_cannot_overwrite_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(build_bundle("baseline")), encoding="utf-8")
            before = path.read_bytes()
            result = subprocess.run([sys.executable, str(SCRIPT), str(path), "--report", str(path)],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(path.read_bytes(), before)
            self.assertIn("must differ", result.stderr)

    def test_report_exclusively_creates_json_and_preserves_oracle_and_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_path = root / "evidence.json"
            evidence_path.write_text(json.dumps(build_bundle("malformed_schema")), encoding="utf-8")
            oracle = root / "oracle.json"
            database = root / "dataset.db"
            link = root / "oracle-link.json"
            oracle.write_bytes(b"oracle-unchanged")
            database.write_bytes(b"database-unchanged")
            link.symlink_to(oracle)
            for target in (oracle, database, link):
                with self.subTest(target=target):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), str(evidence_path), "--report", str(target)],
                        text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(result.returncode, 2)
            self.assertEqual(oracle.read_bytes(), b"oracle-unchanged")
            self.assertEqual(database.read_bytes(), b"database-unchanged")
            self.assertTrue(link.is_symlink())
            report_path = root / "report.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(evidence_path), "--report", str(report_path)],
                text=True, capture_output=True, check=True,
            )
            self.assertFalse(json.loads(result.stdout)["model_called"])
            before = report_path.read_bytes()
            repeated = subprocess.run(
                [sys.executable, str(SCRIPT), str(evidence_path), "--report", str(report_path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(repeated.returncode, 2)
            self.assertEqual(report_path.read_bytes(), before)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.json"
            path.write_text('{"run_id":"first","run_id":"second"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "strict UTF-8 JSON"):
                review_incident.read_snapshot(path)
        for raw in (
            '{"fault_category":"none","fault_category":"schema_rejection"}',
            '{"fault_category":NaN}',
            '{"fault_category":Infinity}',
            '{"fault_category":1e999}',
        ):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "malformed JSON"):
                review_incident.parse_model_response(raw)


if __name__ == "__main__":
    unittest.main()
