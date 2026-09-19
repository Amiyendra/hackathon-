'use client';

import React, { useEffect, useRef } from 'react';
import { TranscriptUtterance } from '@/types/api';
import { formatTimestamp } from '@/lib/utils';

interface TranscriptViewProps {
  utterances: TranscriptUtterance[];
  activeUtteranceId: string | null;
  onSelectUtterance?: (utteranceId: string) => void;
}

export const TranscriptView: React.FC<TranscriptViewProps> = ({
  utterances,
  activeUtteranceId,
  onSelectUtterance,
}) => {
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // Auto-scroll to active utterance when selected from evidence
  useEffect(() => {
    if (activeUtteranceId && itemRefs.current[activeUtteranceId]) {
      itemRefs.current[activeUtteranceId]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [activeUtteranceId]);

  return (
    <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-slate-200/80 bg-slate-50/50 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
            Call Transcript
          </h3>
          <span className="text-[11px] text-slate-400 font-medium">
            ({utterances.length} turns)
          </span>
        </div>
        <span className="text-[11px] text-slate-400 font-medium">
          PII Redacted
        </span>
      </div>

      {/* Utterance Review Stream */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 max-h-[580px]">
        {utterances.length === 0 ? (
          <div className="text-center py-12 text-slate-400 text-xs">
            Loading transcript...
          </div>
        ) : (
          utterances.map((utt, idx) => {
            const isAgent = utt.speaker.toUpperCase() === 'AGENT';
            const isActive =
              activeUtteranceId === utt.utterance_id ||
              (activeUtteranceId && activeUtteranceId.includes(utt.utterance_id));

            // Check gap with previous utterance for Dead Air / Silence display
            const prevUtt = idx > 0 ? utterances[idx - 1] : null;
            const gap = prevUtt ? Math.max(0, utt.start_time - prevUtt.end_time) : 0;
            const isDeadAirGap = gap >= 0.25;
            const isDeadAirActive =
              activeUtteranceId &&
              prevUtt &&
              (activeUtteranceId.includes(prevUtt.utterance_id) &&
                activeUtteranceId.includes(utt.utterance_id));

            return (
              <React.Fragment key={utt.utterance_id}>
                {/* Silence / Dead Air Indicator between utterances */}
                {isDeadAirGap && (
                  <div
                    ref={(el) => {
                      if (prevUtt) {
                        itemRefs.current[`${prevUtt.utterance_id}->${utt.utterance_id}`] = el;
                      }
                    }}
                    className={`flex items-center justify-center my-3 py-1 px-3 text-[11px] font-mono transition-colors rounded ${
                      isDeadAirActive
                        ? 'bg-amber-100/80 text-amber-900 border border-amber-300'
                        : 'text-slate-400'
                    }`}
                  >
                    <span className="text-[10px] text-slate-400">
                      {formatTimestamp(prevUtt!.end_time)}
                    </span>
                    <span className="mx-2 text-slate-300">────────</span>
                    <span className={`font-medium ${isDeadAirActive ? 'text-amber-800' : 'text-slate-500'}`}>
                      {gap.toFixed(2)}s silence
                    </span>
                    <span className="mx-2 text-slate-300">────────</span>
                    <span className="text-[10px] text-slate-400">
                      {formatTimestamp(utt.start_time)}
                    </span>
                  </div>
                )}

                {/* Utterance Card */}
                <div
                  ref={(el) => {
                    itemRefs.current[utt.utterance_id] = el;
                  }}
                  onClick={() => onSelectUtterance && onSelectUtterance(utt.utterance_id)}
                  className={`rounded-lg p-3.5 border transition-all text-xs cursor-pointer ${
                    isActive
                      ? 'bg-amber-50/70 border-amber-300 shadow-2xs'
                      : 'bg-white border-slate-200/80 hover:border-slate-300'
                  }`}
                >
                  {/* Speaker and Timestamp line */}
                  <div className="flex items-center justify-between mb-1.5">
                    <span
                      className={`text-[11px] font-semibold uppercase tracking-wider ${
                        isAgent ? 'text-slate-700' : 'text-slate-500'
                      }`}
                    >
                      {utt.speaker}
                    </span>

                    <span className="font-mono text-[11px] text-slate-400">
                      {formatTimestamp(utt.start_time)}
                    </span>
                  </div>

                  {/* Speech text */}
                  <p
                    className={`leading-relaxed text-xs ${
                      isActive ? 'text-slate-900 font-medium' : 'text-slate-700'
                    }`}
                  >
                    &ldquo;{utt.text}&rdquo;
                  </p>

                  {/* Utterance ID footnote */}
                  <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                    <span>{utt.utterance_id}</span>
                    {isActive && (
                      <span className="text-amber-700 font-medium">
                        Active evidence slice
                      </span>
                    )}
                  </div>
                </div>
              </React.Fragment>
            );
          })
        )}
      </div>
    </div>
  );
};
