import { useState, useEffect } from "react";
import { Link } from "wouter";
import {
  ComposedChart, AreaChart, BarChart,
  Area, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { useActiveContext, useEPSeries, useMultipleMetrics, aggregateByYear } from "../hooks/useMetrics";

// ── Color tokens ──────────────────────────────────────────────────────────────
const NAVY  = "hsl(213 75% 22%)";
const GOLD  = "hsl(38 60% 52%)";
const GREEN = "hsl(152 60% 40%)";
const SLATE = "hsl(215 15% 46%)";

// ── Reusable skeleton ─────────────────────────────────────────────────────────
function Skeleton({ h = 180 }: { h?: number }) {
  return (
    <div style={{
      height: h, background: "hsl(210 20% 96%)", borderRadius: 8,
      backgroundImage: "linear-gradient(90deg,hsl(210 20% 96%),hsl(210 20% 93%),hsl(210 20% 96%))",
      backgroundSize: "200% 100%",
      animation: "shimmer 1.4s infinite",
    }} />
  );
}

// ── KPI tile ──────────────────────────────────────────────────────────────────
function KpiTile({
  label, value, delta, dir, note, icon, loading,
}: {
  label: string; value: string; delta?: string; dir?: "up" | "down" | "flat";
  note?: string; icon: React.ReactNode; loading?: boolean;
}) {
  const deltaColor = dir === "up" ? GREEN : dir === "down" ? "hsl(0 65% 50%)" : GOLD;
  return (
    <div style={{
      background: "#fff",
      borderRadius: 10,
      border: "1px solid hsl(210 16% 90%)",
      padding: "1rem 1.125rem",
      boxShadow: "0 1px 4px hsl(213 40% 50% / 0.06)",
      display: "flex",
      flexDirection: "column",
      gap: "0.375rem",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <span style={{ fontSize: "0.6875rem", fontWeight: 600, color: SLATE, lineHeight: 1.3 }}>{label}</span>
        <div style={{ color: "hsl(213 30% 72%)", flexShrink: 0 }}>{icon}</div>
      </div>
      {loading ? (
        <div style={{ height: 28, background: "hsl(210 20% 94%)", borderRadius: 5, marginTop: 4 }} />
      ) : (
        <div style={{ fontSize: "1.4375rem", fontWeight: 800, color: "hsl(220 35% 12%)", letterSpacing: "-0.03em", lineHeight: 1.1 }}>
          {value}
        </div>
      )}
      {delta && (
        <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
          <span style={{ fontSize: "0.6875rem", fontWeight: 700, color: deltaColor }}>{delta}</span>
          {note && <span style={{ fontSize: "0.5625rem", color: "hsl(215 15% 60%)" }}>· {note}</span>}
        </div>
      )}
    </div>
  );
}

// ── Chart card ────────────────────────────────────────────────────────────────
function ChartCard({ title, subtitle, children, action }: {
  title: string; subtitle?: string; children: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div style={{
      background: "#fff",
      borderRadius: 10,
      border: "1px solid hsl(210 16% 90%)",
      padding: "1rem 1.25rem 1.125rem",
      boxShadow: "0 1px 4px hsl(213 40% 50% / 0.05)",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "0.875rem" }}>
        <div>
          <div style={{ fontSize: "0.8125rem", fontWeight: 700, color: "hsl(220 35% 12%)", lineHeight: 1.2 }}>{title}</div>
          {subtitle && <div style={{ fontSize: "0.6875rem", color: SLATE, marginTop: "0.1875rem" }}>{subtitle}</div>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

// ── Static bow-wave helper ────────────────────────────────────────────────────
function bell(x: number, mu: number, sigma: number, peak: number) {
  return peak * Math.exp(-((x - mu) ** 2) / (2 * sigma * sigma));
}

// ── Principle progress cards ──────────────────────────────────────────────────
const principles = [
  { n: 1, label: "Economic Measures", pct: 92, path: "/principles/1", color: "hsl(213 75% 22%)" },
  { n: 2, label: "Long-Term Focus",   pct: 85, path: "/principles/2", color: "hsl(213 65% 32%)" },
  { n: 3, label: "Capital Market Returns", pct: 78, path: "/principles/3", color: "hsl(38 60% 45%)" },
  { n: 4, label: "EEAI & Sectors",    pct: 70, path: "/principles/4", color: "hsl(160 55% 38%)" },
  { n: 5, label: "Ratio Metrics",     pct: 65, path: "/principles/5", color: "hsl(280 55% 48%)" },
  { n: 6, label: "Valuation & Beta",  pct: 60, path: "/principles/6", color: "hsl(0 60% 46%)" },
];

// ── Custom tooltip ────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label, prefix = "", suffix = "" }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "#fff", border: "1px solid hsl(210 16% 88%)", borderRadius: 8,
      padding: "0.5rem 0.75rem", boxShadow: "0 4px 16px rgba(0,0,0,0.10)", fontSize: "0.75rem",
    }}>
      <div style={{ fontWeight: 700, color: "hsl(220 35% 18%)", marginBottom: "0.25rem" }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color, display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: p.color }} />
          <span>{p.name}: <b>{prefix}{typeof p.value === "number" ? p.value.toFixed(1) : p.value}{suffix}</b></span>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
export default function DashboardHome() {
  const ctx = useActiveContext();

  // Live EP data
  const epSeries = useEPSeries(ctx.datasetId, ctx.paramSetId, "1Y");

  // Live metrics: Beta, Ke, ECF
  const multiMetrics = useMultipleMetrics(
    ctx.datasetId, ctx.paramSetId,
    ["Calc Beta", "Calc Ke", "Calc ECF", "Calc FY TSR", "Calc EE", "Calc 1Y TER"]
  );

  // Build EP bow-wave data
  const epAggregated = aggregateByYear(
    (epSeries.data || []).map(r => ({
      ticker: r.ticker,
      fiscal_year: r.fiscal_year,
      value: (r.ep_1y ?? r.ep_3y ?? null),
    }))
  );

  // Build live bow-wave chart data
  const bowWaveData = (() => {
    if (epAggregated.length >= 4) {
      const max = Math.max(...epAggregated.map(d => Math.abs(d.value)));
      return epAggregated.map(d => ({ year: String(d.year), ep: +(d.value / 1e6).toFixed(2) }));
    }
    // Fallback illustrative
    return Array.from({ length: 26 }, (_, i) => {
      const offset = i - 10;
      const yr = 2014 + offset;
      const baseline = +bell(offset, 3, 6, 350).toFixed(1);
      const newExp = offset >= 0 ? +bell(offset, 5, 8, 720).toFixed(1) : null;
      return { year: String(yr), baseline, newExp };
    });
  })();
  const isLiveEP = epAggregated.length >= 4;

  // KPI computations from live data
  const betaValues = aggregateByYear(multiMetrics.data["Calc Beta"] || []);
  const keValues   = aggregateByYear(multiMetrics.data["Calc Ke"]   || []);
  const ecfValues  = aggregateByYear(multiMetrics.data["Calc ECF"]  || []);
  const tsrValues  = aggregateByYear(multiMetrics.data["Calc FY TSR"] || []);
  const terValues  = aggregateByYear(multiMetrics.data["Calc 1Y TER"] || []);

  const latestBeta = betaValues.length ? betaValues[betaValues.length - 1].value : null;
  const latestKe   = keValues.length   ? keValues[keValues.length - 1].value     : null;
  const latestTSR  = tsrValues.length  ? tsrValues[tsrValues.length - 1].value   : null;
  const latestTER  = terValues.length  ? terValues[terValues.length - 1].value   : null;
  const latestERP  = ctx.params?.equity_risk_premium != null ? Number(ctx.params.equity_risk_premium) : undefined;

  const hasLiveKPIs = !!(latestBeta || latestKe);

  // Build TSR vs Ke line chart
  const tsrKeChartData = keValues.map(ke => {
    const tsr = tsrValues.find(t => t.year === ke.year);
    return { year: String(ke.year), ke: +(ke.value * 100).toFixed(2), tsr: tsr ? +(tsr.value * 100).toFixed(2) : null };
  }).filter(d => d.year >= "2005");

  // ECF annual chart
  const ecfChartData = ecfValues.slice(-15).map(d => ({
    year: String(d.year),
    ecf: +(d.value / 1e6).toFixed(1),
  }));

  const loading = ctx.loading || epSeries.loading || multiMetrics.loading;

  return (
    <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem", maxWidth: 1600 }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontSize: "1.125rem", fontWeight: 800, color: "hsl(220 35% 12%)", margin: 0, letterSpacing: "-0.02em" }}>
            Platform Overview
          </h1>
          <p style={{ fontSize: "0.75rem", color: SLATE, margin: "0.25rem 0 0", lineHeight: 1.5 }}>
            {ctx.stats
              ? `${ctx.stats.companies.count} companies · ${ctx.stats.sectors.count} sectors · FY ${ctx.stats.data_coverage.min_year}–${ctx.stats.data_coverage.max_year}`
              : "Economic Profitability Intelligence Platform — KBA Consulting Group"}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {!ctx.hasMetrics && !ctx.loading && (
            <Link href="/pipeline">
              <a style={{
                display: "flex", alignItems: "center", gap: "0.375rem",
                padding: "0.45rem 0.875rem",
                background: "hsl(38 60% 52%)",
                color: "#fff",
                border: "none",
                borderRadius: 7,
                fontSize: "0.75rem",
                fontWeight: 700,
                textDecoration: "none",
                cursor: "pointer",
                boxShadow: "0 2px 8px hsl(38 60% 52% / 0.35)",
              }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                </svg>
                Run Pipeline
              </a>
            </Link>
          )}
          <Link href="/download">
            <a style={{
              display: "flex", alignItems: "center", gap: "0.375rem",
              padding: "0.45rem 0.875rem",
              background: "#fff",
              color: "hsl(213 75% 22%)",
              border: "1px solid hsl(210 16% 88%)",
              borderRadius: 7,
              fontSize: "0.75rem",
              fontWeight: 600,
              textDecoration: "none",
              cursor: "pointer",
            }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/>
              </svg>
              Export
            </a>
          </Link>
        </div>
      </div>

      {/* ── KPI row ─────────────────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.875rem" }}>
        <KpiTile
          label="Avg Cost of Equity (Ke)"
          value={latestKe ? `${(latestKe * 100).toFixed(1)}%` : "10.0%"}
          delta={latestKe ? "Live" : "Benchmark"}
          dir="flat"
          note="ASX 300 long-run"
          loading={loading && !hasLiveKPIs}
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>}
        />
        <KpiTile
          label="Avg Beta"
          value={latestBeta ? latestBeta.toFixed(2) : "1.00"}
          delta={latestBeta ? "Live" : "Market avg"}
          dir="flat"
          note="Systematic risk"
          loading={loading && !hasLiveKPIs}
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>}
        />
        <KpiTile
          label="FY TSR (Avg)"
          value={latestTSR ? `${(latestTSR * 100).toFixed(1)}%` : "14.8%"}
          delta={latestTSR ? "Live computed" : "+vs EPS dom."}
          dir="up"
          note="10yr annualised"
          loading={loading}
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"/></svg>}
        />
        <KpiTile
          label="Equity Risk Premium"
          value={latestERP ? `${latestERP.toFixed(1)}%` : "5.0%"}
          delta="Active param"
          dir="flat"
          note="CAPM MRP"
          loading={ctx.loading}
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6l3 1m0 0l-3 9a5 5 0 006 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5 5 0 006 0M18 7l3 9m-3-9l-6-2"/></svg>}
        />
        <KpiTile
          label={ctx.hasMetrics ? "Metrics Computed" : "Pipeline Status"}
          value={ctx.hasMetrics ? "Ready" : "Pending"}
          delta={ctx.hasMetrics ? "All 28+ metrics" : "Run ETL first"}
          dir={ctx.hasMetrics ? "up" : "flat"}
          note={ctx.stats ? `${ctx.stats.raw_metrics.count} raw records` : "No data loaded"}
          loading={ctx.loading}
          icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/></svg>}
        />
      </div>

      {/* ── Main charts row ──────────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: "1rem" }}>

        {/* EP Bow Wave */}
        <ChartCard
          title="Economic Profit (EP) — Bow Wave"
          subtitle={isLiveEP ? "Live computed Calc EP aggregated by fiscal year (avg, $m)" : "Illustrative — EP bow wave concept: baseline vs. new expectations"}
          action={
            <span style={{
              fontSize: "0.5625rem", fontWeight: 700, padding: "0.15rem 0.5rem",
              background: isLiveEP ? "hsl(152 60% 40% / 0.12)" : "hsl(38 60% 52% / 0.12)",
              color: isLiveEP ? "hsl(152 60% 32%)" : "hsl(38 60% 35%)",
              borderRadius: 999, border: isLiveEP ? "1px solid hsl(152 60% 40% / 0.3)" : "1px solid hsl(38 60% 52% / 0.3)",
              textTransform: "uppercase",
            }}>
              {isLiveEP ? "● LIVE" : "ILLUSTRATIVE"}
            </span>
          }
        >
          {loading && !isLiveEP ? <Skeleton h={200} /> : (
            <ResponsiveContainer width="100%" height={210}>
              {isLiveEP ? (
                <ComposedChart data={bowWaveData as any} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                  <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}m`} width={44} />
                  <Tooltip content={<ChartTooltip suffix="m" />} />
                  <Area type="monotone" dataKey="ep" name="EP (avg $m)" stroke={NAVY} fill="hsl(213 75% 22% / 0.12)" strokeWidth={2} dot={false} />
                  <ReferenceLine y={0} stroke="hsl(0 60% 50%)" strokeDasharray="4 3" strokeWidth={1.5} />
                </ComposedChart>
              ) : (
                <ComposedChart data={bowWaveData as any} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                  <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} interval={4} />
                  <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}`} width={36} />
                  <Tooltip content={<ChartTooltip suffix="$m" />} />
                  <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                  <Area type="monotone" dataKey="baseline" name="Baseline EP" stroke={GOLD} fill="hsl(38 60% 52% / 0.15)" strokeWidth={2} dot={false} />
                  <Area type="monotone" dataKey="newExp" name="New EP Expectations" stroke={NAVY} fill="hsl(213 75% 22% / 0.12)" strokeWidth={2.5} dot={false} />
                </ComposedChart>
              )}
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* TSR vs Ke */}
        <ChartCard
          title="TSR vs Cost of Equity (Ke)"
          subtitle={tsrKeChartData.length > 0 ? "Live: Index-median TSR against Ke over time (%)" : "Illustrative — Ke creates a wealth-creation hurdle rate"}
          action={
            <span style={{
              fontSize: "0.5625rem", fontWeight: 700, padding: "0.15rem 0.5rem",
              background: tsrKeChartData.length > 0 ? "hsl(152 60% 40% / 0.12)" : "hsl(38 60% 52% / 0.12)",
              color: tsrKeChartData.length > 0 ? "hsl(152 60% 32%)" : "hsl(38 60% 35%)",
              borderRadius: 999, border: tsrKeChartData.length > 0 ? "1px solid hsl(152 60% 40% / 0.3)" : "1px solid hsl(38 60% 52% / 0.3)",
              textTransform: "uppercase",
            }}>
              {tsrKeChartData.length > 0 ? "● LIVE" : "ILLUS."}
            </span>
          }
        >
          {loading ? <Skeleton h={200} /> : (() => {
            const fallbackData = [
              { year: "2005", ke: 9.2, tsr: 12.4 }, { year: "2007", ke: 9.5, tsr: 20.1 },
              { year: "2009", ke: 9.8, tsr: -18.2 },{ year: "2011", ke: 10.0, tsr: 5.3 },
              { year: "2013", ke: 9.6, tsr: 15.8 }, { year: "2015", ke: 9.2, tsr: 8.7 },
              { year: "2017", ke: 8.9, tsr: 11.5 }, { year: "2019", ke: 8.5, tsr: 6.2 },
              { year: "2021", ke: 8.8, tsr: 14.2 }, { year: "2023", ke: 9.1, tsr: 9.8 },
            ];
            const chartData = tsrKeChartData.length > 0 ? tsrKeChartData : fallbackData;
            return (
              <ResponsiveContainer width="100%" height={210}>
                <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                  <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                  <Tooltip content={<ChartTooltip suffix="%" />} />
                  <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                  <ReferenceLine y={0} stroke="hsl(0 60% 50%)" strokeDasharray="3 3" strokeWidth={1} />
                  <Area type="monotone" dataKey="tsr" name="TSR" stroke={NAVY} fill="hsl(213 75% 22% / 0.1)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="ke" name="Cost of Equity (Ke)" stroke={GOLD} strokeWidth={2.5} dot={false} strokeDasharray="5 3" />
                </ComposedChart>
              </ResponsiveContainer>
            );
          })()}
        </ChartCard>
      </div>

      {/* ── Secondary charts ─────────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>

        {/* ECF Bar */}
        <ChartCard
          title="Economic Cash Flow (ECF)"
          subtitle={ecfChartData.length > 0 ? "Live Calc ECF — annual median ($m)" : "Illustrative pattern"}
        >
          {loading ? <Skeleton h={160} /> : (() => {
            const fallback = [
              { year: "2015", ecf: 185 }, { year: "2016", ecf: 201 }, { year: "2017", ecf: 225 },
              { year: "2018", ecf: 242 }, { year: "2019", ecf: 215 }, { year: "2020", ecf: 178 },
              { year: "2021", ecf: 248 }, { year: "2022", ecf: 285 }, { year: "2023", ecf: 312 },
            ];
            const data = ecfChartData.length > 0 ? ecfChartData : fallback;
            return (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={data} margin={{ top: 2, right: 4, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(210 16% 93%)" />
                  <XAxis dataKey="year" tick={{ fontSize: 8 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 8 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}m`} width={40} />
                  <Tooltip content={<ChartTooltip suffix="$m" />} />
                  <Bar dataKey="ecf" name="ECF ($m)" fill={NAVY} radius={[3, 3, 0, 0]} maxBarSize={32} />
                </BarChart>
              </ResponsiveContainer>
            );
          })()}
        </ChartCard>

        {/* Principles coverage */}
        <ChartCard title="Principles Coverage" subtitle="Analysis completeness by principle">
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {principles.map(p => (
              <Link key={p.n} href={p.path}>
                <a style={{ textDecoration: "none" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
                    <div style={{
                      width: 22, height: 22, borderRadius: 6, flexShrink: 0,
                      background: p.color, display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: "0.5625rem", fontWeight: 800, color: "#fff",
                    }}>{p.n}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.15rem" }}>
                        <span style={{ fontSize: "0.6875rem", fontWeight: 500, color: "hsl(220 25% 25%)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.label}</span>
                        <span style={{ fontSize: "0.625rem", fontWeight: 700, color: p.color, flexShrink: 0, marginLeft: 8 }}>{p.pct}%</span>
                      </div>
                      <div style={{ height: 4, background: "hsl(210 16% 92%)", borderRadius: 999, overflow: "hidden" }}>
                        <div style={{ width: `${p.pct}%`, height: "100%", background: p.color, borderRadius: 999, transition: "width 0.5s ease" }} />
                      </div>
                    </div>
                  </div>
                </a>
              </Link>
            ))}
          </div>
        </ChartCard>

        {/* Pipeline status / quick actions */}
        <ChartCard title="Pipeline Status" subtitle="ETL workflow stages">
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {[
              { label: "Data Ingestion",   done: ctx.stats !== null,    detail: ctx.stats ? `${ctx.stats.companies.count} cos loaded` : "Awaiting Bloomberg file" },
              { label: "L1 Metrics",       done: ctx.hasMetrics,         detail: ctx.hasMetrics ? "11 metrics computed" : "Needs dataset" },
              { label: "Runtime Metrics",  done: ctx.hasMetrics,         detail: ctx.hasMetrics ? "Beta → Rf → Ke → TER" : "Awaiting L1" },
              { label: "Ratio Metrics",    done: ctx.hasMetrics,         detail: ctx.hasMetrics ? "17 ratio metrics" : "Awaiting runtime" },
              { label: "Dashboard Ready",  done: ctx.hasMetrics,         detail: ctx.hasMetrics ? "All charts live" : "Run full pipeline" },
            ].map((stage, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <div style={{
                  width: 18, height: 18, borderRadius: "50%", flexShrink: 0,
                  background: stage.done ? "hsl(152 60% 40%)" : ctx.loading ? "hsl(38 60% 52%)" : "hsl(210 16% 88%)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  boxShadow: stage.done ? "0 0 6px hsl(152 60% 40% / 0.5)" : "none",
                }}>
                  {stage.done ? (
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
                  ) : (
                    <span style={{ fontSize: "0.5rem", fontWeight: 800, color: "hsl(215 15% 55%)" }}>{i + 1}</span>
                  )}
                </div>
                <div>
                  <div style={{ fontSize: "0.6875rem", fontWeight: 600, color: "hsl(220 25% 20%)" }}>{stage.label}</div>
                  <div style={{ fontSize: "0.5625rem", color: SLATE }}>{stage.detail}</div>
                </div>
              </div>
            ))}
            <Link href="/pipeline">
              <a style={{
                display: "block", textAlign: "center", marginTop: "0.375rem",
                padding: "0.45rem", borderRadius: 7,
                background: ctx.hasMetrics ? "hsl(152 60% 40% / 0.08)" : "hsl(38 60% 52%)",
                color: ctx.hasMetrics ? "hsl(152 60% 32%)" : "#fff",
                fontSize: "0.75rem", fontWeight: 700,
                textDecoration: "none",
                border: ctx.hasMetrics ? "1px solid hsl(152 60% 40% / 0.3)" : "none",
              }}>
                {ctx.hasMetrics ? "View Pipeline" : "Run ETL Pipeline →"}
              </a>
            </Link>
          </div>
        </ChartCard>
      </div>

      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>
    </div>
  );
}
