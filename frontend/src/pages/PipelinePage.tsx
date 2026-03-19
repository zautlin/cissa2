import { useState, useEffect, useCallback } from "react";
import { apiFetch, isBackendAlive } from "../lib/queryClient";

// ── Types ──────────────────────────────────────────────────────────────────

type StageStatus = "idle" | "running" | "success" | "failed" | "warning";

interface PipelineStage {
  id: string;
  phase: string;
  label: string;
  description: string;
  endpoint?: string;
  method?: "GET" | "POST";
  icon: string;
  color: string;
  depends?: string[];
}

interface StageState {
  status: StageStatus;
  message?: string;
  duration?: number;
  records?: number;
  lastRun?: string;
}

type PipelineStatesMap = Record<string, StageState>;

interface HealthData {
  status: string;
  message: string;
  database: string;
}

// ── Pipeline Stage Definitions ─────────────────────────────────────────────

const PIPELINE_STAGES: PipelineStage[] = [
  // ETL / Data Ingestion
  {
    id: "ingest",
    phase: "Phase 0 — Data Ingestion",
    label: "Data Ingestion",
    description: "Extract Bloomberg Excel data → CSV → load reference & raw tables with numeric validation",
    icon: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12",
    color: "hsl(213 75% 22%)",
    endpoint: "/api/v1/metrics/statistics",
    method: "GET",
  },
  {
    id: "fy-align",
    phase: "Phase 0 — Data Ingestion",
    label: "FY Alignment & Imputation",
    description: "Align financial year boundaries and impute missing data points using statistical methods",
    icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
    color: "hsl(213 75% 22%)",
    endpoint: "/api/v1/metrics/statistics",
    method: "GET",
  },
  // L1 Pre-computed Metrics
  {
    id: "l1-metrics",
    phase: "Phase 1 — L1 Pre-Computed Metrics",
    label: "L1 Metric Calculation",
    description: "Pre-compute 11 L1 metrics in 4 parallel groups: Calc MC, Assets, OA, Op/Non-Op/Tax/XO Cost, ECF, EE, FY TSR, FY TSR PREL",
    icon: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 11h.01M12 11h.01M15 11h.01M4 19h16a2 2 0 002-2V7a2 2 0 00-2-2H4a2 2 0 00-2 2v10a2 2 0 002 2z",
    color: "hsl(38 60% 52%)",
    endpoint: "/api/v1/metrics/calculate",
    method: "POST",
    depends: ["ingest", "fy-align"],
  },
  {
    id: "l2-core",
    phase: "Phase 2 — L2 Derived Metrics",
    label: "L2 Core Metrics",
    description: "Sequential: Core EP metrics (EP, PAT_EX, XO_COST_EX, FC) dependent on L1 Phase 1 outputs",
    icon: "M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z",
    color: "hsl(38 60% 52%)",
    endpoint: "/api/v1/metrics/l2-core/calculate",
    method: "POST",
    depends: ["l1-metrics"],
  },
  // Runtime Metrics (Phase 3+ — parameter-dependent, called via runtime-metrics orchestrator)
  {
    id: "beta",
    phase: "Phase 3 — Runtime: Beta & Ke",
    label: "Beta Rounding",
    description: "Apply parameter-specific rounding to pre-computed Beta values → Calc Beta Rounded (~11,000 records, ~1.5s)",
    icon: "M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z",
    color: "hsl(152 60% 40%)",
    endpoint: "/api/v1/metrics/beta/calculate-from-precomputed",
    method: "POST",
    depends: ["l1-metrics"],
  },
  {
    id: "rates",
    phase: "Phase 3 — Runtime: Beta & Ke",
    label: "Risk-Free Rate (Rf)",
    description: "Calculate Calc Rf from benchmark rates and risk premium parameter → ~10,905 records (~7.9s)",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    color: "hsl(152 60% 40%)",
    endpoint: "/api/v1/metrics/rates/calculate",
    method: "POST",
    depends: ["l1-metrics"],
  },
  {
    id: "coe",
    phase: "Phase 4 — Runtime: Cost of Equity",
    label: "Cost of Equity (Ke)",
    description: "Calc KE = Calc Rf + Calc Beta Rounded × Risk Premium → ~10,905 records (~1.6s)",
    icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    color: "hsl(188 78% 35%)",
    endpoint: "/api/v1/metrics/cost-of-equity/calculate",
    method: "POST",
    depends: ["beta", "rates"],
  },
  {
    id: "fv-ecf",
    phase: "Phase 5 — Runtime: FV ECF → TER → TER Alpha",
    label: "Future Value ECF",
    description: "Project equity cash flows forward: Calc 1Y/3Y/5Y/10Y FV ECF → ~42,120 records (~51.9s, bottleneck)",
    icon: "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6",
    color: "hsl(270 60% 50%)",
    endpoint: "/api/v1/metrics/l2-fv-ecf/calculate",
    method: "POST",
    depends: ["coe"],
  },
  {
    id: "ter",
    phase: "Phase 5 — Runtime: FV ECF → TER → TER Alpha",
    label: "TER & TER-Ke",
    description: "Calc 1Y/3Y/5Y/10Y TER + TER-KE (8 metrics) → ~89,660 records (~14.4s)",
    icon: "M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z",
    color: "hsl(270 60% 50%)",
    endpoint: "/api/v1/metrics/l2-ter/calculate",
    method: "POST",
    depends: ["fv-ecf"],
  },
  {
    id: "ter-alpha",
    phase: "Phase 5 — Runtime: FV ECF → TER → TER Alpha",
    label: "TER Alpha",
    description: "Risk-adjusted performance: Calc 1Y/3Y/5Y/10Y Load RA MM + WC TERA + TER Alpha (12 metrics) → ~131,780 records (~23.9s)",
    icon: "M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm0 8a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zm11-1a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z",
    color: "hsl(0 72% 51%)",
    endpoint: "/api/v1/metrics/l2-ter-alpha/calculate",
    method: "POST",
    depends: ["ter"],
  },
  // Full orchestrators
  {
    id: "orchestrate-l1",
    phase: "Phase 6 — Orchestrators",
    label: "L1 Pre-Computation Orchestrator",
    description: "Parallelises Phase 1 (4 concurrent groups × 11 metrics), sequences Phase 2 — use after fresh data ingestion",
    icon: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
    color: "hsl(213 75% 22%)",
    endpoint: "/api/v1/metrics/calculate-l1",
    method: "POST",
    depends: ["ingest", "fy-align"],
  },
  {
    id: "orchestrate-runtime",
    phase: "Phase 6 — Orchestrators",
    label: "Runtime Metrics Orchestrator",
    description: "Full Phase 3+ pipeline: Beta Rounding → Rf → Ke → FV-ECF → TER → TER Alpha. ~101s total wall-clock time (~296k records)",
    icon: "M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18",
    color: "hsl(213 75% 22%)",
    endpoint: "/api/v1/metrics/runtime-metrics?dataset_id={id}&param_set_id={id}",
    method: "POST",
    depends: ["orchestrate-l1"],
  },
];

