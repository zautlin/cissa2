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
  LineElement, PointElement,
  ArcElement,
  Title, Tooltip, Legend, Filler
);

// ── Types ──────────────────────────────────────────────────────────────────

interface HealthData { status: string; message: string; database: string; }
type StageStatus = "idle" | "running" | "success" | "failed" | "warning";

// ── Horizontal pipeline: 5 conceptual stages ──────────────────────────────

const STAGES = [
  {
    id: "ingestion",
    label: "Data Ingestion",
    icon: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12",
    color: "hsl(213 75% 22%)",
    badge: "Phase 0",
    substages: [
      { id: "ingest", label: "Bloomberg Extract", method: "GET", endpoint: "/api/v1/metrics/statistics", records: 10000, duration: 180 },
      { id: "fy-align", label: "FY Alignment", method: "GET", endpoint: "/api/v1/metrics/statistics", records: 10000, duration: 45 },
    ],
  },
  {
    id: "l1",
    label: "L1 Metrics",
    icon: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 11h.01M12 11h.01M15 11h.01M4 19h16a2 2 0 002-2V7a2 2 0 00-2-2H4a2 2 0 00-2 2v10a2 2 0 002 2z",
    color: "hsl(38 60% 52%)",
    badge: "Phase 1–2",
    substages: [
      { id: "l1-metrics", label: "L1 Pre-Compute", method: "POST", endpoint: "/api/v1/metrics/calculate-l1", records: 130000, duration: 52 },
      { id: "l2-core", label: "L2 Core EP", method: "POST", endpoint: "/api/v1/metrics/l2-core/calculate", records: 10000, duration: 6.8 },
    ],
  },
  {
    id: "runtime",
    label: "Runtime Metrics",
    icon: "M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z",
    color: "hsl(152 60% 40%)",
    badge: "Phase 3–5",
    substages: [
      { id: "beta", label: "Beta Rounding", method: "POST", endpoint: "/api/v1/metrics/beta/calculate-from-precomputed", records: 11000, duration: 1.5 },
      { id: "rates", label: "Risk-Free Rate", method: "POST", endpoint: "/api/v1/metrics/rates/calculate", records: 10905, duration: 7.9 },
      { id: "coe", label: "Cost of Equity", method: "POST", endpoint: "/api/v1/metrics/cost-of-equity/calculate", records: 10905, duration: 1.6 },
      { id: "fv-ecf", label: "FV ECF", method: "POST", endpoint: "/api/v1/metrics/l2-fv-ecf/calculate", records: 42120, duration: 51.9 },
      { id: "ter", label: "TER & TER-Ke", method: "POST", endpoint: "/api/v1/metrics/l2-ter/calculate", records: 89660, duration: 14.4 },
      { id: "ter-alpha", label: "TER Alpha", method: "POST", endpoint: "/api/v1/metrics/l2-ter-alpha/calculate", records: 131780, duration: 23.9 },
    ],
  },
  {
    id: "orchestration",
    label: "Orchestration",
    icon: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
    color: "hsl(188 78% 35%)",
    badge: "Phase 6",
    substages: [
      { id: "orchestrate-l1", label: "L1 Orchestrator", method: "POST", endpoint: "/api/v1/metrics/calculate-l1", records: 130000, duration: 52 },
      { id: "orchestrate-runtime", label: "Runtime Orchestrator", method: "POST", endpoint: "/api/v1/metrics/runtime-metrics", records: 296370, duration: 101.2 },
    ],
  },
  {
    id: "results",
    label: "Results",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    color: "hsl(213 75% 22%)",
    badge: "Dashboard",
    substages: [],
  },
] as const;

type StageId = (typeof STAGES)[number]["id"];

// ── Shared chart options ────────────────────────────────────────────────────

