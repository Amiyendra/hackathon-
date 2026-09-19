"""
Versioned Check Library Models.

CRITICALITY RULE:
Criticality MUST come exclusively from the check library configuration.
The LLM must NEVER be allowed to determine or decide whether a check is critical.
All evaluation decisions inherit the criticality defined in these immutable models.
"""

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.checks.exceptions import CheckValidationError, OverlappingVersionError


class CheckType(str, Enum):
    """Supported check types in QA Gate."""
    VERBATIM = "VERBATIM"
    FACTUAL = "FACTUAL"
    BEHAVIOUR = "BEHAVIOUR"


class CheckDefinition(BaseModel):
    """
    Specification for a single compliance, factual, or behavioral QA check.
    
    Attributes:
        check_id: Unique check identifier (e.g. 'CHK_001_DISCLOSURE').
        retailer: Retailer or client code this check applies to (e.g. 'POWERDIRECT').
        name: Human-readable display name.
        type: CheckType (VERBATIM, FACTUAL, BEHAVIOUR).
        version: Semantic or release version string (e.g. '1.0.0').
        critical: Whether failure of this check blocks approval.
        effective_from: First calendar date on which this check version is active.
        effective_to: Optional last calendar date on which this check version is active (None = indefinitely active).
        description: Explanatory text describing the rule.
        criteria: Specific configuration details (e.g. required phrases, target fields).
        allow_semantic_variation: Default False. If True, semantic equivalence is permitted (VERBATIM).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str = Field(..., min_length=1, description="Unique check ID")
    retailer: str = Field(..., min_length=1, description="Retailer or client identifier")
    name: str = Field(..., min_length=1, description="Human-readable check name")
    type: CheckType = Field(..., description="Type of QA check (VERBATIM, FACTUAL, BEHAVIOUR)")
    version: str = Field(..., min_length=1, description="Version string")
    critical: bool = Field(..., description="Whether failure of this check is critical")
    effective_from: date = Field(..., description="Effective start date")
    effective_to: Optional[date] = Field(default=None, description="Effective end date (inclusive, nullable)")
    description: str = Field(..., min_length=1, description="Check description")
    criteria: Dict[str, Any] = Field(default_factory=dict, description="Evaluation criteria parameters")
    allow_semantic_variation: bool = Field(default=False, description="Whether semantic variation is permitted")

    @field_validator("check_id", "retailer", "name", "version", "description", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, v: Any, info) -> Any:
        if v is None or not str(v).strip():
            raise ValueError(f"Field '{info.field_name}' must be a non-empty string.")
        return str(v).strip()

    @model_validator(mode="after")
    def validate_check_invariants(self) -> "CheckDefinition":
        # 1. Date range validation
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError(
                f"effective_to ({self.effective_to}) cannot be earlier than effective_from ({self.effective_from}) "
                f"for check '{self.check_id}'"
            )

        # 2. Invariant: BEHAVIOUR checks cannot be critical
        if self.type == CheckType.BEHAVIOUR and self.critical:
            raise ValueError(
                f"BEHAVIOUR check '{self.check_id}' cannot be marked critical. "
                "Behaviour checks are strictly non-blocking."
            )

        return self

    def is_active_on(self, target_date: date) -> bool:
        """Return True if this check version is active on target_date."""
        if target_date < self.effective_from:
            return False
        if self.effective_to is not None and target_date > self.effective_to:
            return False
        return True


class CheckLibrary(BaseModel):
    """
    Collection of validated check definitions for one or more retailers.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Optional[str] = Field(default=None, description="Check library release version")
    description: Optional[str] = Field(default=None, description="Check library description")
    checks: List[CheckDefinition] = Field(default_factory=list, description="List of check definitions")

    @model_validator(mode="after")
    def validate_library_integrity(self) -> "CheckLibrary":
        # 1. No duplicate check IDs within the same retailer and version
        seen_keys = set()
        for c in self.checks:
            key = (c.retailer.upper(), c.check_id, c.version)
            if key in seen_keys:
                raise ValueError(
                    f"Duplicate check ID '{c.check_id}' found for retailer '{c.retailer}' and version '{c.version}'."
                )
            seen_keys.add(key)

        # 2. No overlapping active versions for the same retailer and check_id
        checks_by_retailer_id: Dict[tuple[str, str], List[CheckDefinition]] = {}
        for c in self.checks:
            r_key = (c.retailer.upper(), c.check_id)
            checks_by_retailer_id.setdefault(r_key, []).append(c)

        for (retailer, check_id), check_list in checks_by_retailer_id.items():
            if len(check_list) <= 1:
                continue
            for i in range(len(check_list)):
                for j in range(i + 1, len(check_list)):
                    c1 = check_list[i]
                    c2 = check_list[j]
                    start1, end1 = c1.effective_from, c1.effective_to or date.max
                    start2, end2 = c2.effective_from, c2.effective_to or date.max

                    if max(start1, start2) <= min(end1, end2):
                        raise OverlappingVersionError(
                            f"Overlapping active versions detected for retailer '{retailer}', check '{check_id}': "
                            f"version '{c1.version}' [{c1.effective_from} -> {c1.effective_to}] overlaps with "
                            f"version '{c2.version}' [{c2.effective_from} -> {c2.effective_to}]."
                        )

        return self

    def get_checks_for_retailer(self, retailer: str) -> List[CheckDefinition]:
        """Return all check definitions matching a specific retailer."""
        target = retailer.strip().upper()
        return [c for c in self.checks if c.retailer.upper() == target]


class ResolvedRuleSet(BaseModel):
    """
    Immutable set of resolved, active checks for a specific retailer on a specific call date.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    retailer: str = Field(..., description="Retailer code")
    call_date: date = Field(..., description="Call date for which checks were resolved")
    checks: List[CheckDefinition] = Field(default_factory=list, description="Active check definitions")

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def critical_checks(self) -> List[CheckDefinition]:
        return [c for c in self.checks if c.critical]

    def get_check(self, check_id: str) -> Optional[CheckDefinition]:
        for c in self.checks:
            if c.check_id == check_id:
                return c
        return None