// Group stages by phase
const PHASES = Array.from(new Set(PIPELINE_STAGES.map(s => s.phase)));

// ── Mock fallback states ───────────────────────────────────────────────────

const MOCK_STATES: PipelineStatesMap = {
  // ETL (CLI only — no direct API endpoint, status inferred from statistics)
  ingest:            { status: "success", message: "500 tickers × ~20 years ≈ 10,000 fundamentals records", records: 10000, duration: 180, lastRun: "2026-03-19 06:00 AEDT" },
  "fy-align":        { status: "success", message: "FY alignment & imputation complete",                   records: 10000, duration: 45,  lastRun: "2026-03-19 06:03 AEDT" },
  // L1 pre-computed (13 metrics ≈ 130,000 records)
  "l1-metrics":      { status: "success", message: "13 L0 metrics calculated",                             records: 130000, duration: 38, lastRun: "2026-03-19 06:05 AEDT" },
  "l2-core":         { status: "success", message: "Core EP metrics (EP, PAT_EX, XO_COST_EX, FC)",          records: 10000, duration: 6.8, lastRun: "2026-03-19 06:06 AEDT" },
  // Runtime (parameter-dependent)
  beta:              { status: "success", message: "Calc Beta Rounded — 11,000 records",                   records: 11000, duration: 1.5,  lastRun: "2026-03-19 06:07 AEDT" },
  rates:             { status: "success", message: "Calc Rf — 10,905 records",                             records: 10905, duration: 7.9,  lastRun: "2026-03-19 06:07 AEDT" },
  coe:               { status: "success", message: "Calc KE = Rf + Beta × Risk Premium",                  records: 10905, duration: 1.6,  lastRun: "2026-03-19 06:07 AEDT" },
  "fv-ecf":          { status: "success", message: "Calc 1Y/3Y/5Y/10Y FV ECF — 42,120 records",            records: 42120, duration: 51.9, lastRun: "2026-03-19 06:08 AEDT" },
  ter:               { status: "success", message: "8 TER/TER-KE metrics — 89,660 records",                 records: 89660, duration: 14.4, lastRun: "2026-03-19 06:09 AEDT" },
  "ter-alpha":       { status: "warning", message: "TER Alpha implementation pending (Phase 10d)",          records: 131780, duration: 23.9, lastRun: "2026-03-18 06:00 AEDT" },
  // Orchestrators
  "orchestrate-l1":  { status: "success", message: "13/13 L1 metrics complete — ~130k records",            records: 130000, duration: 52,   lastRun: "2026-03-19 06:06 AEDT" },
  "orchestrate-runtime": { status: "success", message: "All phases complete — ~296k records in ~101s",    records: 296370, duration: 101.2, lastRun: "2026-03-19 06:10 AEDT" },
};