const lineOpts: any = {
  responsive: true, maintainAspectRatio: false,
  plugins: {
    legend: { position: "top", labels: { boxWidth: 20, font: { size: 10 }, padding: 8, usePointStyle: true, pointStyle: "line" } },
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

// ── Bow wave data (inline for Results stage) ────────────────────────────────

function bellCurve(years: number[], peakYear: number, peakValue: number, sigma: number): number[] {
  return years.map(y => +(peakValue * Math.exp(-((y - peakYear) ** 2) / (2 * sigma * sigma))).toFixed(2));
}
const yearOffsets = Array.from({ length: 26 }, (_, i) => i - 10);
const yearLabels = yearOffsets.map(o => (2014 + o).toString());
const bowWaveData = {
  labels: yearLabels,
  datasets: [
    { label: "Baseline EP Expectations", data: bellCurve(yearOffsets, 3, 350, 6), borderColor: "hsl(38 70% 48%)", backgroundColor: "hsl(38 70% 48% / 0.15)", borderWidth: 2, pointRadius: 0, fill: true, tension: 0.5 },
    { label: "New EP Expectations", data: yearOffsets.map((o, i) => o >= 0 ? bellCurve(yearOffsets, 5, 720, 8)[i] : null) as (number | null)[], borderColor: "hsl(213 75% 40%)", backgroundColor: "hsl(213 75% 40% / 0.12)", borderWidth: 2, pointRadius: 0, fill: true, tension: 0.5 },
  ],
};
const bowWaveOpts: any = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: "top", labels: { boxWidth: 20, font: { size: 10 }, padding: 8, usePointStyle: true, pointStyle: "line" } }, tooltip: { mode: "index", intersect: false } },
  scales: {
    x: { ticks: { font: { size: 8 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { color: "rgba(0,0,0,0.04)" } },
    y: { title: { display: true, text: "Economic Profit ($m)", font: { size: 9 }, color: "hsl(220 15% 50%)" }, ticks: { font: { size: 8 } }, grid: { color: "rgba(0,0,0,0.04)" }, min: 0 },
  },
};

const kpis = [
  { label: "Avg ROE-Ke (ASX 300)", value: "10.6%", delta: "+0.4%", dir: "positive", note: "LT Avg Economic Profitability" },
  { label: "Avg TER-Ke (10yr Ann.)", value: "6.8%", delta: "+1.2%", dir: "positive", note: "Annualised Wealth Creation" },
  { label: "Avg M:B Ratio", value: "3.7×", delta: "−0.2×", dir: "neutral", note: "Market to Book" },
  { label: "EP Dominant TSR", value: "14.8%", delta: "vs 5.7% EPS Dom.", dir: "positive", note: "10yr Annualised TSR" },
  { label: "Cost of Equity (Ke)", value: "10.0%", delta: "Benchmark rate", dir: "neutral", note: "ASX 300 Long-run estimate" },
];

// ── Record trend (ingestion stage chart) ─────────────────────────────────

const ingestionRecordsData = {
  labels: ["Fundamentals", "Parameters", "L0 Staging", "L1 Precomputed", "L2 Core", "Runtime (total)"],
  datasets: [{
    label: "Records in DB",
    data: [10000, 150, 10000, 130000, 10000, 296370],
    backgroundColor: [
      "hsl(213 75% 22% / 0.8)",
      "hsl(213 75% 35% / 0.8)",
      "hsl(213 75% 45% / 0.8)",
      "hsl(38 60% 52% / 0.8)",
      "hsl(152 60% 40% / 0.8)",
      "hsl(188 78% 35% / 0.8)",
    ],
    borderRadius: 4,
  }],
};
const ingestionOpts: any = {
  responsive: true, maintainAspectRatio: false,
  indexAxis: "y" as const,
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.raw.toLocaleString()} records` } } },
  scales: {
    x: { ticks: { font: { size: 9 }, callback: (v: any) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v }, grid: { color: "rgba(0,0,0,0.04)" } },
    y: { ticks: { font: { size: 10 } }, grid: { display: false } },
  },
};

// ── Processing timeline (runtime stage) ───────────────────────────────────

const runtimeDurationData = {
  labels: ["Beta Round.", "Risk-Free Rf", "Cost of Ke", "FV-ECF (4 hzns)", "TER / TER-Ke", "TER Alpha"],
  datasets: [{
    label: "Wall-clock time (s)",
    data: [1.5, 7.9, 1.6, 51.9, 14.4, 23.9],
    backgroundColor: [
      "hsl(152 60% 40% / 0.8)",
      "hsl(152 60% 40% / 0.8)",
      "hsl(188 78% 35% / 0.8)",
      "hsl(270 60% 50% / 0.8)",
      "hsl(270 60% 50% / 0.8)",
      "hsl(0 72% 51% / 0.8)",
    ],
    borderRadius: 4,
  }],
};
const runtimeOpts: any = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.raw}s` } } },
  scales: {
    x: { ticks: { font: { size: 9 } }, grid: { color: "rgba(0,0,0,0.04)" } },
    y: { ticks: { font: { size: 9 }, callback: (v: any) => `${v}s` }, grid: { color: "rgba(0,0,0,0.04)" } },
  },
};

// ── Sub-components ──────────────────────────────────────────────────────────

function ChartCard({ title, subtitle, height = 200, children }: { title: string; subtitle?: string; height?: number; children: React.ReactNode }) {
  return (
    <div style={{
      background: "hsl(var(--card))",
      border: "1px solid hsl(var(--border))",
      borderRadius: "0.625rem",
      padding: "1rem 1.125rem",
    }}>
      <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.125rem" }}>{title}</div>
      {subtitle && <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginBottom: "0.75rem" }}>{subtitle}</div>}
      <div style={{ height }}>{children}</div>
    </div>
  );
}

