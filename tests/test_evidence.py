"""Evidence and oracle checks for each deterministic incident case."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

from rewindlab.corpus import CASE_IDS
from rewindlab.evidence import (
    BUNDLE_SCHEMA, ORACLE_CATEGORIES, analyst_view, build_bundle, build_report, canonical_digest,
    offline_proposal, validate_bundle, validate_proposal,
)


class EvidenceTests(unittest.TestCase):
    def test_all_six_bundles_and_offline_reports(self) -> None:
        manifest = files("rewindlab").joinpath("data/oracle_seed_1729.json")
        before = hashlib.sha256(manifest.read_bytes()).hexdigest()
        for case_id in CASE_IDS:
            with self.subTest(case_id=case_id):
                bundle = build_bundle(case_id)
                validate_bundle(bundle)
                self.assertEqual(bundle["bundle_schema"], BUNDLE_SCHEMA)
                self.assertEqual(bundle["integrity_digest"], build_bundle(case_id)["integrity_digest"])
                self.assertTrue(bundle["corpus_passed"])
                self.assertIsNone(bundle["observed_mismatch"])
                self.assertEqual(bundle["injected_fault"]["category"], ORACLE_CATEGORIES[case_id])
                self.assertIn("run:expected", [item["id"] for item in bundle["evidence_items"]])
                self.assertIn("run:observed", [item["id"] for item in bundle["evidence_items"]])
                report = build_report(bundle, offline_proposal(bundle), mode="offline_template")
                self.assertFalse(report["model_called"])
                self.assertTrue(report["validation"]["passed"])
                self.assertEqual(report["observed_mismatch"], None)
        after = hashlib.sha256(manifest.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_invalid_input_has_distinct_attempted_evidence_id(self) -> None:
        bundle = build_bundle("malformed_schema")
        self.assertEqual(bundle["attempted_invalid_input_ids"], ["attempted:1"])
        item = next(item for item in bundle["evidence_items"] if item["id"] == "attempted:1")
        self.assertEqual(item["kind"], "attempted_invalid_input")
        self.assertNotIn("known_at", item["value"])
        self.assertIn("attempted:1", offline_proposal(bundle)["citation_ids"])

    def test_analyst_view_hides_oracle_answer_and_case_label(self) -> None:
        bundle = build_bundle("malformed_schema")
        view = analyst_view(bundle)
        self.assertNotIn("case_id", view)
        self.assertNotIn("injected_fault", view)
        self.assertNotIn("integrity_digest", view)
        self.assertNotIn("malformed_schema", str(view))
        self.assertNotIn("case_id", view["expected"])
        self.assertNotIn("case_id", view["observed"])
        self.assertIn("attempted:1", view["attempted_invalid_input_ids"])

    def test_baseline_analyst_view_contains_no_correction_or_late_arrival(self) -> None:
        for case_id in ("baseline", "duplicate", "out_of_order"):
            with self.subTest(case_id=case_id):
                view = analyst_view(build_bundle(case_id))
                self.assertEqual(view["revision_ids"], ["a-original", "b-original"])
                self.assertEqual(view["event_ids"], ["event-a", "event-b"])
                self.assertEqual(
                    len({probe["signal_sum"] for probe in view["observed"]["probes"]}), 1,
                )

    def test_modified_bundle_is_rejected(self) -> None:
        bundle = build_bundle("duplicate")
        bundle["observed_mismatch"] = "forged"
        with self.assertRaisesRegex(ValueError, "integrity digest"):
            validate_bundle(bundle)

    def test_self_rehashed_fabrication_and_missing_item_value_are_rejected(self) -> None:
        bundle = build_bundle("baseline")
        bundle["observed_mismatch"] = "fabricated"
        bundle["observed"]["result_digest"] = "0" * 64
        bundle["integrity_digest"] = canonical_digest({key: value for key, value in bundle.items() if key != "integrity_digest"})
        with self.assertRaisesRegex(ValueError, "deterministic corpus run"):
            validate_bundle(bundle)

        malformed = build_bundle("baseline")
        del malformed["evidence_items"][0]["value"]
        malformed["integrity_digest"] = canonical_digest({key: value for key, value in malformed.items() if key != "integrity_digest"})
        with self.assertRaisesRegex(ValueError, "evidence item fields"):
            analyst_view(malformed)

    def test_report_resolves_attempted_row_to_event_id(self) -> None:
        bundle = build_bundle("malformed_schema")
        report = build_report(bundle, offline_proposal(bundle), mode="offline_template")
        cited = next(item for item in report["cited_evidence"] if item["evidence_id"] == "attempted:1")
        self.assertEqual(cited["event_ids"], ["event-c"])
        self.assertIn("event-c", report["supporting_event_ids"])

    def test_evidence_cli_exclusively_creates_json_and_preserves_existing_files(self) -> None:
        project = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oracle = root / "oracle.json"
            database = root / "dataset.db"
            link = root / "oracle-link.json"
            oracle.write_bytes(b"oracle-unchanged")
            database.write_bytes(b"database-unchanged")
            link.symlink_to(oracle)
            for target in (oracle, database, link):
                with self.subTest(target=target):
                    result = subprocess.run(
                        [sys.executable, "-m", "rewindlab", "evidence", "--case", "baseline", "--report", str(target)],
                        cwd=project, text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(result.returncode, 2)
            self.assertEqual(oracle.read_bytes(), b"oracle-unchanged")
            self.assertEqual(database.read_bytes(), b"database-unchanged")
            self.assertTrue(link.is_symlink())
            fresh = root / "evidence.json"
            created = subprocess.run(
                [sys.executable, "-m", "rewindlab", "evidence", "--case", "baseline", "--report", str(fresh)],
                cwd=project, text=True, capture_output=True, check=True,
            )
            self.assertEqual(json.loads(fresh.read_text(encoding="utf-8"))["case_id"], "baseline")
            self.assertIn("integrity_digest", created.stdout)
            before = fresh.read_bytes()
            repeated = subprocess.run(
                [sys.executable, "-m", "rewindlab", "evidence", "--case", "baseline", "--report", str(fresh)],
                cwd=project, text=True, capture_output=True, check=False,
            )
            self.assertEqual(repeated.returncode, 2)
            self.assertEqual(fresh.read_bytes(), before)

    def test_forged_citation_is_flagged(self) -> None:
        bundle = build_bundle("duplicate")
        proposal = offline_proposal(bundle)
        proposal["citation_ids"].append("revision:forged")
        result = validate_proposal(bundle, proposal)
        self.assertFalse(result["passed"])
        self.assertEqual(result["unsupported_citation_ids"], ["revision:forged"])

    def test_category_and_missing_oracle_citation_are_flagged(self) -> None:
        bundle = build_bundle("out_of_order")
        proposal = offline_proposal(bundle)
        proposal["fault_category"] = "duplicate_delivery"
        result = validate_proposal(bundle, proposal)
        self.assertFalse(result["category_matches_oracle"])
        self.assertTrue(result["citations_match_oracle"])
        self.assertFalse(result["passed"])

        proposal = offline_proposal(bundle)
        proposal["citation_ids"] = ["delivery:0"]
        result = validate_proposal(bundle, proposal)
        self.assertTrue(result["category_matches_oracle"])
        self.assertFalse(result["citations_match_oracle"])
        self.assertEqual(result["missing_oracle_citation_ids"], ["delivery:1", "run:expected", "run:observed"])
        self.assertFalse(result["passed"])

    def test_contract_rejects_extra_keys_and_wrong_run(self) -> None:
        bundle = build_bundle("baseline")
        proposal = offline_proposal(bundle)
        extra = copy.deepcopy(proposal)
        extra["claim"] = "unsupported"
        with self.assertRaisesRegex(ValueError, "strict JSON contract"):
            validate_proposal(bundle, extra)
        proposal["run_id"] = "another-run"
        with self.assertRaisesRegex(ValueError, "differs"):
            validate_proposal(bundle, proposal)


if __name__ == "__main__":
    unittest.main()