// ── Status helpers ─────────────────────────────────────────────────────────

const STATUS_COLORS: Record<StageStatus, string> = {
  idle:    "hsl(220 14% 60%)",
  running: "hsl(38 60% 52%)",
  success: "hsl(152 60% 40%)",
  failed:  "hsl(0 72% 51%)",
  warning: "hsl(38 60% 52%)",
};

const STATUS_BG: Record<StageStatus, string> = {
  idle:    "hsl(220 14% 96%)",
  running: "hsl(38 60% 52% / 0.1)",
  success: "hsl(152 60% 40% / 0.08)",
  failed:  "hsl(0 72% 51% / 0.08)",
  warning: "hsl(38 60% 52% / 0.1)",
};

const STATUS_LABEL: Record<StageStatus, string> = {
  idle:    "Idle",
  running: "Running...",
  success: "Success",
  failed:  "Failed",
  warning: "Warning",
};

function StatusDot({ status }: { status: StageStatus }) {
  const pulse = status === "running";
  return (
    <span style={{
      display: "inline-block",
      width: "8px",
      height: "8px",
      borderRadius: "50%",
      background: STATUS_COLORS[status],
      boxShadow: pulse ? `0 0 8px ${STATUS_COLORS[status]}` : undefined,
      animation: pulse ? "pulse-dot 1s infinite" : undefined,
      flexShrink: 0,
    }} />
  );
}

// ── KPI summary bar ────────────────────────────────────────────────────────

interface KPIStat {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}