function SubstagePill({ id, label, method, endpoint, records, duration }: {
  id: string; label: string; method: string; endpoint: string; records: number; duration: number;
}) {
  return (
    <div style={{
      background: "hsl(var(--muted) / 0.5)",
      border: "1px solid hsl(var(--border))",
      borderRadius: "0.5rem",
      padding: "0.75rem 1rem",
      display: "flex",
      flexDirection: "column",
      gap: "0.375rem",
    }} data-testid={`pipeline-stage-${id}`}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "hsl(152 60% 40%)", flexShrink: 0 }} />
        <span style={{ fontWeight: 600, fontSize: "0.8rem", color: "hsl(var(--foreground))" }}>{label}</span>
        <span style={{
          marginLeft: "auto",
          fontSize: "0.625rem", fontWeight: 600,
          background: "hsl(152 60% 40% / 0.1)", color: "hsl(152 60% 35%)",
          padding: "0.1rem 0.5rem", borderRadius: "999px",
        }}>SUCCESS</span>
      </div>
      <div style={{ display: "flex", gap: "1rem", fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>
        <span>{records.toLocaleString()} records</span>
        <span>{duration}s</span>
        <code style={{ fontFamily: "monospace", fontSize: "0.6rem", background: "hsl(var(--muted))", padding: "0.1rem 0.375rem", borderRadius: "0.25rem" }}>
          {method} {endpoint}
        </code>
      </div>
    </div>
  );
}

// ── Stage Detail Panels ─────────────────────────────────────────────────────

function IngestionPanel() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <ChartCard title="Database Record Counts" subtitle="Records loaded per pipeline layer" height={220}>
        <Bar data={ingestionRecordsData} options={ingestionOpts} />
      </ChartCard>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.25rem" }}>
          Substages
        </div>
        {[
          { id: "ingest", label: "Bloomberg Extract & Load", method: "GET", endpoint: "/api/v1/metrics/statistics", records: 10000, duration: 180 },
          { id: "fy-align", label: "FY Alignment & Imputation", method: "GET", endpoint: "/api/v1/metrics/statistics", records: 10000, duration: 45 },
        ].map(s => <SubstagePill key={s.id} {...s} />)}

        <div className="chart-card" style={{ marginTop: "0.25rem", background: "hsl(213 75% 22% / 0.04)", border: "1px solid hsl(213 75% 22% / 0.15)" }}>
          <div style={{ fontSize: "0.6875rem", color: "hsl(213 75% 25%)", lineHeight: 1.6 }}>
            <strong style={{ display: "block", marginBottom: "0.25rem" }}>Input</strong>
            Bloomberg Excel file — <code style={{ fontFamily: "monospace", fontSize: "0.625rem" }}>raw-data/Bloomberg Download data.xlsx</code><br />
            ~500 ASX tickers × ~20 years ≈ 10,000 fundamental records
          </div>
        </div>
      </div>
    </div>
  );
}

