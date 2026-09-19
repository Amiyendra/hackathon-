"""
Unit tests for Versioned Check Library.

Covers:
1. valid check definition
2. invalid check type
3. missing check_id
4. behaviour marked critical -> rejected
5. invalid date range (effective_to < effective_from)
6. duplicate check ID within same retailer/version
7. correct version selected for a historical call date
8. correct version selected for current call date
9. no matching version -> explicit failure
10. overlapping versions -> explicit failure
11. semantic variation defaults to false
12. semantic variation explicitly enabled
"""

from datetime import date
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.checks import (
    CheckDefinition,
    CheckLibrary,
    CheckType,
    CheckValidationError,
    NoMatchingVersionError,
    OverlappingVersionError,
    VersionResolver,
    load_check_library_from_dict,
    load_check_library_from_yaml,
)


# 1. Valid check definition
def test_valid_check_definition():
    check = CheckDefinition(
        check_id="CHK_001",
        retailer="POWERDIRECT",
        name="Call Recording",
        type=CheckType.VERBATIM,
        version="1.0.0",
        critical=True,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 12, 31),
        description="Must state call is recorded.",
        criteria={"required_phrase": "call is recorded"},
        allow_semantic_variation=False
    )
    assert check.check_id == "CHK_001"
    assert check.retailer == "POWERDIRECT"
    assert check.type == CheckType.VERBATIM
    assert check.critical is True
    assert check.effective_to == date(2024, 12, 31)


# 2. Invalid check type
def test_invalid_check_type():
    with pytest.raises(ValidationError) as excinfo:
        CheckDefinition(
            check_id="CHK_001",
            retailer="POWERDIRECT",
            name="Invalid Type Check",
            type="INVALID_TYPE",  # type: ignore
            version="1.0.0",
            critical=False,
            effective_from=date(2024, 1, 1),
            description="Test"
        )
    assert "Input should be 'VERBATIM', 'FACTUAL' or 'BEHAVIOUR'" in str(excinfo.value)


# 3. Missing check_id
def test_missing_check_id():
    with pytest.raises(ValidationError) as excinfo:
        CheckDefinition(
            check_id="",
            retailer="POWERDIRECT",
            name="No ID Check",
            type=CheckType.FACTUAL,
            version="1.0.0",
            critical=False,
            effective_from=date(2024, 1, 1),
            description="Test"
        )
    assert "String should have at least 1 character" in str(excinfo.value) or "must be a non-empty string" in str(excinfo.value)


# 4. Behaviour marked critical -> rejected
def test_behaviour_marked_critical_rejected():
    with pytest.raises(ValidationError) as excinfo:
        CheckDefinition(
            check_id="CHK_BEHAVIOUR_CRITICAL",
            retailer="POWERDIRECT",
            name="Forbidden Critical Behaviour",
            type=CheckType.BEHAVIOUR,
            version="1.0.0",
            critical=True,  # Invariant violation: BEHAVIOUR cannot be critical
            effective_from=date(2024, 1, 1),
            description="Agent was polite."
        )
    assert "cannot be marked critical" in str(excinfo.value)


# 5. Invalid date range (effective_to < effective_from)
def test_invalid_date_range():
    with pytest.raises(ValidationError) as excinfo:
        CheckDefinition(
            check_id="CHK_DATE_RANGE",
            retailer="POWERDIRECT",
            name="Inverted Dates Check",
            type=CheckType.VERBATIM,
            version="1.0.0",
            critical=False,
            effective_from=date(2025, 6, 1),
            effective_to=date(2025, 5, 1),  # earlier than effective_from
            description="Invalid date range"
        )
    assert "effective_to (2025-05-01) cannot be earlier than effective_from (2025-06-01)" in str(excinfo.value)


# 6. Duplicate check ID within same retailer and version
def test_duplicate_check_id_rejected():
    c1 = CheckDefinition(
        check_id="CHK_DUP",
        retailer="POWERDIRECT",
        name="Original",
        type=CheckType.VERBATIM,
        version="1.0.0",
        critical=False,
        effective_from=date(2024, 1, 1),
        description="First"
    )
    c2 = CheckDefinition(
        check_id="CHK_DUP",
        retailer="POWERDIRECT",
        name="Duplicate",
        type=CheckType.VERBATIM,
        version="1.0.0",
        critical=False,
        effective_from=date(2024, 6, 1),
        description="Second"
    )
    with pytest.raises(ValidationError) as excinfo:
        CheckLibrary(checks=[c1, c2])
    assert "Duplicate check ID 'CHK_DUP' found for retailer 'POWERDIRECT' and version '1.0.0'" in str(excinfo.value)


# 7. Correct version selected for a historical call date
def test_historical_call_date_version_resolution():
    lib = load_check_library_from_yaml(Path(__file__).resolve().parent.parent / "app" / "checks" / "library.yaml")
    resolver = VersionResolver(lib)

    # Call on 2024-06-15 should resolve CHK_CALL_RECORDING to v1.0.0
    resolved = resolver.resolve_check("POWERDIRECT", "CHK_CALL_RECORDING", "2024-06-15")
    assert resolved.version == "1.0.0"
    assert resolved.name == "Call Recording Disclosure (2024 Historical)"
    assert resolved.critical is True
    assert "This call is recorded for quality purposes." in resolved.criteria.get("required_phrase", "")


