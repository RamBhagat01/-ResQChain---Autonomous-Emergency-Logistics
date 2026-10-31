import React, { useState } from 'react';
import { Check, X, ChevronDown, ChevronUp } from 'lucide-react';

const statusConfig = {
  PENDING_APPROVAL: {
    label: 'Pending',
    badge: 'bg-amber-50 text-amber-700 border-amber-200',
  },
  IN_TRANSIT: {
    label: 'In Transit',
    badge: 'bg-sky-50 text-sky-700 border-sky-200',
  },
  DELIVERED: {
    label: 'Delivered',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
  CANCELLED: {
    label: 'Cancelled',
    badge: 'bg-rose-50 text-rose-700 border-rose-200',
  },
};

function formatItem(quantity, item) {
  if (!item) return `${quantity}`;
  const clean = String(item).toLowerCase();
  if (clean.includes('water')) return `${quantity}L Water`;
  if (clean.includes('food')) return `${quantity} Food Kits`;
  if (clean.includes('medical')) return `${quantity} Med Kits`;
  return `${quantity} ${item.replace(/_/g, ' ')}`;
}

function explainSupplierDecision(reasoning = '') {
  const text = String(reasoning);
  const match = text.match(
    /Selected (.+?) \(ID (\d+)\): stock=(\d+) units \(demand requires (\d+)\), distance=(\d+(?:\.\d+)?) km, reliability rating=(\d+(?:\.\d+)?)/i,
  );

  if (!match) {
    return {
      summary: text || 'Standard deterministic rule-based allocation.',
      details: [],
      fallback: '',
    };
  }

  const [, supplier, supplierId, stock, demand, distance, reliability] = match;
  const fallbackMatch = text.match(/Gemini API fallback:\s*(.+)$/i);

  return {
    summary: `${supplier} selected based on stock availability and route distance.`,
    details: [
      `Available: ${stock} units`,
      `Needed: ${demand} units`,
      `Distance: ${distance} km`,
      `Reliability: ${(Number(reliability) * 100).toFixed(0)}%`,
    ],
    fallback: fallbackMatch ? 'Heuristic rule applied' : '',
  };
}

export default function OrdersTable({ orders = [], onApprove, onCancel }) {
  const [expandedOrderId, setExpandedOrderId] = useState(null);

  const toggleReasoning = (id) => {
    setExpandedOrderId(expandedOrderId === id ? null : id);
  };

  if (orders.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-56 text-center p-6 text-slate-400">
        <span className="text-3xl mb-2">📦</span>
        <p className="text-xs font-medium text-slate-500">No active dispatch orders</p>
        <p className="text-[11px] text-slate-400 mt-0.5">Simulate a flood to generate emergency relief demand.</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto overflow-x-hidden">
        <table className="w-full border-collapse text-xs table-fixed">
          <colgroup>
            <col style={{ width: '11%' }} />
            <col style={{ width: '30%' }} />
            <col style={{ width: '21%' }} />
            <col style={{ width: '20%' }} />
            <col style={{ width: '18%' }} />
          </colgroup>
          <thead className="sticky top-0 z-10 bg-slate-50/95 backdrop-blur-xs border-b border-slate-200/80">
            <tr className="text-slate-500 font-semibold text-[11px]">
              <th className="py-2.5 px-2 text-left">Order</th>
              <th className="py-2.5 px-1.5 text-left">Supplies</th>
              <th className="py-2.5 px-1 text-center">Status</th>
              <th className="py-2.5 px-1 text-center">Route</th>
              <th className="py-2.5 px-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {orders.map((order) => {
              const isPending = order.status === 'PENDING_APPROVAL';
              const isExpanded = expandedOrderId === order.id;
              const status = statusConfig[order.status] || {
                label: order.status,
                badge: 'bg-slate-100 text-slate-700 border-slate-200',
              };

              const distKm = order.distance_km ? `${Number(order.distance_km).toFixed(1)} km` : '-';
              const etaTooltip = order.eta_minutes ? `ETA: ${Math.round(order.eta_minutes)} mins` : '';

              return (
                <React.Fragment key={order.id}>
                  <tr className="hover:bg-slate-50/60 transition-colors">
                    {/* Order ID */}
                    <td className="py-2 px-2 font-mono text-xs font-bold text-sky-600 truncate text-left">
                      #{order.id}
                      {order.reroute_count > 0 && (
                        <span
                          className="ml-1 text-[9px] font-bold text-purple-700 bg-purple-50 px-1 py-0.2 rounded border border-purple-200"
                          title={`Dynamically rerouted ${order.reroute_count}x`}
                        >
                          ⚡{order.reroute_count}
                        </span>
                      )}
                    </td>

                    {/* Supplies (Wraps naturally to next line - no truncation) */}
                    <td className="py-2 px-1.5 font-medium text-slate-800 text-[11px] leading-snug break-words text-left">
                      {formatItem(order.quantity, order.item)}
                    </td>

                    {/* Status Pill (Centered for symmetry) */}
                    <td className="py-2 px-1 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold border whitespace-nowrap ${status.badge}`}
                      >
                        {status.label}
                      </span>
                    </td>

                    {/* Route in decimal km (Centered & compact, no minutes clutter) */}
                    <td className="py-2 px-1 text-center font-mono text-[11px] text-slate-600 whitespace-nowrap truncate" title={etaTooltip}>
                      {distKm}
                    </td>

                    {/* Actions: Vertically stacked Accept & Reject buttons */}
                    <td className="py-2 px-2 text-right">
                      {isPending ? (
                        <div className="flex flex-col items-end gap-1 justify-center">
                          <button
                            onClick={() => onApprove(order.id)}
                            className="w-[64px] py-1 bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white rounded text-[10px] font-semibold transition inline-flex items-center justify-center gap-1 shadow-2xs cursor-pointer whitespace-nowrap"
                            title="Accept Order"
                          >
                            <Check className="w-2.5 h-2.5 stroke-[2.5]" />
                            <span>Accept</span>
                          </button>
                          <button
                            onClick={() => onCancel(order.id)}
                            className="w-[64px] py-0.5 bg-rose-50 hover:bg-rose-100 active:scale-95 text-rose-600 border border-rose-200 hover:border-rose-300 rounded text-[10px] font-semibold transition inline-flex items-center justify-center gap-1 cursor-pointer whitespace-nowrap"
                            title="Reject Order"
                          >
                            <X className="w-2.5 h-2.5 stroke-[2.5]" />
                            <span>Reject</span>
                          </button>
                        </div>
                      ) : (
                        <div className="flex justify-end">
                          <button
                            onClick={() => toggleReasoning(order.id)}
                            className="w-[64px] py-1 bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-600 rounded text-[10px] font-medium transition inline-flex items-center justify-center gap-0.5 cursor-pointer"
                            title="View AI reasoning"
                          >
                            <span>Reason</span>
                            {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>

                  {/* Expandable AI Reasoning Row */}
                  {isExpanded && (
                    <tr className="bg-slate-50/70">
                      <td colSpan="5" className="px-3 py-2 text-[11px] text-slate-600 border-b border-slate-100">
                        {(() => {
                          const exp = explainSupplierDecision(order.ai_reasoning);
                          return (
                            <div className="bg-white p-2.5 rounded-lg border border-slate-200/80 shadow-xs space-y-1">
                              <p className="font-semibold text-slate-800 text-[11px]">AI Supplier Allocation</p>
                              <p className="text-slate-600 leading-snug">{exp.summary}</p>
                              {exp.details.length > 0 && (
                                <div className="grid grid-cols-2 gap-1 pt-1 text-[10px] text-slate-500 font-mono">
                                  {exp.details.map((d) => (
                                    <span key={d}>• {d}</span>
                                  ))}
                                </div>
                              )}
                              {exp.fallback && (
                                <p className="text-[10px] text-amber-700 italic pt-0.5">{exp.fallback}</p>
                              )}
                            </div>
                          );
                        })()}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
