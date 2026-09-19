'use client';

import React, { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Building2,
  Calendar,
  FileSpreadsheet,
  ArrowRight,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { GateResult } from '@/types/api';

interface DecisionCardProps {
  gateResult: GateResult | null;
  loading: boolean;
  onSelectCheckById?: (checkId: string) => void;
}

export const DecisionCard: React.FC<DecisionCardProps> = ({
  gateResult,
  loading,
  onSelectCheckById,
}) => {
  const [showGateDetails, setShowGateDetails] = useState(false);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm animate-pulse">
        <div className="h-4 w-48 bg-slate-100 rounded mb-4" />
        <div className="h-8 w-64 bg-slate-100 rounded mb-3" />
        <div className="h-4 w-96 bg-slate-100 rounded" />
      </div>
    );
  }

  if (!gateResult) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500 shadow-sm">
        <p className="text-sm">Select a scenario and click &ldquo;Run QA Evaluation&rdquo; to begin.</p>
      </div>
    );
  }

  const {
    decision,
    lead_id,
    retailer,
    call_date,
    gate_explanation,
    blocking_check_ids,
    review_check_ids,
    critical_checks_total,
    critical_checks_passed,
  } = gateResult;

  // Refined, calm, enterprise color mappings (no neon, no glowing borders)
  const configs = {
    AUTO_SUBMIT: {
      cardBg: 'bg-emerald-50/40 border-emerald-200/80',
      badgeBg: 'bg-emerald-100 text-emerald-800 border-emerald-200',
      statusText: 'text-emerald-900',
      icon: CheckCircle2,
      iconColor: 'text-emerald-700',
      headline: 'AUTO-SUBMIT',
      subhead: 'All critical checks passed',
      statusLabel: 'Auto-Submit Approved',
    },
    HOLD: {
      cardBg: 'bg-rose-50/40 border-rose-200/80',
      badgeBg: 'bg-rose-100 text-rose-800 border-rose-200',
      statusText: 'text-rose-900',
      icon: XCircle,
      iconColor: 'text-rose-700',
      headline: 'HOLD',
      subhead: 'Critical compliance check failed — blocked from submission',
      statusLabel: 'Hold Applied',
    },
    QA_REVIEW: {
      cardBg: 'bg-amber-50/40 border-amber-200/80',
      badgeBg: 'bg-amber-100 text-amber-800 border-amber-200',
      statusText: 'text-amber-900',
      icon: AlertTriangle,
      iconColor: 'text-amber-700',
      headline: 'QA REVIEW',
      subhead: 'Requires human auditor review before proceeding',
      statusLabel: 'Manual QA Review',
    },
  };

  const config = configs[decision] || configs.QA_REVIEW;
  const IconComponent = config.icon;

  const formattedRetailer = retailer
    ? retailer.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
    : 'Unknown Retailer';

  return (
    <div
      className={`rounded-xl border ${config.cardBg} bg-white p-6 sm:p-7 shadow-sm transition-all`}
    >
      {/* Top Meta Header: Lead ID, Retailer, Call Date */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-200/80 mb-5 text-xs text-slate-600">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center space-x-1.5 font-medium">
            <FileSpreadsheet className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">LEAD</span>
            <span className="font-mono text-slate-900 font-semibold">
              {lead_id ? `#${lead_id}` : 'N/A'}
            </span>
          </div>

          <span className="text-slate-300">•</span>

          <div className="flex items-center space-x-1.5 font-medium">
            <Building2 className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-900">{formattedRetailer}</span>
          </div>

          <span className="text-slate-300">•</span>

          <div className="flex items-center space-x-1.5 font-medium">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-600">{call_date || 'Date not recorded'}</span>
          </div>
        </div>

        {/* Status Pill */}
        <div
          className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide border ${config.badgeBg}`}
        >
          <IconComponent className={`w-3.5 h-3.5 ${config.iconColor}`} />
          <span>{config.statusLabel}</span>
        </div>
      </div>

      {/* Main Decision Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-1">
          <div className="flex items-baseline space-x-3">
            <h2 className={`text-3xl font-bold tracking-tight ${config.statusText}`}>
              {config.headline}
            </h2>
          </div>
          <p className="text-sm font-medium text-slate-700">{config.subhead}</p>
          <div className="pt-1 text-xs text-slate-500 font-medium">
            <span className="font-semibold text-slate-900">
              {critical_checks_passed} / {critical_checks_total}
            </span>{' '}
            critical checks verified
          </div>
        </div>

        {/* Actionable Blocking or Review checks quick-links */}
        {(blocking_check_ids.length > 0 || review_check_ids.length > 0) && (
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 p-3 rounded-lg bg-slate-50 border border-slate-200">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 shrink-0">
              {blocking_check_ids.length > 0 ? 'Failing Check:' : 'Flagged Check:'}
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {(blocking_check_ids.length > 0 ? blocking_check_ids : review_check_ids).map(
                (id) => (
                  <button
                    key={id}
                    onClick={() => onSelectCheckById && onSelectCheckById(id)}
                    className="inline-flex items-center space-x-1 text-xs font-mono px-2.5 py-1 rounded bg-white hover:bg-slate-100 border border-slate-300 text-slate-800 transition-colors shadow-2xs font-medium"
                    title="Click to inspect evidence for this check"
                  >
                    <span>{id}</span>
                    <ArrowRight className="w-3 h-3 text-slate-500" />
                  </button>
                )
              )}
            </div>
          </div>
        )}
      </div>

      {/* Collapsible / Clean Gate Explanation */}
      <div className="mt-5 pt-4 border-t border-slate-200/80">
        <button
          onClick={() => setShowGateDetails(!showGateDetails)}
          className="flex items-center space-x-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors"
        >
          <span>Deterministic Gate Rationale</span>
          {showGateDetails ? (
            <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          )}
        </button>

        {showGateDetails && (
          <div className="mt-2.5 p-3.5 rounded-lg bg-slate-50 border border-slate-200/90 text-xs text-slate-700 leading-relaxed font-mono whitespace-pre-line">
            {gate_explanation || 'All critical criteria satisfied without ambiguity.'}
          </div>
        )}
      </div>
    </div>
  );
};
