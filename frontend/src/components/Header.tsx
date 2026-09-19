'use client';

import React from 'react';
import { ShieldCheck, ExternalLink } from 'lucide-react';
import { HealthResponse } from '@/types/api';

interface HeaderProps {
  health: HealthResponse | null;
  healthError: boolean;
  onRefreshHealth: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  healthError,
  onRefreshHealth,
}) => {
  return (
    <header className="border-b border-slate-200/80 bg-white sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-15 flex items-center justify-between">
        {/* Left: Brand & Subtitle */}
        <div className="flex items-center space-x-3">
          <div className="w-7 h-7 rounded bg-slate-900 flex items-center justify-center text-white shadow-xs">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="font-semibold text-sm tracking-wider text-slate-900 uppercase">
              Aurethis
            </span>
            <span className="text-slate-300">/</span>
            <span className="text-xs font-medium text-slate-500 tracking-wide uppercase">
              QA Control Center
            </span>
          </div>
        </div>

        {/* Right: Operational Status & Environment */}
        <div className="flex items-center space-x-3 text-xs">
          {/* Health Status Indicator */}
          <button
            onClick={onRefreshHealth}
            title={health ? `${health.service} v${health.version} — Click to refresh` : 'Re-verify engine connectivity'}
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-200"
          >
            {healthError ? (
              <>
                <span className="w-2 h-2 rounded-full bg-rose-500" />
                <span className="text-rose-700 font-medium text-xs">Backend Offline</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-slate-600 font-medium text-xs">System operational</span>
              </>
            )}
          </button>

          <span className="text-slate-200">•</span>

          {/* Environment Indicator */}
          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200/80">
            DEMO
          </span>

          {/* API Link */}
          <a
            href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:flex items-center space-x-1 text-slate-400 hover:text-slate-600 transition-colors text-xs ml-1"
            title="Open OpenAPI specification"
          >
            <span>API Docs</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </header>
  );
};
