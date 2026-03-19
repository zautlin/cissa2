import { useState, useEffect, useCallback } from "react";
import { Line, Bar, Doughnut } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement,
  LineElement, PointElement,
  ArcElement,
  Title, Tooltip, Legend, Filler,
} from "chart.js";
import { Link } from "wouter";
import { apiFetch, isBackendAlive } from "../lib/queryClient";
import {
  roeKeByIndex, terKeByIndex, mbRatioByIndex,
  roeKeDistribution, terKeDistribution,
  epVsEpsCohorts, wealthCreationDecomp,
} from "../data/chartData";

ChartJS.register(
  CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, ArcElement,
  Title, Tooltip, Legend, Filler
);

// ── Types ──────────────────────────────────────────────────────────────────
interface HealthData { status: string; message: string; database: string; }

// ── Stage definitions ─────────────────────────────────────────────────────
const STAGES = [
  {
    id: "ingestion",
    num: 1,
    label: "Data Ingestion",
    sublabel: "Phase 0",
    desc: "Bloomberg Excel → CSV → PostgreSQL with FY alignment & imputation",
    icon: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12",
    accent: "#0E2D5C",
    accentLight: "rgba(14,45,92,0.08)",
    accentBorder: "rgba(14,45,92,0.2)",
    substages: [
      { id: "ingest",   label: "Bloomberg Extract & Load", ep: "GET /api/v1/metrics/statistics",               records: 10000,  dur: 180  },
      { id: "fy-align", label: "FY Alignment & Imputation", ep: "GET /api/v1/metrics/statistics",             records: 10000,  dur: 45   },
    ],
  },
  {
    id: "l1",
    num: 2,
    label: "L1 Metrics",
    sublabel: "Phase 1–2",
    desc: "11 pre-computed metrics (4 parallel groups) + L2 Core EP metrics",
    icon: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 11h.01M12 11h.01M15 11h.01M4 19h16a2 2 0 002-2V7a2 2 0 00-2-2H4a2 2 0 00-2 2v10a2 2 0 002 2z",
    accent: "#C8922A",
    accentLight: "rgba(200,146,42,0.08)",
    accentBorder: "rgba(200,146,42,0.25)",
    substages: [
      { id: "l1-metrics", label: "L1 Pre-Computation (11 metrics, 4 parallel)", ep: "POST /api/v1/metrics/calculate-l1",          records: 130000, dur: 52   },
      { id: "l2-core",    label: "L2 Core EP Metrics",                           ep: "POST /api/v1/metrics/l2-core/calculate",     records: 10000,  dur: 6.8  },
    ],
  },
  {
    id: "runtime",
    num: 3,
    label: "Runtime Metrics",
    sublabel: "Phase 3–5",
    desc: "Parameter-dependent: Beta → Rf → Ke → FV-ECF → TER → TER Alpha",
    icon: "M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z",
    accent: "#1a8a5c",
    accentLight: "rgba(26,138,92,0.08)",
    accentBorder: "rgba(26,138,92,0.25)",
    substages: [
      { id: "beta",             label: "Beta Rounding",         ep: "POST /api/v1/metrics/beta/calculate-from-precomputed", records: 11000,  dur: 1.5  },
      { id: "rates",            label: "Risk-Free Rate (Rf)",   ep: "POST /api/v1/metrics/rates/calculate",                records: 10905,  dur: 7.9  },
      { id: "coe",              label: "Cost of Equity (Ke)",   ep: "POST /api/v1/metrics/cost-of-equity/calculate",       records: 10905,  dur: 1.6  },
      { id: "fv-ecf",           label: "Future Value ECF",      ep: "POST /api/v1/metrics/l2-fv-ecf/calculate",            records: 42120,  dur: 51.9 },
      { id: "ter",              label: "TER & TER-Ke",          ep: "POST /api/v1/metrics/l2-ter/calculate",               records: 89660,  dur: 14.4 },
      { id: "ter-alpha",        label: "TER Alpha",             ep: "POST /api/v1/metrics/l2-ter-alpha/calculate",         records: 131780, dur: 23.9 },
    ],
  },
  {
    id: "orchestration",
    num: 4,
    label: "Orchestration",
    sublabel: "Phase 6",
    desc: "Full pipeline orchestrators: L1 (~52s) + Runtime (~101s, ~296k records)",
    icon: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
    accent: "#1a6a8a",
    accentLight: "rgba(26,106,138,0.08)",
    accentBorder: "rgba(26,106,138,0.25)",
    substages: [
      { id: "orchestrate-l1",      label: "L1 Pre-Computation Orchestrator", ep: "POST /api/v1/metrics/calculate-l1",      records: 130000, dur: 52    },
      { id: "orchestrate-runtime", label: "Full Runtime Orchestrator",        ep: "POST /api/v1/metrics/runtime-metrics",  records: 296370, dur: 101.2 },
    ],
  },
  {
    id: "results",
    num: 5,
    label: "Results",
    sublabel: "Dashboard",
    desc: "Wealth Creation analysis, EP Bow Wave, Economic Profitability indices",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    accent: "#0E2D5C",
    accentLight: "rgba(14,45,92,0.06)",
    accentBorder: "rgba(14,45,92,0.18)",
    substages: [] as { id: string; label: string; ep: string; records: number; dur: number }[],
  },
] as const;

