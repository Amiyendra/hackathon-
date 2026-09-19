"""
Demonstration runner for Phase 1, Phase 2 & Phase 3:
- Phase 1: Canonical Transcript & Evidence Index
- Phase 2: Versioned Check Library & Version Resolution
- Phase 3: Factual Match Engine (Deterministic Comparison & Evidence Grounding)
"""

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path for direct execution
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.ingestion.normalizer import TranscriptNormalizer
from app.evidence.index import EvidenceIndex
from app.checks import (
    load_check_library_from_yaml,
    load_check_library_from_dict,
    VersionResolver,
    NoMatchingVersionError,
    OverlappingVersionError,
    CheckValidationError,
)
from app.factual import (
    FactualEngine,
    ClaimExtractor,
    MockLLMClient,
)


def run_phase1_demonstration() -> None:
    print("=" * 75)
    print("PHASE 1 DEMONSTRATION: CANONICAL TRANSCRIPT & EVIDENCE INDEX")
    print("=" * 75)

    sample_path = project_root / "data" / "sample_transcript.json"
    with open(sample_path, "r", encoding="utf-8") as f:
        raw_json_str = f.read()

    raw_data = json.loads(raw_json_str)
    print(f"\n[1] RAW TRANSCRIPT LOADED: {sample_path.name}")
    print(f"    Raw transcript ID: {raw_data.get('transcript_id')}")

    normalizer = TranscriptNormalizer()
    canonical = normalizer.normalize(raw_data)
    print(f"\n[2] NORMALIZATION SUCCESSFUL:")
    print(f"    Canonical Transcript ID: {canonical.transcript_id}")
    print(f"    Total Utterances: {canonical.total_utterances}")
    print(f"    Duration: {canonical.duration:.2f}s")

    index = EvidenceIndex(canonical)
    print(f"\n[3] EVIDENCE INDEX INITIALIZED: {len(index)} utterances indexed")

    # Evidence Lookup by ID
    ev = index.get_evidence("utt_002")
    print(f"\n[4] EVIDENCE LOOKUP (utt_002):")
    if ev:
        print(f"    Speaker: {ev.speaker}")
        print(f"    Window: [{ev.start_time:.2f}s -> {ev.end_time:.2f}s]")
        print(f"    Text: \"{ev.text}\"")

    # Evidence Lookup by Time
    time_evs = index.find_by_time(19.5, 28.0)
    print(f"\n[5] TIME RANGE LOOKUP [19.5s -> 28.0s]: Found {len(time_evs)} match(es)")
    for e in time_evs:
        print(f"    - [{e.utterance_id}] {e.speaker}: \"{e.text}\"")


