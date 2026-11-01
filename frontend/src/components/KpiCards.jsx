import React from 'react';
import { AlertTriangle, Package, CheckCircle2, RefreshCw } from 'lucide-react';

const cards = (kpis) => [
  {
    title: 'Active Danger Zones',
    value: kpis.active_zones,
    icon: AlertTriangle,
    bg: '#fef2f2',
    iconBg: '#fee2e2',
    iconColor: '#dc2626',
    valueColor: '#dc2626',
    pulse: kpis.active_zones > 0,
    pulseColor: '#f87171',
    desc: 'flood areas tracked',
  },
  {
    title: 'Open Demands',
    value: kpis.open_demands,
    icon: Package,
    bg: '#fffbeb',
    iconBg: '#fef3c7',
    iconColor: '#d97706',
    valueColor: '#d97706',
    pulse: false,
    desc: 'awaiting fulfilment',
  },
  {
    title: 'Orders In‑Transit',
    value: kpis.orders_in_transit,
    icon: Package,
    bg: '#eff6ff',
    iconBg: '#dbeafe',
    iconColor: '#2563eb',
    valueColor: '#2563eb',
    pulse: kpis.orders_in_transit > 0,
    pulseColor: '#93c5fd',
    desc: 'delivery plans underway',
  },
  {
    title: 'Relief Delivered',
    value: kpis.delivered_orders,
    icon: CheckCircle2,
    bg: '#f0fdf4',
    iconBg: '#dcfce7',
    iconColor: '#16a34a',
    valueColor: '#16a34a',
    pulse: false,
    desc: 'completed deliveries',
  },
  {
    title: 'Dynamic Reroutes',
    value: kpis.total_reroutes,
    icon: RefreshCw,
    bg: '#faf5ff',
    iconBg: '#ede9fe',
    iconColor: '#7c3aed',
    valueColor: '#7c3aed',
    pulse: false,
    desc: 'hazard avoidances',
  },
];

export default function KpiCards({ kpis }) {
  if (!kpis) return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
      {[...Array(5)].map((_, i) => (
        <div
          key={i}
          className="rounded-xl p-2.5 animate-pulse border border-slate-100 bg-slate-100/70 min-h-[115px]"
        />
      ))}
    </div>
  );

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
      {cards(kpis).map((c, i) => {
        const Icon = c.icon;
        return (
          <div
            key={i}
            className="rounded-xl p-2.5 card-hover cursor-default bg-white border border-slate-200/80 shadow-xs flex flex-col justify-between min-w-0 min-h-[118px]"
          >
            {/* Top row: Icon + Pulse */}
            <div className="flex items-center justify-between mb-1.5">
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center relative shrink-0"
                style={{ backgroundColor: c.iconBg }}
              >
                <Icon className="w-3.5 h-3.5" style={{ color: c.iconColor }} />
                {c.pulse && (
                  <span className="absolute -top-0.5 -right-0.5 flex h-2 w-2">
                    <span
                      className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60"
                      style={{ backgroundColor: c.pulseColor }}
                    />
                    <span
                      className="relative inline-flex rounded-full h-2 w-2"
                      style={{ backgroundColor: c.pulseColor }}
                    />
                  </span>
                )}
              </div>
            </div>

            {/* Value */}
            <p className="text-xl font-extrabold leading-tight" style={{ color: c.valueColor }}>
              {c.value}
            </p>

            {/* Label + Description (Wraps naturally to next line - no text truncation) */}
            <div className="mt-1 flex flex-col">
              <p className="text-[11px] font-semibold text-slate-800 leading-tight break-words whitespace-normal">
                {c.title}
              </p>
              <p className="text-[10px] text-slate-400 leading-tight break-words whitespace-normal mt-0.5">
                {c.desc}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
