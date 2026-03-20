/**
 * MetricHistogram
 *
 * Teal bar distribution histogram. Bins data into configurable buckets.
 * Adapted from cissa_merged CompetitivenessHistogram for current app's styling.
 *
 * - Click a bar to see a tooltip with all entities in that bin
 * - Stats bar: n, mean, median, std dev, % positive
 * - Zero-crossing reference line + optional mean/median reference lines
 */
import { useState, useMemo } from "react";
import {
  ResponsiveContainer, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Cell, ReferenceLine,
} from "recharts";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface HistogramDataPoint {
  /** Entity name (ticker or sector label) */
  name: string;
  /** Metric value for this entity */
  value: number;
}

export type HistValueFormat = "pct" | "ratio";

export interface MetricHistogramProps {
  title: string;
  data: HistogramDataPoint[];
  xAxisLabel?: string;
  /** Min bucket edge (default -20) */
  minBucket?: number;
  /** Max bucket edge (default 20) */
  maxBucket?: number;
  /** Bucket width in value units (default 2) */
  bucketWidth?: number;
  /** Bar fill color */
  barColor?: string;
  height?: number;
  valueFormat?: HistValueFormat;
  onBinSelect?: (entities: HistogramDataPoint[], binLabel: string) => void;
  zeroCrossing?: boolean;
  /** When true, render without outer card wrapper — use when embedded inside a page's own card */
  bare?: boolean;
}

// ─── Internal types ───────────────────────────────────────────────────────────

