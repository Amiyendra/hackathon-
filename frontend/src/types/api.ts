/**
 * API Type Definitions for QA Gate Backend.
 * Strictly aligned with FastAPI models in app/api/models.py and app/gate/models.py.
 */

export type GateDecision = 'AUTO_SUBMIT' | 'HOLD' | 'QA_REVIEW';

export type CheckType = 'FACTUAL' | 'VERBATIM' | 'BEHAVIOUR';

export type CheckStatus =
  | 'PASS'
  | 'FAIL'
  | 'AMBIGUOUS'
  | 'LOW_CONFIDENCE'
  | 'UNSUPPORTED_CHECK';

export interface EvidenceReference {
  utterance_id: string;
  start_time: number;
  end_time: number;
  start?: number;
  end?: number;
  duration?: number | null;
  speaker: string;
  text: string;
  preceding_utterance_id?: string | null;
  following_utterance_id?: string | null;
}

export interface CheckResult {
  check_id: string;
  check_type: CheckType;
  critical: boolean;
  status: CheckStatus;
  confidence: number;
  expected: unknown;
  observed: unknown;
  reason: string;
  check_version: string;
  field?: string | null;
  utterance_id?: string | null;
  preceding_utterance_id?: string | null;
  following_utterance_id?: string | null;
  duration?: number | null;
  evidence?: EvidenceReference | null;
}

export interface GateResult {
  lead_id: string | null;
  retailer: string | null;
  call_date: string | null;
  decision: GateDecision;
  critical_checks_total: number;
  critical_checks_passed: number;
  critical_checks_failed: number;
  critical_checks_ambiguous: number;
  non_critical_failures: number;
  blocking_check_ids: string[];
  review_check_ids: string[];
  reasons: string[];
  gate_explanation: string;
  check_results: CheckResult[];
}

export interface IngestionResponse {
  ingestion_id: string;
  lead_id: string | null;
  retailer: string | null;
  call_date: string | null;
  utterance_count: number;
  status: string;
  transcript?: TranscriptPayload | null;
}

export interface AudioIngestionResponse {
  ingestion_id: string;
  status: string;
  source_type: string;
  utterance_count: number;
  duration_seconds: number;
  lead_id?: string | null;
  retailer?: string | null;
  call_date?: string | null;
  transcript?: TranscriptPayload | null;
}

export type QAProcessState =
  | 'IDLE'
  | 'UPLOADING'
  | 'TRANSCRIBING'
  | 'INDEXING'
  | 'VALIDATING'
  | 'READY'
  | 'EVALUATING'
  | 'SUCCESS'
  | 'ERROR';

export interface QARunRequest {
  scenario?: string;
  ingestion_id?: string;
  transcript?: unknown;
  lead_id?: string;
  retailer?: string;
  call_date?: string;
  expected_values_override?: Record<string, unknown>;
  target_check_ids?: string[];
  use_real_anthropic?: boolean;
}

export interface ScenarioInfo {
  scenario_id: string;
  name: string;
  description: string;
  expected_decision: GateDecision | string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  checks_loaded: number;
  default_provider: string;
}

export interface TranscriptUtterance {
  utterance_id: string;
  speaker: string;
  start_time: number;
  end_time: number;
  text: string;
}

export interface TranscriptPayload {
  transcript_id?: string;
  lead_id?: string;
  retailer?: string;
  call_date?: string;
  call_metadata?: {
    call_id?: string;
    retailer?: string;
    call_date?: string;
    provider?: string;
    channel?: string;
    redacted?: boolean;
    [key: string]: unknown;
  };
  utterances: TranscriptUtterance[];
}

export interface CheckDefinitionInfo {
  check_id: string;
  retailer: string;
  name: string;
  type: string;
  version: string;
  critical: boolean;
  description: string;
  criteria?: Record<string, unknown>;
}
