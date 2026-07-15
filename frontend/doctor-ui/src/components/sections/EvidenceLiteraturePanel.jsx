import React from 'react';
import { BookOpen, ExternalLink } from 'lucide-react';
import { GlassCard, Badge } from '../shared';
import { useTheme } from '../../context/ThemeContext';

const TIER_LABEL = { high: 'High', moderate: 'Moderate', low: 'Low' };
const TIER_VARIANT = { high: 'success', moderate: 'warning', low: 'gray' };

export default function EvidenceLiteraturePanel({ evidence = [] }) {
  const { isDark } = useTheme();

  if (!evidence.length) {
    return (
      <GlassCard className="p-6">
        <div className={`text-sm flex items-center gap-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          <BookOpen className="w-4 h-4" /> No recent literature was retrieved for this case.
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-4">
      <div className="space-y-3">
        <div className={`flex items-center gap-2 text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>
          <BookOpen className="w-4 h-4" /> Evidence &amp; Literature (live from Europe PMC)
        </div>
        {evidence.map((e, i) => (
          <div
            key={i}
            className={`rounded-lg border p-3 ${isDark ? 'border-white/10' : 'border-slate-200'}`}
          >
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant={TIER_VARIANT[e.tier] || 'gray'} size="sm">
                {TIER_LABEL[e.tier] || e.tier}
              </Badge>
              {e.cpgGap && (
                <Badge variant="info" size="sm">
                  Literature-based &middot; no local CPG
                </Badge>
              )}
              <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                {e.journal} {e.year || ''}
              </span>
            </div>
            <div className={`text-sm mt-1 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{e.title}</div>
            {e.url && (
              <a
                href={e.url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-sky-500 hover:text-sky-400 inline-flex items-center gap-1 mt-1"
              >
                View on Europe PMC <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