function KpiBar({ stats }: { stats: KPIStat[] }) {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: `repeat(${stats.length}, 1fr)`,
      gap: "1px",
      background: "hsl(var(--border))",
      border: "1px solid hsl(var(--border))",
      borderRadius: "0.5rem",
      overflow: "hidden",
      marginBottom: "1.5rem",
    }}>
      {stats.map(s => (
        <div key={s.label} style={{
          background: "hsl(var(--card))",
          padding: "0.875rem 1.25rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.125rem",
        }}>
          <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            {s.label}
          </span>
          <span style={{ fontSize: "1.25rem", fontWeight: 700, color: s.color || "hsl(var(--foreground))", lineHeight: 1.2 }}>
            {s.value}
          </span>
          {s.sub && (
            <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>{s.sub}</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Stage Card ─────────────────────────────────────────────────────────────

function StageCard({ stage, state }: { stage: PipelineStage; state: StageState }) {
  return (
    <div
      data-testid={`pipeline-stage-${stage.id}`}
      style={{
        background: STATE_BG_OVERRIDE(state.status),
        border: `1px solid ${STATE_BORDER(state.status)}`,
        borderRadius: "0.5rem",
        padding: "1rem 1.125rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
        transition: "border-color 200ms, box-shadow 200ms",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Left accent stripe */}
      <div style={{
        position: "absolute",
        left: 0,
        top: 0,
        bottom: 0,
        width: "3px",
        background: STATUS_COLORS[state.status],
        borderRadius: "0.5rem 0 0 0.5rem",
      }} />

      <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", paddingLeft: "0.25rem" }}>
        {/* Icon */}
        <div style={{
          width: "34px",
          height: "34px",
          borderRadius: "0.375rem",
          background: `${stage.color}18`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={stage.color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={stage.icon} />
          </svg>
        </div>

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
            <span style={{ fontWeight: 600, fontSize: "0.8125rem", color: "hsl(var(--foreground))" }}>
              {stage.label}
            </span>
            <div style={{
              display: "inline-flex", alignItems: "center", gap: "0.3rem",
              fontSize: "0.625rem", fontWeight: 600,
              padding: "0.125rem 0.5rem",
              borderRadius: "999px",
              background: STATUS_BG[state.status],
              color: STATUS_COLORS[state.status],
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}>
              <StatusDot status={state.status} />
              {STATUS_LABEL[state.status]}
            </div>
          </div>
          <p style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.5, margin: 0 }}>
            {stage.description}
          </p>
        </div>
      </div>

      {/* Stats row */}
      {(state.message || state.records || state.duration) && (
        <div style={{
          paddingLeft: "0.25rem",
          display: "flex",
          gap: "1rem",
          flexWrap: "wrap",
          borderTop: "1px solid hsl(var(--border))",
          paddingTop: "0.625rem",
          marginTop: "0.125rem",
        }}>
          {state.message && (
            <span style={{ fontSize: "0.6875rem", color: STATUS_COLORS[state.status], fontWeight: 500 }}>
              {state.message}
            </span>
          )}
          {state.records != null && (
            <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>
              {state.records.toLocaleString()} records
            </span>
          )}
          {state.duration != null && (
            <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>
              {state.duration}s
            </span>
          )}
          {state.lastRun && (
            <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginLeft: "auto" }}>
              Last: {state.lastRun}
            </span>
          )}
        </div>
      )}

      {/* Endpoint badge */}
      {stage.endpoint && (
        <div style={{ paddingLeft: "0.25rem" }}>
          <code style={{
            fontSize: "0.6rem",
            background: "hsl(var(--muted))",
            color: "hsl(var(--muted-foreground))",
            padding: "0.125rem 0.375rem",
            borderRadius: "0.25rem",
            fontFamily: "monospace",
          }}>
            {stage.method} {stage.endpoint}
          </code>
        </div>
      )}
    </div>
  );
}

function STATE_BG_OVERRIDE(s: StageStatus): string {
  if (s === "success") return "hsl(152 60% 40% / 0.03)";
  if (s === "failed") return "hsl(0 72% 51% / 0.03)";
  if (s === "running") return "hsl(38 60% 52% / 0.05)";
  if (s === "warning") return "hsl(38 60% 52% / 0.03)";
  return "hsl(var(--card))";
}
function STATE_BORDER(s: StageStatus): string {
  if (s === "success") return "hsl(152 60% 40% / 0.25)";
  if (s === "failed") return "hsl(0 72% 51% / 0.25)";
  if (s === "running") return "hsl(38 60% 52% / 0.4)";
  if (s === "warning") return "hsl(38 60% 52% / 0.3)";
  return "hsl(var(--border))";
}

// ── Flow arrow ─────────────────────────────────────────────────────────────

function FlowArrow() {
  return (
    <div style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      height: "20px",
      color: "hsl(var(--muted-foreground))",
    }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 5v14M19 12l-7 7-7-7"/>
      </svg>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function PipelinePage() {
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [stageStates, setStageStates] = useState<PipelineStatesMap>(MOCK_STATES);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<string>("");

  // Check backend health
  const checkHealth = useCallback(async () => {
    setLoading(true);
    const alive = await isBackendAlive();
    setBackendOnline(alive);

    if (alive) {
      try {
        const h = await apiFetch<HealthData>("/api/v1/metrics/health");
        setHealth(h);

        // Try to get statistics for ingestion stage
        try {
          const stats = await apiFetch<{ companies?: number; datasets?: number }>("/api/v1/metrics/statistics");
          setStageStates(prev => ({
            ...prev,
            ingest: {
              status: "success",
              message: `${stats.companies ?? "?"} companies • ${stats.datasets ?? "?"} datasets`,
              lastRun: new Date().toLocaleString("en-AU", { timeZone: "Australia/Sydney" }) + " AEDT",
            },
          }));
        } catch {
          // stats endpoint may need params — leave mock
        }
      } catch {
        setHealth(null);
      }
    }

    setLastRefreshed(new Date().toLocaleString("en-AU", { timeZone: "Australia/Sydney" }) + " AEDT");
    setLoading(false);
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  // Derived KPI stats
  const totalStages = PIPELINE_STAGES.length;
  const successCount = Object.values(stageStates).filter(s => s.status === "success").length;
  const failedCount = Object.values(stageStates).filter(s => s.status === "failed").length;
  const warningCount = Object.values(stageStates).filter(s => s.status === "warning").length;
  const runningCount = Object.values(stageStates).filter(s => s.status === "running").length;
  const totalRecords = Object.values(stageStates).reduce((a, s) => a + (s.records ?? 0), 0);

  const kpiStats: KPIStat[] = [
    {
      label: "Backend",
      value: backendOnline === null ? "Checking…" : backendOnline ? "Online" : "Offline",
      sub: health ? `DB: ${health.database}` : "Fallback mode",
      color: backendOnline ? "hsl(152 60% 40%)" : backendOnline === false ? "hsl(0 72% 51%)" : "hsl(220 14% 60%)",
    },
    {
      label: "Stages",
      value: `${successCount}/${totalStages}`,
      sub: "complete",
      color: successCount === totalStages ? "hsl(152 60% 40%)" : "hsl(var(--foreground))",
    },
    {
      label: "Warnings",
      value: String(warningCount),
      sub: failedCount > 0 ? `${failedCount} failed` : "no failures",
      color: warningCount > 0 ? "hsl(38 60% 52%)" : "hsl(152 60% 40%)",
    },
    {
      label: "Records",
      value: totalRecords.toLocaleString(),
      sub: "total processed",
    },
    {
      label: "Last Refresh",
      value: loading ? "…" : lastRefreshed.split(",")[1]?.trim() || "—",
      sub: lastRefreshed.split(",")[0] || "—",
    },
  ];

  return (
    <div style={{ padding: "1.5rem", maxWidth: "1200px" }}>

      {/* Pulse animation for running stages */}
      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.3); }
        }
      `}</style>

      {/* Header */}
      <div style={{ marginBottom: "1.25rem", display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>
            RoZetta Technology — ETL & Metrics
          </div>
          <h1 style={{ fontSize: "1.125rem", fontWeight: 700, color: "hsl(var(--foreground))", margin: 0 }}>
            Data Processing Pipeline
          </h1>
          <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", marginTop: "0.25rem", marginBottom: 0 }}>
            End-to-end orchestration: Bloomberg ingestion → L1/L2 metrics → Beta → Cost of Equity → Wealth Creation indices
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          {/* Backend status pill */}
          <div style={{
            display: "inline-flex", alignItems: "center", gap: "0.375rem",
            padding: "0.375rem 0.75rem",
            borderRadius: "999px",
            border: `1px solid ${backendOnline ? "hsl(152 60% 40% / 0.4)" : "hsl(var(--border))"}`,
            background: backendOnline ? "hsl(152 60% 40% / 0.07)" : "hsl(var(--muted))",
            fontSize: "0.6875rem",
            fontWeight: 600,
            color: backendOnline ? "hsl(152 60% 40%)" : "hsl(var(--muted-foreground))",
          }}>
            <div style={{
              width: "6px", height: "6px", borderRadius: "50%",
              background: backendOnline ? "hsl(152 60% 40%)" : "hsl(220 14% 70%)",
              boxShadow: backendOnline ? "0 0 6px hsl(152 60% 40% / 0.7)" : undefined,
            }} />
            {backendOnline === null ? "Connecting…" : backendOnline ? "API Connected" : "API Offline — Mock Data"}
          </div>

          {/* Refresh button */}
          <button
            data-testid="button-refresh-pipeline"
            onClick={checkHealth}
            disabled={loading || runningCount > 0}
            style={{
              display: "flex", alignItems: "center", gap: "0.375rem",
              padding: "0.375rem 0.875rem",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.375rem",
              background: "hsl(var(--card))",
              color: "hsl(var(--primary))",
              cursor: loading ? "wait" : "pointer",
              fontSize: "0.75rem",
              fontWeight: 500,
              opacity: loading ? 0.6 : 1,
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              style={{ animation: loading ? "spin 1s linear infinite" : undefined }}>
              <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Bar */}
      <KpiBar stats={kpiStats} />

      {/* Offline notice */}
      {backendOnline === false && (
        <div style={{
          background: "hsl(38 60% 52% / 0.08)",
          border: "1px solid hsl(38 60% 52% / 0.3)",
          borderRadius: "0.5rem",
          padding: "0.875rem 1.25rem",
          marginBottom: "1.5rem",
          display: "flex",
          alignItems: "flex-start",
          gap: "0.75rem",
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="hsl(38 60% 52%)" strokeWidth="2" style={{ flexShrink: 0, marginTop: "1px" }}>
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <div>
            <div style={{ fontWeight: 600, fontSize: "0.8125rem", color: "hsl(38 60% 42%)", marginBottom: "0.125rem" }}>
              Backend not reachable — displaying cached pipeline state
            </div>
            <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>
              Start the FastAPI backend at <code style={{ fontFamily: "monospace" }}>localhost:8000</code> to see live metrics.
              Stage states shown reflect last known run.
            </div>
          </div>
        </div>
      )}

      {/* Pipeline flow — grouped by phase */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {PHASES.map((phase, pi) => {
          const stagesInPhase = PIPELINE_STAGES.filter(s => s.phase === phase);
          const phaseSuccess = stagesInPhase.every(s => stageStates[s.id]?.status === "success");
          const phaseWarning = stagesInPhase.some(s => stageStates[s.id]?.status === "warning");
          const phaseFailed  = stagesInPhase.some(s => stageStates[s.id]?.status === "failed");

          return (
            <div key={phase}>
              {/* Phase header */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                marginBottom: "0.75rem",
              }}>
                <div style={{
                  width: "22px", height: "22px",
                  borderRadius: "50%",
                  background: phaseFailed
                    ? "hsl(0 72% 51%)"
                    : phaseWarning
                      ? "hsl(38 60% 52%)"
                      : phaseSuccess
                        ? "hsl(152 60% 40%)"
                        : "hsl(220 14% 75%)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "0.5625rem",
                  fontWeight: 700,
                  color: "white",
                  flexShrink: 0,
                }}>
                  {pi}
                </div>
                <span style={{
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  color: "hsl(var(--foreground))",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}>
                  {phase}
                </span>
                <div style={{ flex: 1, height: "1px", background: "hsl(var(--border))" }} />
              </div>

              {/* Stage cards in this phase */}
              <div style={{
                display: "grid",
                gridTemplateColumns: stagesInPhase.length > 1 ? "1fr 1fr" : "1fr",
                gap: "0.75rem",
              }}>
                {stagesInPhase.map(stage => (
                  <StageCard
                    key={stage.id}
                    stage={stage}
                    state={stageStates[stage.id] ?? { status: "idle" }}
                  />
                ))}
              </div>

              {/* Arrow connector between phases */}
              {pi < PHASES.length - 1 && <FlowArrow />}
            </div>
          );
        })}
      </div>

      {/* Footer: trigger orchestration */}
      <div style={{
        marginTop: "2rem",
        padding: "1.25rem 1.5rem",
        background: "hsl(var(--card))",
        border: "1px solid hsl(var(--border))",
        borderRadius: "0.5rem",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "1rem",
      }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: "0.25rem" }}>
            Run Full Pipeline
          </div>
          <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>
            Step 1 — L1 pre-computation: <code style={{ fontFamily: "monospace" }}>POST /api/v1/metrics/calculate-l1</code> (parallelises 11 metrics, ~52s)<br/>
            Step 2 — Runtime orchestration: <code style={{ fontFamily: "monospace" }}>POST /api/v1/metrics/runtime-metrics?dataset_id=&amp;param_set_id=</code> (~101s, ~296k records)<br/>
            Requires <code style={{ fontFamily: "monospace" }}>dataset_id</code> from ETL ingestion + <code style={{ fontFamily: "monospace" }}>param_set_id</code> from schema init.
          </div>
        </div>
        <button
          data-testid="button-trigger-orchestration"
          disabled={!backendOnline || runningCount > 0}
          style={{
            display: "flex", alignItems: "center", gap: "0.5rem",
            padding: "0.5rem 1.25rem",
            borderRadius: "0.375rem",
            border: "none",
            background: backendOnline && runningCount === 0
              ? "hsl(var(--primary))"
              : "hsl(220 14% 85%)",
            color: backendOnline && runningCount === 0 ? "white" : "hsl(220 14% 55%)",
            fontSize: "0.8125rem",
            fontWeight: 600,
            cursor: backendOnline && runningCount === 0 ? "pointer" : "not-allowed",
            whiteSpace: "nowrap",
            flexShrink: 0,
            transition: "background 200ms",
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
          {runningCount > 0 ? "Running…" : backendOnline ? "Run Orchestration" : "Backend Offline"}
        </button>
      </div>

      {/* spin keyframe */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
