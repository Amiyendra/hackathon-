"""
Behaviour QA Evaluation Engine.

Evaluates conversational timing metrics (dead air, interruptions) and conversational
conduct (rapport, objection handling) across canonical transcripts.

CRITICAL ARCHITECTURAL INVARIANTS:
1. NON-BLOCKING: All behaviour checks are strictly non-blocking (critical=False).
   A behaviour failure NEVER triggers HOLD and NEVER prevents AUTO_SUBMIT.
2. TIMING INTEGRITY: Dead air and speech collisions are calculated deterministically
   in pure Python directly from transcript timestamps.
3. SEMANTIC INTEGRITY: LLM classifications (rapport, objection handling) are grounded
   in EvidenceIndex with mandatory confidence gating.
4. UNTRUSTED DATA: The transcript is treated purely as passive text data.
"""

from typing import Optional

from app.behaviour.exceptions import (
    CriticalBehaviourCheckError,
    InvalidBehaviourCheckTypeError,
    UnsupportedBehaviourCategoryError,
)
from app.behaviour.metrics import BehaviourMetrics
from app.behaviour.models import BehaviourCategory
from app.checks.models import CheckDefinition, CheckType
from app.evidence.index import EvidenceIndex
from app.factual.llm import BaseLLMClient
from app.factual.models import CheckResult, CheckStatus
from app.models import CanonicalTranscript, EvidenceReference

DEFAULT_BEHAVIOUR_CONFIDENCE_THRESHOLD = 0.85


