import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

const agentStyles = {
  monitor: { label: 'MONITOR', badge: 'bg-sky-50 text-sky-700 border-sky-200' },
  risk: { label: 'RISK', badge: 'bg-rose-50 text-rose-700 border-rose-200' },
  inventory: { label: 'INVENTORY', badge: 'bg-amber-50 text-amber-700 border-amber-200' },
  routing: { label: 'ROUTING', badge: 'bg-purple-50 text-purple-700 border-purple-200' },
  dispatch: { label: 'DISPATCH', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  orchestrator: { label: 'ORCHESTRATOR', badge: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
};

export default function AgentLog({ events = [] }) {
  const [expandedId, setExpandedId] = useState(null);

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-56 text-center p-6 text-slate-400">
        <span className="text-3xl mb-2">🤖</span>
        <p className="text-xs font-medium text-slate-500">Awaiting swarm agent observations</p>
        <p className="text-[11px] text-slate-400 mt-0.5">The autonomous cycle runs every 10s.</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-2 text-xs divide-y divide-slate-100">
        {events.map((ev) => {
          const agentCfg = agentStyles[ev.agent] || {
            label: ev.agent.toUpperCase(),
            badge: 'bg-slate-100 text-slate-600 border-slate-200',
          };
          const timeStr = new Date(ev.timestamp).toLocaleTimeString();
          const isAlert = ev.level === 'alert';
          const isWarn = ev.level === 'warn';
          const hasDetails = !!ev.details_json;
          const isExpanded = expandedId === ev.id;

          return (
            <div key={ev.id} className="pt-2 first:pt-0">
              <div
                className={`p-2 rounded-lg transition-colors cursor-pointer ${
                  isAlert
                    ? 'bg-rose-50/80 border border-rose-200'
                    : isWarn
                    ? 'bg-amber-50/80 border border-amber-200'
                    : 'hover:bg-slate-50/90'
                }`}
                onClick={() => hasDetails && toggleExpand(ev.id)}
              >
                <div className="flex items-center justify-between mb-1 text-[11px]">
                  <div className="flex items-center gap-1.5">
                    <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${agentCfg.badge}`}>
                      {agentCfg.label}
                    </span>
                    <span className="text-slate-400 font-mono text-[10px]">{timeStr}</span>
                  </div>
                  {hasDetails && (
                    <span className="text-slate-400 hover:text-slate-700">
                      {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    </span>
                  )}
                </div>

                <p className={`text-slate-700 leading-snug break-words ${isAlert ? 'font-semibold text-rose-700' : ''}`}>
                  {ev.message}
                </p>

                {isExpanded && hasDetails && (
                  <div className="mt-2 p-2 bg-slate-50 rounded border border-slate-200 text-[10px] font-mono text-slate-600 overflow-x-auto whitespace-pre-wrap">
                    {ev.details_json}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
