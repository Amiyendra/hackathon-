"""
Verbatim / Script QA Evaluation Engine.

Evaluates conversation transcripts against approved mandatory wording and disclosures.

PIPELINE & INVARIANTS:
1. Deterministic-first: Normalizes text and evaluates exact phrases & configured allowed variations in pure Python.
2. Controlled Semantic Fallback: Calls BaseLLMClient for candidate utterance discovery ONLY if
   allow_semantic_variation=True on the CheckDefinition.
3. Strict Evidence Grounding: Every candidate utterance_id is verified via EvidenceIndex.
   Missing or invalid evidence can NEVER yield a PASS.
4. Final Authority: Python decides PASS, FAIL, or AMBIGUOUS. The LLM NEVER decides status or criticality.
"""

import json
import re
from typing import List, Optional

from app.checks.models import CheckDefinition, CheckType
from app.evidence.index import EvidenceIndex
from app.factual.llm import BaseLLMClient
from app.factual.models import CheckResult, CheckStatus
from app.models import CanonicalTranscript
from app.verbatim.exceptions import (
    InvalidCheckTypeError,
    MissingApprovedTextError,
)
from app.verbatim.matcher import VerbatimMatcher
from app.verbatim.models import MatchType, VerbatimMatchResult

DEFAULT_SEMANTIC_CONFIDENCE_THRESHOLD = 0.85


