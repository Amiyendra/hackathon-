'use client';

import React from 'react';
import { ShieldCheck, Info } from 'lucide-react';

export const BenchmarkPanel: React.FC = () => {
  return (
    <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-0.5">
            System Validation
          </span>
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
              Transcript-Grounded Benchmark Agreement
            </h3>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold font-mono text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">
            14 eligible cases · 14 correct matches
          </span>
          <span className="text-xs font-semibold font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
            100.00% Agreement
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 my-4 font-mono">
        <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80">
          <span className="text-[10px] text-slate-500 block mb-0.5 uppercase tracking-wide">
            Eligible Cases
          </span>
          <span className="text-xl font-bold text-slate-900">14</span>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80">
          <span className="text-[10px] text-slate-500 block mb-0.5 uppercase tracking-wide">
            Correct Matches
          </span>
          <span className="text-xl font-bold text-emerald-700">14</span>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80">
          <span className="text-[10px] text-slate-500 block mb-0.5 uppercase tracking-wide">
            Incorrect Fails
          </span>
          <span className="text-xl font-bold text-slate-400">0</span>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80">
          <span className="text-[10px] text-slate-500 block mb-0.5 uppercase tracking-wide">
            Agreement
          </span>
          <span className="text-xl font-bold text-emerald-700">100.00%</span>
        </div>
      </div>

      {/* Accuracy & Auditor Context */}
      <div className="flex items-start space-x-2 text-xs text-slate-500 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-200/80 mt-2">
        <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
        <span>
          <strong className="text-slate-700 font-semibold">Transcript-grounded benchmark agreement</strong> evaluated
          strictly against validated ground-truth records. This reflects historical system validation across factual,
          verbatim, and behaviour checks and is independent of the currently uploaded call evaluation.
        </span>
      </div>
    </div>
  );
};
