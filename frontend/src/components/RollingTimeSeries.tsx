/**
 * RollingTimeSeries
 *
 * Multi-line 1Y/3Y/5Y/10Y/LT rolling average chart with period tabs and data table.
 * Adapted from cissa_merged CompetitivenessTimeSeries for the current app's styling.
 *
 * Lines: 1Y=gold  3Y=green  5Y=blue  10Y=grey  LT=dashed-slate
 */
import { useState } from "react";
import {
  ResponsiveContainer, ComposedChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from "recharts";
import type { RollingRow } from "../lib/rollingAverage";

// ─── Constants ────────────────────────────────────────────────────────────────

const LINE_DEFS = [
  { key: "y1",  label: "1Y Avg",  color: "#F59E0B", dashed: false, width: 1.8 },
  { key: "y3",  label: "3Y Avg",  color: "#10B981", dashed: false, width: 1.8 },
  { key: "y5",  label: "5Y Avg",  color: "#3B82F6", dashed: false, width: 1.8 },
  { key: "y10", label: "10Y Avg", color: "#94A3B8", dashed: false, width: 2.0 },
  { key: "lt",  label: "LT Avg",  color: "#64748B", dashed: true,  width: 1.5 },
] as const;

type PeriodKey = "y1" | "y3" | "y5" | "y10";

const PERIOD_TABS: Array<{ key: PeriodKey; label: string }> = [
  { key: "y1",  label: "1Y"  },
  { key: "y3",  label: "3Y"  },
  { key: "y5",  label: "5Y"  },
  { key: "y10", label: "10Y" },
];

// ─── Types ────────────────────────────────────────────────────────────────────

export type RtsValueFormat = "pct" | "ratio";

export interface RollingTimeSeriesProps {
  title:          string;
  subtitle?:      string;
  rows:           RollingRow[];
  valueFormat?:   RtsValueFormat;
  height?:        number;
  /** Show "LIVE" / "ILLUS." badge */
  isLive?:        boolean;
  /** When true, render without outer card wrapper — use when embedded inside a page's own card */
  bare?:          boolean;
}

// ─── Formatters ───────────────────────────────────────────────────────────────

function fmtVal(v: number | null | undefined, fmt: RtsValueFormat): string {
  if (v == null || !isFinite(v)) return "—";
  if (fmt === "ratio") return v < 0 ? `(${Math.abs(v).toFixed(2)}×)` : `${v.toFixed(2)}×`;
  return v < 0 ? `(${Math.abs(v).toFixed(1)}%)` : `${v.toFixed(1)}%`;
}

function fmtAxis(v: number, fmt: RtsValueFormat): string {
  if (fmt === "ratio") return v < 0 ? `(${Math.abs(v).toFixed(1)}×)` : `${v.toFixed(1)}×`;
  return v < 0 ? `(${Math.abs(v).toFixed(0)}%)` : `${v.toFixed(0)}%`;
}

// ─── Tooltip ──────────────────────────────────────────────────────────────────

function RTSTooltip({ active, payload, label, fmt }: {
  active?:   boolean;
  payload?:  Array<{ dataKey: string; value: number | null; color: string }>;
  label?:    number;
  fmt:       RtsValueFormat;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "hsl(var(--card))", border: "1px solid hsl(var(--border))",
      borderRadius: "0.375rem", padding: "0.5rem 0.75rem", fontSize: "0.75rem",
    }}>
      <div style={{ fontWeight: 600, marginBottom: "0.25rem", color: "hsl(var(--foreground))" }}>{label}</div>
      {payload.map(p => {
        const def = LINE_DEFS.find(l => l.key === p.dataKey);
        const isNeg = p.value != null && p.value < 0;
        return (
          <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: "0.375rem", marginBottom: "0.1rem" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: p.color, flexShrink: 0 }} />
            <span style={{ color: "hsl(var(--muted-foreground))", minWidth: 50 }}>{def?.label ?? p.dataKey}</span>
            <span style={{ fontVariantNumeric: "tabular-nums", color: isNeg ? "hsl(0 72% 51%)" : "hsl(var(--foreground))", fontWeight: 500 }}>
              {fmtVal(p.value, fmt)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function RollingTimeSeries({
  title,
  subtitle,
  rows,
  valueFormat = "pct",
  height = 220,
  isLive,
  bare = false,
}: RollingTimeSeriesProps) {
  const [activePeriod, setActivePeriod] = useState<PeriodKey>("y5");

  const isEmpty = rows.length === 0;

  const inner = (
    <>
      {/* Header — only show title/subtitle when not bare (bare = page card handles it) */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
        <div>
          {!bare && title && <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "hsl(var(--foreground))" }}>{title}</div>}
          {!bare && subtitle && <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginTop: "0.1rem" }}>{subtitle}</div>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {isLive !== undefined && (
            <span style={{
              fontSize: "0.6rem", fontWeight: 700, padding: "0.1rem 0.4rem", borderRadius: "3px",
              background: isLive ? "hsl(152 60% 40% / 0.15)" : "hsl(38 60% 52% / 0.15)",
              color: isLive ? "hsl(152 60% 40%)" : "hsl(38 60% 52%)",
            }}>
              {isLive ? "● LIVE" : "ILLUS."}
            </span>
          )}
          <div style={{ display: "flex", gap: "0.25rem" }}>
            {PERIOD_TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActivePeriod(tab.key)}
                style={{
                  padding: "0.15rem 0.45rem", borderRadius: "3px", fontSize: "0.6875rem",
                  border: "1px solid hsl(var(--border))",
                  background: activePeriod === tab.key ? "hsl(var(--primary))" : "transparent",
                  color: activePeriod === tab.key ? "#fff" : "hsl(var(--muted-foreground))",
                  cursor: "pointer",
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chart */}
      {isEmpty ? (
        <div style={{ height, display: "flex", alignItems: "center", justifyContent: "center", color: "hsl(var(--muted-foreground))", fontSize: "0.8125rem" }}>
          No data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <ComposedChart data={rows} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
            <XAxis dataKey="year" tick={{ fill: "#94a3b8", fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 9 }}
              tickFormatter={v => fmtAxis(v, valueFormat)}
              axisLine={false} tickLine={false} width={40}
            />
            <Tooltip content={<RTSTooltip fmt={valueFormat} />} cursor={{ stroke: "hsl(var(--border))", strokeWidth: 1 }} />
            <Legend
              verticalAlign="top" align="right" iconType="plainline"
              wrapperStyle={{ fontSize: "0.65rem", color: "#94a3b8", paddingBottom: 4 }}
              formatter={(v: string) => LINE_DEFS.find(l => l.key === v)?.label ?? v}
            />
            <ReferenceLine y={0} stroke="hsl(0 72% 51% / 0.25)" strokeDasharray="4 3" />
            {LINE_DEFS.map(l => (
              <Line
                key={l.key}
                type="monotone"
                dataKey={l.key}
                name={l.key}
                stroke={l.color}
                strokeWidth={activePeriod === l.key ? l.width + 1.2 : l.width}
                strokeDasharray={l.dashed ? "5 3" : undefined}
                dot={false}
                connectNulls
                strokeOpacity={l.key === "lt" ? 0.6 : activePeriod === l.key ? 1 : 0.3}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Data table */}
      {!isEmpty && (
        <div style={{ overflowX: "auto", marginTop: "0.75rem" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.6875rem" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: "0.25rem 0.5rem", color: "hsl(var(--muted-foreground))", fontWeight: 600, borderBottom: "1px solid hsl(var(--border))", minWidth: 60 }}>Period</th>
                {rows.map(r => (
                  <th key={r.year} style={{ textAlign: "right", padding: "0.25rem 0.375rem", color: "hsl(var(--muted-foreground))", fontWeight: 500, borderBottom: "1px solid hsl(var(--border))" }}>{r.year}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {LINE_DEFS.map((l, idx) => (
                <tr key={l.key} style={{ background: idx % 2 === 0 ? "hsl(var(--muted) / 0.3)" : "transparent" }}>
                  <td style={{ padding: "0.2rem 0.5rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    <span style={{ width: 7, height: 7, borderRadius: "50%", background: l.color, flexShrink: 0 }} />
                    <span style={{ color: "hsl(var(--muted-foreground))" }}>{l.label}</span>
                  </td>
                  {rows.map(r => {
                    const v = (r as unknown as Record<string, number | null>)[l.key];
                    const isNeg = v != null && v < 0;
                    return (
                      <td key={r.year} style={{ textAlign: "right", padding: "0.2rem 0.375rem", fontVariantNumeric: "tabular-nums", color: isNeg ? "hsl(0 72% 51%)" : "hsl(var(--foreground))" }}>
                        {fmtVal(v, valueFormat)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );

  if (bare) return inner;
  return <div className="chart-card" style={{ padding: "1rem" }}>{inner}</div>;
}

export default RollingTimeSeries;
