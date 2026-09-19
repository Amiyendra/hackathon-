'use client';

import React, { useState, useMemo } from 'react';
import {
  Check,
  X,
  AlertTriangle,
  HelpCircle,
  Search,
  ChevronRight,
} from 'lucide-react';
import { CheckResult } from '@/types/api';

interface ChecksTableProps {
  checks: CheckResult[];
  selectedCheckId: string | null;
  onSelectCheck: (check: CheckResult) => void;
}

export const ChecksTable: React.FC<ChecksTableProps> = ({
  checks,
  selectedCheckId,
  onSelectCheck,
}) => {
  const [filterTab, setFilterTab] = useState<'ALL' | 'CRITICAL' | 'ISSUES' | 'PASS'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredChecks = useMemo(() => {
    return checks.filter((c) => {
      // 1. Tab filter
      if (filterTab === 'CRITICAL' && !c.critical) return false;
      if (filterTab === 'ISSUES' && c.status === 'PASS') return false;
      if (filterTab === 'PASS' && c.status !== 'PASS') return false;

      // 2. Search query filter
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        c.check_id.toLowerCase().includes(q) ||
        (c.field && c.field.toLowerCase().includes(q)) ||
        c.check_type.toLowerCase().includes(q) ||
        c.reason.toLowerCase().includes(q)
      );
    });
  }, [checks, filterTab, searchQuery]);

  // Clean, human-friendly check names for the table
  const getFriendlyCheckName = (check: CheckResult) => {
    if (check.field) {
      return check.field
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (l) => l.toUpperCase());
    }
    const parts = check.check_id.split('_');
    if (parts.length >= 4) {
      return parts.slice(3).join(' ').replace(/\b\w/g, (l) => l.toUpperCase());
    }
    return check.check_id;
  };

  const renderStatusIcon = (status: string, critical: boolean) => {
    switch (status) {
      case 'PASS':
        return (
          <div className="w-6 h-6 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center border border-emerald-200">
            <Check className="w-3.5 h-3.5 stroke-[2.5]" />
          </div>
        );
      case 'FAIL':
        return critical ? (
          <div className="w-6 h-6 rounded-full bg-rose-50 text-rose-700 flex items-center justify-center border border-rose-200">
            <X className="w-3.5 h-3.5 stroke-[2.5]" />
          </div>
        ) : (
          <div className="w-6 h-6 rounded-full bg-amber-50 text-amber-700 flex items-center justify-center border border-amber-200">
            <AlertTriangle className="w-3.5 h-3.5" />
          </div>
        );
      case 'AMBIGUOUS':
      case 'LOW_CONFIDENCE':
        return (
          <div className="w-6 h-6 rounded-full bg-amber-50 text-amber-700 flex items-center justify-center border border-amber-200">
            <AlertTriangle className="w-3.5 h-3.5" />
          </div>
        );
      default:
        return (
          <div className="w-6 h-6 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center border border-slate-200">
            <HelpCircle className="w-3.5 h-3.5" />
          </div>
        );
    }
  };

  const renderResultText = (c: CheckResult) => {
    if (c.status === 'PASS') {
      return <span className="text-emerald-700 font-medium text-xs">Passed</span>;
    }
    if (c.status === 'FAIL') {
      if (c.critical) {
        return (
          <span className="text-rose-700 font-semibold text-xs">
            Failed
          </span>
        );
      }
      return (
        <span className="text-amber-700 font-medium text-xs">
          Warning (Non-blocking)
        </span>
      );
    }
    if (c.status === 'AMBIGUOUS' || c.status === 'LOW_CONFIDENCE') {
      return (
        <span className="text-amber-700 font-medium text-xs">
          Needs Review
        </span>
      );
    }
    return <span className="text-slate-500 text-xs">{c.status}</span>;
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
      {/* Table Top Controls */}
      <div className="px-5 py-3.5 border-b border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50">
        {/* Filter Tabs */}
        <div className="flex items-center space-x-1">
          {[
            { id: 'ALL', label: `All (${checks.length})` },
            { id: 'CRITICAL', label: 'Critical' },
            {
              id: 'ISSUES',
              label: `Issues (${checks.filter((c) => c.status !== 'PASS').length})`,
            },
            {
              id: 'PASS',
              label: `Passed (${checks.filter((c) => c.status === 'PASS').length})`,
            },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterTab(tab.id as 'ALL' | 'CRITICAL' | 'ISSUES' | 'PASS')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                filterTab === tab.id
                  ? 'bg-white text-slate-900 shadow-2xs border border-slate-200'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search checks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full sm:w-56 pl-8 pr-3 py-1 text-xs rounded-md bg-white border border-slate-200 text-slate-800 placeholder-slate-400 focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-400 shadow-2xs"
          />
        </div>
      </div>

      {/* Clean Table List */}
      <div className="overflow-x-auto max-h-[580px] overflow-y-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-slate-50/95 border-b border-slate-200/80 text-slate-500 font-medium text-[11px] uppercase tracking-wider z-10">
            <tr>
              <th className="py-2.5 px-4 w-12 text-center">Status</th>
              <th className="py-2.5 px-4">Check</th>
              <th className="py-2.5 px-4 w-28">Category</th>
              <th className="py-2.5 px-4 w-32">Criticality</th>
              <th className="py-2.5 px-4 w-44">Result</th>
              <th className="py-2.5 px-3 w-8"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredChecks.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-400 text-xs">
                  No checks match the filter.
                </td>
              </tr>
            ) : (
              filteredChecks.map((c) => {
                const isSelected = selectedCheckId === c.check_id;
                const friendlyName = getFriendlyCheckName(c);

                return (
                  <tr
                    key={c.check_id}
                    onClick={() => onSelectCheck(c)}
                    className={`cursor-pointer transition-colors group ${
                      isSelected
                        ? 'bg-slate-50/90 font-medium'
                        : 'hover:bg-slate-50/60'
                    }`}
                  >
                    {/* Status Icon */}
                    <td className="py-3 px-4 text-center">
                      <div className="flex justify-center">
                        {renderStatusIcon(c.status, c.critical)}
                      </div>
                    </td>

                    {/* Check Name */}
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900 text-xs group-hover:text-slate-950">
                        {friendlyName}
                      </div>
                      <div className="text-[11px] text-slate-400 truncate max-w-xs font-mono">
                        {c.field || c.check_id}
                      </div>
                    </td>

                    {/* Category */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className="text-slate-600 font-medium text-[11px]">
                        {c.check_type}
                      </span>
                    </td>

                    {/* Criticality */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      {c.critical ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200/60">
                          Critical
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200/60">
                          Non-blocking
                        </span>
                      )}
                    </td>

                    {/* Result */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      {renderResultText(c)}
                    </td>

                    {/* Action hint */}
                    <td className="py-3 px-3 text-right">
                      <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 transition-colors" />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