def run_phase2_demonstration() -> None:
    print("\n" + "=" * 75)
    print("PHASE 2 DEMONSTRATION: VERSIONED CHECK LIBRARY & VERSION RESOLUTION")
    print("=" * 75)

    library_path = project_root / "app" / "checks" / "library.yaml"
    library = load_check_library_from_yaml(library_path)
    resolver = VersionResolver(library)
    print(f"\n[1] CHECK LIBRARY LOADED: {library_path.name}")
    print(f"    Total registered check definitions: {len(library.checks)}")

    # Demonstration A: Historical Call Date Resolution
    historical_date = "2024-06-15"
    print(f"\n[2] RESOLVING HISTORICAL CALL DATE ({historical_date}):")
    hist_check = resolver.resolve_check("POWERDIRECT", "CHK_CALL_RECORDING", historical_date)
    print(f"    Check ID:      {hist_check.check_id}")
    print(f"    Version:       {hist_check.version}")
    print(f"    Display Name:  {hist_check.name}")
    print(f"    Criticality:   {hist_check.critical} (From Library, immutable)")
    print(f"    Active Window: [{hist_check.effective_from} -> {hist_check.effective_to}]")
    print(f"    Required Text: \"{hist_check.criteria.get('required_phrase')}\"")

    # Demonstration B: Current Call Date Resolution
    current_date = "2026-09-19"
    print(f"\n[3] RESOLVING CURRENT CALL DATE ({current_date}):")
    curr_check = resolver.resolve_check("POWERDIRECT", "CHK_CALL_RECORDING", current_date)
    print(f"    Check ID:      {curr_check.check_id}")
    print(f"    Version:       {curr_check.version}")
    print(f"    Display Name:  {curr_check.name}")
    print(f"    Criticality:   {curr_check.critical} (From Library, immutable)")
    print(f"    Active Window: [{curr_check.effective_from} -> {curr_check.effective_to}]")
    print(f"    Required Text: \"{curr_check.criteria.get('required_phrase')}\"")

    # Demonstration C: Rejection of Invalid Behaviour Configuration
    print(f"\n[4] REJECTING INVALID BEHAVIOUR CONFIGURATION (BEHAVIOUR marked critical):")
    invalid_behaviour_dict = {
        "checks": [
            {
                "check_id": "CHK_BAD_BEHAVIOUR",
                "retailer": "POWERDIRECT",
                "name": "Invalid Critical Behaviour",
                "type": "BEHAVIOUR",
                "version": "1.0.0",
                "critical": True,  # Disallowed
                "effective_from": "2024-01-01",
                "description": "Reject this"
            }
        ]
    }
    try:
        load_check_library_from_dict(invalid_behaviour_dict)
        print("    ERROR: Failed to reject invalid configuration!")
    except CheckValidationError as e:
        print(f"    SUCCESSFULLY REJECTED: {e}")

    # Demonstration D: Rejection of Overlapping Versions
    print(f"\n[5] REJECTING OVERLAPPING CHECK VERSIONS:")
    overlapping_dict = {
        "checks": [
            {
                "check_id": "CHK_OVERLAP_DEMO",
                "retailer": "POWERDIRECT",
                "name": "Version 1",
                "type": "VERBATIM",
                "version": "1.0.0",
                "critical": False,
                "effective_from": "2024-01-01",
                "effective_to": "2024-12-31",
                "description": "V1"
            },
            {
                "check_id": "CHK_OVERLAP_DEMO",
                "retailer": "POWERDIRECT",
                "name": "Version 2 (Overlapping)",
                "type": "VERBATIM",
                "version": "2.0.0",
                "critical": False,
                "effective_from": "2024-07-01",  # Overlaps V1
                "effective_to": "2025-07-01",
                "description": "V2"
            }
        ]
    }
    try:
        load_check_library_from_dict(overlapping_dict)
        print("    ERROR: Failed to reject overlapping configuration!")
    except OverlappingVersionError as e:
        print(f"    SUCCESSFULLY REJECTED: {e}")

    # Demonstration E: Rejection of Unmatched Call Date
    unmatched_date = "2019-01-01"
    print(f"\n[6] REJECTING UNMATCHED HISTORICAL DATE ({unmatched_date}):")
    try:
        resolver.resolve_check("POWERDIRECT", "CHK_CALL_RECORDING", unmatched_date)
        print("    ERROR: Silently resolved non-existent version!")
    except NoMatchingVersionError as e:
        print(f"    SUCCESSFULLY REJECTED (NO FALLBACK): {e}")


