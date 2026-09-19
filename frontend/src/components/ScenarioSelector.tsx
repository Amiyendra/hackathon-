'use client';

import React, { useState } from 'react';
import { Play, Loader2, ChevronDown, ChevronUp, Code2 } from 'lucide-react';
import { ScenarioInfo } from '@/types/api';

interface ScenarioSelectorProps {
  scenarios: ScenarioInfo[];
  selectedScenario: string;
  onSelectScenario: (scenarioId: string) => void;
  onRunQA: () => void;
  loading: boolean;
}

interface ScenarioMeta {
  id: string;
  label: string;
  isSynthetic: boolean;
  description: string;
  expectedDecision: string;
}

const PRESET_METAS: Record<string, { label: string; isSynthetic: boolean; description: string }> = {
  auto_submit: {
    label: 'Transcript-Grounded Clean Call',
    isSynthetic: false,
    description: 'All 11 critical checks pass with verified evidence. Auto-submits with 1 non-blocking behaviour warning.',
  },
  hold: {
    label: 'Synthetic Critical Failure',
    isSynthetic: true,
    description: 'Promotional price rate-card mismatch ($42.90 quoted vs $55.00 expected). Critical failure triggers immediate HOLD.',
  },
  qa_review: {
    label: 'QA Review',
    isSynthetic: true,
    description: 'Unsupported disclosure check specification. Fails closed to human auditor review.',
  },
  default: {
    label: 'Behaviour Warning & Multi-Check',
    isSynthetic: true,
    description: 'Lead evaluation demonstrating non-blocking behaviour dead-air detection alongside synthetic mismatches.',
  },
};

export const ScenarioSelector: React.FC<ScenarioSelectorProps> = ({
  scenarios,
  selectedScenario,
  onSelectScenario,
  onRunQA,
  loading,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  // Merge backend scenarios with human-friendly display labels
  const scenarioOptions: ScenarioMeta[] = scenarios.map((s) => {
    const meta = PRESET_METAS[s.scenario_id] || {
      label: s.name,
      isSynthetic: false,
      description: s.description,
    };
    return {
      id: s.scenario_id,
      label: meta.label,
      isSynthetic: meta.isSynthetic,
      description: meta.description,
      expectedDecision: s.expected_decision,
    };
  });

  // Active scenario details
  const activeMeta = scenarioOptions.find((o) => o.id === selectedScenario) || scenarioOptions[0];

  return (
    <div className="bg-white border border-slate-200/90 rounded-xl shadow-2xs overflow-hidden transition-all">
      {/* Header Toggle */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-slate-50/50 transition-colors"
      >
        <div className="flex items-center space-x-2.5">
          <div className="w-6 h-6 rounded bg-slate-100 flex items-center justify-center text-slate-600">
            <Code2 className="w-3.5 h-3.5" />
          </div>
          <div>
            <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider block">
              Developer / Demo Scenarios
            </span>
            <span className="text-[11px] text-slate-400">
              Pre-configured synthetic leads for offline developer rehearsal and test evaluation
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs text-slate-500 font-medium">
          <span>{isOpen ? 'Hide scenarios' : 'Show scenarios'}</span>
          {isOpen ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>

      {/* Collapsible Content */}
      {isOpen && (
        <div className="p-6 pt-2 border-t border-slate-100 bg-slate-50/30 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            {/* Dropdown Selector */}
            <div className="flex flex-col sm:flex-row sm:items-center gap-3 flex-1">
              <label
                htmlFor="scenario-select"
                className="text-xs font-semibold text-slate-500 uppercase tracking-wider shrink-0"
              >
                Select preset
              </label>

              <div className="relative flex-1 max-w-md">
                <select
                  id="scenario-select"
                  value={selectedScenario}
                  onChange={(e) => onSelectScenario(e.target.value)}
                  className="w-full appearance-none bg-white hover:bg-slate-50 border border-slate-200 rounded-lg py-2 pl-3.5 pr-10 text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-colors cursor-pointer shadow-2xs"
                >
                  {scenarioOptions.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label} {opt.isSynthetic ? '— SYNTHETIC DEMO' : '— REHEARSAL'}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>

              {/* Synthetic Demo Label */}
              {activeMeta?.isSynthetic ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold tracking-wide bg-amber-50 text-amber-800 border border-amber-200 shrink-0">
                  SYNTHETIC DEMO
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold tracking-wide bg-emerald-50 text-emerald-800 border border-emerald-200 shrink-0">
                  REHEARSAL CLEAN CALL
                </span>
              )}
            </div>

            {/* Action Button */}
            <button
              onClick={onRunQA}
              disabled={loading}
              className="inline-flex items-center justify-center space-x-2 px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-medium text-xs tracking-wide transition-colors cursor-pointer disabled:cursor-not-allowed shrink-0 shadow-2xs"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-300" />
                  <span>Evaluating...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Run Scenario</span>
                </>
              )}
            </button>
          </div>

          {/* Scenario Description */}
          {activeMeta && (
            <div className="pt-3 border-t border-slate-200/60 flex items-center justify-between text-xs text-slate-500">
              <p className="line-clamp-1">{activeMeta.description}</p>
              <span className="text-[11px] font-mono text-slate-400 shrink-0 ml-4 font-medium">
                Expected: {activeMeta.expectedDecision}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