interface Bin {
  label: string;
  count: number;
  entities: HistogramDataPoint[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function buildBins(data: HistogramDataPoint[], min: number, max: number, width: number): Bin[] {
  const bins: Bin[] = [];
  for (let edge = min; edge < max; edge += width) {
    const lo = edge;
    const hi = edge + width;
    const entities = data.filter(d => d.value >= lo && d.value < hi);
    bins.push({ label: `${lo}`, count: entities.length, entities });
  }
  // Catch values exactly at max
  const last = bins[bins.length - 1];
  if (last) {
    const atMax = data.filter(d => d.value === max);
    last.entities.push(...atMax);
    last.count += atMax.length;
  }
  return bins;
}

function fmtV(v: number, fmt: HistValueFormat) {
  return fmt === "ratio" ? `${v.toFixed(2)}×` : `${v.toFixed(1)}%`;
}

// ─── Tooltip ──────────────────────────────────────────────────────────────────

function BinTooltip({ active, payload, valueFormat = "pct" }: {
  active?: boolean;
  payload?: Array<{ payload: Bin }>;
  valueFormat?: HistValueFormat;
}) {
  if (!active || !payload?.length) return null;
  const bin = payload[0].payload;
  if (bin.count === 0) return null;

  const width = valueFormat === "ratio" ? 0.5 : 2;
  const hi = (Number(bin.label) + width).toFixed(valueFormat === "ratio" ? 1 : 0);

  return (
    <div style={{
      background: "hsl(var(--card))", border: "1px solid hsl(var(--border))",
      borderRadius: "0.375rem", padding: "0.5rem 0.75rem", fontSize: "0.72rem",
      maxWidth: 220, boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
    }}>
      <div style={{ fontWeight: 600, color: "hsl(var(--foreground))", marginBottom: "0.25rem" }}>
        [{bin.label}, {hi})
        <span style={{ marginLeft: "0.4rem", fontWeight: 400, color: "hsl(var(--muted-foreground))" }}>
          {bin.count} {bin.count === 1 ? "co." : "cos."}
        </span>
      </div>
      {bin.entities.slice(0, 20).map((e, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.5 }}>
          <span>{e.name}</span>
          <span style={{ fontVariantNumeric: "tabular-nums", color: "hsl(var(--foreground))", fontWeight: 500 }}>{fmtV(e.value, valueFormat)}</span>
        </div>
      ))}
      {bin.entities.length > 20 && (
        <div style={{ color: "hsl(var(--muted-foreground))", marginTop: "0.15rem" }}>+{bin.entities.length - 20} more</div>
      )}
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function MetricHistogram({
  title,
  data,
  xAxisLabel,
  minBucket = -20,
  maxBucket = 20,
  bucketWidth = 2,
  barColor = "#0891b2",
  height = 220,
  valueFormat = "pct",
  onBinSelect,
  zeroCrossing = true,
  bare = false,
}: MetricHistogramProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const bins = useMemo(
    () => buildBins(data, minBucket, maxBucket, bucketWidth),
    [data, minBucket, maxBucket, bucketWidth],
  );

  const stats = useMemo(() => {
    if (data.length === 0) return null;
    const vals = data.map(d => d.value).sort((a, b) => a - b);
    const n = vals.length;
    const avg = vals.reduce((s, v) => s + v, 0) / n;
    const mid = Math.floor(n / 2);
    const med = n % 2 === 0 ? (vals[mid - 1] + vals[mid]) / 2 : vals[mid];
    const stdDev = Math.sqrt(vals.reduce((s, v) => s + (v - avg) ** 2, 0) / n);
    const posPct = Math.round((vals.filter(v => v > 0).length / n) * 100);
    return { n, avg, med, stdDev, posPct };
  }, [data]);

  function handleBarClick(_: unknown, index: number) {
    const newActive = activeIndex === index ? null : index;
    setActiveIndex(newActive);
    if (onBinSelect) {
      onBinSelect(newActive === null ? [] : bins[newActive].entities, newActive === null ? "" : bins[newActive].label);
    }
  }

  const inner = (
    <>
      {!bare && title && <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "hsl(var(--foreground))", marginBottom: "0.75rem" }}>{title}</div>}

      {data.length === 0 ? (
        <div style={{ height, display: "flex", alignItems: "center", justifyContent: "center", color: "hsl(var(--muted-foreground))", fontSize: "0.8125rem" }}>
          No data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={bins} margin={{ top: 4, right: 12, left: 0, bottom: xAxisLabel ? 24 : 6 }} barCategoryGap="5%">
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 93%)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "#94a3b8", fontSize: 9 }}
              tickLine={false}
              axisLine={false}
              interval={1}
              label={xAxisLabel ? {
                value: xAxisLabel,
                position: "insideBottom",
                offset: -8,
                style: { fill: "#94a3b8", fontSize: 10 },
              } : undefined}
            />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 9 }}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              width={28}
              label={{ value: "# Cos.", angle: -90, position: "insideLeft", offset: 12, style: { fill: "#94a3b8", fontSize: 8 } }}
            />
            <Tooltip content={<BinTooltip valueFormat={valueFormat} />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
            <Bar dataKey="count" name="Companies" radius={[2, 2, 0, 0]} onClick={handleBarClick} style={{ cursor: "pointer" }}>
              {bins.map((_, i) => (
                <Cell
                  key={i}
                  fill={activeIndex === i ? "#26a69a" : barColor}
                  fillOpacity={activeIndex !== null && activeIndex !== i ? 0.45 : 1}
                />
              ))}
            </Bar>
            {zeroCrossing && (
              <ReferenceLine x="0" stroke="hsl(0 72% 51%)" strokeDasharray="4 2" strokeWidth={1.5} />
            )}
          </BarChart>
        </ResponsiveContainer>
      )}

      {stats && (
        <div style={{
          display: "flex", flexWrap: "wrap", gap: "0.25rem 0.75rem",
          fontSize: "0.65rem", color: "hsl(var(--muted-foreground))", marginTop: "0.5rem",
          paddingTop: "0.4rem", borderTop: "1px solid hsl(var(--border))",
        }}>
          <span>n={stats.n}</span>
          <span>Mean: {fmtV(stats.avg, valueFormat)}</span>
          <span>Median: {fmtV(stats.med, valueFormat)}</span>
          <span>Std: {fmtV(stats.stdDev, valueFormat)}</span>
          <span>Positive: {stats.posPct}%</span>
        </div>
      )}
    </>
  );

  if (bare) return inner;
  return <div className="chart-card" style={{ padding: "1rem" }}>{inner}</div>;
}

export default MetricHistogram;