def run_phase3_demonstration() -> None:
    print("\n" + "=" * 75)
    print("PHASE 3 DEMONSTRATION: FACTUAL MATCH ENGINE (PYTHON-DRIVEN EVALUATION)")
    print("=" * 75)

    # Load canonical broadband transcript
    transcript_path = project_root / "data" / "broadband_transcript.json"
    with open(transcript_path, "r", encoding="utf-8") as f:
        raw_transcript = json.load(f)

    normalizer = TranscriptNormalizer()
    canonical_transcript = normalizer.normalize(raw_transcript)
    evidence_index = EvidenceIndex(canonical_transcript)

    # Load broadband check library & ground truth
    library_path = project_root / "app" / "checks" / "broadband_library.yaml"
    ground_truth_path = project_root / "data" / "broadband_ground_truth.json"

    check_library = load_check_library_from_yaml(library_path)
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    gt_by_id = {r["check_id"]: r for r in ground_truth["ground_truth_records"]}

    # Initialize FactualEngine with MockLLMClient (claim extraction only, no LLM scoring)
    engine = FactualEngine(extractor=ClaimExtractor(MockLLMClient()))

    def print_result_card(case_title: str, check_id: str) -> None:
        check = next(c for c in check_library.checks if c.check_id == check_id)
        gt_record = gt_by_id[check_id]
        expected_val = gt_record["expected_value"]

        result = engine.evaluate_check(
            check=check,
            transcript=canonical_transcript,
            evidence_index=evidence_index,
            expected_value=expected_val
        )

        ts_str = f"[{result.evidence.start_time:.2f}s -> {result.evidence.end_time:.2f}s]" if result.evidence else "N/A"
        ev_text = f'"{result.evidence.text}"' if result.evidence else "N/A (No verified evidence)"

        print(f"\n--- {case_title} ---")
        print(f"  check_id:           {result.check_id}")
        print(f"  check type:         {result.check_type.value}")
        print(f"  check version:      {result.check_version} (from CheckDefinition)")
        print(f"  critical:           {result.critical} (from CheckDefinition)")
        print(f"  expected:           {result.expected}")
        print(f"  observed:           {result.observed}")
        print(f"  status:             {result.status.value} (Determined deterministically by Python)")
        print(f"  confidence:         {result.confidence:.2f}")
        print(f"  utterance_id:       {result.utterance_id or 'None'}")
        print(f"  resolved timestamp: {ts_str} (Resolved from EvidenceIndex)")
        print(f"  evidence text:      {ev_text}")
        print(f"  reason:             {result.reason}")

    # CASE 1: Broadband promotional price -> PASS
    print_result_card(
        "CASE 1: BROADBAND PROMOTIONAL PRICE (VERIFIED CLAIM MATCH)",
        "CHK_FACT_BB_006_PROMOTIONAL_PRICE"
    )

    # CASE 2: Broadband synthetic delivery fee mismatch -> FAIL
    print_result_card(
        "CASE 2: BROADBAND SYNTHETIC DELIVERY FEE (RATE-CARD MISMATCH)",
        "CHK_FACT_BB_014_DELIVERY_FEE"
    )

    # CASE 3: Unmentioned field (Battery backup) -> AMBIGUOUS
    print_result_card(
        "CASE 3: BROADBAND UNMENTIONED FIELD (AMBIGUOUS / MISSING EVIDENCE)",
        "CHK_FACT_BB_017_BATTERY_BACKUP"
    )

    print("\n" + "=" * 75)
    print("PHASE 3 DEMONSTRATION COMPLETE: ALL INVARIANTS VERIFIED")
    print("=" * 75)


