'use client';

import React from 'react';
import { GateResult } from '@/types/api';

interface MetricsRowProps {
  gateResult: GateResult | null;
}

export const MetricsRow: React.FC<MetricsRowProps> = ({ gateResult }) => {
  if (!gateResult) {
    return null;
  }

  const {
    critical_checks_total,
    critical_checks_passed,
    critical_checks_failed,
    critical_checks_ambiguous,
    non_critical_failures,
  } = gateResult;

  const items = [
    {
      value: critical_checks_total,
      label: 'Critical checks',
      color: 'text-slate-900',
      tag: null,
    },
    {
      value: critical_checks_passed,
      label: 'Passed',
      color: 'text-emerald-700',
      tag: null,
    },
    {
      value: critical_checks_failed,
      label: 'Failed',
      color: critical_checks_failed > 0 ? 'text-rose-600 font-bold' : 'text-slate-400',
      tag: critical_checks_failed > 0 ? 'Blocking' : null,
      tagColor: 'bg-rose-100 text-rose-700',
    },
    {
      value: critical_checks_ambiguous,
      label: 'Needs review',
      color: critical_checks_ambiguous > 0 ? 'text-amber-600 font-bold' : 'text-slate-400',
      tag: critical_checks_ambiguous > 0 ? 'Review' : null,
      tagColor: 'bg-amber-100 text-amber-700',
    },
    {
      value: non_critical_failures,
      label: 'Non-blocking warning',
      color: non_critical_failures > 0 ? 'text-slate-800' : 'text-slate-400',
      tag: non_critical_failures > 0 ? 'Behaviour' : null,
      tagColor: 'bg-slate-100 text-slate-600',
    },
  ];

  return (
    <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs py-4 px-6">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-6 sm:gap-4 divide-y sm:divide-y-0 sm:divide-x divide-slate-100">
        {items.map((item, idx) => (
          <div
            key={idx}
            className={`flex flex-col justify-center ${
              idx > 0 ? 'sm:pl-6 pt-4 sm:pt-0' : ''
            }`}
          >
            <div className="flex items-baseline space-x-2">
              <span className={`text-3xl font-semibold tracking-tight font-sans ${item.color}`}>
                {item.value}
              </span>
              {item.tag && (
                <span
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${item.tagColor}`}
                >
                  {item.tag}
                </span>
              )}
            </div>
            <span className="text-xs font-medium text-slate-500 mt-1">
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
