"""
Unit tests for Synthetic Broadband Ground Truth and Check Library.

Validates:
- ground-truth schema integrity
- all factual checks have valid IDs
- no duplicate check IDs
- PASS/FAIL/AMBIGUOUS fixtures are represented in both files
- synthetic assumptions are explicitly and clearly labelled
- broadband check library validates cleanly against Phase 2 CheckLibrary
- broadband transcript normalizes cleanly through Phase 1 TranscriptNormalizer
- consistency between ground truth checks and broadband_library.yaml checks
"""

import json
from pathlib import Path
import pytest

from app.checks import (
    load_check_library_from_yaml,
    VersionResolver,
    CheckType,
)
from app.ingestion.normalizer import TranscriptNormalizer


@pytest.fixture
def project_root():
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def ground_truth_data(project_root):
    gt_path = project_root / "data" / "broadband_ground_truth.json"
    with open(gt_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def broadband_check_library(project_root):
    lib_path = project_root / "app" / "checks" / "broadband_library.yaml"
    return load_check_library_from_yaml(lib_path)


def test_ground_truth_metadata_schema(ground_truth_data):
    metadata = ground_truth_data.get("metadata")
    assert metadata is not None, "Ground truth missing metadata"
    assert "dataset_name" in metadata
    assert "dataset_version" in metadata
    assert "disclaimer" in metadata
    assert "NOT official hackathon" in metadata["disclaimer"]
    assert "records" in ground_truth_data or "ground_truth_records" in ground_truth_data


def test_ground_truth_records_schema(ground_truth_data):
    records = ground_truth_data.get("ground_truth_records", [])
    assert len(records) >= 15, "Expected comprehensive record set"

    valid_bases = {"explicitly_stated_in_transcript", "synthetic_test_variation"}
    valid_categories = {"PASS", "FAIL", "AMBIGUOUS"}

    seen_ids = set()
    for rec in records:
        assert "field" in rec and rec["field"], "Record missing field"
        assert "check_id" in rec and rec["check_id"].startswith("CHK_FACT_BB_"), f"Invalid check_id in {rec}"
        assert rec["check_id"] not in seen_ids, f"Duplicate check_id in ground truth: {rec['check_id']}"
        seen_ids.add(rec["check_id"])

        assert rec.get("source") == "synthetic_hackathon_fixture", "source must be synthetic_hackathon_fixture"
        assert rec.get("basis") in valid_bases, f"Invalid basis in {rec['check_id']}"
        assert rec.get("test_case_category") in valid_categories, f"Invalid category in {rec['check_id']}"
        assert "rationale" in rec and len(rec["rationale"]) > 10, f"Missing rationale in {rec['check_id']}"
        assert "expected_value" in rec, f"Missing expected_value in {rec['check_id']}"


def test_ground_truth_categories_representation(ground_truth_data):
    records = ground_truth_data.get("ground_truth_records", [])
    categories = {r["test_case_category"] for r in records}
    assert "PASS" in categories, "Ground truth must contain PASS fixtures"
    assert "FAIL" in categories, "Ground truth must contain FAIL fixtures"
    assert "AMBIGUOUS" in categories, "Ground truth must contain AMBIGUOUS fixtures"

    pass_count = sum(1 for r in records if r["test_case_category"] == "PASS")
    fail_count = sum(1 for r in records if r["test_case_category"] == "FAIL")
    ambig_count = sum(1 for r in records if r["test_case_category"] == "AMBIGUOUS")

    assert pass_count >= 10, f"Expected at least 10 PASS cases, got {pass_count}"
    assert fail_count >= 2, f"Expected at least 2 FAIL cases, got {fail_count}"
    assert ambig_count >= 2, f"Expected at least 2 AMBIGUOUS cases, got {ambig_count}"


def test_broadband_check_library_valid(broadband_check_library):
    assert broadband_check_library.version == "1.0.0"
    assert len(broadband_check_library.checks) >= 15

    # Check all checks are FACTUAL and belong to TANGENT_BROADBAND
    for check in broadband_check_library.checks:
        assert check.type == CheckType.FACTUAL
        assert check.retailer == "TANGENT_BROADBAND"
        assert check.check_id.startswith("CHK_FACT_BB_")
        assert "field" in check.criteria
        assert "comparison_method" in check.criteria
        assert "confidence_requirements" in check.criteria


def test_broadband_library_no_duplicate_check_ids(broadband_check_library):
    check_ids = [c.check_id for c in broadband_check_library.checks]
    assert len(check_ids) == len(set(check_ids)), "Duplicate check IDs found in broadband library"


def test_broadband_library_matches_ground_truth(ground_truth_data, broadband_check_library):
    gt_check_ids = {r["check_id"] for r in ground_truth_data["ground_truth_records"]}
    lib_check_ids = {c.check_id for c in broadband_check_library.checks}

    # Every check in library should have a ground truth counterpart and vice versa
    assert gt_check_ids == lib_check_ids, (
        f"Mismatch between ground truth check IDs and library check IDs: "
        f"Only in GT: {gt_check_ids - lib_check_ids}, Only in Lib: {lib_check_ids - gt_check_ids}"
    )


def test_broadband_library_version_resolution(broadband_check_library):
    resolver = VersionResolver(broadband_check_library)
    active_ruleset = resolver.resolve_ruleset("TANGENT_BROADBAND", "2026-09-19")
    assert active_ruleset.check_count == len(broadband_check_library.checks)

    # Resolve specific check
    chk = resolver.resolve_check("TANGENT_BROADBAND", "CHK_FACT_BB_004_DOWNLOAD_SPEED", "2026-09-19")
    assert chk.version == "1.0.0"
    assert chk.critical is True
    assert chk.criteria["field"] == "download_speed_mbps"


def test_broadband_transcript_normalization(project_root):
    transcript_path = project_root / "data" / "broadband_transcript.json"
    assert transcript_path.exists(), "Broadband transcript file missing"

    with open(transcript_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    normalizer = TranscriptNormalizer()
    canonical = normalizer.normalize(raw_data)

    assert canonical.transcript_id == "broadband_call_20260919_001"
    assert canonical.total_utterances == 17
    assert canonical.duration > 85.0

    texts = " ".join(u.text for u in canonical.utterances)
    assert "[CUSTOMER_NAME]" in texts
    assert "[SERVICE_ADDRESS]" in texts
    assert "[PHONE_NUMBER]" in texts
    assert "iPRIMUS" in texts
    assert "FTTP" in texts
    assert "$42.90" in texts
    assert "$72.90" in texts
    assert "$317" in texts


def test_nbn_technology_type_is_fttp_transcript_supported(ground_truth_data, broadband_check_library):
    # Locate nbn_technology_type in ground truth records
    rec = next(r for r in ground_truth_data["ground_truth_records"] if r["field"] == "nbn_technology_type")
    assert rec["expected_value"] == "FTTP"
    assert rec["test_case_category"] == "PASS"
    assert rec["basis"] == "explicitly_stated_in_transcript"
    assert "FTTP" in rec["observed_transcript_claim"]

    # Verify matching check in broadband library
    check = next(c for c in broadband_check_library.checks if c.check_id == "CHK_FACT_BB_016_TECHNOLOGY_TYPE")
    assert check.criteria["field"] == "nbn_technology_type"
    assert check.criteria["test_case_category"] == "PASS"
    assert check.criteria["synthetic_basis"] == "explicitly_stated_in_transcript"

