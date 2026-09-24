'use client';

import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileJson,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RotateCcw,
  ArrowRight,
  Mic,
  FileAudio,
  Radio,
  Check,
  Circle,
} from 'lucide-react';
import { IngestionResponse, AudioIngestionResponse, QAProcessState } from '@/types/api';

export type { QAProcessState };

interface UploadTranscriptCardProps {
  onStartReview: (
    file: File,
    metadata: { lead_id?: string; retailer?: string; call_date?: string }
  ) => Promise<void>;
  onStartAudioReview: (
    file: File,
    metadata: {
      lead_id?: string;
      retailer?: string;
      call_date?: string;
      speaker_0_role?: string;
      speaker_1_role?: string;
    }
  ) => Promise<void>;
  processState: QAProcessState;
  stateMessage?: string;
  errorMessage?: string | null;
  ingestion: IngestionResponse | AudioIngestionResponse | null;
  retailers: string[];
  onReset: () => void;
}

export const UploadTranscriptCard: React.FC<UploadTranscriptCardProps> = ({
  onStartReview,
  onStartAudioReview,
  processState,
  stateMessage,
  errorMessage,
  ingestion,
  retailers,
  onReset,
}) => {
  const [mode, setMode] = useState<'AUDIO' | 'TRANSCRIPT'>('AUDIO');
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [leadIdInput, setLeadIdInput] = useState('');
  const [retailerInput, setRetailerInput] = useState('');
  const [callDateInput, setCallDateInput] = useState('');

  // Speaker Role Mapping for Audio STT
  const [speaker0Role, setSpeaker0Role] = useState<'AGENT' | 'CUSTOMER'>('AGENT');
  const [speaker1Role, setSpeaker1Role] = useState<'AGENT' | 'CUSTOMER'>('CUSTOMER');

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Derived effective values
  const effectiveLeadId = leadIdInput || ingestion?.lead_id || '';
  const effectiveRetailer = retailerInput || ingestion?.retailer || '';
  const effectiveCallDate = callDateInput || ingestion?.call_date || '';

  const isBusy =
    processState === 'UPLOADING' ||
    processState === 'TRANSCRIBING' ||
    processState === 'INDEXING' ||
    processState === 'VALIDATING' ||
    processState === 'READY' ||
    processState === 'EVALUATING';

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      const name = file.name.toLowerCase();
      if (mode === 'AUDIO') {
        if (name.endsWith('.mp3') || name.endsWith('.wav')) {
          setSelectedFile(file);
        }
      } else {
        if (name.endsWith('.json') || file.type === 'application/json') {
          setSelectedFile(file);
        }
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleModeChange = (newMode: 'AUDIO' | 'TRANSCRIPT') => {
    if (isBusy) return;
    setMode(newMode);
    setSelectedFile(null);
    onReset();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    if (mode === 'AUDIO') {
      await onStartAudioReview(selectedFile, {
        lead_id: effectiveLeadId.trim() || undefined,
        retailer: effectiveRetailer.trim() || undefined,
        call_date: effectiveCallDate.trim() || undefined,
        speaker_0_role: speaker0Role,
        speaker_1_role: speaker1Role,
      });
    } else {
      await onStartReview(selectedFile, {
        lead_id: effectiveLeadId.trim() || undefined,
        retailer: effectiveRetailer.trim() || undefined,
        call_date: effectiveCallDate.trim() || undefined,
      });
    }
  };

  const getStageStatus = (
    stage: 'UPLOAD' | 'TRANSCRIBE' | 'IDENTIFY' | 'INDEX' | 'EVAL'
  ): 'done' | 'active' | 'pending' => {
    if (stage === 'UPLOAD') {
      if (['TRANSCRIBING', 'INDEXING', 'READY', 'EVALUATING', 'SUCCESS'].includes(processState)) {
        return 'done';
      }
      return processState === 'UPLOADING' ? 'active' : 'pending';
    }
    if (stage === 'TRANSCRIBE') {
      if (['INDEXING', 'READY', 'EVALUATING', 'SUCCESS'].includes(processState)) {
        return 'done';
      }
      return processState === 'TRANSCRIBING' ? 'active' : 'pending';
    }
    if (stage === 'IDENTIFY') {
      if (['INDEXING', 'READY', 'EVALUATING', 'SUCCESS'].includes(processState)) {
        return 'done';
      }
      return processState === 'INDEXING' ? 'active' : 'pending';
    }
    if (stage === 'INDEX') {
      if (['READY', 'EVALUATING', 'SUCCESS'].includes(processState)) {
        return 'done';
      }
      return processState === 'READY' ? 'active' : 'pending';
    }
    if (stage === 'EVAL') {
      if (processState === 'SUCCESS') {
        return 'done';
      }
      return processState === 'EVALUATING' ? 'active' : 'pending';
    }
    return 'pending';
  };

  const uploadStatus = getStageStatus('UPLOAD');
  const transcribeStatus = getStageStatus('TRANSCRIBE');
  const identifyStatus = getStageStatus('IDENTIFY');
  const indexStatus = getStageStatus('INDEX');
  const evalStatus = getStageStatus('EVAL');

  return (
    <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs p-6 sm:p-7 transition-all">
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100 mb-5">
        <div>
          <span className="text-[11px] font-semibold tracking-wider uppercase text-slate-500 block mb-1">
            Real Ingestion Pipeline
          </span>
          <h2 className="text-xl font-bold tracking-tight text-slate-900">
            Start a QA Review
          </h2>
        </div>

        {/* Tab Selector: Audio (Primary) vs JSON (Developer) */}
        <div className="flex items-center space-x-2">
          <div className="inline-flex p-1 bg-slate-100 rounded-lg text-xs font-medium">
            <button
              type="button"
              onClick={() => handleModeChange('AUDIO')}
              disabled={isBusy}
              className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
                mode === 'AUDIO'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Mic className="w-3.5 h-3.5" />
              <span>Audio Recording</span>
            </button>
            <button
              type="button"
              onClick={() => handleModeChange('TRANSCRIPT')}
              disabled={isBusy}
              className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
                mode === 'TRANSCRIPT'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <FileJson className="w-3.5 h-3.5" />
              <span>JSON Transcript</span>
            </button>
          </div>

          {selectedFile && (
            <button
              type="button"
              onClick={() => {
                setSelectedFile(null);
                setLeadIdInput('');
                setRetailerInput('');
                setCallDateInput('');
                onReset();
              }}
              disabled={isBusy}
              className="inline-flex items-center space-x-1.5 text-xs text-slate-500 hover:text-slate-800 disabled:opacity-50 transition-colors ml-2"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Dropzone Area */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`relative border-2 border-dashed rounded-xl p-6 sm:p-8 text-center cursor-pointer transition-all ${
            dragActive
              ? 'border-slate-900 bg-slate-50/80 scale-[0.99]'
              : selectedFile
              ? 'border-emerald-300 bg-emerald-50/20'
              : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/40'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={mode === 'AUDIO' ? '.mp3,.wav,audio/mpeg,audio/wav' : '.json,application/json'}
            onChange={handleFileChange}
            className="hidden"
            disabled={isBusy}
          />

          {selectedFile ? (
            <div className="flex flex-col items-center justify-center space-y-2">
              <div className="w-11 h-11 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center">
                {mode === 'AUDIO' ? <FileAudio className="w-6 h-6" /> : <FileJson className="w-6 h-6" />}
              </div>
              <div className="text-sm font-semibold text-slate-900">
                {selectedFile.name}
              </div>
              <p className="text-xs text-slate-500">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Click or drag another file to replace
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center space-y-2.5">
              <div className="w-11 h-11 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center">
                {mode === 'AUDIO' ? <UploadCloud className="w-6 h-6" /> : <UploadCloud className="w-6 h-6" />}
              </div>
              <div>
                <span className="text-sm font-semibold text-slate-900 hover:underline">
                  {mode === 'AUDIO' ? 'Drop MP3 or WAV audio file here' : 'Drop JSON transcript here'}
                </span>
                <span className="text-sm text-slate-500"> or browse from your computer</span>
              </div>
              <p className="text-xs text-slate-400">
                {mode === 'AUDIO'
                  ? 'Transcribes speech via Deepgram with diarization, utterances & timestamps'
                  : 'Accepts valid JSON telephony transcripts with timestamped utterances'}
              </p>
            </div>
          )}
        </div>

        {/* Audio Speaker Role Mapping (Shown only for Audio Mode) */}
        {mode === 'AUDIO' && (
          <div className="p-4 rounded-xl bg-slate-50/70 border border-slate-200/80 space-y-2.5">
            <div className="flex items-center space-x-2">
              <Radio className="w-4 h-4 text-slate-500" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                Diarization Speaker Role Mapping
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Configure speaker mapping for diarized speech channels. Speaker 0 is not assumed to be AGENT.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-white border border-slate-200">
                <span className="text-xs font-medium text-slate-700">Speaker 0 Role:</span>
                <select
                  value={speaker0Role}
                  onChange={(e) => setSpeaker0Role(e.target.value as 'AGENT' | 'CUSTOMER')}
                  disabled={isBusy}
                  className="text-xs font-semibold px-2.5 py-1 rounded border border-slate-200 bg-white text-slate-900 focus:outline-none cursor-pointer"
                >
                  <option value="AGENT">AGENT</option>
                  <option value="CUSTOMER">CUSTOMER</option>
                </select>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg bg-white border border-slate-200">
                <span className="text-xs font-medium text-slate-700">Speaker 1 Role:</span>
                <select
                  value={speaker1Role}
                  onChange={(e) => setSpeaker1Role(e.target.value as 'AGENT' | 'CUSTOMER')}
                  disabled={isBusy}
                  className="text-xs font-semibold px-2.5 py-1 rounded border border-slate-200 bg-white text-slate-900 focus:outline-none cursor-pointer"
                >
                  <option value="CUSTOMER">CUSTOMER</option>
                  <option value="AGENT">AGENT</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Optional Metadata Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
          <div>
            <label
              htmlFor="meta-lead-id"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              Lead ID <span className="text-slate-400">(Optional)</span>
            </label>
            <input
              id="meta-lead-id"
              type="text"
              placeholder="e.g. 3613790"
              value={effectiveLeadId}
              onChange={(e) => setLeadIdInput(e.target.value)}
              disabled={isBusy}
              className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-colors"
            />
          </div>

          <div>
            <label
              htmlFor="meta-retailer"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              Retailer <span className="text-slate-400">(Optional)</span>
            </label>
            <select
              id="meta-retailer"
              value={effectiveRetailer}
              onChange={(e) => setRetailerInput(e.target.value)}
              disabled={isBusy}
              className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-colors cursor-pointer"
            >
              <option value="">Auto-detect from ruleset</option>
              {retailers.map((r) => (
                <option key={r} value={r}>
                  {r.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="meta-call-date"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              Call Date <span className="text-slate-400">(Optional)</span>
            </label>
            <input
              id="meta-call-date"
              type="date"
              value={effectiveCallDate}
              onChange={(e) => setCallDateInput(e.target.value)}
              disabled={isBusy}
              className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-colors"
            />
          </div>
        </div>

        {/* Live Audio Ingestion Multi-Stage Progress Banner */}
        {mode === 'AUDIO' && processState !== 'IDLE' && (
          <div
            className={`p-4 rounded-xl border text-xs transition-all ${
              processState === 'ERROR'
                ? 'bg-rose-50 border-rose-200 text-rose-800'
                : processState === 'SUCCESS'
                ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                : 'bg-slate-50 border-slate-200 text-slate-700'
            }`}
          >
            {/* Checklist of 5 stages */}
            <div className="space-y-2 mb-3">
              <div className="flex items-center space-x-2">
                {uploadStatus === 'done' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-600 font-bold shrink-0" />
                ) : uploadStatus === 'active' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-600 shrink-0" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                )}
                <span className={uploadStatus === 'done' ? 'font-medium text-slate-900' : 'text-slate-500'}>
                  {uploadStatus === 'done' ? '✓ Recording uploaded' : 'Recording upload'}
                </span>
              </div>

              <div className="flex items-center space-x-2">
                {transcribeStatus === 'done' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-600 font-bold shrink-0" />
                ) : transcribeStatus === 'active' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-600 shrink-0" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                )}
                <span className={transcribeStatus === 'done' ? 'font-medium text-slate-900' : 'text-slate-500'}>
                  {transcribeStatus === 'done' ? '✓ Speech transcribed' : 'Speech transcription (Deepgram STT)'}
                </span>
              </div>

              <div className="flex items-center space-x-2">
                {identifyStatus === 'done' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-600 font-bold shrink-0" />
                ) : identifyStatus === 'active' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-600 shrink-0" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                )}
                <span className={identifyStatus === 'done' ? 'font-medium text-slate-900' : 'text-slate-500'}>
                  {identifyStatus === 'done' ? '✓ Speakers identified' : 'Speakers identified (Diarization)'}
                </span>
              </div>

              <div className="flex items-center space-x-2">
                {indexStatus === 'done' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-600 font-bold shrink-0" />
                ) : indexStatus === 'active' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-600 shrink-0" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                )}
                <span className={indexStatus === 'done' ? 'font-medium text-slate-900' : 'text-slate-500'}>
                  {indexStatus === 'done' ? '✓ Transcript indexed' : 'Transcript indexed & canonicalized'}
                </span>
              </div>

              <div className="flex items-center space-x-2">
                {evalStatus === 'done' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-600 font-bold shrink-0" />
                ) : evalStatus === 'active' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-600 shrink-0" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                )}
                <span className={evalStatus === 'done' ? 'font-medium text-slate-900' : 'text-slate-500'}>
                  {evalStatus === 'done' ? '✓ QA evaluation complete' : 'QA evaluation & deterministic gate'}
                </span>
              </div>
            </div>

            {stateMessage && <p className="text-slate-600 text-xs border-t border-slate-200/60 pt-2">{stateMessage}</p>}
            {errorMessage && (
              <p className="font-mono text-[11px] text-rose-700 mt-2 border-t border-rose-200 pt-2">
                {errorMessage}
              </p>
            )}

            {ingestion && (
              <div className="flex flex-wrap items-center gap-3 pt-2 text-[11px] font-mono text-slate-600 border-t border-slate-200/60">
                <span>Ingestion ID: {ingestion.ingestion_id}</span>
                <span>•</span>
                <span>Utterances: {ingestion.utterance_count}</span>
                {'duration_seconds' in ingestion && (
                  <>
                    <span>•</span>
                    <span>Duration: {ingestion.duration_seconds}s</span>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* Existing JSON Transcript State Display (Shown when in JSON mode) */}
        {mode === 'TRANSCRIPT' && processState !== 'IDLE' && (
          <div
            className={`p-4 rounded-xl border text-xs transition-all ${
              processState === 'ERROR'
                ? 'bg-rose-50 border-rose-200 text-rose-800'
                : processState === 'SUCCESS'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-slate-50 border-slate-200 text-slate-700'
            }`}
          >
            <div className="flex items-start space-x-3">
              {isBusy ? (
                <Loader2 className="w-4 h-4 animate-spin text-slate-600 shrink-0 mt-0.5" />
              ) : processState === 'SUCCESS' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              )}

              <div className="space-y-1 flex-1">
                <div className="font-semibold">
                  {processState === 'UPLOADING' && 'Uploading transcript...'}
                  {processState === 'VALIDATING' && 'Validating transcript against canonical schema...'}
                  {processState === 'READY' && 'Transcript validated & ready for evaluation'}
                  {processState === 'EVALUATING' && 'Evaluating QA checks & applying deterministic gate...'}
                  {processState === 'SUCCESS' && 'Evaluation complete'}
                  {processState === 'ERROR' && 'Evaluation stopped'}
                </div>

                {stateMessage && <p className="text-slate-600">{stateMessage}</p>}
                {errorMessage && (
                  <p className="font-mono text-[11px] text-rose-700 mt-1">
                    {errorMessage}
                  </p>
                )}

                {ingestion && (
                  <div className="flex items-center space-x-3 pt-1 text-[11px] font-mono text-slate-500">
                    <span>ID: {ingestion.ingestion_id}</span>
                    <span>•</span>
                    <span>Utterances: {ingestion.utterance_count}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="flex items-center justify-between pt-2">
          <div className="text-xs text-slate-500">
            Supported formats:{' '}
            {mode === 'AUDIO' ? (
              <>
                <code className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">.mp3</code>,{' '}
                <code className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">.wav</code>
              </>
            ) : (
              <code className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">.json</code>
            )}
          </div>

          <button
            type="submit"
            disabled={!selectedFile || isBusy}
            className="inline-flex items-center space-x-2 px-6 py-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-medium text-xs tracking-wide transition-colors cursor-pointer disabled:cursor-not-allowed shadow-2xs"
          >
            {isBusy ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-slate-300" />
                <span>Processing Audio...</span>
              </>
            ) : (
              <>
                <span>{mode === 'AUDIO' ? 'Start Audio QA Review' : 'Start QA Review'}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