class VerbatimEngine:
    """
    Evaluator for VERBATIM and script compliance checks.
    """

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        matcher: Optional[VerbatimMatcher] = None,
        default_confidence_threshold: float = DEFAULT_SEMANTIC_CONFIDENCE_THRESHOLD,
    ):
        """
        Initialize VerbatimEngine.
        
        Args:
            llm_client: Optional BaseLLMClient for semantic candidate discovery.
            matcher: Optional custom text matcher (defaults to VerbatimMatcher).
            default_confidence_threshold: Minimum confidence required for semantic matches.
        """
        self.llm_client = llm_client
        self.matcher = matcher or VerbatimMatcher()
        self.default_confidence_threshold = default_confidence_threshold

    def evaluate_check(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript,
        evidence_index: EvidenceIndex,
    ) -> CheckResult:
        """
        Evaluate a single VERBATIM check against a canonical transcript.
        
        Args:
            check: The resolved versioned CheckDefinition.
            transcript: The validated CanonicalTranscript.
            evidence_index: Backend EvidenceIndex for evidence resolution.
            
        Returns:
            CheckResult conforming strictly to QA Gate specifications.
        """
        # 1. Type validation
        if check.type != CheckType.VERBATIM:
            raise InvalidCheckTypeError(
                f"VerbatimEngine only evaluates checks of type VERBATIM, got '{check.type.value}' "
                f"for check '{check.check_id}'."
            )

        # 2. Extract approved text and parameters
        approved_text = check.criteria.get("approved_text") or check.criteria.get("required_phrase")
        if not approved_text or not str(approved_text).strip():
            raise MissingApprovedTextError(
                f"CheckDefinition '{check.check_id}' is missing 'approved_text' or 'required_phrase' in criteria."
            )
        approved_text = str(approved_text).strip()

        allowed_variations: List[str] = check.criteria.get("allowed_variations", [])
        speaker_constraint: Optional[str] = check.criteria.get("speaker", "AGENT")
        semantic_allowed: bool = (
            check.allow_semantic_variation or
            check.criteria.get("semantic_variation_allowed", False)
        )
        min_confidence: float = check.criteria.get("min_confidence", self.default_confidence_threshold)

        # 3. Deterministic Matching (Pure Python)
        match_result = self.matcher.find_deterministic_match(
            approved_text=approved_text,
            allowed_variations=allowed_variations,
            transcript=transcript,
            speaker_constraint=speaker_constraint,
        )

        if match_result.matched and match_result.utterance_id:
            # Resolve evidence from EvidenceIndex
            evidence_ref = evidence_index.get_evidence(match_result.utterance_id)
            if evidence_ref is None:
                return CheckResult(
                    check_id=check.check_id,
                    check_type=check.type,
                    critical=check.critical,
                    status=CheckStatus.AMBIGUOUS,
                    confidence=0.0,
                    expected=approved_text,
                    observed=match_result.observed_text,
                    evidence=None,
                    reason=(
                        f"Matched utterance '{match_result.utterance_id}' could not be verified "
                        f"in EvidenceIndex. Cannot pass without backend-grounded evidence."
                    ),
                    check_version=check.version,
                    utterance_id=match_result.utterance_id,
                )

            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=check.critical,
                status=CheckStatus.PASS,
                confidence=match_result.confidence,
                expected=match_result.matched_phrase or approved_text,
                observed=evidence_ref.text,
                evidence=evidence_ref,
                reason=match_result.reason,
                check_version=check.version,
                utterance_id=match_result.utterance_id,
            )

        # 4. Check if the check specification itself is flagged as unsupported/invented
        is_unsupported_spec = (
            check.criteria.get("synthetic_status") == "UNSUPPORTED_INVENTED_CHECK" or
            check.criteria.get("unsupported_check", False) is True
        )
        if is_unsupported_spec and not match_result.matched:
            rationale = check.criteria.get(
                "unsupported_rationale",
                "Approved wording is unsupported by the transcript or retailer specification."
            )
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=False,  # Never counts as a critical QA failure and never causes HOLD
                status=CheckStatus.UNSUPPORTED_CHECK,
                confidence=1.0,
                expected=approved_text,
                observed=None,
                evidence=None,
                reason=f"UNSUPPORTED CHECK SPECIFICATION: {rationale} (Excluded from critical fail metrics).",
                check_version=check.version,
                utterance_id=None,
            )

        # 5. If deterministic match failed, check if semantic variation is permitted
        if not semantic_allowed:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=check.critical,
                status=CheckStatus.FAIL,
                confidence=1.0,
                expected=approved_text,
                observed=None,
                evidence=None,
                reason=(
                    f"Required wording was not spoken in the transcript. "
                    f"Semantic variation is strictly disabled for this check."
                ),
                check_version=check.version,
                utterance_id=None,
            )

        # 5. Semantic matching via BaseLLMClient candidate extraction
        if self.llm_client is None:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=check.critical,
                status=CheckStatus.AMBIGUOUS,
                confidence=0.0,
                expected=approved_text,
                observed=None,
                evidence=None,
                reason=(
                    f"Exact wording not found and semantic variation is permitted, but no "
                    f"LLM client is configured for semantic candidate evaluation."
                ),
                check_version=check.version,
                utterance_id=None,
            )

        return self._evaluate_semantic_match(
            check=check,
            approved_text=approved_text,
            transcript=transcript,
            evidence_index=evidence_index,
            min_confidence=min_confidence,
            speaker_constraint=speaker_constraint,
        )

    def _evaluate_semantic_match(
        self,
        check: CheckDefinition,
        approved_text: str,
        transcript: CanonicalTranscript,
        evidence_index: EvidenceIndex,
        min_confidence: float,
        speaker_constraint: Optional[str],
    ) -> CheckResult:
        """
        Perform controlled semantic candidate discovery using the LLM client.
        """
        # Call LLM client extraction
        extracted_claim = self.llm_client.extract_claim(check=check, transcript=transcript)

        candidate_utterance_id = extracted_claim.utterance_id
        confidence = extracted_claim.confidence or 0.0

        # Case A: LLM detected no utterance
        if not candidate_utterance_id:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=check.critical,
                status=CheckStatus.FAIL,
                confidence=confidence,
                expected=approved_text,
                observed=None,
                evidence=None,
                reason="Required meaning or concept was not conveyed in transcript.",
                check_version=check.version,
                utterance_id=None,
            )

        # Case B: Resolve evidence in EvidenceIndex
        evidence_ref = evidence_index.get_evidence(candidate_utterance_id)
        if evidence_ref is None:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=check.critical,
                status=CheckStatus.AMBIGUOUS,
                confidence=0.0,
                expected=approved_text,
                observed=extracted_claim.raw_value,
                evidence=None,
                reason=(
                    f"Semantic candidate utterance '{candidate_utterance_id}' was not found in EvidenceIndex. "
                    f"Cannot pass ungrounded evidence."
                ),
                check_version=check.version,
                utterance_id=candidate_utterance_id,
            )

        # Case C: Speaker constraint validation
        if speaker_constraint and evidence_ref.speaker.upper() != speaker_constraint.upper():
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=check.critical,
                status=CheckStatus.FAIL,
                confidence=confidence,
                expected=approved_text,
                observed=evidence_ref.text,
                evidence=evidence_ref,
                reason=(
                    f"Candidate wording was spoken by {evidence_ref.speaker}, but check requires "
                    f"speaker {speaker_constraint.upper()}."
                ),
                check_version=check.version,
                utterance_id=candidate_utterance_id,
            )

        # Case D: Confidence threshold check
        if confidence < min_confidence:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=check.critical,
                status=CheckStatus.AMBIGUOUS,
                confidence=confidence,
                expected=approved_text,
                observed=evidence_ref.text,
                evidence=evidence_ref,
                reason=(
                    f"Semantic variation match confidence ({confidence:.2f}) is below the required "
                    f"threshold ({min_confidence:.2f}). Requires manual QA review."
                ),
                check_version=check.version,
                utterance_id=candidate_utterance_id,
            )

        # Case E: Valid semantic match
        return CheckResult(
            check_id=check.check_id,
            check_type=check.type,
            critical=check.critical,
            status=CheckStatus.PASS,
            confidence=confidence,
            expected=approved_text,
            observed=evidence_ref.text,
            evidence=evidence_ref,
            reason=(
                f"Approved concept verified via semantic variation in utterance '{candidate_utterance_id}' "
                f"(confidence: {confidence:.2f})."
            ),
            check_version=check.version,
            utterance_id=candidate_utterance_id,
        )