# 8. Correct version selected for current call date
def test_current_call_date_version_resolution():
    lib = load_check_library_from_yaml(Path(__file__).resolve().parent.parent / "app" / "checks" / "library.yaml")
    resolver = VersionResolver(lib)

    # Call on 2026-09-19 should resolve CHK_CALL_RECORDING to v2.0.0
    resolved = resolver.resolve_check("POWERDIRECT", "CHK_CALL_RECORDING", date(2026, 9, 19))
    assert resolved.version == "2.0.0"
    assert resolved.name == "Call Recording Disclosure (2025+ Modern)"
    assert resolved.critical is True
    assert "Please be advised that this call may be recorded" in resolved.criteria.get("required_phrase", "")


# 9. No matching version -> explicit failure
def test_no_matching_version_explicit_failure():
    lib = load_check_library_from_yaml(Path(__file__).resolve().parent.parent / "app" / "checks" / "library.yaml")
    resolver = VersionResolver(lib)

    # Date prior to any effective date (e.g. 2020-01-01)
    with pytest.raises(NoMatchingVersionError) as excinfo:
        resolver.resolve_check("POWERDIRECT", "CHK_CALL_RECORDING", "2020-01-01")
    assert "No active version found for check 'CHK_CALL_RECORDING'" in str(excinfo.value)

    # Retailer with no registered checks
    with pytest.raises(NoMatchingVersionError) as excinfo:
        resolver.resolve_check("UNKNOWN_RETAILER", "CHK_CALL_RECORDING", "2026-09-19")
    assert "No check definitions exist" in str(excinfo.value)


# 10. Overlapping versions -> explicit failure
def test_overlapping_versions_explicit_failure():
    data = {
        "checks": [
            {
                "check_id": "CHK_OVERLAP",
                "retailer": "ENERGY_CO",
                "name": "Version A",
                "type": "VERBATIM",
                "version": "1.0.0",
                "critical": False,
                "effective_from": "2024-01-01",
                "effective_to": "2024-12-31",
                "description": "A"
            },
            {
                "check_id": "CHK_OVERLAP",
                "retailer": "ENERGY_CO",
                "name": "Version B",
                "type": "VERBATIM",
                "version": "1.1.0",
                "critical": False,
                "effective_from": "2024-06-01",  # Overlaps with Version A [2024-01-01 -> 2024-12-31]
                "effective_to": "2025-06-01",
                "description": "B"
            }
        ]
    }
    with pytest.raises(OverlappingVersionError) as excinfo:
        load_check_library_from_dict(data)
    assert "Overlapping active versions detected" in str(excinfo.value)
    assert "version '1.0.0'" in str(excinfo.value)
    assert "version '1.1.0'" in str(excinfo.value)


# 11. Semantic variation defaults to false
def test_semantic_variation_defaults_to_false():
    check = CheckDefinition(
        check_id="CHK_SEM_DEFAULT",
        retailer="POWERDIRECT",
        name="Default Variation",
        type=CheckType.VERBATIM,
        version="1.0.0",
        critical=True,
        effective_from=date(2024, 1, 1),
        description="Test defaults"
    )
    assert check.allow_semantic_variation is False


# 12. Semantic variation explicitly enabled
def test_semantic_variation_explicitly_enabled():
    check = CheckDefinition(
        check_id="CHK_SEM_ENABLED",
        retailer="POWERDIRECT",
        name="Enabled Variation",
        type=CheckType.VERBATIM,
        version="1.0.0",
        critical=False,
        effective_from=date(2024, 1, 1),
        description="Test enabled",
        allow_semantic_variation=True
    )
    assert check.allow_semantic_variation is True


def test_resolve_ruleset_for_date():
    lib = load_check_library_from_yaml(Path(__file__).resolve().parent.parent / "app" / "checks" / "library.yaml")
    resolver = VersionResolver(lib)

    # 2024-07-01 ruleset
    ruleset_2024 = resolver.resolve_ruleset("POWERDIRECT", "2024-07-01")
    assert ruleset_2024.check_count == 3  # CHK_CALL_RECORDING (v1.0.0), CHK_COMPLAINT_RIGHT (v1.1.0), CHK_PROFESSIONAL_GREETING (v1.0.0)
    assert ruleset_2024.get_check("CHK_CALL_RECORDING").version == "1.0.0"
    assert ruleset_2024.get_check("CHK_TARIFF_ACCURACY") is None  # only effective 2025+

    # 2026-09-19 ruleset
    ruleset_2026 = resolver.resolve_ruleset("POWERDIRECT", "2026-09-19")
    assert ruleset_2026.check_count == 4
    assert ruleset_2026.get_check("CHK_CALL_RECORDING").version == "2.0.0"
    assert ruleset_2026.get_check("CHK_TARIFF_ACCURACY").version == "1.0.0"
    assert len(ruleset_2026.critical_checks) == 2  # CHK_CALL_RECORDING and CHK_TARIFF_ACCURACY