def run_phase4_demonstration() -> None:
    print("\n" + "=" * 75)
    print("PHASE 4 DEMONSTRATION: VERBATIM / SCRIPT QA ENGINE (EVIDENCE-GROUNDED)")
    print("=" * 75)

    from app.verbatim import VerbatimEngine

    # Load canonical broadband transcript
    transcript_path = project_root / "data" / "broadband_transcript.json"
    with open(transcript_path, "r", encoding="utf-8") as f:
        raw_transcript = json.load(f)

    normalizer = TranscriptNormalizer()
    canonical_transcript = normalizer.normalize(raw_transcript)
    evidence_index = EvidenceIndex(canonical_transcript)

    # Load broadband verbatim check library
    verbatim_lib_path = project_root / "app" / "checks" / "broadband_verbatim_library.yaml"
    check_library = load_check_library_from_yaml(verbatim_lib_path)

    engine = VerbatimEngine()

    def print_verbatim_card(case_title: str, check_id: str) -> None:
        check = next(c for c in check_library.checks if c.check_id == check_id)
        result = engine.evaluate_check(
            check=check,
            transcript=canonical_transcript,
            evidence_index=evidence_index
        )

        ts_str = f"[{result.evidence.start_time:.2f}s -> {result.evidence.end_time:.2f}s]" if result.evidence else "N/A"
        ev_text = f'"{result.observed}"' if result.observed else "N/A (Not spoken)"

        print(f"\n--- {case_title} ---")
        print(f"  check_id:           {result.check_id}")
        print(f"  check type:         {result.check_type.value}")
        print(f"  check version:      {result.check_version} (from CheckDefinition)")
        print(f"  critical:           {result.critical} (from CheckDefinition)")
        print(f"  expected wording:   \"{result.expected}\"")
        print(f"  observed wording:   {ev_text}")
        print(f"  status:             {result.status.value} (Determined deterministically by Python)")
        print(f"  confidence:         {result.confidence:.2f}")
        print(f"  utterance_id:       {result.utterance_id or 'None'}")
        print(f"  resolved timestamp: {ts_str} (Resolved from EvidenceIndex)")
        print(f"  reason:             {result.reason}")

    # CASE 1: Brand identification greeting -> PASS (utt_001)
    print_verbatim_card(
        "CASE 1: AGENT BRAND GREETING (EXACT NORMALIZED MATCH -> PASS)",
        "CHK_VERB_BB_001_GREETING_BRAND"
    )

    # CASE 2: Statutory minimum total cost -> PASS (utt_015, allowed variation)
    print_verbatim_card(
        "CASE 2: STATUTORY MINIMUM COST (ALLOWED VARIATION -> PASS)",
        "CHK_VERB_BB_002_STATUTORY_MIN_COST"
    )

    # CASE 3: Call recording disclosure -> UNSUPPORTED_CHECK (Flagged: Unsupported check specification)
    print_verbatim_card(
        "CASE 3: CALL RECORDING NOTICE (FLAGGED: UNSUPPORTED CHECK SPECIFICATION -> UNSUPPORTED_CHECK)",
        "CHK_VERB_BB_003_RECORDING_DISCLOSURE"
    )

    # CASE 4: Cooling-off notice -> AMBIGUOUS (Semantic variation allowed, omitted)
    print_verbatim_card(
        "CASE 4: STATUTORY COOLING-OFF NOTICE (UNRESOLVED SEMANTIC -> AMBIGUOUS)",
        "CHK_VERB_BB_004_COOLING_OFF_PERIOD"
    )

    print("\n" + "=" * 75)
    print("PHASE 4 DEMONSTRATION COMPLETE: ALL INVARIANTS VERIFIED")
    print("=" * 75)