function L1Panel() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <ChartCard title="Economic Profitability (ROE-Ke) by Index" subtitle="Time series of historical annualised ROE-Ke — ASX 300 · 2001–2019" height={220}>
        <Line data={roeKeByIndex} options={lineOpts} />
      </ChartCard>

      <ChartCard title="ROE-Ke Distribution by Industry Sector" subtitle="Frequency distribution across ASX sectors" height={220}>
        <Bar data={roeKeDistribution} options={barOpts} />
      </ChartCard>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.25rem" }}>Substages</div>
        {[
          { id: "l1-metrics", label: "L1 Metric Pre-Computation", method: "POST", endpoint: "/api/v1/metrics/calculate-l1", records: 130000, duration: 52 },
          { id: "l2-core", label: "L2 Core EP Metrics", method: "POST", endpoint: "/api/v1/metrics/l2-core/calculate", records: 10000, duration: 6.8 },
        ].map(s => <SubstagePill key={s.id} {...s} />)}
      </div>

      <div className="chart-card" style={{ background: "hsl(38 60% 52% / 0.04)", border: "1px solid hsl(38 60% 52% / 0.2)" }}>
        <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "hsl(38 60% 35%)", marginBottom: "0.5rem" }}>L1 Metrics Computed (11 metrics, 4 parallel groups)</div>
        {[
          "Calc MC (Market Capitalisation)",
          "Calc Assets, OA",
          "Op/Non-Op/Tax/XO Cost",
          "Calc ECF, EE (Equity Cash Flow)",
          "FY TSR, FY TSR PREL",
          "EP, PAT_EX, XO_COST_EX, FC (L2 Core)",
        ].map(m => (
          <div key={m} style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
            <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "hsl(152 60% 40%)", flexShrink: 0 }} />
            <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>{m}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RuntimePanel() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <ChartCard title="Runtime Processing Duration by Stage" subtitle="Wall-clock time per computation step" height={200}>
        <Bar data={runtimeDurationData} options={runtimeOpts} />
      </ChartCard>

      <ChartCard title="TER-Ke Distribution by Industry Sector" subtitle="Wealth creation frequency distribution — ASX sectors" height={200}>
        <Bar data={terKeDistribution} options={barOpts} />
      </ChartCard>

      <div style={{ gridColumn: "1 / -1" }}>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.625rem" }}>Substages</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.625rem" }}>
          {[
            { id: "beta", label: "Beta Rounding", method: "POST", endpoint: "/api/v1/metrics/beta/calculate-from-precomputed", records: 11000, duration: 1.5 },
            { id: "rates", label: "Risk-Free Rate (Rf)", method: "POST", endpoint: "/api/v1/metrics/rates/calculate", records: 10905, duration: 7.9 },
            { id: "coe", label: "Cost of Equity (Ke)", method: "POST", endpoint: "/api/v1/metrics/cost-of-equity/calculate", records: 10905, duration: 1.6 },
            { id: "fv-ecf", label: "Future Value ECF", method: "POST", endpoint: "/api/v1/metrics/l2-fv-ecf/calculate", records: 42120, duration: 51.9 },
            { id: "ter", label: "TER & TER-Ke (8 metrics)", method: "POST", endpoint: "/api/v1/metrics/l2-ter/calculate", records: 89660, duration: 14.4 },
            { id: "ter-alpha", label: "TER Alpha (12 metrics)", method: "POST", endpoint: "/api/v1/metrics/l2-ter-alpha/calculate", records: 131780, duration: 23.9 },
          ].map(s => <SubstagePill key={s.id} {...s} />)}
        </div>
      </div>
    </div>
  );
}

