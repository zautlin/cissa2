/**
 * PipelinePage — CISSA ETL Pipeline
 * Full live API wiring:
 *   Stage 1: Data Selection (pick existing dataset from backend)
 *   Stage 2: Parameter Configuration
 *   Stage 3: L1 Metrics Computation (orchestrate-l1)
 *   Stage 4: Runtime Metrics (beta → rf → ke → fv-ecf → ter → ter-alpha)
 *   Stage 5: Results Dashboard
 */
import { useState, useCallback, useRef, useEffect } from "react";
import {
  getStatistics, getActiveParameters, orchestrateL1Metrics,
  runRuntimeMetrics, calculateBetaFromPrecomputed,
  calculateRates, calculateCostOfEquity, calculateFvEcf,
  calculateTer, calculateTerAlpha, calculateL2Core,
  updateParameterSet, metricsExist,
  DatasetStatistics, ParameterSetResponse,
} from "../lib/api";
import { Link } from "wouter";

// ── Types ──────────────────────────────────────────────────────────────────
type StageStatus = "pending" | "running" | "done" | "error";

interface StageResult {
  status: StageStatus;
  message: string;
  detail?: string;
  records?: number;
  seconds?: number;
}

// ── Color tokens ────────────────────────────────────────────────────────────
const NAVY  = "hsl(213 75% 22%)";
const GOLD  = "hsl(38 60% 52%)";
const GREEN = "hsl(152 60% 40%)";
const RED   = "hsl(0 65% 50%)";
const SLATE = "hsl(215 15% 46%)";

// ── Parameter labels ────────────────────────────────────────────────────────
const PARAM_META: Record<string, { label: string; type: "number" | "boolean" | "select"; options?: string[] }> = {
  country:                                { label: "Country",                   type: "select", options: ["Australia", "USA", "UK"] },
  currency_notation:                      { label: "Currency Notation",         type: "select", options: ["A$m", "USD", "GBP"] },
  cost_of_equity_approach:                { label: "Cost of Equity Approach",   type: "select", options: ["Floating", "Fixed", "CAPM"] },
  equity_risk_premium:                    { label: "Equity Risk Premium (%)",   type: "number" },
  fixed_benchmark_return_wealth_preservation: { label: "Fixed Benchmark Return (%)", type: "number" },
  tax_rate_franking_credits:              { label: "Tax Rate — Franking Credits (%)", type: "number" },
  value_of_franking_credits:              { label: "Value of Franking Credits (%)", type: "number" },
  include_franking_credits_tsr:           { label: "Include Franking Credits in TSR", type: "boolean" },
  beta_rounding:                          { label: "Beta Rounding (decimal places)", type: "number" },
  risk_free_rate_rounding:                { label: "Risk-Free Rate Rounding",   type: "number" },
  last_calendar_year:                     { label: "Last Calendar Year",        type: "number" },
  beta_relative_error_tolerance:          { label: "Beta Relative Error Tolerance (%)", type: "number" },
  terminal_year:                          { label: "Terminal Year",             type: "number" },
};

// ── Parameter groups ────────────────────────────────────────────────────────
const PARAM_GROUPS: { label: string; icon: string; keys: string[] }[] = [
  {
    label: "Market Configuration",
    icon: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z",
    keys: ["country", "currency_notation", "cost_of_equity_approach", "equity_risk_premium", "fixed_benchmark_return_wealth_preservation"],
  },
  {
    label: "Franking Credits",
    icon: "M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z",
    keys: ["include_franking_credits_tsr", "tax_rate_franking_credits", "value_of_franking_credits"],
  },
  {
    label: "Technical Parameters",
    icon: "M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.74,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.07,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.44-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.47-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z",
    keys: ["beta_rounding", "risk_free_rate_rounding", "beta_relative_error_tolerance", "last_calendar_year", "terminal_year"],
  },
];

// ── Toggle switch ────────────────────────────────────────────────────────────
function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      style={{
        width: 36, height: 20, borderRadius: 10, flexShrink: 0,
        background: on ? GREEN : "hsl(210 15% 78%)",
        border: "none", cursor: "pointer", padding: 2,
        transition: "background 0.2s", display: "flex", alignItems: "center",
      }}
    >
      <div style={{
        width: 16, height: 16, borderRadius: "50%", background: "#fff",
        boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
        transition: "transform 0.2s",
        transform: on ? "translateX(16px)" : "translateX(0)",
      }} />
    </button>
  );
}

// ── Spinner ────────────────────────────────────────────────────────────────
function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ animation: "spin 0.9s linear infinite" }}>
      <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
      <path d="M22 12a10 10 0 00-10-10" />
    </svg>
  );
}

// ── Stage indicator ────────────────────────────────────────────────────────
function StageNode({
  num, label, sublabel, status, isActive, onClick,
}: {
  num: number; label: string; sublabel: string;
  status: StageStatus; isActive: boolean;
  onClick?: () => void;
}) {
  const bg = status === "done" ? GREEN : status === "running" ? GOLD : status === "error" ? RED : "hsl(210 16% 90%)";
  const fg = (status === "done" || status === "running" || status === "error") ? "#fff" : SLATE;
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex", flexDirection: "column", alignItems: "center", gap: "0.4rem",
        background: "none", border: "none", cursor: onClick ? "pointer" : "default",
        padding: "0.5rem 0.75rem",
        borderRadius: 10,
        outline: isActive ? `2px solid ${NAVY}` : "2px solid transparent",
        transition: "all 0.2s",
        minWidth: 100,
      }}
    >
      <div style={{
        width: 40, height: 40, borderRadius: "50%",
        background: isActive ? NAVY : bg,
        color: isActive ? "#fff" : fg,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "0.8125rem", fontWeight: 800,
        boxShadow: isActive ? `0 0 0 4px hsl(213 75% 22% / 0.15)` : status === "done" ? `0 0 8px hsl(152 60% 40% / 0.4)` : "none",
        transition: "all 0.2s",
        position: "relative",
      }}>
        {status === "running" ? <Spinner size={18} /> : status === "done" ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.8"><path d="M20 6L9 17l-5-5"/></svg>
        ) : status === "error" ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.8"><path d="M18 6L6 18M6 6l12 12"/></svg>
        ) : num}
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: isActive ? NAVY : "hsl(220 30% 20%)", lineHeight: 1.2 }}>{label}</div>
        <div style={{ fontSize: "0.5625rem", color: SLATE, lineHeight: 1.2 }}>{sublabel}</div>
      </div>
    </button>
  );
}