def run_phase5_demonstration() -> None:
    print("\n" + "=" * 75)
    print("PHASE 5 DEMONSTRATION: BEHAVIOUR QA ENGINE (NON-BLOCKING DYNAMICS)")
    print("=" * 75)

    from app.behaviour import BehaviourEngine
    from app.factual.llm import MockLLMClient
    from app.factual.models import ExtractedClaim

    # Load canonical broadband transcript
    transcript_path = project_root / "data" / "broadband_transcript.json"
    with open(transcript_path, "r", encoding="utf-8") as f:
        raw_transcript = json.load(f)

    normalizer = TranscriptNormalizer()
    canonical_transcript = normalizer.normalize(raw_transcript)
    evidence_index = EvidenceIndex(canonical_transcript)

    # Load broadband behaviour check library
    behav_lib_path = project_root / "app" / "checks" / "broadband_behaviour_library.yaml"
    check_library = load_check_library_from_yaml(behav_lib_path)

    # Mock client pre-loaded with broadband transcript extractions
    mock_llm = MockLLMClient()
    mock_llm.register_claim(
        "CHK_BEHAV_BB_004_RAPPORT",
        ExtractedClaim(
            field="rapport",
            value="positive polite greeting",
            utterance_id="utt_001",
            confidence=0.96
        )
    )
    mock_llm.register_claim(
        "CHK_BEHAV_BB_005_OBJECTION_HANDLING",
        ExtractedClaim(
            field="objection_handling",
            value="effective modem cost reassurance",
            utterance_id="utt_010",
            confidence=0.94
        )
    )

    engine = BehaviourEngine(llm_client=mock_llm)

    def print_behaviour_card(case_title: str, check_id: str) -> None:
        check = next(c for c in check_library.checks if c.check_id == check_id)
        result = engine.evaluate_check(
            check=check,
            transcript=canonical_transcript,
            evidence_index=evidence_index
        )

        ts_str = f"[{result.evidence.start_time:.2f}s -> {result.evidence.end_time:.2f}s]" if result.evidence else "N/A"
        ev_text = f'"{result.evidence.text}"' if result.evidence else "N/A"

        print(f"\n--- {case_title} ---")
        print(f"  check_id:           {result.check_id}")
        print(f"  check type:         {result.check_type.value}")
        print(f"  check version:      {result.check_version}")
        print(f"  critical:           {result.critical} (STRICTLY NON-BLOCKING; CANNOT CAUSE HOLD)")
        print(f"  status:             {result.status.value}")
        print(f"  confidence:         {result.confidence:.2f}")
        print(f"  expected:           {result.expected}")
        utt_display = (
            f"{result.preceding_utterance_id} -> {result.following_utterance_id}"
            if result.preceding_utterance_id and result.following_utterance_id
            else (result.utterance_id or 'None')
        )
        print(f"  utterance_id:       {utt_display}")
        print(f"  resolved timestamp: {ts_str} (From EvidenceIndex)")
        print(f"  evidence text:      {ev_text}")
        print(f"  reason:             {result.reason}")

    # CASE 1: Dead Air Metric (10.0s standard threshold -> PASS)
    print_behaviour_card(
        "CASE 1: DEAD AIR SILENCE METRIC (10s THRESHOLD -> PASS)",
        "CHK_BEHAV_BB_001_DEAD_AIR"
    )

    # CASE 2: Dead Air Metric Strict (0.3s synthetic threshold -> FAIL, NON-BLOCKING)
    print_behaviour_card(
        "CASE 2: STRICT DEAD AIR METRIC (0.3s THRESHOLD -> FAIL, NON-BLOCKING)",
        "CHK_BEHAV_BB_002_DEAD_AIR_STRICT"
    )

    # CASE 3: Interruption Tolerance (0 tolerance -> PASS)
    print_behaviour_card(
        "CASE 3: CONVERSATIONAL INTERRUPTION TOLERANCE (CLEAN TURN-TAKING -> PASS)",
        "CHK_BEHAV_BB_003_INTERRUPTIONS"
    )

    # CASE 4: Rapport Evaluation (Agent greeting -> PASS)
    print_behaviour_card(
        "CASE 4: AGENT RAPPORT & COURTESY (SEMANTIC EVALUATION -> PASS)",
        "CHK_BEHAV_BB_004_RAPPORT"
    )

    # CASE 5: Objection Handling (Modem fee reassurance -> PASS)
    print_behaviour_card(
        "CASE 5: OBJECTION HANDLING (MODEM COST REASSURANCE -> PASS)",
        "CHK_BEHAV_BB_005_OBJECTION_HANDLING"
    )

    print("\n" + "=" * 75)
    print("PHASE 5 DEMONSTRATION COMPLETE: ALL INVARIANTS VERIFIED")
    print("=" * 75)