class BehaviourEngine:
    """
    Evaluator for non-functional conversational conduct and timing metrics.
    """

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        default_confidence_threshold: float = DEFAULT_BEHAVIOUR_CONFIDENCE_THRESHOLD,
    ):
        self.llm_client = llm_client
        self.default_confidence_threshold = default_confidence_threshold

    def evaluate_check(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript,
        evidence_index: EvidenceIndex,
    ) -> CheckResult:
        """
        Evaluate a single BEHAVIOUR check against a canonical transcript.
        
        Args:
            check: The resolved CheckDefinition.
            transcript: Validated CanonicalTranscript.
            evidence_index: Backend EvidenceIndex.
            
        Returns:
            CheckResult conforming strictly to QA Gate specifications with critical=False.
        """
        # 1. Type validation
        if check.type != CheckType.BEHAVIOUR:
            raise InvalidBehaviourCheckTypeError(
                f"BehaviourEngine only evaluates checks of type BEHAVIOUR, got '{check.type.value}' "
                f"for check '{check.check_id}'."
            )

        # 2. Strict non-blocking enforcement
        if check.critical is True:
            raise CriticalBehaviourCheckError(
                f"BEHAVIOUR check '{check.check_id}' cannot be marked critical=True. "
                f"Behaviour checks are strictly non-blocking."
            )

        # 3. Category routing
        raw_category = (
            check.criteria.get("category") or
            check.criteria.get("behaviour_type") or
            ""
        ).upper().strip()

        if "DEAD_AIR" in raw_category or "SILENCE" in raw_category:
            return self._evaluate_dead_air(check, transcript, evidence_index)
        elif "INTERRUPTION" in raw_category or "OVERLAP" in raw_category:
            return self._evaluate_interruptions(check, transcript, evidence_index)
        elif "RAPPORT" in raw_category or "COURTESY" in raw_category or "GREETING" in raw_category:
            return self._evaluate_semantic_conduct(
                check=check,
                transcript=transcript,
                evidence_index=evidence_index,
                behaviour_name="rapport",
            )
        elif "OBJECTION" in raw_category or "PUSHBACK" in raw_category:
            return self._evaluate_semantic_conduct(
                check=check,
                transcript=transcript,
                evidence_index=evidence_index,
                behaviour_name="objection handling",
            )
        else:
            raise UnsupportedBehaviourCategoryError(
                f"Unrecognized behaviour category '{raw_category}' for check '{check.check_id}'. "
                f"Supported: DEAD_AIR, INTERRUPTIONS, RAPPORT, OBJECTION_HANDLING."
            )

    # -------------------------------------------------------------------------
    # Deterministic Metrics: Dead Air
    # -------------------------------------------------------------------------
    def _evaluate_dead_air(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript,
        evidence_index: EvidenceIndex,
    ) -> CheckResult:
        threshold = float(check.criteria.get("dead_air_threshold_seconds", 30.0))
        incidents, max_gap, largest_incident = BehaviourMetrics.calculate_dead_air(
            transcript=transcript,
            threshold_seconds=threshold,
        )

        if incidents:
            primary_incident = incidents[0]
            evidence_ref = EvidenceReference(
                utterance_id=f"{primary_incident.preceding_utterance_id}->{primary_incident.following_utterance_id}",
                start_time=primary_incident.start_time,
                end_time=primary_incident.end_time,
                duration=primary_incident.gap_seconds,
                speaker="SILENCE",
                text=(
                    f"[SILENCE GAP: {primary_incident.gap_seconds:.2f}s between "
                    f"'{primary_incident.preceding_utterance_id}' and '{primary_incident.following_utterance_id}']"
                ),
                preceding_utterance_id=primary_incident.preceding_utterance_id,
                following_utterance_id=primary_incident.following_utterance_id,
            )
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=False,  # Strictly non-blocking
                status=CheckStatus.FAIL,
                confidence=1.0,
                expected=f"Silence gap <= {threshold:.1f}s",
                observed=f"Observed gap of {primary_incident.gap_seconds:.2f}s",
                evidence=evidence_ref,
                reason=(
                    f"Dead air gap of {primary_incident.gap_seconds:.2f}s between utterances "
                    f"'{primary_incident.preceding_utterance_id}' and '{primary_incident.following_utterance_id}' "
                    f"exceeded threshold of {threshold:.1f}s."
                ),
                check_version=check.version,
                utterance_id=primary_incident.preceding_utterance_id,
                preceding_utterance_id=primary_incident.preceding_utterance_id,
                following_utterance_id=primary_incident.following_utterance_id,
                duration=primary_incident.gap_seconds,
            )

        # No dead air exceeding threshold
        sample_ev = None
        if largest_incident:
            sample_ev = EvidenceReference(
                utterance_id=f"{largest_incident.preceding_utterance_id}->{largest_incident.following_utterance_id}",
                start_time=largest_incident.start_time,
                end_time=largest_incident.end_time,
                duration=largest_incident.gap_seconds,
                speaker="SILENCE",
                text=(
                    f"[MAX SILENCE GAP: {max_gap:.2f}s between "
                    f"'{largest_incident.preceding_utterance_id}' and '{largest_incident.following_utterance_id}']"
                ),
                preceding_utterance_id=largest_incident.preceding_utterance_id,
                following_utterance_id=largest_incident.following_utterance_id,
            )
        return CheckResult(
            check_id=check.check_id,
            check_type=check.type,
            critical=False,
            status=CheckStatus.PASS,
            confidence=1.0,
            expected=f"Silence gap <= {threshold:.1f}s",
            observed=f"Max observed gap: {max_gap:.2f}s",
            evidence=sample_ev,
            reason=(
                f"Maximum silence gap ({max_gap:.2f}s) is within the permitted "
                f"threshold of {threshold:.1f}s. Zero excessive dead air detected."
            ),
            check_version=check.version,
            utterance_id=largest_incident.preceding_utterance_id if largest_incident else None,
            preceding_utterance_id=largest_incident.preceding_utterance_id if largest_incident else None,
            following_utterance_id=largest_incident.following_utterance_id if largest_incident else None,
            duration=max_gap if largest_incident else None,
        )

    # -------------------------------------------------------------------------
    # Deterministic Metrics: Interruptions
    # -------------------------------------------------------------------------
    def _evaluate_interruptions(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript,
        evidence_index: EvidenceIndex,
    ) -> CheckResult:
        max_allowed = int(check.criteria.get("max_allowed_interruptions", 0))
        incidents = BehaviourMetrics.detect_interruptions(transcript)

        if len(incidents) > max_allowed:
            first_incident = incidents[0]
            evidence_ref = evidence_index.get_evidence(first_incident.utterance_id_a)
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=False,
                status=CheckStatus.FAIL,
                confidence=1.0,
                expected=f"Interruptions <= {max_allowed}",
                observed=f"{len(incidents)} speech collision(s) detected",
                evidence=evidence_ref,
                reason=(
                    f"Detected {len(incidents)} conversational interruption(s) exceeding tolerance of {max_allowed}. "
                    f"First collision between '{first_incident.utterance_id_a}' and '{first_incident.utterance_id_b}' "
                    f"with {first_incident.overlap_seconds:.2f}s overlap."
                ),
                check_version=check.version,
                utterance_id=first_incident.utterance_id_a,
            )

        first_ev = evidence_index.get_evidence(transcript.utterances[0].utterance_id) if transcript.utterances else None
        return CheckResult(
            check_id=check.check_id,
            check_type=check.type,
            critical=False,
            status=CheckStatus.PASS,
            confidence=1.0,
            expected=f"Interruptions <= {max_allowed}",
            observed=f"{len(incidents)} interruption(s)",
            evidence=first_ev,
            reason=(
                f"Clean conversational turn-taking observed. {len(incidents)} interruption(s) "
                f"detected, satisfying requirement of <= {max_allowed}."
            ),
            check_version=check.version,
            utterance_id=transcript.utterances[0].utterance_id if transcript.utterances else None,
        )

    # -------------------------------------------------------------------------
    # Controlled Semantic Evaluation: Rapport & Objection Handling
    # -------------------------------------------------------------------------
    def _evaluate_semantic_conduct(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript,
        evidence_index: EvidenceIndex,
        behaviour_name: str,
    ) -> CheckResult:
        min_confidence = float(check.criteria.get("min_confidence", self.default_confidence_threshold))

        if self.llm_client is None:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=False,
                status=CheckStatus.AMBIGUOUS,
                confidence=0.0,
                expected=f"Adequate {behaviour_name}",
                observed=None,
                evidence=None,
                reason=(
                    f"Semantic evaluation required for {behaviour_name}, but no LLM client "
                    f"is configured. Yields AMBIGUOUS for manual QA review."
                ),
                check_version=check.version,
                utterance_id=None,
            )

        extracted_claim = self.llm_client.extract_claim(check=check, transcript=transcript)
        confidence = extracted_claim.confidence or 0.0
        candidate_utterance_id = extracted_claim.utterance_id

        # Missing utterance evidence
        if not candidate_utterance_id:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=False,
                status=CheckStatus.AMBIGUOUS,
                confidence=confidence,
                expected=f"Positive {behaviour_name}",
                observed=None,
                evidence=None,
                reason=f"No supporting utterance identified for {behaviour_name}.",
                check_version=check.version,
                utterance_id=None,
            )

        # Grounding check in EvidenceIndex
        evidence_ref = evidence_index.get_evidence(candidate_utterance_id)
        if evidence_ref is None:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=False,
                status=CheckStatus.AMBIGUOUS,
                confidence=0.0,
                expected=f"Positive {behaviour_name}",
                observed=extracted_claim.raw_value,
                evidence=None,
                reason=(
                    f"Referenced utterance '{candidate_utterance_id}' for {behaviour_name} was not "
                    f"found in EvidenceIndex. Hallucinated evidence rejected."
                ),
                check_version=check.version,
                utterance_id=candidate_utterance_id,
            )

        # Confidence gating
        if confidence < min_confidence:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=False,
                status=CheckStatus.AMBIGUOUS,
                confidence=confidence,
                expected=f"Confidence >= {min_confidence:.2f}",
                observed=evidence_ref.text,
                evidence=evidence_ref,
                reason=(
                    f"Semantic classification confidence for {behaviour_name} ({confidence:.2f}) "
                    f"is below required threshold ({min_confidence:.2f}). Requires manual QA review."
                ),
                check_version=check.version,
                utterance_id=candidate_utterance_id,
            )

        # Classify polarity / outcome
        raw_val = str(extracted_claim.value or "").lower()
        if "negative" in raw_val or "fail" in raw_val or "poor" in raw_val or "dismissive" in raw_val:
            return CheckResult(
                check_id=check.check_id,
                check_type=check.type,
                critical=False,
                status=CheckStatus.FAIL,
                confidence=confidence,
                expected=f"Positive {behaviour_name}",
                observed=evidence_ref.text,
                evidence=evidence_ref,
                reason=f"Substandard {behaviour_name} detected in utterance '{candidate_utterance_id}'.",
                check_version=check.version,
                utterance_id=candidate_utterance_id,
            )

        return CheckResult(
            check_id=check.check_id,
            check_type=check.type,
            critical=False,
            status=CheckStatus.PASS,
            confidence=confidence,
            expected=f"Positive {behaviour_name}",
            observed=evidence_ref.text,
            evidence=evidence_ref,
            reason=(
                f"Effective {behaviour_name} demonstrated in utterance '{candidate_utterance_id}' "
                f"(confidence: {confidence:.2f})."
            ),
            check_version=check.version,
            utterance_id=candidate_utterance_id,
        )