function OrchestrationPanel() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <ChartCard title="Annualised Wealth Creation (TER-Ke) by Index" subtitle="1yr, 3yr, 5yr, 10yr rolling — ASX 300 · 2001–2019" height={220}>
        <Line data={terKeByIndex} options={{ ...lineOpts, scales: { ...lineOpts.scales, y: { ...lineOpts.scales.y, min: -45 } } }} />
      </ChartCard>

      <ChartCard title="Market to Book Ratio (M:B) by Index" subtitle="Historical M:B ratio — ASX 300 · 2001–2019" height={220}>
        <Line data={mbRatioByIndex} options={mbOpts} />
      </ChartCard>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.25rem" }}>Substages</div>
        {[
          { id: "orchestrate-l1", label: "L1 Pre-Computation Orchestrator", method: "POST", endpoint: "/api/v1/metrics/calculate-l1", records: 130000, duration: 52 },
          { id: "orchestrate-runtime", label: "Full Runtime Orchestrator", method: "POST", endpoint: "/api/v1/metrics/runtime-metrics", records: 296370, duration: 101.2 },
        ].map(s => <SubstagePill key={s.id} {...s} />)}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.25rem" }}>Pipeline Summary</div>
        {[
          { label: "L1 Pre-Compute", records: "~130,000", time: "~52s", color: "hsl(38 60% 52%)" },
          { label: "Runtime (full)", records: "~296,370", time: "~101s", color: "hsl(152 60% 40%)" },
          { label: "Total DB Records", records: "~882,740", time: "—", color: "hsl(213 75% 22%)" },
        ].map(r => (
          <div key={r.label} style={{
            background: `${r.color.replace(")", " / 0.07)")}`,
            border: `1px solid ${r.color.replace(")", " / 0.25)")}`,
            borderRadius: "0.5rem",
            padding: "0.75rem 1rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "hsl(var(--foreground))" }}>{r.label}</span>
            <div style={{ display: "flex", gap: "1.25rem", fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>
              <span>{r.records} records</span>
              <span>{r.time}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ResultsPanel() {
  const principles = [
    { number: 1, label: "Economic Measures are Better", completion: 85, color: "hsl(213 75% 22%)", path: "/principles/1" },
    { number: 2, label: "Primary Focus on the Longer Term", completion: 40, color: "hsl(213 65% 35%)", path: "/principles/2" },
    { number: 3, label: "Central Role of Creativity & Innovation", completion: 30, color: "hsl(213 55% 45%)", path: "/principles/1" },
    { number: 4, label: "Focus on All Stakeholders", completion: 20, color: "hsl(213 45% 55%)", path: "/principles/1" },
    { number: 5, label: "Clear Purpose by Noble Intent", completion: 15, color: "hsl(213 35% 62%)", path: "/principles/1" },
    { number: 6, label: "More is Not Always Better", completion: 10, color: "hsl(213 25% 70%)", path: "/principles/1" },
  ];

  const decompositionRows = [
    { label: "TSR-Ke (Observed Wealth Creation)", value: "8.2%", color: "hsl(213 75% 22%)" },
    { label: "Intrinsic Wealth Creation", value: "5.4%", color: "hsl(38 60% 52%)" },
    { label: "Sustainable Intrinsic Wealth", value: "3.8%", color: "hsl(152 60% 40%)" },
    { label: "Wealth Appropriation", value: "2.8%", color: "hsl(0 72% 51%)" },
  ];

  return (
    <div>
      {/* EP Bow Wave Hero */}
      <div style={{
        background: "linear-gradient(135deg, hsl(213 75% 22% / 0.04) 0%, hsl(38 60% 52% / 0.05) 100%)",
        border: "1px solid hsl(var(--border))",
        borderTop: "3px solid hsl(213 75% 22%)",
        borderRadius: "0.75rem",
        padding: "1.25rem 1.5rem",
        marginBottom: "1rem",
        display: "grid",
        gridTemplateColumns: "1fr 380px",
        gap: "1.5rem",
        alignItems: "center",
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", marginBottom: "0.5rem" }}>
            <span style={{ background: "hsl(38 60% 52%)", color: "#fff", fontSize: "0.625rem", fontWeight: 700, padding: "0.1875rem 0.625rem", borderRadius: "999px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Signature Concept
            </span>
            <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>Principle 2</span>
          </div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 800, color: "hsl(var(--primary))", margin: "0 0 0.375rem 0", lineHeight: 1.25 }}>
            The EP Bow Wave
          </h2>
          <p style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.65, margin: "0 0 0.875rem 0" }}>
            A company's market capitalisation equals its book equity plus the present value of its entire expected Economic Profit stream — the EP Bow Wave. The pair of waves reveals wealth created or destroyed during any measurement period.
          </p>
          <div style={{ display: "flex", gap: "0.625rem" }}>
            <Link href="/principles/2" style={{ display: "inline-flex", alignItems: "center", gap: "0.375rem", padding: "0.5rem 1rem", background: "hsl(213 75% 22%)", color: "white", borderRadius: "0.375rem", fontSize: "0.75rem", fontWeight: 700, textDecoration: "none" }}>
              Explore the Bow Wave
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="m9 18 6-6-6-6" /></svg>
            </Link>
            <Link href="/outputs" style={{ display: "inline-flex", alignItems: "center", gap: "0.375rem", padding: "0.5rem 1rem", background: "transparent", border: "1px solid hsl(var(--border))", color: "hsl(var(--foreground))", borderRadius: "0.375rem", fontSize: "0.75rem", fontWeight: 600, textDecoration: "none" }}>
              View Full Outputs
            </Link>
          </div>
        </div>
        <div>
          <div style={{ height: "190px" }}>
            <Line data={bowWaveData} options={bowWaveOpts} />
          </div>
          <div style={{ textAlign: "center", marginTop: "0.5rem" }}>
            <span style={{ fontSize: "0.6875rem", fontWeight: 700, color: "hsl(152 60% 35%)", background: "hsl(152 60% 95%)", padding: "0.1875rem 0.625rem", borderRadius: "999px", border: "1px solid hsl(152 60% 75%)" }}>
              ▲ $3.1b enhancement · Cochlear (COH)
            </span>
          </div>
        </div>
      </div>

      {/* KPI bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "1px", background: "hsl(var(--border))", border: "1px solid hsl(var(--border))", borderRadius: "0.625rem", overflow: "hidden", marginBottom: "1rem" }}>
        {kpis.map(k => (
          <div key={k.label} style={{ background: "hsl(var(--card))", padding: "0.875rem 1rem" }}>
            <div style={{ fontSize: "0.625rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "hsl(var(--muted-foreground))", marginBottom: "0.125rem" }}>{k.label}</div>
            <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "hsl(var(--primary))", lineHeight: 1.1 }}>{k.value}</div>
            <div style={{ fontSize: "0.625rem", color: k.dir === "positive" ? "hsl(152 60% 40%)" : "hsl(var(--muted-foreground))", marginTop: "0.125rem" }}>{k.delta}</div>
            <div style={{ fontSize: "0.625rem", color: "hsl(var(--muted-foreground))", marginTop: "0.125rem" }}>{k.note}</div>
          </div>
        ))}
      </div>

      {/* Charts grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
        <ChartCard title="Economic Profitability (ROE-Ke) by Index" subtitle="Historical annualised ROE-Ke — ASX 300 · 2001–2019" height={210}>
          <Line data={roeKeByIndex} options={lineOpts} />
        </ChartCard>

        <div style={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "0.625rem", padding: "1rem 1.125rem" }}>
          <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.125rem" }}>Six CISSA Principles</div>
          <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginBottom: "0.75rem" }}>Navigate the Principles Menu</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
            {principles.map(p => (
              <Link href={p.path} key={p.number} style={{ textDecoration: "none", display: "block" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.2rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <div style={{ width: "18px", height: "18px", borderRadius: "50%", background: p.color, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.5625rem", fontWeight: 700, flexShrink: 0 }}>{p.number}</div>
                    <span style={{ fontSize: "0.6875rem", color: "hsl(var(--foreground))", fontWeight: 500, lineHeight: 1.3 }}>{p.label}</span>
                  </div>
                  <span style={{ fontSize: "0.625rem", color: "hsl(var(--muted-foreground))", flexShrink: 0, marginLeft: "0.5rem" }}>{p.completion}%</span>
                </div>
                <div style={{ height: "4px", background: "hsl(var(--muted))", borderRadius: "2px", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${p.completion}%`, background: p.color, borderRadius: "2px", transition: "width 600ms ease" }} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
        <ChartCard title="Annualised Wealth Creation (TER-Ke)" subtitle="ASX 300 · 1yr, 3yr, 5yr, 10yr rolling · 2001–2019" height={190}>
          <Line data={terKeByIndex} options={{ ...lineOpts, scales: { ...lineOpts.scales, y: { ...lineOpts.scales.y, min: -45 } } }} />
        </ChartCard>

        <ChartCard title="Market to Book Ratio (M:B)" subtitle="Historical M:B ratio — ASX 300 · 2001–2019" height={190}>
          <Line data={mbRatioByIndex} options={mbOpts} />
        </ChartCard>

        <div style={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "0.625rem", padding: "1rem 1.125rem" }}>
          <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.125rem" }}>Wealth Creation Decomposition</div>
          <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginBottom: "0.75rem" }}>ASX 300 · 10yr annualised · 2001–2024</div>
          <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: "0.75rem", alignItems: "center" }}>
            <div style={{ height: "150px" }}>
              <Doughnut data={{
                labels: wealthCreationDecomp.labels,
                datasets: [{ data: wealthCreationDecomp.datasets[0].data, backgroundColor: wealthCreationDecomp.datasets[0].backgroundColor as string[], borderWidth: 2, borderColor: "white" }],
              }} options={{ responsive: true, maintainAspectRatio: false, cutout: "65%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.raw}%` } } } }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
              {decompositionRows.map(r => (
                <div key={r.label} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <div style={{ width: "8px", height: "8px", borderRadius: "2px", background: r.color, flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: "0.5625rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.2 }}>{r.label}</div>
                    <div style={{ fontSize: "0.75rem", fontWeight: 700, color: r.color }}>{r.value}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* EP vs EPS chart */}
      <div style={{ marginTop: "1rem" }}>
        <ChartCard title="EP-Dominant vs EPS-Dominant Cohort Performance" subtitle="10yr annualised TSR — EP dominant companies outperform EPS-focused peers" height={210}>
          <Bar data={epVsEpsCohorts} options={barOpts} />
        </ChartCard>
      </div>
    </div>
  );
}

// ── Main Pipeline Page ──────────────────────────────────────────────────────

export default function PipelinePage() {
  const [activeStage, setActiveStage] = useState<StageId>("ingestion");
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);

  const checkHealth = useCallback(async () => {
    setLoading(true);
    const alive = await isBackendAlive();
    setBackendOnline(alive);
    if (alive) {
      try {
        const h = await apiFetch<HealthData>("/api/v1/metrics/health");
        setHealth(h);
      } catch { setHealth(null); }
    }
    setLoading(false);
  }, []);

  useEffect(() => { checkHealth(); }, [checkHealth]);

  const activeIdx = STAGES.findIndex(s => s.id === activeStage);
  const activeData = STAGES[activeIdx];

  return (
    <div style={{ padding: "1.5rem", maxWidth: "1400px" }}>

      {/* Page header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1.5rem" }}>
        <div>
          <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>
            RoZetta Technology — ETL &amp; Metrics
          </div>
          <h1 style={{ fontSize: "1.125rem", fontWeight: 700, color: "hsl(var(--foreground))", margin: 0 }}>
            Data Processing Pipeline
          </h1>
          <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", marginTop: "0.25rem", marginBottom: 0 }}>
            End-to-end orchestration: Bloomberg ingestion → L1/L2 metrics → Beta → Cost of Equity → Wealth Creation indices
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: "0.375rem",
            padding: "0.375rem 0.75rem", borderRadius: "999px",
            border: `1px solid ${backendOnline ? "hsl(152 60% 40% / 0.4)" : "hsl(var(--border))"}`,
            background: backendOnline ? "hsl(152 60% 40% / 0.07)" : "hsl(var(--muted))",
            fontSize: "0.6875rem", fontWeight: 600,
            color: backendOnline ? "hsl(152 60% 40%)" : "hsl(var(--muted-foreground))",
          }}>
            <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: backendOnline ? "hsl(152 60% 40%)" : "hsl(220 14% 70%)", boxShadow: backendOnline ? "0 0 6px hsl(152 60% 40% / 0.7)" : undefined }} />
            {backendOnline === null ? "Connecting…" : backendOnline ? "API Connected" : "API Offline — Mock Data"}
          </div>
          <button
            data-testid="button-refresh-pipeline"
            onClick={checkHealth}
            disabled={loading}
            style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.375rem 0.875rem", border: "1px solid hsl(var(--border))", borderRadius: "0.375rem", background: "hsl(var(--card))", color: "hsl(var(--primary))", cursor: loading ? "wait" : "pointer", fontSize: "0.75rem", fontWeight: 500, opacity: loading ? 0.6 : 1 }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: loading ? "spin 1s linear infinite" : undefined }}>
              <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* ── Horizontal Pipeline Stepper ── */}
      <div style={{
        position: "relative",
        display: "flex",
        alignItems: "stretch",
        marginBottom: "2rem",
        background: "hsl(var(--card))",
        border: "1px solid hsl(var(--border))",
        borderRadius: "0.75rem",
        overflow: "hidden",
      }}>
        {/* Connecting line behind */}
        <div style={{
          position: "absolute",
          top: "50%",
          left: "10%",
          right: "10%",
          height: "2px",
          background: "hsl(var(--border))",
          transform: "translateY(-50%)",
          zIndex: 0,
          pointerEvents: "none",
        }} />

        {STAGES.map((stage, idx) => {
          const isActive = stage.id === activeStage;
          const isPast = idx < activeIdx;
          const statusColor = isPast ? "hsl(152 60% 40%)" : isActive ? stage.color : "hsl(220 14% 70%)";

          return (
            <button
              key={stage.id}
              data-testid={`stepper-${stage.id}`}
              onClick={() => setActiveStage(stage.id)}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "0.5rem",
                padding: "1.125rem 0.75rem",
                background: isActive
                  ? `${stage.color.replace(")", " / 0.06)")}`
                  : "transparent",
                borderRight: idx < STAGES.length - 1 ? "1px solid hsl(var(--border))" : "none",
                borderBottom: isActive ? `3px solid ${stage.color}` : "3px solid transparent",
                cursor: "pointer",
                border: "none",
                outline: "none",
                transition: "background 150ms, border-bottom-color 150ms",
                position: "relative",
                zIndex: 1,
              }}
            >
              {/* Stage icon circle */}
              <div style={{
                width: "44px", height: "44px",
                borderRadius: "50%",
                background: isActive ? stage.color : isPast ? "hsl(152 60% 40%)" : "hsl(220 14% 92%)",
                border: isActive ? `3px solid ${stage.color}` : isPast ? "3px solid hsl(152 60% 40%)" : "3px solid hsl(220 14% 82%)",
                display: "flex", alignItems: "center", justifyContent: "center",
                boxShadow: isActive ? `0 0 0 4px ${stage.color.replace(")", " / 0.15)")}` : "none",
                transition: "all 200ms",
                flexShrink: 0,
              }}>
                {isPast ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                    <path d="m20 6-11 11-5-5" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={isActive ? "white" : "hsl(220 14% 55%)"} strokeWidth="2">
                    <path d={stage.icon} />
                  </svg>
                )}
              </div>

              {/* Badge */}
              <span style={{
                fontSize: "0.5625rem", fontWeight: 700,
                textTransform: "uppercase", letterSpacing: "0.04em",
                background: isActive ? `${stage.color.replace(")", " / 0.12)")}` : "hsl(220 14% 94%)",
                color: isActive ? stage.color : "hsl(220 14% 55%)",
                padding: "0.1rem 0.5rem", borderRadius: "999px",
              }}>
                {stage.badge}
              </span>

              {/* Label */}
              <span style={{
                fontSize: "0.75rem", fontWeight: isActive ? 700 : 500,
                color: isActive ? "hsl(var(--foreground))" : "hsl(var(--muted-foreground))",
                textAlign: "center", lineHeight: 1.3,
                whiteSpace: "nowrap",
              }}>
                {stage.label}
              </span>

              {/* Substage count */}
              {stage.substages.length > 0 && (
                <span style={{ fontSize: "0.5625rem", color: "hsl(var(--muted-foreground))" }}>
                  {stage.substages.length} substage{(stage.substages.length as number) !== 1 ? "s" : ""}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Active Stage Detail Panel ── */}
      <div style={{
        background: "hsl(var(--background))",
        border: "1px solid hsl(var(--border))",
        borderTop: `3px solid ${activeData.color}`,
        borderRadius: "0.75rem",
        padding: "1.5rem",
        minHeight: "300px",
      }}>
        {/* Panel header */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.25rem" }}>
          <div style={{
            width: "36px", height: "36px", borderRadius: "50%",
            background: `${activeData.color.replace(")", " / 0.12)")}`,
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={activeData.color} strokeWidth="2">
              <path d={activeData.icon} />
            </svg>
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "hsl(var(--foreground))", margin: 0 }}>
                {activeData.label}
              </h2>
              <span style={{
                fontSize: "0.625rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em",
                background: `${activeData.color.replace(")", " / 0.12)")}`, color: activeData.color,
                padding: "0.125rem 0.625rem", borderRadius: "999px",
              }}>
                {activeData.badge}
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", margin: "0.1rem 0 0 0" }}>
              {activeStage === "ingestion" && "Bloomberg Excel extraction → CSV → database load with FY alignment & imputation"}
              {activeStage === "l1" && "11 L1 pre-computed metrics in 4 parallel groups · L2 Core EP metrics sequence"}
              {activeStage === "runtime" && "Parameter-dependent runtime computations: Beta → Rf → Ke → FV-ECF → TER → TER Alpha"}
              {activeStage === "orchestration" && "Full pipeline orchestrators: L1 pre-computation (~52s) → runtime metrics (~101s, ~296k records)"}
              {activeStage === "results" && "Final analytics dashboard: Wealth Creation, Economic Profitability, Bow Wave analysis"}
            </p>
          </div>

          {/* Stage nav arrows */}
          <div style={{ marginLeft: "auto", display: "flex", gap: "0.5rem" }}>
            <button
              onClick={() => activeIdx > 0 && setActiveStage(STAGES[activeIdx - 1].id)}
              disabled={activeIdx === 0}
              style={{ padding: "0.375rem 0.625rem", border: "1px solid hsl(var(--border))", borderRadius: "0.375rem", background: "hsl(var(--card))", color: "hsl(var(--foreground))", cursor: activeIdx === 0 ? "not-allowed" : "pointer", opacity: activeIdx === 0 ? 0.4 : 1, fontSize: "0.75rem", fontWeight: 600 }}
            >
              ← Prev
            </button>
            <button
              onClick={() => activeIdx < STAGES.length - 1 && setActiveStage(STAGES[activeIdx + 1].id)}
              disabled={activeIdx === STAGES.length - 1}
              style={{ padding: "0.375rem 0.625rem", border: "1px solid hsl(var(--border))", borderRadius: "0.375rem", background: "hsl(var(--card))", color: "hsl(var(--foreground))", cursor: activeIdx === STAGES.length - 1 ? "not-allowed" : "pointer", opacity: activeIdx === STAGES.length - 1 ? 0.4 : 1, fontSize: "0.75rem", fontWeight: 600 }}
            >
              Next →
            </button>
          </div>
        </div>

        {/* Panel content */}
        {activeStage === "ingestion"    && <IngestionPanel />}
        {activeStage === "l1"           && <L1Panel />}
        {activeStage === "runtime"      && <RuntimePanel />}
        {activeStage === "orchestration" && <OrchestrationPanel />}
        {activeStage === "results"      && <ResultsPanel />}
      </div>

      {/* Footer trigger */}
      <div style={{
        marginTop: "1.5rem",
        padding: "1.125rem 1.5rem",
        background: "hsl(var(--card))",
        border: "1px solid hsl(var(--border))",
        borderRadius: "0.5rem",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "1rem",
      }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: "0.25rem" }}>Run Full Pipeline</div>
          <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>
            Step 1 — <code style={{ fontFamily: "monospace" }}>POST /api/v1/metrics/calculate-l1</code> (~52s) &nbsp;·&nbsp;
            Step 2 — <code style={{ fontFamily: "monospace" }}>POST /api/v1/metrics/runtime-metrics?dataset_id=&amp;param_set_id=</code> (~101s, ~296k records)
          </div>
        </div>
        <button
          data-testid="button-trigger-orchestration"
          disabled={!backendOnline}
          style={{
            display: "flex", alignItems: "center", gap: "0.5rem",
            padding: "0.5rem 1.25rem", borderRadius: "0.375rem", border: "none",
            background: backendOnline ? "hsl(var(--primary))" : "hsl(220 14% 85%)",
            color: backendOnline ? "white" : "hsl(220 14% 55%)",
            fontSize: "0.8125rem", fontWeight: 600,
            cursor: backendOnline ? "pointer" : "not-allowed",
            whiteSpace: "nowrap", flexShrink: 0,
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          {backendOnline ? "Run Orchestration" : "Backend Offline"}
        </button>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
