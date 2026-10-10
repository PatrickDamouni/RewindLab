"""Versioned, reproducible evidence for read-only incident analysis.

The integrity digest detects accidental edits to an exported bundle. It is not
a signature and does not establish that the corpus generator is trustworthy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .corpus import CASE_IDS, DEFAULT_SEED, generated_case, run_case


BUNDLE_SCHEMA = "rewindlab.incident-evidence.v1"
REPORT_SCHEMA = "rewindlab.incident-report.v1"
PROPOSAL_SCHEMA = "rewindlab.incident-proposal.v1"

# These are labels for injected corpus conditions, not observed engine defects.
ORACLE_CATEGORIES = {
    "baseline": "none",
    "duplicate": "duplicate_delivery",
    "out_of_order": "out_of_order_delivery",
    "malformed_schema": "schema_rejection",
    "late_correction": "late_correction",
    "interrupted_import": "interrupted_import",
}
ORACLE_CITATIONS = {
    "baseline": ("run:expected", "run:observed"),
    "duplicate": ("delivery:0", "delivery:1", "run:expected", "run:observed"),
    "out_of_order": ("delivery:0", "delivery:1", "run:expected", "run:observed"),
    "malformed_schema": ("attempted:1", "run:import-error", "run:expected", "run:observed"),
    "late_correction": ("revision:a-corrected", "run:expected", "run:observed"),
    "interrupted_import": ("run:recovery", "run:expected", "run:observed"),
}
OFFLINE_HYPOTHESES = {
    "baseline": "No fault was injected; the observed corpus run agrees with the independent oracle.",
    "duplicate": "The same revision was delivered more than once; retry handling remained idempotent.",
    "out_of_order": "Revisions were delivered in reverse order; point-in-time results still matched the oracle.",
    "malformed_schema": "A delivery omitted known_at; the batch was rejected without a partial write.",
    "late_correction": "A correction was delivered after the early knowledge cutoff; replay respected the cutoff.",
    "interrupted_import": "The import process exited before commit; recovery replay reached the expected final state.",
}


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_new_json(path: Path, value: object) -> None:
    """Create a new JSON artifact with an exclusive filesystem open."""
    if path.suffix.lower() != ".json":
        raise ValueError("Evidence and report output paths must end in .json")
    encoded = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as target:
            target.write(encoded)
    except FileExistsError as exc:
        raise ValueError(f"Output path already exists: {path}") from exc


def build_bundle(case_id: str, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """Build a copy of the selected synthetic case without a write handle to its data."""
    if case_id not in CASE_IDS:
        raise ValueError(f"Unknown corpus case: {case_id}")
    case = generated_case(case_id, seed)
    result = run_case(case_id, seed)
    items: list[dict[str, Any]] = []
    revisions: dict[str, dict[str, Any]] = {}
    for row in case["preload"] + case["deliveries"]:
        if {"revision_id", "event_id", "valid_at", "known_at", "signal_value", "source"} <= row.keys():
            revisions[row["revision_id"]] = row
    for revision_id, row in sorted(revisions.items()):
        items.append({"id": f"revision:{revision_id}", "kind": "revision", "value": row})
    for index, row in enumerate(case["preload"]):
        items.append({"id": f"preload:{index}", "kind": "preload", "value": row})
    invalid_ids: list[str] = []
    for index, row in enumerate(case["deliveries"]):
        if {"revision_id", "event_id", "valid_at", "known_at", "signal_value", "source"} <= row.keys():
            items.append({"id": f"delivery:{index}", "kind": "delivery", "value": row})
        else:
            evidence_id = f"attempted:{index}"
            invalid_ids.append(evidence_id)
            items.append({"id": evidence_id, "kind": "attempted_invalid_input", "value": row})
    items.extend((
        {"id": "run:expected", "kind": "oracle_result", "value": result["expected"]},
        {"id": "run:observed", "kind": "observed_result", "value": result["observed"]},
    ))
    if result["import_error"] is not None:
        items.append({"id": "run:import-error", "kind": "import_error", "value": result["import_error"]})
    if result["recovery_evidence"] is not None:
        items.append({"id": "run:recovery", "kind": "recovery_evidence", "value": result["recovery_evidence"]})
    # Opaque run ID keeps the injected category out of the analyst prompt.
    run_id = f"corpus-{seed}-{canonical_digest([case_id, result['observed']['result_digest']])[:16]}"
    bundle: dict[str, Any] = {
        "bundle_schema": BUNDLE_SCHEMA,
        "run_id": run_id,
        "case_id": case_id,
        "seed": seed,
        "source_type": "synthetic",
        "injected_fault": {
            "category": ORACLE_CATEGORIES[case_id],
            "oracle_citation_ids": list(ORACLE_CITATIONS[case_id]),
        },
        "observed_mismatch": result["first_mismatch"],
        "corpus_passed": result["passed"],
        "expected": result["expected"],
        "observed": result["observed"],
        "event_ids": sorted({row["event_id"] for row in revisions.values()}),
        "revision_ids": sorted(revisions),
        "attempted_invalid_input_ids": invalid_ids,
        "evidence_items": items,
    }
    bundle["integrity_digest"] = canonical_digest(bundle)
    return bundle


def validate_bundle(bundle: dict[str, Any]) -> None:
    """Reject malformed or edited bundles before any report or provider call."""
    required = {
        "bundle_schema", "run_id", "case_id", "seed", "source_type",
        "injected_fault", "observed_mismatch", "corpus_passed", "expected",
        "observed", "event_ids", "revision_ids", "attempted_invalid_input_ids",
        "evidence_items", "integrity_digest",
    }
    if not isinstance(bundle, dict) or set(bundle) != required:
        raise ValueError("Evidence bundle does not match the v1 field contract")
    if bundle.get("bundle_schema") != BUNDLE_SCHEMA:
        raise ValueError(f"Expected evidence bundle schema {BUNDLE_SCHEMA}")
    case_id = bundle.get("case_id")
    if case_id not in CASE_IDS or not isinstance(bundle.get("run_id"), str) or not bundle["run_id"]:
        raise ValueError("Evidence bundle has invalid case or run ID")
    if type(bundle["seed"]) is not int or bundle["source_type"] != "synthetic":
        raise ValueError("Evidence bundle has invalid seed or source type")
    if bundle["observed_mismatch"] is not None and not isinstance(bundle["observed_mismatch"], str):
        raise ValueError("Evidence bundle has invalid observed mismatch")
    if type(bundle["corpus_passed"]) is not bool:
        raise ValueError("Evidence bundle has invalid pass flag")
    for name in ("event_ids", "revision_ids", "attempted_invalid_input_ids"):
        if not isinstance(bundle[name], list) or any(not isinstance(item, str) or not item for item in bundle[name]):
            raise ValueError(f"Evidence bundle has invalid {name}")
    if not isinstance(bundle.get("integrity_digest"), str):
        raise ValueError("Evidence bundle has no integrity digest")
    payload = {key: value for key, value in bundle.items() if key != "integrity_digest"}
    if canonical_digest(payload) != bundle["integrity_digest"]:
        raise ValueError("Evidence bundle integrity digest does not match content")
    items = bundle.get("evidence_items")
    if not isinstance(items, list):
        raise ValueError("Evidence bundle has invalid evidence items")
    value_types: dict[str, type] = {
        "revision": dict, "preload": dict, "delivery": dict,
        "attempted_invalid_input": dict, "oracle_result": dict,
        "observed_result": dict, "import_error": str, "recovery_evidence": dict,
    }
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "kind", "value"}:
            raise ValueError("Evidence bundle has invalid evidence item fields")
        kind = item["kind"]
        if not isinstance(item["id"], str) or not item["id"] or not isinstance(kind, str) or kind not in value_types:
            raise ValueError("Evidence bundle has invalid evidence item ID or kind")
        if not isinstance(item["value"], value_types[kind]):
            raise ValueError("Evidence bundle has invalid evidence item value")
        if kind in {"revision", "preload", "delivery", "attempted_invalid_input"}:
            if not isinstance(item["value"].get("event_id"), str) or not item["value"]["event_id"]:
                raise ValueError("Evidence row has no event ID")
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Evidence bundle has duplicate evidence IDs")
    fault = bundle.get("injected_fault")
    if not isinstance(fault, dict) or fault.get("category") != ORACLE_CATEGORIES[case_id]:
        raise ValueError("Evidence bundle has invalid injected fault label")
    citations = fault.get("oracle_citation_ids")
    if not isinstance(citations, list) or citations != list(ORACLE_CITATIONS[case_id]):
        raise ValueError("Evidence bundle has invalid oracle citations")
    if not set(citations) <= set(ids):
        raise ValueError("Evidence bundle is missing oracle evidence")
    if not isinstance(bundle.get("expected"), dict) or not isinstance(bundle.get("observed"), dict):
        raise ValueError("Evidence bundle must include expected and observed results")
    # The SHA-256 field only catches accidental changes. For this deterministic
    # synthetic corpus we can also reject a self-rehashed but fabricated run.
    if bundle != build_bundle(case_id, bundle["seed"]):
        raise ValueError("Evidence bundle differs from the deterministic corpus run")


def analyst_view(bundle: dict[str, Any]) -> dict[str, Any]:
    """Give the model facts to inspect without revealing the oracle category."""
    validate_bundle(bundle)

    def without_case_id(value: dict[str, Any]) -> dict[str, Any]:
        return {key: item for key, item in value.items() if key != "case_id"}

    items = []
    for item in bundle["evidence_items"]:
        value = item["value"]
        if item["id"] in {"run:expected", "run:observed"}:
            value = without_case_id(value)
        items.append({"id": item["id"], "kind": item["kind"], "value": value})
    return {
        "analyst_view_schema": "rewindlab.incident-analyst-view.v1",
        "run_id": bundle["run_id"],
        "seed": bundle["seed"],
        "source_type": bundle["source_type"],
        "observed_mismatch": bundle["observed_mismatch"],
        "corpus_passed": bundle["corpus_passed"],
        "expected": without_case_id(bundle["expected"]),
        "observed": without_case_id(bundle["observed"]),
        "event_ids": bundle["event_ids"],
        "revision_ids": bundle["revision_ids"],
        "attempted_invalid_input_ids": bundle["attempted_invalid_input_ids"],
        "evidence_items": items,
    }


def offline_proposal(bundle: dict[str, Any]) -> dict[str, Any]:
    validate_bundle(bundle)
    case_id = bundle["case_id"]
    return {
        "proposal_schema": PROPOSAL_SCHEMA,
        "run_id": bundle["run_id"],
        "fault_category": ORACLE_CATEGORIES[case_id],
        "fault_hypothesis": OFFLINE_HYPOTHESES[case_id],
        "citation_ids": list(ORACLE_CITATIONS[case_id]),
        "uncertainty": "Template uses the known synthetic injection and deterministic run; it is not an independent diagnosis.",
    }


def validate_proposal(bundle: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    validate_bundle(bundle)
    required = {"proposal_schema", "run_id", "fault_category", "fault_hypothesis", "citation_ids", "uncertainty"}
    if set(proposal) != required or proposal.get("proposal_schema") != PROPOSAL_SCHEMA:
        raise ValueError("Report proposal does not match the strict JSON contract")
    if proposal["run_id"] != bundle["run_id"]:
        raise ValueError("Report proposal run ID differs from evidence bundle")
    for field in ("fault_category", "fault_hypothesis", "uncertainty"):
        if not isinstance(proposal[field], str) or not proposal[field].strip():
            raise ValueError(f"Report proposal {field} must be a nonempty string")
    if proposal["fault_category"] not in set(ORACLE_CATEGORIES.values()):
        raise ValueError("Report proposal uses unknown fault category")
    citations = proposal["citation_ids"]
    if not isinstance(citations, list) or not citations or any(not isinstance(item, str) or not item for item in citations):
        raise ValueError("Report proposal citation_ids must be a nonempty string list")
    if len(citations) != len(set(citations)):
        raise ValueError("Report proposal has duplicate citation IDs")
    available = {item["id"] for item in bundle["evidence_items"]}
    required_citations = set(bundle["injected_fault"]["oracle_citation_ids"])
    unsupported = sorted(set(citations) - available)
    missing = sorted(required_citations - set(citations))
    category_match = proposal["fault_category"] == bundle["injected_fault"]["category"]
    citations_match = not unsupported and not missing
    return {
        "oracle_fault_category": bundle["injected_fault"]["category"],
        "category_matches_oracle": category_match,
        "unsupported_citation_ids": unsupported,
        "missing_oracle_citation_ids": missing,
        "citations_match_oracle": citations_match,
        "passed": category_match and citations_match,
        "scope": "Citation existence and required IDs are checked; free-text claims are not semantically verified.",
    }


def cited_evidence(bundle: dict[str, Any], citation_ids: list[str]) -> list[dict[str, Any]]:
    """Resolve exact citations to their underlying event IDs where possible."""
    by_id = {item["id"]: item for item in bundle["evidence_items"]}
    revision_events = {
        item["value"]["revision_id"]: item["value"]["event_id"]
        for item in bundle["evidence_items"] if item["kind"] == "revision"
    }
    details: list[dict[str, Any]] = []
    for evidence_id in citation_ids:
        item = by_id.get(evidence_id)
        if item is None:
            details.append({"evidence_id": evidence_id, "kind": None, "event_ids": []})
            continue
        kind, value = item["kind"], item["value"]
        if kind in {"revision", "preload", "delivery", "attempted_invalid_input"}:
            events = {value["event_id"]}
        elif kind in {"oracle_result", "observed_result"}:
            events = {
                revision_events[revision_id]
                for probe in value["probes"] for revision_id in probe["revision_ids"]
                if revision_id in revision_events
            }
        elif kind == "import_error":
            events = {
                by_id[attempt]["value"]["event_id"]
                for attempt in bundle["attempted_invalid_input_ids"]
            }
        else:  # recovery evidence covers the interrupted delivery set
            events = {
                row["value"]["event_id"] for row in bundle["evidence_items"]
                if row["kind"] == "delivery"
            }
        details.append({"evidence_id": evidence_id, "kind": kind, "event_ids": sorted(events)})
    return details


def build_report(bundle: dict[str, Any], proposal: dict[str, Any], *, mode: str,
                 provider_path: str | None = None) -> dict[str, Any]:
    if mode not in {"offline_template", "live_hermes_omniroute"}:
        raise ValueError(f"Unsupported report mode: {mode}")
    validation = validate_proposal(bundle, proposal)
    details = cited_evidence(bundle, proposal["citation_ids"])
    return {
        "report_schema": REPORT_SCHEMA,
        "run_id": bundle["run_id"],
        "case_id": bundle["case_id"],
        "evidence_digest": bundle["integrity_digest"],
        "mode": mode,
        "model_called": mode == "live_hermes_omniroute",
        "provider_path": provider_path,
        "injected_fault_category": bundle["injected_fault"]["category"],
        "observed_mismatch": bundle["observed_mismatch"],
        "expected": bundle["expected"],
        "observed": bundle["observed"],
        "proposal": proposal,
        "cited_evidence": details,
        "supporting_event_ids": sorted({event_id for item in details for event_id in item["event_ids"]}),
        "validation": validation,
    }