type StageId = (typeof STAGES)[number]["id"];

// ── Chart helpers ─────────────────────────────────────────────────────────

const lineOpts: any = {
  responsive: true, maintainAspectRatio: false,
  plugins: {
    legend: { position: "top", labels: { boxWidth: 18, font: { size: 10 }, padding: 8, usePointStyle: true, pointStyle: "line" } },
    tooltip: { mode: "index", intersect: false },
  },
  scales: {
    x: { ticks: { font: { size: 9 }, maxRotation: 45, autoSkip: true, maxTicksLimit: 10 }, grid: { color: "rgba(0,0,0,0.04)" } },
    y: { ticks: { font: { size: 9 }, callback: (v: any) => `${v}%` }, grid: { color: "rgba(0,0,0,0.04)" } },
  },
};
const mbOpts: any = {
  ...lineOpts,
  scales: { ...lineOpts.scales, y: { ...lineOpts.scales.y, ticks: { font: { size: 9 }, callback: (v: any) => `${v}×` } } },
};
const barOpts: any = {
  responsive: true, maintainAspectRatio: false,
  plugins: {
    legend: { position: "top", labels: { boxWidth: 14, font: { size: 10 }, padding: 8 } },
    tooltip: { mode: "index", intersect: false },
  },
  scales: {
    x: { ticks: { font: { size: 8 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 12 }, grid: { display: false } },
    y: { ticks: { font: { size: 9 } }, grid: { color: "rgba(0,0,0,0.04)" } },
  },
};

// Bow wave data
function bellCurve(years: number[], peakYear: number, peakValue: number, sigma: number): number[] {
  return years.map(y => +(peakValue * Math.exp(-((y - peakYear) ** 2) / (2 * sigma * sigma))).toFixed(2));
}
const yOff = Array.from({ length: 26 }, (_, i) => i - 10);
const yLabels = yOff.map(o => (2014 + o).toString());
const bowWaveData = {
  labels: yLabels,
  datasets: [
    { label: "Baseline EP Expectations", data: bellCurve(yOff, 3, 350, 6), borderColor: "hsl(38 70% 48%)", backgroundColor: "hsl(38 70% 48% / 0.15)", borderWidth: 2, pointRadius: 0, fill: true, tension: 0.5 },
    { label: "New EP Expectations", data: yOff.map((o, i) => o >= 0 ? bellCurve(yOff, 5, 720, 8)[i] : null) as (number | null)[], borderColor: "hsl(213 75% 40%)", backgroundColor: "hsl(213 75% 40% / 0.12)", borderWidth: 2, pointRadius: 0, fill: true, tension: 0.5 },
  ],
};
const bowWaveOpts: any = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: "top", labels: { boxWidth: 18, font: { size: 10 }, padding: 8, usePointStyle: true, pointStyle: "line" } }, tooltip: { mode: "index", intersect: false } },
  scales: {
    x: { ticks: { font: { size: 8 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { color: "rgba(0,0,0,0.04)" } },
    y: { title: { display: true, text: "Economic Profit ($m)", font: { size: 9 }, color: "#64748b" }, ticks: { font: { size: 8 } }, grid: { color: "rgba(0,0,0,0.04)" }, min: 0 },
  },
};

const ingestionRecordsData = {
  labels: ["Fundamentals", "Parameters", "L0 Staging", "L1 Precomputed", "L2 Core", "Runtime (total)"],
  datasets: [{ label: "Records", data: [10000, 150, 10000, 130000, 10000, 296370], backgroundColor: ["#0E2D5C","#1a4a8a","#2a5fa0","#C8922A","#1a8a5c","#1a6a8a"], borderRadius: 4 }],
};
const ingestionOpts: any = {
  responsive: true, maintainAspectRatio: false, indexAxis: "y" as const,
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.raw.toLocaleString()} records` } } },
  scales: {
    x: { ticks: { font: { size: 9 }, callback: (v: any) => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v }, grid: { color: "rgba(0,0,0,0.04)" } },
    y: { ticks: { font: { size: 10 } }, grid: { display: false } },
  },
};
const runtimeDurData = {
  labels: ["Beta", "Risk-Free Rf", "Cost Ke", "FV-ECF", "TER/TER-Ke", "TER Alpha"],
  datasets: [{ label: "Wall-clock (s)", data: [1.5, 7.9, 1.6, 51.9, 14.4, 23.9], backgroundColor: ["#1a8a5c","#1a8a5c","#1a6a8a","#8b5cf6","#8b5cf6","#dc2626"], borderRadius: 4 }],
};
const durOpts: any = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.raw}s` } } },
  scales: {
    x: { ticks: { font: { size: 9 } }, grid: { color: "rgba(0,0,0,0.04)" } },
    y: { ticks: { font: { size: 9 }, callback: (v: any) => `${v}s` }, grid: { color: "rgba(0,0,0,0.04)" } },
  },
};