// ── Log line ───────────────────────────────────────────────────────────────
function LogLine({ text, type = "info" }: { text: string; type?: "info" | "success" | "error" | "warn" }) {
  const color = type === "success" ? GREEN : type === "error" ? RED : type === "warn" ? GOLD : "hsl(220 25% 30%)";
  const prefix = type === "success" ? "✓" : type === "error" ? "✗" : type === "warn" ? "⚠" : "·";
  return (
    <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start", padding: "0.15rem 0" }}>
      <span style={{ color, fontWeight: 700, flexShrink: 0, fontSize: "0.75rem" }}>{prefix}</span>
      <span style={{ color, fontSize: "0.6875rem", lineHeight: 1.5 }}>{text}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
export default function PipelinePage() {
  const [activeStage, setActiveStage] = useState(0);
  const [stageResults, setStageResults] = useState<StageResult[]>(
    Array(5).fill({ status: "pending" as StageStatus, message: "" })
  );
  const [logs, setLogs] = useState<{ text: string; type: string }[]>([]);
  const [dataset, setDataset] = useState<DatasetStatistics | null>(null);
  const [params, setParams]   = useState<ParameterSetResponse | null>(null);
  const [paramEdits, setParamEdits] = useState<Record<string, unknown>>({});
  const [originalParams, setOriginalParams] = useState<Record<string, unknown>>({});
  const [allDatasets, setAllDatasets] = useState<Record<string, DatasetStatistics>>({});
  const logEndRef    = useRef<HTMLDivElement>(null);

  // Auto-load dataset + params + metrics status on mount
  useEffect(() => {
    const autoInit = async () => {
      try {
        const statsRaw = await getStatistics() as any;
        const statsMap: Record<string, DatasetStatistics> = statsRaw?.datasets ?? statsRaw;
        const entries = Object.entries(statsMap).filter(
          ([, v]) => v && typeof v === "object" && "dataset_id" in v
        );
        if (entries.length > 0) {
          const dsMap = Object.fromEntries(entries) as Record<string, DatasetStatistics>;
          setAllDatasets(dsMap);
          const ds = entries[0][1] as DatasetStatistics;
          setDataset(ds);
          const companiesCount = ds.companies?.count;
          setStage(0, {
            status: "done",
            message: `${entries.length} dataset${entries.length > 1 ? "s" : ""} available${companiesCount ? ` · ${companiesCount} companies` : ""}`,
            detail: ds.data_coverage?.min_year
              ? `FY ${ds.data_coverage.min_year}–${ds.data_coverage.max_year} · Country: ${ds.country || "AU"}`
              : `Dataset: ${ds.dataset_id.slice(0, 8)}…`,
          });

          const p = await getActiveParameters();
          setParams(p);
          setParamEdits({ ...p.parameters });
          setOriginalParams({ ...p.parameters });
          setStage(1, {
            status: "done",
            message: `Active: ${p.param_set_name}`,
            detail: `Ke: ${p.parameters.cost_of_equity_approach} · ERP: ${p.parameters.equity_risk_premium}%`,
          });

          try {
            const ex = await metricsExist(ds.dataset_id, p.param_set_id);
            if (ex.exists) {
              setStage(2, { status: "done", message: "L1 metrics already computed", detail: "Re-run to recompute" });
              setStage(3, { status: "done", message: "Runtime metrics already computed", detail: "Re-run to recompute" });
              setStage(4, { status: "done", message: "Metrics verified — Dashboard ready", detail: "All principle pages show live data" });
            }
          } catch (_) { /* metrics may not exist yet */ }
        }
      } catch (_) { /* user can manually run stages */ }
    };
    autoInit();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const addLog = useCallback((text: string, type: "info" | "success" | "error" | "warn" = "info") => {
    setLogs(l => [...l, { text, type }]);
    setTimeout(() => logEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }, []);

  const setStage = useCallback((idx: number, result: Partial<StageResult>) => {
    setStageResults(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], ...result };
      return next;
    });
  }, []);

  // ── Stage 1: Data Selection ──────────────────────────────────────────────
  const runIngestion = useCallback(async () => {
    setActiveStage(0);
    setStage(0, { status: "running", message: "Loading available datasets…" });
    addLog("Stage 1: Data Selection — fetching datasets from backend…");
    const t0 = Date.now();
    try {
      const statsRaw = await getStatistics() as any;
      const statsMap: Record<string, DatasetStatistics> = statsRaw?.datasets ?? statsRaw;
      const entries = Object.entries(statsMap).filter(
        ([, v]) => v && typeof v === "object" && "dataset_id" in v
      );
      if (entries.length === 0) {
        setStage(0, { status: "error", message: "No datasets found in database" });
        addLog("No datasets found in backend. Please ingest Bloomberg data first.", "error");
        return;
      }
      const dsMap = Object.fromEntries(entries) as Record<string, DatasetStatistics>;
      setAllDatasets(dsMap);
      // Auto-select the first (most recent) dataset
      const ds = entries[0][1] as DatasetStatistics;
      setDataset(ds);
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      const companiesCount = ds.companies?.count;
      const rawCount = ds.raw_metrics?.count;
      setStage(0, {
        status: "done",
        message: `${entries.length} dataset${entries.length > 1 ? "s" : ""} available${companiesCount ? ` · ${companiesCount} companies` : ""}`,
        detail: ds.data_coverage?.min_year
          ? `FY ${ds.data_coverage.min_year}–${ds.data_coverage.max_year} · ${rawCount?.toLocaleString() ?? "—"} raw records`
          : `Dataset ID: ${ds.dataset_id.slice(0, 8)}…`,
        records: rawCount ?? undefined,
        seconds: Number(elapsed),
      });
      addLog(`Found ${entries.length} dataset(s) in backend`, "success");
      addLog(`Auto-selected: ${ds.dataset_id} — ${companiesCount ?? "?"} companies, ${ds.sectors?.count ?? "?"} sectors`, "success");
      addLog(`Coverage: FY ${ds.data_coverage?.min_year ?? "?"} → FY ${ds.data_coverage?.max_year ?? "?"} · Country: ${ds.country || "AU"}`, "info");
      addLog(`Elapsed: ${elapsed}s`, "info");
      setActiveStage(1);
    } catch (err: any) {
      setStage(0, { status: "error", message: err.message || "Connection failed" });
      addLog(`Connection error: ${err.message}`, "error");
    }
  }, [addLog, setStage]);

  // ── Stage 2: Parameter Configuration ───────────────────────────────────
  const loadParams = useCallback(async () => {
    setActiveStage(1);
    setStage(1, { status: "running", message: "Fetching active parameters…" });
    addLog("Stage 2: Loading active parameter set…");
    try {
      const p = await getActiveParameters();
      setParams(p);
      setParamEdits({ ...p.parameters });
      setOriginalParams({ ...p.parameters });
      setStage(1, {
        status: "done",
        message: `Active: ${p.param_set_name}`,
        detail: `Ke approach: ${p.parameters.cost_of_equity_approach} · ERP: ${p.parameters.equity_risk_premium}%`,
      });
      addLog(`Loaded param set: ${p.param_set_name}`, "success");
      addLog(`Ke approach: ${p.parameters.cost_of_equity_approach} · ERP: ${p.parameters.equity_risk_premium}%`, "info");
      addLog(`Beta rounding: ${p.parameters.beta_rounding} · Terminal year: ${p.parameters.terminal_year}`, "info");
      setActiveStage(2);
    } catch (err: any) {
      setStage(1, { status: "error", message: err.message });
      addLog(`Parameter load failed: ${err.message}`, "error");
    }
  }, [addLog, setStage]);

  // ── Stage 3: L1 Metrics ─────────────────────────────────────────────────
  const runL1 = useCallback(async () => {
    if (!dataset || !params) { addLog("Run ingestion and load params first", "warn"); return; }
    setActiveStage(2);
    setStage(2, { status: "running", message: "Running L1 orchestrator (11 metrics, 4 parallel groups)…" });
    addLog("Stage 3: L1 Pre-Computation — 11 metrics in 4 parallel groups…");
    addLog("Phase 1A: Calc MC, Calc Assets, Calc OA (parallel)…", "info");
    addLog("Phase 1B: Calc Op Cost, Calc Non Op Cost, Calc Tax Cost, Calc XO Cost (parallel)…", "info");
    addLog("Phase 2:  Calc ECF, Non Div ECF, Calc EE, Calc FY TSR (sequential)…", "info");
    const t0 = Date.now();
    try {
      const res = await orchestrateL1Metrics(dataset.dataset_id, params.param_set_id);
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      if (res.success) {
        setStage(2, {
          status: "done",
          message: `${res.total_successful} metrics computed`,
          detail: `${(res.total_records_inserted || 0).toLocaleString()} records · ${elapsed}s`,
          records: res.total_records_inserted,
          seconds: Number(elapsed),
        });
        addLog(`L1 complete: ${res.total_successful}/13 metrics ✓`, "success");
        if (res.total_failed > 0) addLog(`${res.total_failed} metrics failed — check backend logs`, "warn");
        addLog(`Records inserted: ${(res.total_records_inserted || 0).toLocaleString()} · Time: ${elapsed}s`, "info");
        // Also run L2 Core immediately after
        addLog("Running L2 Core (EP, PAT_EX, FC)…", "info");
        try {
          await calculateL2Core(dataset.dataset_id, params.param_set_id);
          addLog("L2 Core complete: EP, PAT_EX, FC computed", "success");
        } catch (_) { addLog("L2 Core skipped (may already exist)", "warn"); }
        setActiveStage(3);
      } else {
        setStage(2, { status: "error", message: `${res.total_failed} metrics failed` });
        addLog(`L1 failed: ${res.total_failed} errors`, "error");
        (res.errors || []).forEach(e => addLog(e, "error"));
      }
    } catch (err: any) {
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      setStage(2, { status: "error", message: err.message });
      addLog(`L1 error after ${elapsed}s: ${err.message}`, "error");
    }
  }, [dataset, params, addLog, setStage]);

  // ── Stage 4: Runtime Metrics ────────────────────────────────────────────
  const runRuntime = useCallback(async () => {
    if (!dataset || !params) { addLog("Complete previous stages first", "warn"); return; }
    setActiveStage(3);
    setStage(3, { status: "running", message: "Running full runtime orchestrator (Beta → Rf → Ke → FV-ECF → TER → TER Alpha)…" });
    addLog("Stage 4: Runtime Metrics — 6-phase orchestration…");
    const t0 = Date.now();
    try {
      // Run full runtime orchestrator (handles all phases)
      const res = await runRuntimeMetrics(dataset.dataset_id, params.param_set_id);
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);

      const completed = res.metrics_completed || {};
      const phases = Object.entries(completed);
      let totalRecords = 0;
      phases.forEach(([name, detail]: [string, any]) => {
        totalRecords += detail.records_inserted || 0;
        if (detail.status === "success") {
          addLog(`  ${name}: ${(detail.records_inserted || 0).toLocaleString()} records · ${detail.time_seconds?.toFixed(1)}s`, "success");
        } else {
          addLog(`  ${name}: ${detail.status}`, detail.status === "error" ? "error" : "warn");
        }
      });

      setStage(3, {
        status: res.success ? "done" : "error",
        message: res.success ? `${phases.length} phase(s) complete` : "Some phases failed",
        detail: `${totalRecords.toLocaleString()} records · ${elapsed}s`,
        records: totalRecords,
        seconds: Number(elapsed),
      });
      if (res.success) {
        addLog(`Runtime complete: ${totalRecords.toLocaleString()} records · ${elapsed}s`, "success");
        setActiveStage(4);
      } else {
        addLog(`Runtime partial: check phase results above`, "warn");
      }
    } catch (err: any) {
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      addLog(`Runtime orchestrator failed after ${elapsed}s: ${err.message}`, "error");
      addLog("Falling back to individual phase endpoints…", "warn");
      // Fallback: run each phase individually
      const phases = [
        { name: "Beta Rounding",      fn: () => calculateBetaFromPrecomputed(dataset.dataset_id, params.param_set_id) },
        { name: "Risk-Free Rate (Rf)", fn: () => calculateRates(dataset.dataset_id, params.param_set_id) },
        { name: "Cost of Equity (Ke)", fn: () => calculateCostOfEquity(dataset.dataset_id, params.param_set_id) },
        { name: "FV-ECF (4 intervals)",fn: () => calculateFvEcf(dataset.dataset_id, params.param_set_id) },
        { name: "TER & TER-Ke",        fn: () => calculateTer(dataset.dataset_id, params.param_set_id) },
        { name: "TER Alpha",           fn: () => calculateTerAlpha(dataset.dataset_id, params.param_set_id) },
      ];
      let allOk = true;
      let totalRecs = 0;
      for (const phase of phases) {
        try {
          addLog(`  Running ${phase.name}…`, "info");
          const r: any = await phase.fn();
          const recs = r.records_inserted || r.results_count || 0;
          totalRecs += recs;
          addLog(`  ✓ ${phase.name}: ${recs} records`, "success");
        } catch (pe: any) {
          addLog(`  ✗ ${phase.name}: ${pe.message}`, "error");
          allOk = false;
        }
      }
      const elapsed2 = ((Date.now() - t0) / 1000).toFixed(1);
      setStage(3, {
        status: allOk ? "done" : "error",
        message: allOk ? "All phases complete" : "Some phases failed",
        detail: `${totalRecs.toLocaleString()} records · ${elapsed2}s`,
        records: totalRecs,
        seconds: Number(elapsed2),
      });
      if (allOk) setActiveStage(4);
    }
  }, [dataset, params, addLog, setStage]);

  // ── Stage 5: Results ────────────────────────────────────────────────────
  const checkResults = useCallback(async () => {
    if (!dataset || !params) { addLog("Complete pipeline stages first", "warn"); return; }
    setActiveStage(4);
    setStage(4, { status: "running", message: "Verifying computed metrics…" });
    addLog("Stage 5: Verifying results…");
    try {
      const exists = await metricsExist(dataset.dataset_id, params.param_set_id);
      if (exists.exists) {
        setStage(4, { status: "done", message: "Metrics verified — Dashboard ready", detail: "All principle pages now show live data" });
        addLog("All metrics verified in database ✓", "success");
        addLog("Dashboard pages are now displaying live computed data", "success");
        addLog("Navigate to any Principle page to view results", "info");
      } else {
        setStage(4, { status: "error", message: "Metrics not found — re-run pipeline" });
        addLog("Metrics not found in database — try running pipeline again", "error");
      }
    } catch (err: any) {
      setStage(4, { status: "error", message: err.message });
      addLog(`Verification failed: ${err.message}`, "error");
    }
  }, [dataset, params, addLog, setStage]);

  const stageActions = [runIngestion, loadParams, runL1, runRuntime, checkResults];
  const stageConfigs = [
    { label: "Data Selection",    sublabel: "Select DB",  status: stageResults[0].status },
    { label: "Parameters",        sublabel: "Configure", status: stageResults[1].status },
    { label: "L1 Metrics",        sublabel: "Phase 1–2", status: stageResults[2].status },
    { label: "Runtime Metrics",   sublabel: "Phase 3–5", status: stageResults[3].status },
    { label: "Results",           sublabel: "Dashboard", status: stageResults[4].status },
  ];

  const runAll = useCallback(async () => {
    addLog("═══ FULL PIPELINE RUN ═══", "info");
    await runIngestion();
    // wait a tick so state updates
    await new Promise(r => setTimeout(r, 300));
    await loadParams();
    await new Promise(r => setTimeout(r, 300));
    await runL1();
    await new Promise(r => setTimeout(r, 300));
    await runRuntime();
    await new Promise(r => setTimeout(r, 300));
    await checkResults();
  }, [runIngestion, loadParams, runL1, runRuntime, checkResults, addLog]);

  return (
    <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem", maxWidth: 1400 }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontSize: "1.125rem", fontWeight: 800, color: "hsl(220 35% 12%)", margin: 0, letterSpacing: "-0.02em" }}>
            ETL Pipeline — Data Processing Workflow
          </h1>
          <p style={{ fontSize: "0.75rem", color: SLATE, margin: "0.25rem 0 0" }}>
            Bloomberg Excel → PostgreSQL → L1 Metrics → Runtime Metrics → Dashboard
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={runAll}
            style={{
              display: "flex", alignItems: "center", gap: "0.375rem",
              padding: "0.5rem 1rem",
              background: NAVY, color: "#fff",
              border: "none", borderRadius: 8,
              fontSize: "0.8125rem", fontWeight: 700,
              cursor: "pointer",
              boxShadow: "0 2px 8px hsl(213 75% 22% / 0.3)",
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            Run Full Pipeline
          </button>
        </div>
      </div>

      {/* ── Stage stepper ────────────────────────────────────────────────── */}
      <div style={{
        background: "#fff",
        borderRadius: 12,
        border: "1px solid hsl(210 16% 90%)",
        padding: "1.5rem",
        boxShadow: "0 1px 4px hsl(213 40% 50% / 0.06)",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
          {stageConfigs.map((stage, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center" }}>
              <StageNode
                num={i + 1}
                label={stage.label}
                sublabel={stage.sublabel}
                status={stage.status}
                isActive={activeStage === i}
                onClick={() => { setActiveStage(i); stageActions[i](); }}
              />
              {i < stageConfigs.length - 1 && (
                <div style={{
                  width: 60, height: 2,
                  background: stageResults[i].status === "done"
                    ? GREEN
                    : stageResults[i].status === "running"
                      ? GOLD
                      : "hsl(210 16% 88%)",
                  transition: "background 0.4s",
                  margin: "0 0.25rem",
                  marginTop: "-1.5rem",
                }} />
              )}
            </div>
          ))}
        </div>

        {/* Stage result summary */}
        {stageResults[activeStage].message && (
          <div style={{
            marginTop: "1.25rem",
            padding: "0.75rem 1rem",
            borderRadius: 8,
            background: stageResults[activeStage].status === "done"
              ? "hsl(152 60% 40% / 0.07)"
              : stageResults[activeStage].status === "error"
                ? "hsl(0 65% 50% / 0.07)"
                : "hsl(38 60% 52% / 0.07)",
            border: `1px solid ${
              stageResults[activeStage].status === "done"
                ? "hsl(152 60% 40% / 0.25)"
                : stageResults[activeStage].status === "error"
                  ? "hsl(0 65% 50% / 0.25)"
                  : "hsl(38 60% 52% / 0.25)"
            }`,
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
          }}>
            {stageResults[activeStage].status === "running" && <Spinner size={16} />}
            <div>
              <div style={{ fontSize: "0.8125rem", fontWeight: 700, color: "hsl(220 35% 15%)" }}>
                {stageResults[activeStage].message}
              </div>
              {stageResults[activeStage].detail && (
                <div style={{ fontSize: "0.6875rem", color: SLATE, marginTop: "0.125rem" }}>
                  {stageResults[activeStage].detail}
                </div>
              )}
            </div>
            {stageResults[activeStage].records !== undefined && (
              <div style={{ marginLeft: "auto", textAlign: "right" }}>
                <div style={{ fontSize: "1.0625rem", fontWeight: 800, color: NAVY, letterSpacing: "-0.02em" }}>
                  {stageResults[activeStage].records!.toLocaleString()}
                </div>
                <div style={{ fontSize: "0.5625rem", color: SLATE, textTransform: "uppercase", letterSpacing: "0.04em" }}>records</div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Main content: 2 columns ──────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", alignItems: "start" }}>

        {/* Left: Stage detail panels */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

          {/* Stage 1: Data Selection */}
          <StagePanel
            num={1} title="Data Selection" status={stageResults[0].status}
            onRun={runIngestion} active={activeStage === 0}
          >
            {Object.keys(allDatasets).length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div style={{ fontSize: "0.6875rem", color: SLATE, marginBottom: "0.25rem" }}>Select a dataset to use for this pipeline run:</div>
                {Object.entries(allDatasets).map(([key, ds]) => {
                  const isSelected = dataset?.dataset_id === ds.dataset_id;
                  return (
                    <div
                      key={key}
                      onClick={() => {
                        setDataset(ds);
                        addLog(`Dataset selected: ${ds.dataset_id}`, "info");
                      }}
                      style={{
                        padding: "0.625rem 0.75rem",
                        borderRadius: 8,
                        border: `2px solid ${isSelected ? NAVY : "hsl(210 16% 88%)"}`,
                        background: isSelected ? "hsl(213 75% 22% / 0.06)" : "#fff",
                        cursor: "pointer",
                        transition: "all 0.15s",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.375rem" }}>
                        <div style={{ fontSize: "0.75rem", fontWeight: 700, color: NAVY, fontFamily: "monospace" }}>{ds.dataset_id}</div>
                        {isSelected && (
                          <span style={{ fontSize: "0.5625rem", fontWeight: 800, background: NAVY, color: "#fff", padding: "0.15rem 0.5rem", borderRadius: 999 }}>SELECTED</span>
                        )}
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "0.375rem" }}>
                        {[
                          { label: "Companies", value: ds.companies?.count ?? "—" },
                          { label: "Sectors",   value: ds.sectors?.count ?? "—" },
                          { label: "Min Year",  value: ds.data_coverage?.min_year ?? "—" },
                          { label: "Max Year",  value: ds.data_coverage?.max_year ?? "—" },
                        ].map(kv => (
                          <div key={kv.label} style={{ padding: "0.3rem 0.4rem", background: "hsl(213 40% 97%)", borderRadius: 5 }}>
                            <div style={{ fontSize: "0.5rem", color: SLATE, textTransform: "uppercase", fontWeight: 700 }}>{kv.label}</div>
                            <div style={{ fontSize: "0.875rem", fontWeight: 800, color: NAVY }}>{kv.value}</div>
                          </div>
                        ))}
                      </div>
                      <div style={{ fontSize: "0.5625rem", color: SLATE, marginTop: "0.3rem" }}>
                        {ds.raw_metrics?.count != null ? ds.raw_metrics.count.toLocaleString() : "—"} raw records · Country: {ds.country || "AU"} · Created: {ds.dataset_created_at ? new Date(ds.dataset_created_at).toLocaleDateString() : "—"}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: "1.25rem 1rem" }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={SLATE} strokeWidth="1.5" style={{ margin: "0 auto 0.625rem", display: "block" }}>
                  <ellipse cx="12" cy="5" rx="9" ry="3"/>
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                </svg>
                <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "hsl(220 30% 35%)", marginBottom: "0.25rem" }}>No datasets loaded yet</div>
                <div style={{ fontSize: "0.6875rem", color: SLATE }}>Click <b>Run</b> to connect and fetch available datasets from the backend database.</div>
              </div>
            )}
          </StagePanel>

          {/* Stage 2: Parameters */}
          <StagePanel
            num={2} title="Parameter Configuration" status={stageResults[1].status}
            onRun={loadParams} active={activeStage === 1}
          >
            {params ? (() => {
              // Compute which keys have changed from original
              const changedKeys = new Set(
                Object.entries(paramEdits).filter(([key, val]) => {
                  const orig = originalParams[key];
                  const meta = PARAM_META[key];
                  const coerce = (v: unknown) => meta?.type === "number" ? Number(v) : meta?.type === "boolean" ? Boolean(v) : v;
                  return String(coerce(val)) !== String(coerce(orig));
                }).map(([key]) => key)
              );

              const handleSave = async () => {
                try {
                  const coerced: Record<string, unknown> = {};
                  for (const [key, val] of Object.entries(paramEdits)) {
                    const meta = PARAM_META[key];
                    if (meta?.type === "number") coerced[key] = Number(val);
                    else if (meta?.type === "boolean") coerced[key] = Boolean(val);
                    else coerced[key] = val;
                  }
                  const changed: Record<string, unknown> = {};
                  for (const [key, val] of Object.entries(coerced)) {
                    const orig = originalParams[key];
                    const origCoerced = PARAM_META[key]?.type === "number" ? Number(orig)
                      : PARAM_META[key]?.type === "boolean" ? Boolean(orig) : orig;
                    if (String(val) !== String(origCoerced)) changed[key] = val;
                  }
                  if (Object.keys(changed).length === 0) {
                    addLog("No parameters changed — nothing to save", "warn");
                    return;
                  }
                  addLog(`Saving ${Object.keys(changed).length} changed parameter(s): ${Object.keys(changed).join(", ")}…`, "info");
                  const result = await updateParameterSet(params.param_set_id, changed, true);
                  setParams(result);
                  setParamEdits({ ...result.parameters });
                  setOriginalParams({ ...result.parameters });
                  addLog(`Parameters saved ✓ — new param set: ${result.param_set_id}`, "success");
                } catch (e: any) { addLog(`Save failed: ${e.message}`, "error"); }
              };

              return (
                <div>
                  {/* Header */}
                  <div style={{
                    display: "flex", alignItems: "flex-start", justifyContent: "space-between",
                    paddingBottom: "0.75rem", marginBottom: "0.75rem",
                    borderBottom: "1px solid hsl(210 16% 92%)",
                  }}>
                    <div>
                      <div style={{ fontSize: "0.5625rem", color: SLATE, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 700, marginBottom: "0.2rem" }}>
                        Active Parameter Set
                      </div>
                      <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "hsl(220 35% 15%)", fontFamily: "ui-monospace, monospace", letterSpacing: "-0.01em" }}>
                        {params.param_set_name}
                      </div>
                      <div style={{ fontSize: "0.5rem", color: SLATE, marginTop: "0.15rem" }}>
                        ID: {params.param_set_id.slice(0, 8)}…
                        {params.is_default ? " · Default" : ""}
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.25rem" }}>
                      <span style={{
                        fontSize: "0.5rem", fontWeight: 800, letterSpacing: "0.07em",
                        background: "hsl(152 60% 40% / 0.1)", color: "hsl(152 42% 28%)",
                        padding: "0.25rem 0.6rem", borderRadius: 999,
                        border: "1px solid hsl(152 60% 40% / 0.25)",
                      }}>
                        ● ACTIVE
                      </span>
                      {changedKeys.size > 0 && (
                        <span style={{
                          fontSize: "0.5rem", fontWeight: 700,
                          background: "hsl(38 60% 52% / 0.12)", color: "hsl(38 50% 32%)",
                          padding: "0.2rem 0.5rem", borderRadius: 999,
                          border: "1px solid hsl(38 60% 52% / 0.3)",
                        }}>
                          {changedKeys.size} unsaved
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Grouped parameters */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem", maxHeight: 340, overflowY: "auto", paddingRight: "2px" }}>
                    {PARAM_GROUPS.map(group => {
                      const groupKeys = group.keys.filter(k => {
                        const v = paramEdits[k] ?? (params.parameters as any)[k];
                        return v !== undefined;
                      });
                      if (groupKeys.length === 0) return null;
                      return (
                        <div key={group.label}>
                          {/* Group header */}
                          <div style={{
                            display: "flex", alignItems: "center", gap: "0.375rem",
                            marginBottom: "0.375rem",
                          }}>
                            <svg width="10" height="10" viewBox="0 0 24 24" style={{ flexShrink: 0, opacity: 0.5 }}>
                              <path d={group.icon} fill={NAVY} />
                            </svg>
                            <div style={{
                              fontSize: "0.5625rem", fontWeight: 800, color: NAVY,
                              textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.65,
                            }}>
                              {group.label}
                            </div>
                          </div>

                          {/* Rows */}
                          <div style={{ borderRadius: 8, border: "1px solid hsl(210 16% 91%)", overflow: "hidden" }}>
                            {groupKeys.map((key, idx) => {
                              const meta = PARAM_META[key];
                              if (!meta) return null;
                              const val = paramEdits[key] ?? (params.parameters as any)[key];
                              const isChanged = changedKeys.has(key);
                              const isLast = idx === groupKeys.length - 1;
                              return (
                                <div
                                  key={key}
                                  style={{
                                    display: "flex", alignItems: "center", gap: "0.625rem",
                                    padding: "0.5rem 0.625rem",
                                    background: isChanged ? "hsl(213 75% 22% / 0.04)" : idx % 2 === 0 ? "#fff" : "hsl(210 20% 99%)",
                                    borderLeft: `3px solid ${isChanged ? NAVY : "transparent"}`,
                                    borderBottom: isLast ? "none" : "1px solid hsl(210 16% 93%)",
                                    transition: "background 0.15s",
                                  }}
                                >
                                  <label style={{
                                    fontSize: "0.6875rem", flex: 1, lineHeight: 1.3,
                                    color: isChanged ? "hsl(220 40% 14%)" : "hsl(220 15% 40%)",
                                    fontWeight: isChanged ? 600 : 400,
                                  }}>
                                    {meta.label}
                                  </label>
                                  {meta.type === "boolean" ? (
                                    <Toggle on={!!val} onChange={v => setParamEdits(p => ({ ...p, [key]: v }))} />
                                  ) : meta.type === "select" ? (
                                    <select
                                      value={String(val)}
                                      onChange={e => setParamEdits(p => ({ ...p, [key]: e.target.value }))}
                                      style={{
                                        fontSize: "0.6875rem", padding: "0.3rem 0.4rem",
                                        borderRadius: 6,
                                        border: `1px solid ${isChanged ? "hsl(213 75% 22% / 0.45)" : "hsl(210 16% 85%)"}`,
                                        background: "#fff", color: "hsl(220 35% 15%)",
                                        fontWeight: 500, cursor: "pointer", minWidth: 100,
                                      }}
                                    >
                                      {meta.options?.map(o => <option key={o} value={o}>{o}</option>)}
                                    </select>
                                  ) : (
                                    <input
                                      type="number"
                                      value={Number(val)}
                                      onChange={e => setParamEdits(p => ({ ...p, [key]: Number(e.target.value) }))}
                                      style={{
                                        width: 72, fontSize: "0.6875rem",
                                        padding: "0.3rem 0.5rem", borderRadius: 6,
                                        border: `1px solid ${isChanged ? "hsl(213 75% 22% / 0.45)" : "hsl(210 16% 85%)"}`,
                                        textAlign: "right", color: "hsl(220 35% 15%)",
                                        fontWeight: isChanged ? 700 : 400,
                                        background: isChanged ? "hsl(213 75% 22% / 0.03)" : "#fff",
                                      }}
                                    />
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Save footer */}
                  <div style={{
                    marginTop: "0.875rem", paddingTop: "0.75rem",
                    borderTop: "1px solid hsl(210 16% 92%)",
                    display: "flex", alignItems: "center", gap: "0.5rem",
                  }}>
                    {changedKeys.size > 0 ? (
                      <div style={{ fontSize: "0.5625rem", color: "hsl(38 50% 32%)", fontWeight: 600 }}>
                        {changedKeys.size} unsaved change{changedKeys.size > 1 ? "s" : ""}
                      </div>
                    ) : (
                      <div style={{ fontSize: "0.5625rem", color: SLATE }}>No changes</div>
                    )}
                    <button
                      onClick={handleSave}
                      style={{
                        marginLeft: "auto",
                        display: "flex", alignItems: "center", gap: "0.375rem",
                        padding: "0.45rem 1rem", borderRadius: 7,
                        background: changedKeys.size > 0 ? NAVY : "hsl(210 16% 93%)",
                        color: changedKeys.size > 0 ? "#fff" : SLATE,
                        border: "none", fontWeight: 700, fontSize: "0.6875rem",
                        cursor: changedKeys.size > 0 ? "pointer" : "default",
                        transition: "all 0.2s",
                        boxShadow: changedKeys.size > 0 ? "0 2px 6px hsl(213 75% 22% / 0.25)" : "none",
                      }}
                    >
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                        <polyline points="17 21 17 13 7 13 7 21"/>
                        <polyline points="7 3 7 8 15 8"/>
                      </svg>
                      Save Parameters
                    </button>
                  </div>
                </div>
              );
            })() : (
              <div style={{ textAlign: "center", padding: "1.25rem 1rem" }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={SLATE} strokeWidth="1.5" style={{ margin: "0 auto 0.5rem", display: "block" }}>
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
                </svg>
                <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "hsl(220 30% 35%)", marginBottom: "0.25rem" }}>Parameters not loaded</div>
                <div style={{ fontSize: "0.6875rem", color: SLATE }}>Click <b>Run</b> to fetch the active parameter set from the backend.</div>
              </div>
            )}
          </StagePanel>
        </div>

        {/* Right: Stages 3–5 + log */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

          {/* Stage 3: L1 */}
          <StagePanel num={3} title="L1 Metrics Computation" status={stageResults[2].status} onRun={runL1} active={activeStage === 2}>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
              {[
                { phase: "Phase 1A", metrics: "Calc MC, Calc Assets, Calc OA", parallel: true },
                { phase: "Phase 1B", metrics: "Calc Op Cost, Non Op Cost, Tax Cost, XO Cost", parallel: true },
                { phase: "Phase 2",  metrics: "Calc ECF, Non Div ECF, Calc EE, Calc FY TSR", parallel: false },
                { phase: "L2 Core", metrics: "EP, PAT_EX, XO_COST_EX, FC", parallel: false },
              ].map(p => (
                <div key={p.phase} style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", padding: "0.375rem 0.5rem", borderRadius: 6, background: "hsl(210 20% 98%)", border: "1px solid hsl(210 16% 90%)" }}>
                  <div style={{ width: 52, flexShrink: 0 }}>
                    <div style={{ fontSize: "0.5625rem", fontWeight: 800, color: NAVY, textTransform: "uppercase" }}>{p.phase}</div>
                    {p.parallel && <div style={{ fontSize: "0.5rem", color: GREEN, fontWeight: 700 }}>‖ PARALLEL</div>}
                  </div>
                  <div style={{ fontSize: "0.6875rem", color: "hsl(220 20% 30%)", lineHeight: 1.4 }}>{p.metrics}</div>
                  <div style={{ marginLeft: "auto", flexShrink: 0 }}>
                    {stageResults[2].status === "done" ? (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={GREEN} strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
                    ) : stageResults[2].status === "running" ? (
                      <Spinner size={12} />
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </StagePanel>

          {/* Stage 4: Runtime */}
          <StagePanel num={4} title="Runtime Metrics" status={stageResults[3].status} onRun={runRuntime} active={activeStage === 3}>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              {[
                { name: "Beta Rounding",     detail: "4-tier fallback, pre-computed" },
                { name: "Risk-Free Rate Rf", detail: "Fixed or floating approach" },
                { name: "Cost of Equity Ke", detail: "Ke = Rf + Beta × MRP" },
                { name: "FV-ECF",            detail: "4 intervals: 1Y/3Y/5Y/10Y" },
                { name: "TER & TER-Ke",      detail: "Total Expense Ratio · 4 intervals" },
                { name: "TER Alpha",         detail: "Risk-adjusted outperformance" },
              ].map((m, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.3rem 0.5rem", borderRadius: 6, background: "hsl(210 20% 98%)", border: "1px solid hsl(210 16% 90%)" }}>
                  <div style={{
                    width: 20, height: 20, borderRadius: "50%", flexShrink: 0,
                    background: stageResults[3].status === "done" ? GREEN : stageResults[3].status === "running" ? GOLD : "hsl(210 16% 88%)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    {stageResults[3].status === "done" ? (
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
                    ) : stageResults[3].status === "running" ? (
                      <Spinner size={10} />
                    ) : <span style={{ fontSize: "0.5rem", color: SLATE, fontWeight: 700 }}>{i + 1}</span>}
                  </div>
                  <div>
                    <div style={{ fontSize: "0.6875rem", fontWeight: 600, color: "hsl(220 25% 20%)" }}>{m.name}</div>
                    <div style={{ fontSize: "0.5625rem", color: SLATE }}>{m.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </StagePanel>

          {/* Stage 5: Results */}
          <StagePanel num={5} title="Results & Dashboard" status={stageResults[4].status} onRun={checkResults} active={activeStage === 4}>
            {stageResults[4].status === "done" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div style={{ padding: "0.75rem", background: "hsl(152 60% 40% / 0.08)", borderRadius: 8, border: "1px solid hsl(152 60% 40% / 0.25)", textAlign: "center" }}>
                  <div style={{ fontSize: "0.875rem", fontWeight: 800, color: "hsl(152 50% 28%)" }}>Pipeline Complete ✓</div>
                  <div style={{ fontSize: "0.6875rem", color: SLATE, marginTop: "0.25rem" }}>All metrics computed and verified</div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.375rem" }}>
                  {[
                    { label: "Dashboard", path: "/" },
                    { label: "Principle 1", path: "/principles/1" },
                    { label: "Principle 2", path: "/principles/2" },
                    { label: "Principle 3", path: "/principles/3" },
                    { label: "Principle 4", path: "/principles/4" },
                    { label: "Download", path: "/download" },
                  ].map(l => (
                    <Link key={l.path} href={l.path}>
                      <a style={{
                        display: "block", textAlign: "center",
                        padding: "0.4rem 0.5rem",
                        background: "hsl(213 40% 97%)", borderRadius: 6,
                        border: "1px solid hsl(213 30% 88%)",
                        fontSize: "0.6875rem", fontWeight: 600, color: NAVY,
                        textDecoration: "none",
                      }}>
                        {l.label} →
                      </a>
                    </Link>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ color: SLATE, fontSize: "0.75rem", textAlign: "center", padding: "1rem" }}>
                Complete all stages to view results
              </div>
            )}
          </StagePanel>
        </div>
      </div>

      {/* ── Log console ───────────────────────────────────────────────────── */}
      <div style={{
        background: "hsl(220 30% 8%)",
        borderRadius: 10,
        border: "1px solid hsl(220 20% 18%)",
        padding: "0.875rem 1rem",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.625rem" }}>
          <div style={{ display: "flex", gap: "0.3rem" }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: "hsl(0 65% 55%)" }} />
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: "hsl(38 70% 52%)" }} />
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: "hsl(120 50% 45%)" }} />
          </div>
          <span style={{ fontSize: "0.6875rem", color: "hsl(220 15% 55%)", fontWeight: 600 }}>Pipeline Log</span>
          {logs.length > 0 && (
            <button onClick={() => setLogs([])}
              style={{ marginLeft: "auto", fontSize: "0.5625rem", color: "hsl(220 15% 45%)", background: "none", border: "none", cursor: "pointer" }}>
              Clear
            </button>
          )}
        </div>
        <div style={{ maxHeight: 200, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.1rem" }}>
          {logs.length === 0 ? (
            <span style={{ color: "hsl(220 15% 40%)", fontSize: "0.6875rem" }}>$ awaiting pipeline run…</span>
          ) : (
            logs.map((l, i) => (
              <div key={i} style={{
                fontSize: "0.6875rem", lineHeight: 1.6,
                color: l.type === "success" ? "hsl(120 50% 60%)" : l.type === "error" ? "hsl(0 65% 65%)" : l.type === "warn" ? "hsl(38 70% 62%)" : "hsl(210 20% 70%)",
              }}>
                {l.text}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// ── Stage panel wrapper ────────────────────────────────────────────────────
function StagePanel({
  num, title, status, onRun, active, children,
}: {
  num: number; title: string; status: StageStatus;
  onRun: () => void; active: boolean;
  children?: React.ReactNode;
}) {
  const borderColor = status === "done"   ? "hsl(152 60% 40%)"
    : status === "running" ? "hsl(38 60% 52%)"
    : status === "error"   ? "hsl(0 65% 50%)"
    : active               ? "hsl(213 75% 22%)"
    : "hsl(210 16% 90%)";

  return (
    <div style={{
      background: "#fff",
      borderRadius: 10,
      border: `1px solid ${borderColor}`,
      boxShadow: active ? `0 0 0 2px hsl(213 75% 22% / 0.12)` : "0 1px 4px hsl(213 40% 50% / 0.05)",
      overflow: "hidden",
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: "0.625rem",
        padding: "0.75rem 1rem",
        borderBottom: `1px solid ${active || status !== "pending" ? borderColor : "hsl(210 16% 92%)"}`,
        background: active ? "hsl(213 75% 22% / 0.03)" : "#fff",
      }}>
        <div style={{
          width: 26, height: 26, borderRadius: "50%", flexShrink: 0,
          background: status === "done" ? GREEN : status === "running" ? GOLD : status === "error" ? RED : active ? NAVY : "hsl(210 16% 88%)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "0.6875rem", fontWeight: 800, color: "#fff",
        }}>
          {status === "running" ? <Spinner size={13} /> : status === "done" ? (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
          ) : status === "error" ? (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M18 6L6 18M6 6l12 12"/></svg>
          ) : num}
        </div>
        <span style={{ fontSize: "0.8125rem", fontWeight: 700, color: "hsl(220 35% 12%)", flex: 1 }}>{title}</span>
        <button
          onClick={onRun}
          style={{
            padding: "0.3rem 0.75rem",
            background: status === "done" ? "hsl(152 60% 40% / 0.1)" : active ? NAVY : "hsl(210 20% 95%)",
            color: status === "done" ? "hsl(152 50% 30%)" : active ? "#fff" : "hsl(215 15% 40%)",
            border: "none", borderRadius: 6,
            fontSize: "0.6875rem", fontWeight: 700,
            cursor: "pointer",
          }}
        >
          {status === "done" ? "Re-run" : status === "running" ? "Running…" : "Run"}
        </button>
      </div>
      {children && (
        <div style={{ padding: "0.875rem 1rem" }}>{children}</div>
      )}
    </div>
  );
}