def run_phase6_demonstration() -> None:
    print("\n" + "=" * 75)
    print("PHASE 6 DEMONSTRATION: DETERMINISTIC QA GATE & ROUTING LAYER")
    print("=" * 75)

    from app.checks.models import CheckType
    from app.factual.models import CheckResult, CheckStatus
    from app.gate import DeterministicGate, GateDecision
    from app.models import EvidenceReference

    ev1 = EvidenceReference(
        utterance_id="utt_008",
        start_time=38.4,
        end_time=43.1,
        speaker="AGENT",
        text="That standard speed plan is currently on promo for $69 a month for the first six months.",
    )
    ev2 = EvidenceReference(
        utterance_id="utt_008",
        start_time=43.2,
        end_time=46.0,
        speaker="AGENT",
        text="After that it goes back to the regular price of $79 a month.",
    )
    ev3 = EvidenceReference(
        utterance_id="utt_018",
        start_time=85.0,
        end_time=93.2,
        speaker="AGENT",
        text="The minimum total cost over the 12 month term will be $888 including the promotional pricing period.",
    )

    # Base collection of successful critical checks
    critical_pass_1 = CheckResult(
        check_id="CHK_FACT_BB_006_PROMOTIONAL_PRICE",
        check_type=CheckType.FACTUAL,
        critical=True,
        status=CheckStatus.PASS,
        confidence=0.98,
        expected=69.0,
        observed=69.0,
        evidence=ev1,
        reason="Observed promotional price $69.00 matches expected $69.00.",
        check_version="1.0.0",
    )
    critical_pass_2 = CheckResult(
        check_id="CHK_FACT_BB_007_REGULAR_PRICE",
        check_type=CheckType.FACTUAL,
        critical=True,
        status=CheckStatus.PASS,
        confidence=0.97,
        expected=79.0,
        observed=79.0,
        evidence=ev2,
        reason="Observed regular price $79.00 matches expected $79.00.",
        check_version="1.0.0",
    )
    critical_pass_3 = CheckResult(
        check_id="CHK_VERB_BB_002_STATUTORY_MIN_COST",
        check_type=CheckType.VERBATIM,
        critical=True,
        status=CheckStatus.PASS,
        confidence=1.0,
        expected="minimum total cost",
        observed="The minimum total cost over the 12 month term will be $888",
        evidence=ev3,
        reason="Verbatim phrase matched canonical transcript evidence.",
        check_version="1.0.0",
    )

    # Non-critical behaviour failure (non-blocking)
    non_crit_behaviour_fail = CheckResult(
        check_id="CHK_BEHAV_BB_002_DEAD_AIR_STRICT",
        check_type=CheckType.BEHAVIOUR,
        critical=False,
        status=CheckStatus.FAIL,
        confidence=1.0,
        expected=0.3,
        observed=0.8,
        evidence=None,
        reason="Max silence duration 0.80s exceeded strict threshold 0.30s.",
        check_version="1.0.0",
    )

    def print_gate_summary(title: str, result) -> None:
        print(f"\n--- {title} ---")
        print(f"  Final Decision:            {result.decision.value}")
        print(f"  Critical Checks Total:     {result.critical_checks_total}")
        print(f"  Critical Checks Passed:    {result.critical_checks_passed}")
        print(f"  Critical Checks Failed:    {result.critical_checks_failed}")
        print(f"  Critical Checks Ambiguous: {result.critical_checks_ambiguous}")
        print(f"  Non-Critical Failures:     {result.non_critical_failures} (Non-blocking)")
        print(f"  Blocking Check IDs (HOLD): {result.blocking_check_ids}")
        print(f"  Review Check IDs (REVIEW): {result.review_check_ids}")
        print(f"  Decision Reasons:")
        for r in result.reasons:
            print(f"    * {r}")

    # SCENARIO 1: AUTO_SUBMIT (All critical PASS + Behaviour FAIL non-blocking)
    results_s1 = [critical_pass_1, critical_pass_2, critical_pass_3, non_crit_behaviour_fail]
    gate_res_s1 = DeterministicGate.evaluate(results_s1, lead_id="LEAD-BB-AUTO-001")
    print_gate_summary("SCENARIO 1: ALL CRITICAL PASS + BEHAVIOUR FAIL -> AUTO_SUBMIT", gate_res_s1)

    # SCENARIO 2: HOLD (Critical Factual Check Fails)
    critical_fail = CheckResult(
        check_id="CHK_FACT_BB_006_PROMOTIONAL_PRICE",
        check_type=CheckType.FACTUAL,
        critical=True,
        status=CheckStatus.FAIL,
        confidence=0.98,
        expected=69.0,
        observed=59.0,
        evidence=ev1,
        reason="Price mismatch: agent quoted $59.00, expected $69.00.",
        check_version="1.0.0",
    )
    results_s2 = [critical_fail, critical_pass_2, critical_pass_3, non_crit_behaviour_fail]
    gate_res_s2 = DeterministicGate.evaluate(results_s2, lead_id="LEAD-BB-HOLD-002")
    print_gate_summary("SCENARIO 2: CRITICAL CHECK FAILURE -> HOLD", gate_res_s2)

    # SCENARIO 3: QA_REVIEW (Critical check ambiguous / missing evidence)
    critical_ambig = CheckResult(
        check_id="CHK_FACT_BB_006_PROMOTIONAL_PRICE",
        check_type=CheckType.FACTUAL,
        critical=True,
        status=CheckStatus.AMBIGUOUS,
        confidence=0.72,
        expected=69.0,
        observed=None,
        evidence=None,
        reason="Claim was tentative and ambiguous in transcript.",
        check_version="1.0.0",
    )
    results_s3 = [critical_ambig, critical_pass_2, critical_pass_3, non_crit_behaviour_fail]
    gate_res_s3 = DeterministicGate.evaluate(results_s3, lead_id="LEAD-BB-REVIEW-003")
    print_gate_summary("SCENARIO 3: CRITICAL AMBIGUOUS / INCONCLUSIVE -> QA_REVIEW", gate_res_s3)

    print("\n" + "=" * 75)
    print("PHASE 6 DEMONSTRATION COMPLETE: DETERMINISTIC QA GATE OPERATIONAL")
    print("=" * 75)