const kpis = [
  { label: "Avg ROE-Ke",     value: "10.6%", sub: "LT Avg Econ. Profitability", pos: true  },
  { label: "TER-Ke (10yr)",  value: "6.8%",  sub: "Annualised Wealth Creation",  pos: true  },
  { label: "M:B Ratio",      value: "3.7×",  sub: "Market to Book (LT avg)",     pos: null  },
  { label: "EP Dom. TSR",    value: "14.8%", sub: "vs 5.7% EPS-dominant",        pos: true  },
  { label: "Cost of Equity", value: "10.0%", sub: "ASX 300 Long-run Ke",         pos: null  },
];

// ── Sub-components ────────────────────────────────────────────────────────

function Card({ title, subtitle, height = 210, children }: { title: string; subtitle?: string; height?: number; children: React.ReactNode }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: "1rem 1.125rem", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
      <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "#1e293b", marginBottom: subtitle ? "0.1rem" : "0.75rem" }}>{title}</div>
      {subtitle && <div style={{ fontSize: "0.6875rem", color: "#64748b", marginBottom: "0.75rem" }}>{subtitle}</div>}
      <div style={{ height }}>{children}</div>
    </div>
  );
}

function SubstageRow({ s }: { s: { id: string; label: string; ep: string; records: number; dur: number } }) {
  return (
    <div data-testid={`pipeline-stage-${s.id}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.625rem 0.875rem", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8 }}>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#1a8a5c", flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: "0.8125rem", color: "#1e293b" }}>{s.label}</div>
        <code style={{ fontSize: "0.6rem", color: "#64748b", fontFamily: "monospace" }}>{s.ep}</code>
      </div>
      <div style={{ display: "flex", gap: "1rem", flexShrink: 0, fontSize: "0.6875rem", color: "#64748b" }}>
        <span>{s.records.toLocaleString()} rec</span>
        <span>{s.dur}s</span>
      </div>
      <div style={{ background: "rgba(26,138,92,0.1)", color: "#1a8a5c", fontSize: "0.6rem", fontWeight: 700, padding: "0.1rem 0.5rem", borderRadius: 999, textTransform: "uppercase" as const, letterSpacing: "0.04em" }}>
        Success
      </div>
    </div>
  );
}

// ── Per-stage content panels ──────────────────────────────────────────────

function IngestionPanel({ substages }: { substages: readonly { id: string; label: string; ep: string; records: number; dur: number }[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <Card title="Database Record Counts" subtitle="Records loaded per pipeline layer" height={230}>
        <Bar data={ingestionRecordsData} options={ingestionOpts} />
      </Card>
      <div>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "#1e293b", marginBottom: "0.625rem" }}>Pipeline Substages</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "0.875rem" }}>
          {substages.map(s => <SubstageRow key={s.id} s={s} />)}
        </div>
        <div style={{ background: "rgba(14,45,92,0.04)", border: "1px solid rgba(14,45,92,0.14)", borderRadius: 8, padding: "0.75rem 1rem" }}>
          <div style={{ fontWeight: 700, fontSize: "0.75rem", color: "#0E2D5C", marginBottom: "0.375rem" }}>Input Source</div>
          <div style={{ fontSize: "0.6875rem", color: "#475569", lineHeight: 1.65 }}>
            Bloomberg Excel — <code style={{ fontFamily: "monospace", fontSize: "0.625rem" }}>Bloomberg Download data.xlsx</code><br />
            ~500 ASX tickers × ~20 years ≈ <strong>10,000</strong> fundamental records
          </div>
        </div>
      </div>
    </div>
  );
}

function L1Panel({ substages }: { substages: readonly { id: string; label: string; ep: string; records: number; dur: number }[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <Card title="Economic Profitability (ROE-Ke) by Index" subtitle="Historical annualised ROE-Ke — ASX 300 · 2001–2019" height={220}>
        <Line data={roeKeByIndex} options={lineOpts} />
      </Card>
      <Card title="ROE-Ke Distribution by Industry Sector" subtitle="Frequency distribution across ASX sectors" height={220}>
        <Bar data={roeKeDistribution} options={barOpts} />
      </Card>
      <div>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "#1e293b", marginBottom: "0.625rem" }}>Pipeline Substages</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {substages.map(s => <SubstageRow key={s.id} s={s} />)}
        </div>
      </div>
      <div style={{ background: "rgba(200,146,42,0.05)", border: "1px solid rgba(200,146,42,0.2)", borderRadius: 8, padding: "0.875rem 1rem" }}>
        <div style={{ fontWeight: 700, fontSize: "0.75rem", color: "#a0661a", marginBottom: "0.5rem" }}>Metrics Computed</div>
        {["Calc MC (Market Cap)", "Calc Assets, OA", "Op/Non-Op/Tax/XO Cost", "Calc ECF, EE (Equity Cash Flow)", "FY TSR, FY TSR PREL", "EP, PAT_EX, XO_COST_EX, FC (L2 Core)"].map(m => (
          <div key={m} style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.3rem" }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#C8922A", flexShrink: 0 }} />
            <span style={{ fontSize: "0.6875rem", color: "#475569" }}>{m}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RuntimePanel({ substages }: { substages: readonly { id: string; label: string; ep: string; records: number; dur: number }[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <Card title="Runtime Processing Duration" subtitle="Wall-clock time per computation step (seconds)" height={200}>
        <Bar data={runtimeDurData} options={durOpts} />
      </Card>
      <Card title="TER-Ke Distribution by Industry Sector" subtitle="Wealth creation frequency — ASX sectors" height={200}>
        <Bar data={terKeDistribution} options={barOpts} />
      </Card>
      <div style={{ gridColumn: "1 / -1" }}>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "#1e293b", marginBottom: "0.625rem" }}>Pipeline Substages ({substages.length} steps)</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem" }}>
          {substages.map(s => <SubstageRow key={s.id} s={s} />)}
        </div>
      </div>
    </div>
  );
}

function OrchestrationPanel({ substages }: { substages: readonly { id: string; label: string; ep: string; records: number; dur: number }[] }) {
  const summary = [
    { label: "L1 Pre-Compute",  records: "~130,000", time: "~52s",  color: "#C8922A" },
    { label: "Runtime (full)",  records: "~296,370", time: "~101s", color: "#1a8a5c" },
    { label: "Total DB Records",records: "~882,740", time: "—",     color: "#0E2D5C" },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <Card title="Annualised Wealth Creation (TER-Ke)" subtitle="1yr, 3yr, 5yr, 10yr rolling — ASX 300 · 2001–2019" height={220}>
        <Line data={terKeByIndex} options={{ ...lineOpts, scales: { ...lineOpts.scales, y: { ...lineOpts.scales.y, min: -45 } } }} />
      </Card>
      <Card title="Market to Book Ratio (M:B)" subtitle="Historical M:B ratio — ASX 300 · 2001–2019" height={220}>
        <Line data={mbRatioByIndex} options={mbOpts} />
      </Card>
      <div>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "#1e293b", marginBottom: "0.625rem" }}>Orchestrator Substages</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {substages.map(s => <SubstageRow key={s.id} s={s} />)}
        </div>
      </div>
      <div>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "#1e293b", marginBottom: "0.625rem" }}>Pipeline Summary</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {summary.map(r => (
            <div key={r.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.75rem 1rem", background: "#f8fafc", border: `1px solid ${r.color}33`, borderLeft: `4px solid ${r.color}`, borderRadius: 8 }}>
              <span style={{ fontWeight: 600, fontSize: "0.8125rem", color: "#1e293b" }}>{r.label}</span>
              <div style={{ display: "flex", gap: "1.25rem", fontSize: "0.75rem", color: "#64748b" }}>
                <span>{r.records}</span>
                <span style={{ fontFamily: "monospace" }}>{r.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ResultsPanel() {
  const principles = [
    { number: 1, label: "Economic Measures are Better",       pct: 85, color: "#0E2D5C", path: "/principles/1" },
    { number: 2, label: "Primary Focus on the Longer Term",   pct: 40, color: "#1a4a8a", path: "/principles/2" },
    { number: 3, label: "Creativity & Innovation",            pct: 30, color: "#2a5fa0", path: "/principles/1" },
    { number: 4, label: "Focus on All Stakeholders",          pct: 20, color: "#3a74b6", path: "/principles/1" },
    { number: 5, label: "Clear Purpose by Noble Intent",      pct: 15, color: "#4a89cc", path: "/principles/1" },
    { number: 6, label: "More is Not Always Better",          pct: 10, color: "#5a9ee2", path: "/principles/1" },
  ];
  const decompRows = [
    { label: "TSR-Ke (Observed Wealth)", value: "8.2%",  color: "#0E2D5C" },
    { label: "Intrinsic Wealth",          value: "5.4%", color: "#C8922A" },
    { label: "Sustainable Intrinsic",     value: "3.8%", color: "#1a8a5c" },
    { label: "Wealth Appropriation",      value: "2.8%", color: "#dc2626" },
  ];
  return (
    <div>
      {/* Bow Wave hero */}
      <div style={{ background: "linear-gradient(135deg, rgba(14,45,92,0.04) 0%, rgba(200,146,42,0.05) 100%)", border: "1px solid #e2e8f0", borderTop: "3px solid #0E2D5C", borderRadius: 12, padding: "1.25rem 1.5rem", marginBottom: "1rem", display: "grid", gridTemplateColumns: "1fr 380px", gap: "1.5rem", alignItems: "center", boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ background: "#C8922A", color: "#fff", fontSize: "0.625rem", fontWeight: 700, padding: "0.2rem 0.625rem", borderRadius: 999, textTransform: "uppercase" as const, letterSpacing: "0.05em" }}>Signature Concept</span>
            <span style={{ fontSize: "0.75rem", color: "#64748b" }}>Principle 2</span>
          </div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 800, color: "#0E2D5C", margin: "0 0 0.5rem 0" }}>The EP Bow Wave</h2>
          <p style={{ fontSize: "0.8125rem", color: "#475569", lineHeight: 1.7, margin: "0 0 0.875rem 0" }}>
            A company's market capitalisation equals its book equity plus the present value of its entire expected Economic Profit stream — the EP Bow Wave. The pair of waves reveals wealth created or destroyed during any measurement period.
          </p>
          <div style={{ display: "flex", gap: "0.625rem" }}>
            <Link href="/principles/2" style={{ display: "inline-flex", alignItems: "center", gap: "0.375rem", padding: "0.5rem 1rem", background: "#0E2D5C", color: "white", borderRadius: 6, fontSize: "0.75rem", fontWeight: 700, textDecoration: "none" }}>
              Explore Bow Wave <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="m9 18 6-6-6-6"/></svg>
            </Link>
            <Link href="/outputs" style={{ display: "inline-flex", alignItems: "center", gap: "0.375rem", padding: "0.5rem 1rem", background: "transparent", border: "1px solid #cbd5e1", color: "#1e293b", borderRadius: 6, fontSize: "0.75rem", fontWeight: 600, textDecoration: "none" }}>
              View Full Outputs
            </Link>
          </div>
        </div>
        <div>
          <div style={{ height: 190 }}><Line data={bowWaveData} options={bowWaveOpts} /></div>
          <div style={{ textAlign: "center", marginTop: "0.5rem" }}>
            <span style={{ fontSize: "0.6875rem", fontWeight: 700, color: "#1a8a5c", background: "#f0fdf4", padding: "0.1875rem 0.625rem", borderRadius: 999, border: "1px solid #bbf7d0" }}>▲ $3.1b enhancement · Cochlear (COH)</span>
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.75rem", marginBottom: "1rem" }}>
        {kpis.map(k => (
          <div key={k.label} style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: "0.875rem 1rem", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
            <div style={{ fontSize: "0.625rem", fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.05em", color: "#64748b", marginBottom: "0.25rem" }}>{k.label}</div>
            <div style={{ fontSize: "1.375rem", fontWeight: 800, color: "#0E2D5C", lineHeight: 1.1 }}>{k.value}</div>
            <div style={{ fontSize: "0.625rem", color: k.pos ? "#1a8a5c" : "#64748b", marginTop: "0.2rem", fontWeight: 500 }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
        <Card title="Economic Profitability (ROE-Ke) by Index" subtitle="Historical annualised ROE-Ke — ASX 300 · 2001–2019" height={210}>
          <Line data={roeKeByIndex} options={lineOpts} />
        </Card>
        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: "1rem 1.125rem", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
          <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "#1e293b", marginBottom: "0.125rem" }}>Six CISSA Principles</div>
          <div style={{ fontSize: "0.6875rem", color: "#64748b", marginBottom: "0.75rem" }}>Coverage progress</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
            {principles.map(p => (
              <Link href={p.path} key={p.number} style={{ textDecoration: "none" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                  <div style={{ width: 20, height: 20, borderRadius: "50%", background: p.color, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.5625rem", fontWeight: 700, flexShrink: 0 }}>{p.number}</div>
                  <span style={{ fontSize: "0.6875rem", color: "#1e293b", fontWeight: 500, flex: 1 }}>{p.label}</span>
                  <span style={{ fontSize: "0.625rem", color: "#64748b" }}>{p.pct}%</span>
                </div>
                <div style={{ height: 4, background: "#f1f5f9", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${p.pct}%`, background: p.color, borderRadius: 2 }} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
        <Card title="TER-Ke (Wealth Creation)" subtitle="ASX 300 · rolling 1–10yr · 2001–2019" height={190}>
          <Line data={terKeByIndex} options={{ ...lineOpts, scales: { ...lineOpts.scales, y: { ...lineOpts.scales.y, min: -45 } } }} />
        </Card>
        <Card title="Market to Book Ratio (M:B)" subtitle="Historical M:B — ASX 300 · 2001–2019" height={190}>
          <Line data={mbRatioByIndex} options={mbOpts} />
        </Card>
        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: "1rem 1.125rem", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
          <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "#1e293b", marginBottom: "0.125rem" }}>Wealth Creation Decomposition</div>
          <div style={{ fontSize: "0.6875rem", color: "#64748b", marginBottom: "0.75rem" }}>ASX 300 · 10yr annualised · 2001–2024</div>
          <div style={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: "0.75rem", alignItems: "center" }}>
            <div style={{ height: 150 }}>
              <Doughnut data={{ labels: wealthCreationDecomp.labels, datasets: [{ data: wealthCreationDecomp.datasets[0].data, backgroundColor: wealthCreationDecomp.datasets[0].backgroundColor as string[], borderWidth: 2, borderColor: "white" }] }}
                options={{ responsive: true, maintainAspectRatio: false, cutout: "65%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.raw}%` } } } }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
              {decompRows.map(r => (
                <div key={r.label} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: r.color, flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: "0.5625rem", color: "#64748b", lineHeight: 1.2 }}>{r.label}</div>
                    <div style={{ fontSize: "0.8125rem", fontWeight: 700, color: r.color }}>{r.value}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <Card title="EP-Dominant vs EPS-Dominant Cohort Performance" subtitle="10yr annualised TSR — EP dominant companies significantly outperform EPS-focused peers" height={210}>
        <Bar data={epVsEpsCohorts} options={barOpts} />
      </Card>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

export default function PipelinePage() {
  const [active, setActive] = useState<StageId>("ingestion");
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);

  const checkHealth = useCallback(async () => {
    setLoading(true);
    const alive = await isBackendAlive();
    setBackendOnline(alive);
    if (alive) {
      try { setHealth(await apiFetch<HealthData>("/api/v1/metrics/health")); }
      catch { setHealth(null); }
    }
    setLoading(false);
  }, []);
  useEffect(() => { checkHealth(); }, [checkHealth]);

  const activeIdx = STAGES.findIndex(s => s.id === active);
  const activeStage = STAGES[activeIdx];

  return (
    <div style={{ padding: "1.5rem 1.75rem", maxWidth: 1400, fontFamily: "inherit" }}>

      {/* ── Page header ── */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1.75rem" }}>
        <div>
          <div style={{ fontSize: "0.6875rem", fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.07em", color: "#94a3b8", marginBottom: "0.3rem" }}>
            RoZetta Technology — ETL &amp; Metrics Pipeline
          </div>
          <h1 style={{ fontSize: "1.375rem", fontWeight: 800, color: "#0E2D5C", margin: 0, lineHeight: 1.2 }}>
            Data Processing Pipeline
          </h1>
          <p style={{ fontSize: "0.8125rem", color: "#64748b", marginTop: "0.3rem", marginBottom: 0 }}>
            End-to-end: Bloomberg ingestion → L1/L2 metrics → Beta → Cost of Equity → Wealth Creation indices
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.625rem", alignItems: "center", flexShrink: 0 }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: "0.4rem",
            padding: "0.4rem 0.875rem", borderRadius: 999,
            border: `1px solid ${backendOnline ? "#bbf7d0" : "#e2e8f0"}`,
            background: backendOnline ? "#f0fdf4" : "#f8fafc",
            fontSize: "0.75rem", fontWeight: 600,
            color: backendOnline ? "#166534" : "#64748b",
          }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: backendOnline ? "#22c55e" : "#94a3b8", boxShadow: backendOnline ? "0 0 6px #22c55e" : undefined }} />
            {backendOnline === null ? "Connecting…" : backendOnline ? "API Connected" : "API Offline — Mock Data"}
          </div>
          <button
            data-testid="button-refresh-pipeline"
            onClick={checkHealth} disabled={loading}
            style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.4rem 0.875rem", border: "1px solid #e2e8f0", borderRadius: 6, background: "#fff", color: "#0E2D5C", cursor: loading ? "wait" : "pointer", fontSize: "0.75rem", fontWeight: 600, opacity: loading ? 0.6 : 1, boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: loading ? "spin 1s linear infinite" : undefined }}>
              <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* ── HORIZONTAL STAGE TRACK ── */}
      <div style={{ marginBottom: "1.75rem" }}>
        {/* Track label */}
        <div style={{ fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.07em", color: "#94a3b8", marginBottom: "0.75rem" }}>
          Pipeline Stages — click a stage to explore
        </div>

        {/* Stage cards row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 0, position: "relative" }}>

          {/* Background connector line */}
          <div style={{ position: "absolute", top: 44, left: "10%", right: "10%", height: 3, background: "#e2e8f0", zIndex: 0, borderRadius: 2 }} />
          {/* Progress fill */}
          <div style={{ position: "absolute", top: 44, left: "10%", width: `${(activeIdx / (STAGES.length - 1)) * 80}%`, height: 3, background: "#0E2D5C", zIndex: 1, borderRadius: 2, transition: "width 400ms ease" }} />

          {STAGES.map((stage, idx) => {
            const isActive = stage.id === active;
            const isPast   = idx < activeIdx;
            const isFuture = idx > activeIdx;

            return (
              <button
                key={stage.id}
                data-testid={`stepper-${stage.id}`}
                onClick={() => setActive(stage.id)}
                style={{
                  display: "flex", flexDirection: "column", alignItems: "center",
                  gap: "0.625rem", padding: "0 0.5rem 1rem 0.5rem",
                  background: "transparent", border: "none", cursor: "pointer",
                  position: "relative", zIndex: 2,
                  outline: "none",
                }}
              >
                {/* Circle node */}
                <div style={{
                  width: 52, height: 52, borderRadius: "50%",
                  background: isActive ? stage.accent : isPast ? "#1a8a5c" : "#fff",
                  border: `3px solid ${isActive ? stage.accent : isPast ? "#1a8a5c" : "#cbd5e1"}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  boxShadow: isActive
                    ? `0 0 0 5px ${stage.accentLight}, 0 4px 16px rgba(14,45,92,0.25)`
                    : isPast ? "0 2px 8px rgba(26,138,92,0.2)" : "0 1px 4px rgba(0,0,0,0.07)",
                  transition: "all 220ms ease",
                  flexShrink: 0,
                }}>
                  {isPast ? (
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
                      <path d="m20 6-11 11-5-5" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={isActive ? "#fff" : isFuture ? "#94a3b8" : "#fff"} strokeWidth="2">
                      <path d={stage.icon} />
                    </svg>
                  )}
                </div>

                {/* Stage number badge */}
                <div style={{
                  fontSize: "0.5625rem", fontWeight: 800,
                  textTransform: "uppercase" as const, letterSpacing: "0.06em",
                  color: isActive ? stage.accent : isPast ? "#1a8a5c" : "#94a3b8",
                  background: isActive ? stage.accentLight : isPast ? "rgba(26,138,92,0.08)" : "#f8fafc",
                  border: `1px solid ${isActive ? stage.accentBorder : isPast ? "rgba(26,138,92,0.25)" : "#e2e8f0"}`,
                  padding: "0.15rem 0.55rem", borderRadius: 999,
                }}>
                  {stage.sublabel}
                </div>

                {/* Stage name — BIG and bold */}
                <div style={{
                  fontSize: "0.875rem",
                  fontWeight: isActive ? 800 : 600,
                  color: isActive ? stage.accent : isFuture ? "#94a3b8" : "#475569",
                  textAlign: "center", lineHeight: 1.25,
                  transition: "color 200ms",
                }}>
                  {stage.label}
                </div>

                {/* Substage count pill */}
                {(stage.substages as unknown[]).length > 0 && (
                  <div style={{
                    fontSize: "0.625rem", color: isActive ? stage.accent : "#94a3b8",
                    background: isActive ? stage.accentLight : "#f8fafc",
                    border: `1px solid ${isActive ? stage.accentBorder : "#e2e8f0"}`,
                    padding: "0.1rem 0.5rem", borderRadius: 999,
                  }}>
                    {(stage.substages as unknown[]).length} substages
                  </div>
                )}

                {/* Active indicator dot */}
                {isActive && (
                  <div style={{ position: "absolute", bottom: 0, left: "50%", transform: "translateX(-50%)", width: 6, height: 6, borderRadius: "50%", background: stage.accent }} />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Active stage detail panel ── */}
      <div style={{
        background: "#fff",
        border: `1px solid ${activeStage.accentBorder}`,
        borderTop: `4px solid ${activeStage.accent}`,
        borderRadius: 12,
        padding: "1.5rem",
        boxShadow: `0 4px 24px rgba(14,45,92,0.07)`,
        marginBottom: "1.5rem",
      }}>
        {/* Panel header */}
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.25rem", paddingBottom: "1rem", borderBottom: "1px solid #f1f5f9" }}>
          <div style={{ width: 44, height: 44, borderRadius: "50%", background: activeStage.accentLight, border: `2px solid ${activeStage.accentBorder}`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={activeStage.accent} strokeWidth="2">
              <path d={activeStage.icon} />
            </svg>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", marginBottom: "0.1rem" }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 800, color: "#1e293b", margin: 0 }}>{activeStage.label}</h2>
              <span style={{ fontSize: "0.625rem", fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.05em", background: activeStage.accentLight, color: activeStage.accent, border: `1px solid ${activeStage.accentBorder}`, padding: "0.15rem 0.6rem", borderRadius: 999 }}>
                {activeStage.sublabel}
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#166534", fontSize: "0.625rem", fontWeight: 700, padding: "0.15rem 0.6rem", borderRadius: 999 }}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#22c55e" }} /> COMPLETE
              </div>
            </div>
            <p style={{ fontSize: "0.8125rem", color: "#64748b", margin: 0 }}>{activeStage.desc}</p>
          </div>

          {/* Step navigation */}
          <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
            <button onClick={() => activeIdx > 0 && setActive(STAGES[activeIdx - 1].id)} disabled={activeIdx === 0}
              style={{ display: "flex", alignItems: "center", gap: "0.25rem", padding: "0.4rem 0.75rem", border: "1px solid #e2e8f0", borderRadius: 6, background: "#fff", color: "#475569", cursor: activeIdx === 0 ? "not-allowed" : "pointer", opacity: activeIdx === 0 ? 0.35 : 1, fontSize: "0.75rem", fontWeight: 600 }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="m15 18-6-6 6-6"/></svg> Prev
            </button>
            <div style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
              {STAGES.map((s, i) => (
                <div key={s.id} onClick={() => setActive(s.id)} style={{ width: i === activeIdx ? 20 : 6, height: 6, borderRadius: 3, background: i === activeIdx ? activeStage.accent : i < activeIdx ? "#1a8a5c" : "#e2e8f0", cursor: "pointer", transition: "all 200ms" }} />
              ))}
            </div>
            <button onClick={() => activeIdx < STAGES.length - 1 && setActive(STAGES[activeIdx + 1].id)} disabled={activeIdx === STAGES.length - 1}
              style={{ display: "flex", alignItems: "center", gap: "0.25rem", padding: "0.4rem 0.75rem", border: "1px solid #e2e8f0", borderRadius: 6, background: "#fff", color: "#475569", cursor: activeIdx === STAGES.length - 1 ? "not-allowed" : "pointer", opacity: activeIdx === STAGES.length - 1 ? 0.35 : 1, fontSize: "0.75rem", fontWeight: 600 }}>
              Next <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="m9 18 6-6-6-6"/></svg>
            </button>
          </div>
        </div>

        {/* Panel content */}
        {active === "ingestion"     && <IngestionPanel     substages={STAGES[0].substages} />}
        {active === "l1"            && <L1Panel            substages={STAGES[1].substages} />}
        {active === "runtime"       && <RuntimePanel       substages={STAGES[2].substages} />}
        {active === "orchestration" && <OrchestrationPanel substages={STAGES[3].substages} />}
        {active === "results"       && <ResultsPanel />}
      </div>

      {/* ── Footer trigger ── */}
      <div style={{ padding: "1.125rem 1.5rem", background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: "0.875rem", color: "#1e293b", marginBottom: "0.25rem" }}>Run Full Pipeline</div>
          <div style={{ fontSize: "0.6875rem", color: "#64748b" }}>
            Step 1 — <code style={{ fontFamily: "monospace", background: "#f8fafc", padding: "0.1rem 0.3rem", borderRadius: 3 }}>POST /api/v1/metrics/calculate-l1</code> (~52s)
            &nbsp;·&nbsp;
            Step 2 — <code style={{ fontFamily: "monospace", background: "#f8fafc", padding: "0.1rem 0.3rem", borderRadius: 3 }}>POST /api/v1/metrics/runtime-metrics?dataset_id=&amp;param_set_id=</code> (~101s, ~296k records)
          </div>
        </div>
        <button
          data-testid="button-trigger-orchestration"
          disabled={!backendOnline}
          style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.625rem 1.5rem", borderRadius: 7, border: "none", background: backendOnline ? "#0E2D5C" : "#e2e8f0", color: backendOnline ? "white" : "#94a3b8", fontSize: "0.8125rem", fontWeight: 700, cursor: backendOnline ? "pointer" : "not-allowed", whiteSpace: "nowrap" as const, flexShrink: 0, boxShadow: backendOnline ? "0 4px 12px rgba(14,45,92,0.3)" : undefined }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          {backendOnline ? "Run Orchestration" : "Backend Offline"}
        </button>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
