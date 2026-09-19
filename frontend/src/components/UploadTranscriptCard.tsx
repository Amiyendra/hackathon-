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
} from 'lucide-react';
import { IngestionResponse } from '@/types/api';

export type QAProcessState =
  | 'IDLE'
  | 'UPLOADING'
  | 'VALIDATING'
  | 'READY'
  | 'EVALUATING'
  | 'SUCCESS'
  | 'ERROR';

interface UploadTranscriptCardProps {
  onStartReview: (
    file: File,
    metadata: { lead_id?: string; retailer?: string; call_date?: string }
  ) => Promise<void>;
  processState: QAProcessState;
  stateMessage?: string;
  errorMessage?: string | null;
  ingestion: IngestionResponse | null;
  retailers: string[];
  onReset: () => void;
}

export const UploadTranscriptCard: React.FC<UploadTranscriptCardProps> = ({
  onStartReview,
  processState,
  stateMessage,
  errorMessage,
  ingestion,
  retailers,
  onReset,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [leadIdInput, setLeadIdInput] = useState('');
  const [retailerInput, setRetailerInput] = useState('');
  const [callDateInput, setCallDateInput] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Derived effective values (syncs with ingestion without cascading renders)
  const effectiveLeadId = leadIdInput || ingestion?.lead_id || '';
  const effectiveRetailer = retailerInput || ingestion?.retailer || '';
  const effectiveCallDate = callDateInput || ingestion?.call_date || '';

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
      if (file.name.endsWith('.json') || file.type === 'application/json') {
        setSelectedFile(file);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    await onStartReview(selectedFile, {
      lead_id: effectiveLeadId.trim() || undefined,
      retailer: effectiveRetailer.trim() || undefined,
      call_date: effectiveCallDate.trim() || undefined,
    });
  };

  const isBusy =
    processState === 'UPLOADING' ||
    processState === 'VALIDATING' ||
    processState === 'EVALUATING';

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
            className="inline-flex items-center space-x-1.5 text-xs text-slate-500 hover:text-slate-800 disabled:opacity-50 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset upload</span>
          </button>
        )}
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
            accept=".json,application/json"
            onChange={handleFileChange}
            className="hidden"
            disabled={isBusy}
          />

          {selectedFile ? (
            <div className="flex flex-col items-center justify-center space-y-2">
              <div className="w-11 h-11 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center">
                <FileJson className="w-6 h-6" />
              </div>
              <div className="text-sm font-semibold text-slate-900">
                {selectedFile.name}
              </div>
              <p className="text-xs text-slate-500">
                {(selectedFile.size / 1024).toFixed(1)} KB · Click or drag another file to replace
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center space-y-2.5">
              <div className="w-11 h-11 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div>
                <span className="text-sm font-semibold text-slate-900 hover:underline">
                  Drop JSON transcript here
                </span>
                <span className="text-sm text-slate-500"> or browse from your computer</span>
              </div>
              <p className="text-xs text-slate-400">
                Accepts valid JSON telephony transcripts with timestamped utterances
              </p>
            </div>
          )}
        </div>

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
              <option value="">Auto-detect from transcript</option>
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

        {/* Live State Progress & Feedback */}
        {processState !== 'IDLE' && (
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
            Supported format: <code className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">.json</code>
          </div>

          <button
            type="submit"
            disabled={!selectedFile || isBusy}
            className="inline-flex items-center space-x-2 px-6 py-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-medium text-xs tracking-wide transition-colors cursor-pointer disabled:cursor-not-allowed shadow-2xs"
          >
            {isBusy ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-slate-300" />
                <span>Processing...</span>
              </>
            ) : (
              <>
                <span>Start QA Review</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
