'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Header } from '@/components/Header';
import { DecisionCard } from '@/components/DecisionCard';
import { MetricsRow } from '@/components/MetricsRow';
import { UploadTranscriptCard, QAProcessState } from '@/components/UploadTranscriptCard';
import { ScenarioSelector } from '@/components/ScenarioSelector';
import { ChecksTable } from '@/components/ChecksTable';
import { CheckDetailDrawer } from '@/components/CheckDetailDrawer';
import { TranscriptView } from '@/components/TranscriptView';
import { BenchmarkPanel } from '@/components/BenchmarkPanel';
import { api, ApiError } from '@/lib/api';
import {
  GateResult,
  HealthResponse,
  ScenarioInfo,
  CheckResult,
  TranscriptPayload,
  IngestionResponse,
  AudioIngestionResponse,
} from '@/types/api';
import { AlertCircle, RefreshCw, CheckSquare } from 'lucide-react';

export default function QAControlCenterPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [retailers, setRetailers] = useState<string[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>('auto_submit');

  // Real Ingestion + QA State
  const [processState, setProcessState] = useState<QAProcessState>('IDLE');
  const [stateMessage, setStateMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [ingestion, setIngestion] = useState<IngestionResponse | AudioIngestionResponse | null>(null);

  // Result state (dynamically populated exclusively from API)
  const [gateResult, setGateResult] = useState<GateResult | null>(null);
  const [transcript, setTranscript] = useState<TranscriptPayload | null>(null);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [selectedCheck, setSelectedCheck] = useState<CheckResult | null>(null);
  const [activeUtteranceId, setActiveUtteranceId] = useState<string | null>(null);

  // 1. Fetch initial metadata: health, available scenarios, retailers
  const loadInitialData = useCallback(async () => {
    try {
      const [h, sc, ret] = await Promise.allSettled([
        api.getHealth(),
        api.getScenarios(),
        api.getRetailers(),
      ]);

      if (h.status === 'fulfilled') {
        setHealth(h.value);
        setHealthError(false);
      } else {
        setHealthError(true);
      }

      if (sc.status === 'fulfilled') {
        setScenarios(sc.value);
      }

      if (ret.status === 'fulfilled') {
        setRetailers(ret.value);
      }
    } catch {
      setHealthError(true);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const [h, sc, ret] = await Promise.allSettled([
          api.getHealth(),
          api.getScenarios(),
          api.getRetailers(),
        ]);

        if (!ignore) {
          if (h.status === 'fulfilled') {
            setHealth(h.value);
            setHealthError(false);
          } else {
            setHealthError(true);
          }

          if (sc.status === 'fulfilled') {
            setScenarios(sc.value);
          }

          if (ret.status === 'fulfilled') {
            setRetailers(ret.value);
          }
        }
      } catch {
        if (!ignore) setHealthError(true);
      }
    }

    init();
    return () => {
      ignore = true;
    };
  }, []);

  // 2. Real Upload Workflow: Upload -> Ingest -> Evaluate -> Render
  const handleStartReview = async (
    file: File,
    metadata: { lead_id?: string; retailer?: string; call_date?: string }
  ) => {
    setErrorMessage(null);
    setProcessState('UPLOADING');
    setStateMessage('Uploading transcript JSON payload...');

    try {
      // Step A: Ingest transcript via API
      const ingestRes = await api.uploadTranscript(file, metadata);
      setIngestion(ingestRes);
      setProcessState('VALIDATING');
      setStateMessage(`✓ Transcript validated · ${ingestRes.utterance_count} utterances normalized`);

      // Step B: Evaluate ingested transcript through QA pipeline
      setProcessState('EVALUATING');
      setStateMessage('Evaluating compliance checks against check library & applying deterministic gate...');

      const qaResult = await api.runQA({
        ingestion_id: ingestRes.ingestion_id,
        retailer: metadata.retailer || ingestRes.retailer || undefined,
        call_date: metadata.call_date || ingestRes.call_date || undefined,
        lead_id: metadata.lead_id || ingestRes.lead_id || undefined,
      });

      // Step C: Retrieve canonical transcript for this ingestion session
      const transcriptData = await api.getTranscript(ingestRes.ingestion_id);
      setTranscript(transcriptData);
      setGateResult(qaResult);
      setProcessState('SUCCESS');
      setStateMessage('✓ Evaluation complete — live deterministic decision rendered');

      // Select first failing check if any, or first check
      const firstIssue = qaResult.check_results.find((c) => c.status !== 'PASS');
      if (firstIssue) {
        setSelectedCheck(firstIssue);
        if (firstIssue.evidence) {
          setActiveUtteranceId(firstIssue.evidence.utterance_id);
        }
      } else if (qaResult.check_results.length > 0) {
        setSelectedCheck(qaResult.check_results[0]);
      }
    } catch (err: unknown) {
      setProcessState('ERROR');
      let detail = 'An unexpected error occurred during evaluation.';
      if (err instanceof ApiError) {
        detail = err.detail || err.message;
      } else if (err instanceof Error) {
        detail = err.message;
      }

      // Explicit Anthropic credentials warning
      if (detail.includes('Anthropic') || detail.includes('credentials')) {
        detail = 'QA evaluation unavailable — configure Anthropic API credentials.';
      }

      setErrorMessage(detail);
      setStateMessage('');
    }
  };

  // 2b. Audio Upload Workflow: Audio File -> Deepgram STT -> Ingestion -> Evaluate -> Render
  const handleStartAudioReview = async (
    file: File,
    metadata: {
      lead_id?: string;
      retailer?: string;
      call_date?: string;
      speaker_0_role?: string;
      speaker_1_role?: string;
    }
  ) => {
    setErrorMessage(null);
    setProcessState('UPLOADING');
    setStateMessage('Uploading audio recording to QA Control Center...');

    try {
      // Step A: Transcribe via Deepgram
      setProcessState('TRANSCRIBING');
      setStateMessage('Transcribing speech via Deepgram STT (prerecorded audio)...');

      const audioRes = await api.uploadAudio(file, metadata);
      setIngestion(audioRes);

      // Step B: Indexing & Diarization
      setProcessState('INDEXING');
      setStateMessage(`✓ Speech transcribed (${audioRes.utterance_count} utterances) · Identifying speakers & indexing transcript...`);
      await new Promise((r) => setTimeout(r, 450));

      // Step C: Ready for QA
      setProcessState('READY');
      setStateMessage('✓ Speakers identified · Transcript indexed & ready for QA evaluation');
      await new Promise((r) => setTimeout(r, 350));

      // Step D: Evaluate through existing QA Pipeline
      setProcessState('EVALUATING');
      setStateMessage('Evaluating compliance checks against check library & applying deterministic gate...');

      const qaResult = await api.runQA({
        ingestion_id: audioRes.ingestion_id,
        retailer: metadata.retailer || audioRes.retailer || undefined,
        call_date: metadata.call_date || audioRes.call_date || undefined,
        lead_id: metadata.lead_id || audioRes.lead_id || undefined,
      });

      // Step E: Retrieve canonical transcript for this session
      const transcriptData = await api.getTranscript(audioRes.ingestion_id);
      setTranscript(transcriptData);
      setGateResult(qaResult);
      setProcessState('SUCCESS');
      setStateMessage('✓ QA evaluation complete — live deterministic decision rendered');

      const firstIssue = qaResult.check_results.find((c) => c.status !== 'PASS');
      if (firstIssue) {
        setSelectedCheck(firstIssue);
        if (firstIssue.evidence) {
          setActiveUtteranceId(firstIssue.evidence.utterance_id);
        }
      } else if (qaResult.check_results.length > 0) {
        setSelectedCheck(qaResult.check_results[0]);
      }
    } catch (err: unknown) {
      setProcessState('ERROR');
      let detail = 'An unexpected error occurred during audio transcription or evaluation.';
      if (err instanceof ApiError) {
        detail = err.detail || err.message;
      } else if (err instanceof Error) {
        detail = err.message;
      }

      if (detail.includes('Anthropic') || detail.includes('credentials')) {
        detail = 'QA evaluation unavailable — configure Anthropic API credentials.';
      }

      setErrorMessage(detail);
      setStateMessage('');
    }
  };

  // 3. Developer / Demo Scenario Rehearsal
  const handleRunScenario = async (scenarioId: string) => {
    setScenarioLoading(true);
    setErrorMessage(null);
    try {
      const [result, defaultTranscript] = await Promise.all([
        api.runQA({ scenario: scenarioId }),
        api.getTranscript(),
      ]);

      setGateResult(result);
      setTranscript(defaultTranscript);
      setIngestion(null);
      setProcessState('IDLE');

      const failed = result.check_results.find((c) => c.status !== 'PASS');
      if (failed) {
        setSelectedCheck(failed);
        if (failed.evidence) {
          setActiveUtteranceId(failed.evidence.utterance_id);
        }
      } else if (result.check_results.length > 0) {
        setSelectedCheck(result.check_results[0]);
      }
    } catch (err: unknown) {
      const detail =
        (err as { detail?: string })?.detail ||
        (err instanceof Error ? err.message : String(err));
      setErrorMessage(detail || 'Failed to execute demo scenario evaluation.');
    } finally {
      setScenarioLoading(false);
    }
  };

  const handleSelectCheck = (check: CheckResult) => {
    setSelectedCheck(check);
    if (check.evidence) {
      setActiveUtteranceId(check.evidence.utterance_id);
    }
  };

  const handleLocateInTranscript = (utteranceId: string) => {
    setActiveUtteranceId(utteranceId);
  };

  const handleReset = () => {
    setGateResult(null);
    setTranscript(null);
    setIngestion(null);
    setSelectedCheck(null);
    setActiveUtteranceId(null);
    setProcessState('IDLE');
    setErrorMessage(null);
    setStateMessage('');
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50/50 text-slate-900 selection:bg-slate-200">
      {/* Top Application Header */}
      <Header
        health={health}
        healthError={healthError}
        onRefreshHealth={loadInitialData}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-7 space-y-7">
        {/* Backend Error Alert Banner if unreachable */}
        {healthError && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start justify-between gap-4 text-xs">
            <div className="flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-rose-900 block text-sm">
                  QA Engine Backend Unavailable
                </span>
                <p className="text-rose-700 mt-1">
                  Unable to establish connection to FastAPI service at http://localhost:8000.
                </p>
              </div>
            </div>

            <button
              onClick={loadInitialData}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-white hover:bg-rose-100 text-rose-800 border border-rose-300 transition-colors shrink-0 text-xs font-medium shadow-2xs"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {/* PRIMARY WORKFLOW: Real Transcript Ingestion & QA Review Trigger */}
        <UploadTranscriptCard
          onStartReview={handleStartReview}
          onStartAudioReview={handleStartAudioReview}
          processState={processState}
          stateMessage={stateMessage}
          errorMessage={errorMessage}
          ingestion={ingestion}
          retailers={retailers}
          onReset={handleReset}
        />

        {/* LIVE RESULTS SECTION: Only shown when an evaluation has been executed */}
        {gateResult && (
          <div className="space-y-6 pt-2 animate-in fade-in duration-300">
            {/* Top Decision Banner */}
            <DecisionCard
              gateResult={gateResult}
              loading={scenarioLoading}
              onSelectCheckById={(id) => {
                const match = gateResult?.check_results.find((c) => c.check_id === id);
                if (match) handleSelectCheck(match);
              }}
            />

            {/* Key Operational Metrics */}
            <MetricsRow gateResult={gateResult} />

            {/* Main Work Area: Evaluated QA Checks (Left) + Uploaded Call Transcript (Right) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left: Checks Table (7 cols) */}
              <div className="lg:col-span-7 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <CheckSquare className="w-4 h-4 text-slate-500" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                      Evaluated QA Checks ({gateResult.check_results.length})
                    </h3>
                  </div>
                  <span className="text-xs text-slate-400 font-medium">
                    Click any check to inspect evidence trace
                  </span>
                </div>

                <ChecksTable
                  checks={gateResult.check_results}
                  selectedCheckId={selectedCheck?.check_id || null}
                  onSelectCheck={handleSelectCheck}
                />
              </div>

              {/* Right: Dynamic Call Audio Transcript (5 cols) */}
              <div className="lg:col-span-5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                    Call Audio Transcript
                  </span>
                  {activeUtteranceId && (
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 font-medium">
                      Target: {activeUtteranceId}
                    </span>
                  )}
                </div>

                <TranscriptView
                  utterances={transcript?.utterances || []}
                  activeUtteranceId={activeUtteranceId}
                  onSelectUtterance={(id) => setActiveUtteranceId(id)}
                />
              </div>
            </div>
          </div>
        )}

        {/* SECONDARY WORKFLOW: Developer / Demo Scenarios (Collapsible) */}
        <ScenarioSelector
          scenarios={scenarios}
          selectedScenario={selectedScenario}
          onSelectScenario={(id) => setSelectedScenario(id)}
          onRunQA={() => handleRunScenario(selectedScenario)}
          loading={scenarioLoading}
        />

        {/* SYSTEM VALIDATION: Ground-Truth Benchmark Agreement Panel */}
        <BenchmarkPanel />
      </main>

      {/* Slide-Over Drawer for Selected Check Detail & Evidence */}
      {selectedCheck && (
        <>
          <div
            onClick={() => setSelectedCheck(null)}
            className="fixed inset-0 bg-slate-900/25 backdrop-blur-[2px] z-40 transition-opacity"
          />
          <CheckDetailDrawer
            check={selectedCheck}
            onClose={() => setSelectedCheck(null)}
            onLocateInTranscript={handleLocateInTranscript}
          />
        </>
      )}
    </div>
  );
}
