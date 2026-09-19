'use client';

import React, { useState } from 'react';
import {
  X,
  ArrowRight,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { CheckResult } from '@/types/api';
import { formatSeconds } from '@/lib/utils';

interface CheckDetailDrawerProps {
  check: CheckResult | null;
  onClose: () => void;
  onLocateInTranscript: (utteranceId: string) => void;
}

export const CheckDetailDrawer: React.FC<CheckDetailDrawerProps> = ({
  check,
  onClose,
  onLocateInTranscript,
}) => {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  if (!check) return null;

  const ev = check.evidence;
  const isDeadAir = check.check_id.includes('DEAD_AIR') || (ev && ev.speaker === 'SILENCE');

  // Resolved utterance ID target for jumping to transcript
  const primaryUtteranceId =
    check.utterance_id ||
    (ev ? ev.utterance_id.split('->')[0] : null) ||
    check.preceding_utterance_id;

  // Clean title for drawer
  const friendlyName = check.field
    ? check.field.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
    : check.check_id.split('_').slice(3).join(' ').replace(/\b\w/g, (l) => l.toUpperCase()) ||
      check.check_id;

  const getStatusBadge = () => {
    switch (check.status) {
      case 'PASS':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            PASS
          </span>
        );
      case 'FAIL':
        return check.critical ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
            FAIL
          </span>
        ) : (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            WARNING
          </span>
        );
      case 'AMBIGUOUS':
      case 'LOW_CONFIDENCE':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            REVIEW
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            {check.status}
          </span>
        );
    }
  };

  const getReasonHeading = () => {
    if (check.status === 'PASS') return 'Why it passed';
    if (check.status === 'FAIL') return 'Why it failed';
    return 'Why it needs review';
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[480px] md:w-[520px] bg-white border-l border-slate-200 shadow-xl z-50 flex flex-col animate-in slide-in-from-right duration-200">
      {/* Top Header */}
      <div className="p-6 border-b border-slate-100 flex items-start justify-between bg-white">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2">
            {getStatusBadge()}
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              {check.check_type} · {check.critical ? 'Critical' : 'Non-blocking'}
            </span>
          </div>
          <h3 className="text-lg font-semibold text-slate-900">
            {friendlyName}
          </h3>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors -mr-1"
          aria-label="Close drawer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Drawer Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Verification Comparison (Expected vs Observed) */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80">
            <span className="text-[11px] font-medium uppercase text-slate-500 block mb-1">
              Expected
            </span>
            <span className="text-sm font-semibold text-slate-800 break-words font-mono">
              {check.expected !== null && check.expected !== undefined
                ? String(check.expected)
                : 'N/A'}
            </span>
          </div>

          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80">
            <span className="text-[11px] font-medium uppercase text-slate-500 block mb-1">
              Observed
            </span>
            <span
              className={`text-sm font-semibold break-words font-mono ${
                check.status === 'PASS'
                  ? 'text-emerald-700'
                  : check.status === 'FAIL'
                  ? 'text-rose-700'
                  : 'text-amber-700'
              }`}
            >
              {check.observed !== null && check.observed !== undefined
                ? String(check.observed)
                : 'None detected'}
            </span>
          </div>
        </div>

        {/* Why it passed / failed */}
        <div>
          <span className="text-xs font-semibold text-slate-900 block mb-1.5">
            {getReasonHeading()}
          </span>
          <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3.5 rounded-lg border border-slate-200/80 font-sans">
            {check.reason}
          </p>
        </div>

        {/* EVIDENCE */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
              Evidence
            </span>

            {primaryUtteranceId && (
              <button
                onClick={() => onLocateInTranscript(primaryUtteranceId)}
                className="inline-flex items-center space-x-1 text-xs font-medium text-slate-700 hover:text-slate-950 transition-colors"
              >
                <span>View in transcript</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {ev ? (
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80 space-y-3">
              {/* Timestamp & Speaker */}
              <div className="flex items-center justify-between text-xs text-slate-600">
                <span className="font-mono text-slate-800 font-medium">
                  {formatSeconds(ev.start_time)} — {formatSeconds(ev.end_time)}
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase bg-white border border-slate-200 text-slate-700">
                  {isDeadAir ? 'SILENCE GAP' : ev.speaker}
                </span>
              </div>

              {/* Verbatim quote or silence note */}
              {isDeadAir ? (
                <div className="p-3 bg-white rounded border border-slate-200/80 text-xs text-slate-700 font-mono">
                  <div className="font-semibold text-amber-800 mb-1">
                    {formatSeconds(ev.duration)} silence detected
                  </div>
                  <div className="text-slate-500 text-[11px]">
                    Between {ev.preceding_utterance_id || 'utt_prev'} and {ev.following_utterance_id || 'utt_next'}
                  </div>
                </div>
              ) : (
                <div className="p-3 bg-white rounded border border-slate-200/80 text-xs text-slate-800 font-sans leading-relaxed italic">
                  &ldquo;{ev.text}&rdquo;
                </div>
              )}
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/80 text-slate-500 text-xs text-center">
              No evidence span linked to this check.
            </div>
          )}
        </div>

        {/* Collapsible Technical Details */}
        <div className="pt-2 border-t border-slate-200">
          <button
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            className="flex items-center justify-between w-full py-2 text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors"
          >
            <span>Technical details</span>
            {showTechnicalDetails ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {showTechnicalDetails && (
            <div className="mt-2 p-3.5 rounded-lg bg-slate-50 border border-slate-200/80 space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between py-1 border-b border-slate-200/60">
                <span className="text-slate-500">Check ID:</span>
                <span className="text-slate-800 font-medium">{check.check_id}</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-200/60">
                <span className="text-slate-500">Version:</span>
                <span className="text-slate-800 font-medium">v{check.check_version}</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-200/60">
                <span className="text-slate-500">Utterance ID:</span>
                <span className="text-slate-800 font-medium">{ev?.utterance_id || check.utterance_id || 'N/A'}</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-200/60">
                <span className="text-slate-500">Confidence:</span>
                <span className="text-slate-800 font-medium">{check.confidence.toFixed(2)}</span>
              </div>
              {check.field && (
                <div className="flex items-center justify-between py-1">
                  <span className="text-slate-500">Field:</span>
                  <span className="text-slate-800 font-medium">{check.field}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