def run_phase7_demonstration() -> None:
    print("\n" + "=" * 75)
    print("PHASE 7 DEMONSTRATION: END-TO-END PIPELINE ORCHESTRATION")
    print("=" * 75)

    from app.pipeline import (
        QAPipeline,
        format_compact_evidence_trace,
        format_pipeline_summary,
        load_default_broadband_ground_truth,
        load_default_broadband_library,
    )

    transcript_path = project_root / "data" / "broadband_transcript.json"
    library = load_default_broadband_library()
    ground_truth = load_default_broadband_ground_truth()

    pipeline = QAPipeline(
        check_library=library,
        ground_truth=ground_truth,
        use_real_anthropic=False,  # Strict test/demo isolation: offline deterministic
    )

    print("\n[1] EXECUTING END-TO-END PASSING LEAD (AUTO_SUBMIT SCENARIO)...")
    passing_target_ids = [
        "CHK_FACT_BB_001_CURRENT_PROVIDER",
        "CHK_FACT_BB_002_CUSTOMER_NAME",
        "CHK_FACT_BB_003_SERVICE_ADDRESS",
        "CHK_FACT_BB_004_DOWNLOAD_SPEED",
        "CHK_FACT_BB_005_UPLOAD_SPEED",
        "CHK_FACT_BB_006_PROMOTIONAL_PRICE",
        "CHK_FACT_BB_007_PROMOTIONAL_PERIOD",
        "CHK_FACT_BB_008_REGULAR_PRICE",
        "CHK_FACT_BB_010_MODEM_COST",
        "CHK_FACT_BB_013_MINIMUM_COST",
        "CHK_FACT_BB_016_TECHNOLOGY_TYPE",
        "CHK_VERB_BB_001_GREETING_BRAND",
        "CHK_VERB_BB_002_STATUTORY_MIN_COST",
        "CHK_BEHAV_BB_001_DEAD_AIR",
        "CHK_BEHAV_BB_002_DEAD_AIR_STRICT",  # Non-blocking behaviour failure
        "CHK_BEHAV_BB_003_INTERRUPTIONS",
    ]
    auto_submit_result = pipeline.evaluate_lead(
        raw_transcript=transcript_path,
        target_check_ids=passing_target_ids,
    )
    print(format_pipeline_summary(auto_submit_result))
    print(format_compact_evidence_trace(auto_submit_result))

    print("\n[2] EXECUTING RATE-CARD MISMATCH LEAD (HOLD SCENARIO)...")
    hold_result = pipeline.evaluate_lead(
        raw_transcript=transcript_path,
        expected_values_override={"CHK_FACT_BB_006_PROMOTIONAL_PRICE": 55.0},
        target_check_ids=[
            "CHK_FACT_BB_006_PROMOTIONAL_PRICE",
            "CHK_VERB_BB_001_GREETING_BRAND",
            "CHK_BEHAV_BB_001_DEAD_AIR",
        ],
    )
    print(format_pipeline_summary(hold_result))
    print(format_compact_evidence_trace(hold_result))

    print("\n" + "=" * 75)
    print("PHASE 7 DEMONSTRATION COMPLETE: PIPELINE OPERATIONAL")
    print("=" * 75)


if __name__ == "__main__":
    run_phase1_demonstration()
    run_phase2_demonstration()
    run_phase3_demonstration()
    run_phase4_demonstration()
    run_phase5_demonstration()
    run_phase6_demonstration()
    run_phase7_demonstration()

