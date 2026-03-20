/**
 * PipelinePage — CISSA ETL Pipeline (Redesigned)
 * Full-width single-column layout. 5 stages:
 *   1. Data Selection
 *   2. Parameter Configuration (summary + collapsible editor)
 *   3. Runtime Metrics  — POST /api/v1/metrics/runtime-metrics
 *   4. Bow Wave Generation — GET /api/v1/metrics/economic-profitability ×4
 *   5. Results & Dashboard
 */
import { useState, useCallback, useRef, useEffect } from "react";
import {
  getStatistics, getActiveParameters, runRuntimeMetrics,
  getEconomicProfitability, updateParameterSet, metricsExist,
  getMetrics,
  DatasetStatistics, ParameterSetResponse, MetricResultItem,
  EconomicProfitabilityResult,
} from "../lib/api";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as ReTooltip, ResponsiveContainer, Legend,
} from "recharts";
import { Link } from "wouter";

// ── Types ────────────────────────────────────────────────────────────────────
type StageStatus = "pending" | "running" | "done" | "error";

interface StageResult {
  status: StageStatus;
  message: string;
  detail?: string;
  records?: number;
  seconds?: number;
}

interface BowWaveEntry {
  window: "1Y" | "3Y" | "5Y" | "10Y";
  status: StageStatus;
  count: number;
  seconds: number;
}

interface PhaseEntry {
  name: string;
  status: string;
  records: number;
  seconds: number;
}

// ── Color tokens ─────────────────────────────────────────────────────────────
const NAVY  = "hsl(213 75% 22%)";
const GOLD  = "hsl(38 60% 52%)";
const GREEN = "hsl(152 60% 40%)";
const RED   = "hsl(0 65% 50%)";
const SLATE = "hsl(215 15% 46%)";

// ── Runtime metric options ────────────────────────────────────────────────────
const RUNTIME_METRICS = [
  { key: "beta",        label: "Beta" },
  { key: "risk_free_rate", label: "Risk-Free Rate (Rf)" },
  { key: "cost_of_equity", label: "Cost of Equity (Ke)" },
  { key: "fv_ecf_1y",  label: "FV-ECF 1Y" },
  { key: "fv_ecf_3y",  label: "FV-ECF 3Y" },
  { key: "fv_ecf_5y",  label: "FV-ECF 5Y" },
  { key: "fv_ecf_10y", label: "FV-ECF 10Y" },
  { key: "ter",        label: "TER" },
  { key: "ter_ke",     label: "TER-Ke" },
  { key: "ter_alpha",  label: "TER Alpha" },
];

// ── Parameter metadata ───────────────────────────────────────────────────────
const PARAM_META: Record<string, { label: string; type: "number" | "boolean" | "select"; options?: string[] }> = {
  country:                                    { label: "Country",                          type: "select", options: ["Australia", "USA", "UK"] },
  currency_notation:                          { label: "Currency Notation",                type: "select", options: ["A$m", "USD", "GBP"] },
  cost_of_equity_approach:                    { label: "Cost of Equity Approach",          type: "select", options: ["Floating", "Fixed", "CAPM"] },
  equity_risk_premium:                        { label: "Equity Risk Premium (%)",          type: "number" },
  fixed_benchmark_return_wealth_preservation: { label: "Fixed Benchmark Return (%)",       type: "number" },
  tax_rate_franking_credits:                  { label: "Tax Rate — Franking Credits (%)",  type: "number" },
  value_of_franking_credits:                  { label: "Value of Franking Credits (%)",    type: "number" },
  include_franking_credits_tsr:               { label: "Include Franking Credits in TSR",  type: "boolean" },
  beta_rounding:                              { label: "Beta Rounding (decimal places)",   type: "number" },
  risk_free_rate_rounding:                    { label: "Risk-Free Rate Rounding",          type: "number" },
  last_calendar_year:                         { label: "Last Calendar Year",               type: "number" },
  beta_relative_error_tolerance:              { label: "Beta Relative Error Tolerance (%)",type: "number" },
  terminal_year:                              { label: "Terminal Year",                    type: "number" },
};

const PARAM_GROUPS: { label: string; keys: string[] }[] = [
  { label: "Market Configuration", keys: ["country", "currency_notation", "cost_of_equity_approach", "equity_risk_premium", "fixed_benchmark_return_wealth_preservation"] },
  { label: "Franking Credits",     keys: ["include_franking_credits_tsr", "tax_rate_franking_credits", "value_of_franking_credits"] },
  { label: "Technical",            keys: ["beta_rounding", "risk_free_rate_rounding", "beta_relative_error_tolerance", "last_calendar_year", "terminal_year"] },
];

// ── Summary params shown in collapsed view ───────────────────────────────────
const PARAM_SUMMARY_KEYS = [
  { key: "cost_of_equity_approach", label: "Ke Approach" },
  { key: "equity_risk_premium",     label: "ERP" },
  { key: "country",                 label: "Country" },
  { key: "currency_notation",       label: "Currency" },
  { key: "beta_rounding",           label: "Beta Rounding" },
  { key: "include_franking_credits_tsr", label: "Franking Credits" },
];

// ── Toggle switch ────────────────────────────────────────────────────────────
function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" onClick={() => onChange(!on)} style={{
      width: 36, height: 20, borderRadius: 10, flexShrink: 0,
      background: on ? GREEN : "hsl(210 15% 78%)",
      border: "none", cursor: "pointer", padding: 2,
      transition: "background 0.2s", display: "flex", alignItems: "center",
    }}>
      <div style={{
        width: 16, height: 16, borderRadius: "50%", background: "#fff",
        boxShadow: "0 1px 3px rgba(0,0,0,0.3)", transition: "transform 0.2s",
        transform: on ? "translateX(16px)" : "translateX(0)",
      }} />
    </button>
  );
}

// ── Spinner ──────────────────────────────────────────────────────────────────
function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ animation: "spin 0.9s linear infinite" }}>
      <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
      <path d="M22 12a10 10 0 00-10-10" />
    </svg>
  );
}

// ── Stage stepper node ───────────────────────────────────────────────────────
function StageNode({ num, label, sublabel, status, isActive, onClick }: {
  num: number; label: string; sublabel: string;
  status: StageStatus; isActive: boolean; onClick?: () => void;
}) {
  const bg = status === "done" ? GREEN : status === "running" ? GOLD : status === "error" ? RED : "hsl(210 16% 90%)";
  const fg = (status === "done" || status === "running" || status === "error") ? "#fff" : SLATE;
  return (
    <button onClick={onClick} style={{
      display: "flex", flexDirection: "column", alignItems: "center", gap: "0.4rem",
      background: "none", border: "none", cursor: onClick ? "pointer" : "default",
      padding: "0.5rem 0.75rem", borderRadius: 10,
      outline: isActive ? `2px solid ${NAVY}` : "2px solid transparent",
      transition: "all 0.2s", minWidth: 100,
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: "50%",
        background: isActive ? NAVY : bg,
        color: isActive ? "#fff" : fg,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "0.8125rem", fontWeight: 800,
        boxShadow: isActive ? `0 0 0 4px hsl(213 75% 22% / 0.15)` : status === "done" ? `0 0 8px hsl(152 60% 40% / 0.4)` : "none",
        transition: "all 0.2s",
      }}>
        {status === "running" ? <Spinner size={18} />
          : status === "done" ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.8"><path d="M20 6L9 17l-5-5"/></svg>
          : status === "error" ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.8"><path d="M18 6L6 18M6 6l12 12"/></svg>
          : num}
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: isActive ? NAVY : "hsl(220 30% 20%)", lineHeight: 1.2 }}>{label}</div>
        <div style={{ fontSize: "0.5625rem", color: SLATE, lineHeight: 1.2 }}>{sublabel}</div>
      </div>
    </button>
  );
}

// ── Log line ─────────────────────────────────────────────────────────────────
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

// ── Stage panel wrapper ───────────────────────────────────────────────────────
function StagePanel({ num, title, status, onRun, active, children }: {
  num: number; title: string; status: StageStatus;
  onRun: () => void; active: boolean; children?: React.ReactNode;
}) {
  const borderColor = status === "done" ? "hsl(152 60% 40%)"
    : status === "running" ? "hsl(38 60% 52%)"
    : status === "error"   ? "hsl(0 65% 50%)"
    : active               ? "hsl(213 75% 22%)"
    : "hsl(210 16% 90%)";

  return (
    <div style={{
      background: "#fff", borderRadius: 12,
      border: `1px solid ${borderColor}`,
      boxShadow: active ? `0 0 0 3px hsl(213 75% 22% / 0.1)` : "0 1px 4px hsl(213 40% 50% / 0.05)",
      overflow: "hidden",
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: "0.625rem",
        padding: "0.875rem 1.25rem",
        borderBottom: `1px solid ${active || status !== "pending" ? borderColor : "hsl(210 16% 92%)"}`,
        background: active ? "hsl(213 75% 22% / 0.02)" : "#fff",
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
          background: status === "done" ? GREEN : status === "running" ? GOLD : status === "error" ? RED : active ? NAVY : "hsl(210 16% 88%)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "0.6875rem", fontWeight: 800, color: "#fff",
        }}>
          {status === "running" ? <Spinner size={13} />
            : status === "done" ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
            : status === "error" ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M18 6L6 18M6 6l12 12"/></svg>
            : num}
        </div>
        <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "hsl(220 35% 12%)", flex: 1 }}>{title}</span>
        <button onClick={onRun} style={{
          padding: "0.35rem 0.875rem", borderRadius: 6,
          background: status === "done" ? "hsl(152 60% 40% / 0.1)" : active ? NAVY : "hsl(210 20% 95%)",
          color: status === "done" ? "hsl(152 50% 30%)" : active ? "#fff" : "hsl(215 15% 40%)",
          border: "none", fontSize: "0.6875rem", fontWeight: 700, cursor: "pointer",
        }}>
          {status === "running" ? "Running…" : status === "done" ? "Re-run" : "Run"}
        </button>
      </div>
      {children && <div style={{ padding: "1rem 1.25rem" }}>{children}</div>}
    </div>
  );
}

// ── Phase status dot ─────────────────────────────────────────────────────────
function PhaseDot({ status }: { status: "pending" | "running" | "done" | "error" }) {
  if (status === "running") return <Spinner size={12} />;
  if (status === "done") return (
    <div style={{ width: 18, height: 18, borderRadius: "50%", background: GREEN, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
    </div>
  );
  if (status === "error") return (
    <div style={{ width: 18, height: 18, borderRadius: "50%", background: RED, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M18 6L6 18M6 6l12 12"/></svg>
    </div>
  );
  return <div style={{ width: 18, height: 18, borderRadius: "50%", background: "hsl(210 16% 88%)", flexShrink: 0 }} />;
}

// ─────────────────────────────────────────────────────────────────────────────
export default function PipelinePage() {
  const [activeStage, setActiveStage] = useState(0);
  const [stageResults, setStageResults] = useState<StageResult[]>(
    Array(5).fill({ status: "pending" as StageStatus, message: "" })
  );
  const [logs, setLogs]             = useState<{ text: string; type: string }[]>([]);
  const [dataset, setDataset]       = useState<DatasetStatistics | null>(null);
  const [allDatasets, setAllDatasets] = useState<Record<string, DatasetStatistics>>({});
  const [params, setParams]         = useState<ParameterSetResponse | null>(null);
  const [paramEdits, setParamEdits] = useState<Record<string, unknown>>({});
  const [originalParams, setOriginalParams] = useState<Record<string, unknown>>({});
  const [paramExpanded, setParamExpanded]   = useState(false);
  const [runtimePhases, setRuntimePhases]   = useState<PhaseEntry[]>([]);
  const [bowWaveStatus, setBowWaveStatus]   = useState<BowWaveEntry[]>([
    { window: "1Y",  status: "pending", count: 0, seconds: 0 },
    { window: "3Y",  status: "pending", count: 0, seconds: 0 },
    { window: "5Y",  status: "pending", count: 0, seconds: 0 },
    { window: "10Y", status: "pending", count: 0, seconds: 0 },
  ]);
  // Stage 3 chart state
  const [s3Metric, setS3Metric] = useState("cost_of_equity");
  const [s3Ticker, setS3Ticker] = useState("BHP AU Equity");
  const [s3Data,   setS3Data]   = useState<MetricResultItem[]>([]);
  // Stage 4 chart state
  const [s4Window, setS4Window] = useState<"1Y" | "3Y" | "5Y" | "10Y">("1Y");
  const [s4Ticker, setS4Ticker] = useState("BHP AU Equity");
  const [s4Data,   setS4Data]   = useState<EconomicProfitabilityResult[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  // ── Auto-init on mount ────────────────────────────────────────────────────
  useEffect(() => {
    const autoInit = async () => {
      try {
        const statsRaw = await getStatistics() as any;
        const statsMap: Record<string, DatasetStatistics> = statsRaw?.datasets ?? statsRaw;
        const entries = Object.entries(statsMap).filter(([, v]) => v && typeof v === "object" && "dataset_id" in v);
        if (entries.length === 0) return;
        const dsMap = Object.fromEntries(entries) as Record<string, DatasetStatistics>;
        setAllDatasets(dsMap);
        const ds = entries[0][1] as DatasetStatistics;
        setDataset(ds);
        setStage(0, {
          status: "done",
          message: `${entries.length} dataset${entries.length > 1 ? "s" : ""} available · ${ds.companies?.count ?? "?"} companies`,
          detail: `FY ${ds.data_coverage?.min_year ?? "?"}–${ds.data_coverage?.max_year ?? "?"} · ${ds.country || "AU"}`,
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
            setStage(2, { status: "done", message: "Runtime metrics computed", detail: "Re-run to recompute" });
            setStage(3, { status: "done", message: "Bow wave data available", detail: "Re-run to regenerate" });
            setStage(4, { status: "done", message: "Metrics verified — Dashboard ready", detail: "All principle pages show live data" });
          }
        } catch (_) {}
      } catch (_) {}
    };
    autoInit();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stage 4 chart auto-fetch ──────────────────────────────────────────────
  useEffect(() => {
    if (stageResults[3].status !== "done" || !dataset || !params) return;
    getEconomicProfitability({
      dataset_id: dataset.dataset_id,
      parameter_set_id: params.param_set_id,
      temporal_window: s4Window,
      ticker: s4Ticker,
    })
      .then(r => setS4Data(r.results ?? []))
      .catch(() => setS4Data([]));
  }, [stageResults[3].status, s4Window, s4Ticker, dataset, params]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stage 3 chart auto-fetch ──────────────────────────────────────────────
  useEffect(() => {
    if (stageResults[2].status !== "done" || !dataset || !params) return;
    getMetrics({
      dataset_id: dataset.dataset_id,
      parameter_set_id: params.param_set_id,
      metric_name: s3Metric,
      ticker: s3Ticker,
    })
      .then(r => setS3Data(r.results ?? []))
      .catch(() => setS3Data([]));
  }, [stageResults[2].status, s3Metric, s3Ticker, dataset, params]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // ── Stage 1: Data Selection ───────────────────────────────────────────────
  const runIngestion = useCallback(async () => {
    setActiveStage(0);
    setStage(0, { status: "running", message: "Loading available datasets…" });
    addLog("Stage 1: fetching datasets from backend…");
    const t0 = Date.now();
    try {
      const statsRaw = await getStatistics() as any;
      const statsMap: Record<string, DatasetStatistics> = statsRaw?.datasets ?? statsRaw;
      const entries = Object.entries(statsMap).filter(([, v]) => v && typeof v === "object" && "dataset_id" in v);
      if (entries.length === 0) {
        setStage(0, { status: "error", message: "No datasets found in database" });
        addLog("No datasets found. Please ingest Bloomberg data first.", "error");
        return;
      }
      const dsMap = Object.fromEntries(entries) as Record<string, DatasetStatistics>;
      setAllDatasets(dsMap);
      const ds = entries[0][1] as DatasetStatistics;
      setDataset(ds);
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      setStage(0, {
        status: "done",
        message: `${entries.length} dataset${entries.length > 1 ? "s" : ""} available · ${ds.companies?.count ?? "?"} companies`,
        detail: `FY ${ds.data_coverage?.min_year ?? "?"}–${ds.data_coverage?.max_year ?? "?"} · ${ds.country || "AU"}`,
        seconds: Number(elapsed),
      });
      addLog(`Found ${entries.length} dataset(s)`, "success");
      addLog(`Selected: ${ds.dataset_id} — ${ds.companies?.count ?? "?"} companies, ${ds.sectors?.count ?? "?"} sectors`, "success");
      addLog(`FY ${ds.data_coverage?.min_year ?? "?"}–${ds.data_coverage?.max_year ?? "?"} · Country: ${ds.country || "AU"} · ${elapsed}s`, "info");
      setActiveStage(1);
    } catch (err: any) {
      setStage(0, { status: "error", message: err.message || "Connection failed" });
      addLog(`Connection error: ${err.message}`, "error");
    }
  }, [addLog, setStage]);

  // ── Stage 2: Parameters ───────────────────────────────────────────────────
  const loadParams = useCallback(async () => {
    setActiveStage(1);
    setStage(1, { status: "running", message: "Fetching active parameters…" });
    addLog("Stage 2: loading active parameter set…");
    try {
      const p = await getActiveParameters();
      setParams(p);
      setParamEdits({ ...p.parameters });
      setOriginalParams({ ...p.parameters });
      setStage(1, {
        status: "done",
        message: `Active: ${p.param_set_name}`,
        detail: `Ke: ${p.parameters.cost_of_equity_approach} · ERP: ${p.parameters.equity_risk_premium}%`,
      });
      addLog(`Loaded: ${p.param_set_name}`, "success");
      setActiveStage(2);
    } catch (err: any) {
      setStage(1, { status: "error", message: err.message });
      addLog(`Parameter load failed: ${err.message}`, "error");
    }
  }, [addLog, setStage]);

  // ── Stage 3: Runtime Metrics (single endpoint) ────────────────────────────
  const runRuntimeAll = useCallback(async () => {
    if (!dataset || !params) { addLog("Complete previous stages first", "warn"); return; }
    setActiveStage(2);
    setRuntimePhases([]);
    setStage(2, { status: "running", message: "Running runtime metrics orchestrator…" });
    addLog("Stage 3: POST /api/v1/metrics/runtime-metrics — full orchestration…");
    const t0 = Date.now();
    try {
      const res = await runRuntimeMetrics(dataset.dataset_id, params.param_set_id);
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      const completed = res.metrics_completed ?? {};
      const phases: PhaseEntry[] = Object.entries(completed).map(([name, d]: [string, any]) => ({
        name,
        status: d.status ?? "done",
        records: d.records_inserted ?? 0,
        seconds: d.time_seconds ?? 0,
      }));
      setRuntimePhases(phases);
      const totalRecords = phases.reduce((s, p) => s + p.records, 0);
      const failed = phases.filter(p => p.status !== "success" && p.status !== "done").length;
      if (res.success) {
        setStage(2, {
          status: "done",
          message: `${phases.length} phases complete · ${totalRecords.toLocaleString()} records`,
          detail: `${elapsed}s total`,
          records: totalRecords,
          seconds: Number(elapsed),
        });
        phases.forEach(p => {
          const ok = p.status === "success" || p.status === "done";
          addLog(`  ${p.name}: ${p.records.toLocaleString()} records · ${p.seconds.toFixed(1)}s`, ok ? "success" : "warn");
        });
        addLog(`Runtime complete: ${totalRecords.toLocaleString()} records · ${elapsed}s`, "success");
        setActiveStage(3);
      } else {
        setStage(2, { status: failed > 0 ? "error" : "done", message: `${failed} phase(s) failed` });
        addLog(`Runtime finished with ${failed} failure(s)`, failed > 0 ? "error" : "warn");
      }
    } catch (err: any) {
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      setStage(2, { status: "error", message: err.message });
      addLog(`Runtime failed after ${elapsed}s: ${err.message}`, "error");
    }
  }, [dataset, params, addLog, setStage]);

  // ── Stage 4: Bow Wave Generation ──────────────────────────────────────────
  const runBowWave = useCallback(async () => {
    if (!dataset || !params) { addLog("Complete previous stages first", "warn"); return; }
    setActiveStage(3);
    const windows: ("1Y" | "3Y" | "5Y" | "10Y")[] = ["1Y", "3Y", "5Y", "10Y"];
    setBowWaveStatus(windows.map(w => ({ window: w, status: "pending", count: 0, seconds: 0 })));
    setStage(3, { status: "running", message: "Generating bow wave data…" });
    addLog("Stage 4: Bow Wave Generation — EP 1Y / 3Y / 5Y / 10Y…");
    const t0 = Date.now();
    let allOk = true;
    let totalCount = 0;
    for (let i = 0; i < windows.length; i++) {
      const w = windows[i];
      setBowWaveStatus(prev => prev.map(e => e.window === w ? { ...e, status: "running" } : e));
      const wt0 = Date.now();
      try {
        const r = await getEconomicProfitability({
          dataset_id: dataset.dataset_id,
          parameter_set_id: params.param_set_id,
          temporal_window: w,
        });
        const count = r.results_count ?? r.results?.length ?? 0;
        totalCount += count;
        const wElapsed = ((Date.now() - wt0) / 1000);
        setBowWaveStatus(prev => prev.map(e => e.window === w ? { ...e, status: "done", count, seconds: wElapsed } : e));
        addLog(`  EP ${w}: ${count} results · ${wElapsed.toFixed(1)}s`, "success");
      } catch (err: any) {
        const wElapsed = ((Date.now() - wt0) / 1000);
        setBowWaveStatus(prev => prev.map(e => e.window === w ? { ...e, status: "error", seconds: wElapsed } : e));
        addLog(`  EP ${w}: ${err.message}`, "error");
        allOk = false;
      }
    }
    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    setStage(3, {
      status: allOk ? "done" : "error",
      message: allOk
        ? totalCount > 0
          ? `Bow wave complete — ${totalCount.toLocaleString()} EP records`
          : "Bow wave complete — no EP data (run Runtime Metrics first)"
        : "Some windows failed",
      detail: `${elapsed}s`,
      seconds: Number(elapsed),
    });
    if (allOk) {
      addLog(`Bow wave complete: 1Y / 3Y / 5Y / 10Y · ${elapsed}s`, "success");
      setActiveStage(4);
    }
  }, [dataset, params, addLog, setStage]);

  // ── Stage 5: Results ──────────────────────────────────────────────────────
  const checkResults = useCallback(async () => {
    if (!dataset || !params) { addLog("Complete pipeline stages first", "warn"); return; }
    setActiveStage(4);
    setStage(4, { status: "running", message: "Verifying computed metrics…" });
    addLog("Stage 5: verifying results…");
    try {
      const exists = await metricsExist(dataset.dataset_id, params.param_set_id);
      if (exists.exists) {
        setStage(4, { status: "done", message: "Metrics verified — Dashboard ready", detail: "All principle pages show live data" });
        addLog("All metrics verified ✓", "success");
        addLog("Navigate to any Principle page to view results", "info");
      } else {
        setStage(4, { status: "error", message: "Metrics not found — re-run pipeline" });
        addLog("Metrics not found — try running the pipeline again", "error");
      }
    } catch (err: any) {
      setStage(4, { status: "error", message: err.message });
      addLog(`Verification failed: ${err.message}`, "error");
    }
  }, [dataset, params, addLog, setStage]);

  // ── Run All ───────────────────────────────────────────────────────────────
  const runAll = useCallback(async () => {
    addLog("═══ FULL PIPELINE RUN ═══", "info");
    await runIngestion();
    await new Promise(r => setTimeout(r, 200));
    await loadParams();
    await new Promise(r => setTimeout(r, 200));
    await runRuntimeAll();
    await new Promise(r => setTimeout(r, 200));
    await runBowWave();
    await new Promise(r => setTimeout(r, 200));
    await checkResults();
  }, [runIngestion, loadParams, runRuntimeAll, runBowWave, checkResults, addLog]);

  const stageConfigs = [
    { label: "Data Selection",    sublabel: "Select DB",   status: stageResults[0].status },
    { label: "Parameters",        sublabel: "Configure",   status: stageResults[1].status },
    { label: "Runtime Metrics",   sublabel: "Compute",     status: stageResults[2].status },
    { label: "Bow Wave",          sublabel: "Generate",    status: stageResults[3].status },
    { label: "Results",           sublabel: "Dashboard",   status: stageResults[4].status },
  ];
  const stageActions = [runIngestion, loadParams, runRuntimeAll, runBowWave, checkResults];

  // ── Param save handler ────────────────────────────────────────────────────
  const handleSaveParams = async () => {
    if (!params) return;
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

  // ── Derived ───────────────────────────────────────────────────────────────
  const changedParamKeys = new Set(
    Object.entries(paramEdits).filter(([key, val]) => {
      const orig = originalParams[key];
      const meta = PARAM_META[key];
      const coerce = (v: unknown) => meta?.type === "number" ? Number(v) : meta?.type === "boolean" ? Boolean(v) : v;
      return String(coerce(val)) !== String(coerce(orig));
    }).map(([key]) => key)
  );

  const bowWaveDone = bowWaveStatus.filter(e => e.status === "done").length;
  const bowWavePct  = Math.round((bowWaveDone / 4) * 100);

  return (
    <div>

      {/* ── Sticky stage stepper ──────────────────────────────────────────── */}
      <div style={{
        position: "sticky", top: 0, zIndex: 20,
        background: "hsl(var(--background))",
        borderBottom: "1px solid hsl(210 16% 90%)",
        boxShadow: "0 2px 8px hsl(213 40% 50% / 0.07)",
        padding: "0.875rem 1.5rem",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          {stageConfigs.map((stage, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center" }}>
              <StageNode
                num={i + 1} label={stage.label} sublabel={stage.sublabel}
                status={stage.status} isActive={activeStage === i}
                onClick={() => { setActiveStage(i); stageActions[i](); }}
              />
              {i < stageConfigs.length - 1 && (
                <div style={{
                  width: 64, height: 2, margin: "0 0.25rem", marginTop: "-1.5rem",
                  background: stageResults[i].status === "done" ? GREEN
                    : stageResults[i].status === "running" ? GOLD : "hsl(210 16% 88%)",
                  transition: "background 0.4s",
                }} />
              )}
            </div>
          ))}
        </div>

        {/* Stage result summary banner */}
        {stageResults[activeStage].message && (
          <div style={{
            marginTop: "1.25rem", padding: "0.75rem 1rem", borderRadius: 8,
            background: stageResults[activeStage].status === "done" ? "hsl(152 60% 40% / 0.07)"
              : stageResults[activeStage].status === "error" ? "hsl(0 65% 50% / 0.07)"
              : "hsl(38 60% 52% / 0.07)",
            border: `1px solid ${stageResults[activeStage].status === "done" ? "hsl(152 60% 40% / 0.25)"
              : stageResults[activeStage].status === "error" ? "hsl(0 65% 50% / 0.25)"
              : "hsl(38 60% 52% / 0.25)"}`,
            display: "flex", alignItems: "center", gap: "0.75rem",
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

      {/* ── Content ───────────────────────────────────────────────────────── */}
      <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem", maxWidth: 1200 }}>

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontSize: "1.125rem", fontWeight: 800, color: "hsl(220 35% 12%)", margin: 0, letterSpacing: "-0.02em" }}>
            ETL Pipeline — Data Processing Workflow
          </h1>
          <p style={{ fontSize: "0.75rem", color: SLATE, margin: "0.25rem 0 0" }}>
            Bloomberg Excel → PostgreSQL → Runtime Metrics → Bow Wave → Dashboard
          </p>
        </div>
        <button onClick={runAll} style={{
          display: "flex", alignItems: "center", gap: "0.375rem",
          padding: "0.5rem 1.125rem", background: NAVY, color: "#fff",
          border: "none", borderRadius: 8, fontSize: "0.8125rem", fontWeight: 700,
          cursor: "pointer", boxShadow: "0 2px 8px hsl(213 75% 22% / 0.3)",
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          Run Full Pipeline
        </button>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════
          Stage 1 — Data Selection (full width)
      ══════════════════════════════════════════════════════════════════════ */}
      <StagePanel num={1} title="Data Selection" status={stageResults[0].status} onRun={runIngestion} active={activeStage === 0}>
        {Object.keys(allDatasets).length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
            {Object.entries(allDatasets).map(([key, ds]) => {
              const isSelected = dataset?.dataset_id === ds.dataset_id;
              return (
                <div key={key} onClick={() => { setDataset(ds); addLog(`Dataset selected: ${ds.dataset_id}`, "info"); }} style={{
                  borderRadius: 10, border: `2px solid ${isSelected ? NAVY : "hsl(210 16% 88%)"}`,
                  background: isSelected ? "hsl(213 75% 22% / 0.04)" : "#fff",
                  cursor: "pointer", transition: "all 0.15s", overflow: "hidden",
                }}>
                  {/* Dataset header row */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.75rem 1rem", borderBottom: `1px solid ${isSelected ? "hsl(213 75% 22% / 0.12)" : "hsl(210 16% 92%)"}` }}>
                    <span style={{ fontSize: "0.75rem", fontWeight: 700, color: NAVY, fontFamily: "ui-monospace, monospace", letterSpacing: "-0.01em" }}>{ds.dataset_id}</span>
                    {isSelected && (
                      <span style={{ fontSize: "0.5rem", fontWeight: 800, background: NAVY, color: "#fff", padding: "0.2rem 0.625rem", borderRadius: 999, letterSpacing: "0.06em" }}>SELECTED</span>
                    )}
                  </div>
                  {/* Stats band */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", padding: "0.875rem 1rem" }}>
                    {[
                      { label: "Companies", value: ds.companies?.count ?? "—" },
                      { label: "Sectors",   value: ds.sectors?.count ?? "—" },
                      { label: "Min Year",  value: ds.data_coverage?.min_year ?? "—" },
                      { label: "Max Year",  value: ds.data_coverage?.max_year ?? "—" },
                      { label: "Country",   value: ds.country || "—" },
                    ].map(kv => (
                      <div key={kv.label} style={{ textAlign: "center" }}>
                        <div style={{ fontSize: "0.5rem", color: SLATE, textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.06em", marginBottom: "0.25rem" }}>{kv.label}</div>
                        <div style={{ fontSize: "1.25rem", fontWeight: 800, color: NAVY, letterSpacing: "-0.02em" }}>{kv.value}</div>
                      </div>
                    ))}
                  </div>
                  {/* Footnote */}
                  <div style={{ padding: "0.5rem 1rem", background: "hsl(213 30% 98%)", borderTop: "1px solid hsl(210 16% 92%)", fontSize: "0.5625rem", color: SLATE }}>
                    {ds.raw_metrics?.count != null ? `${ds.raw_metrics.count.toLocaleString()} raw metric types` : "—"} · Created: {ds.dataset_created_at ? new Date(ds.dataset_created_at).toLocaleDateString("en-AU") : "—"}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "2rem 1rem" }}>
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke={SLATE} strokeWidth="1.5" style={{ margin: "0 auto 0.75rem", display: "block" }}>
              <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
            </svg>
            <div style={{ fontSize: "0.875rem", fontWeight: 600, color: "hsl(220 30% 35%)", marginBottom: "0.25rem" }}>No datasets loaded yet</div>
            <div style={{ fontSize: "0.6875rem", color: SLATE }}>Click <b>Run</b> to connect to the backend database.</div>
          </div>
        )}
      </StagePanel>

      {/* ══════════════════════════════════════════════════════════════════════
          Stage 2 — Parameter Configuration
      ══════════════════════════════════════════════════════════════════════ */}
      <StagePanel num={2} title="Parameter Configuration" status={stageResults[1].status} onRun={loadParams} active={activeStage === 1}>
        {params ? (
          <div>
            {/* Summary header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1rem" }}>
              <div>
                <div style={{ fontSize: "0.5625rem", color: SLATE, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 700, marginBottom: "0.2rem" }}>Active Parameter Set</div>
                <div style={{ fontSize: "0.8125rem", fontWeight: 700, color: "hsl(220 35% 15%)", fontFamily: "ui-monospace, monospace" }}>{params.param_set_name}</div>
                <div style={{ fontSize: "0.5rem", color: SLATE, marginTop: "0.15rem" }}>ID: {params.param_set_id.slice(0, 8)}…{params.is_default ? " · Default" : ""}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                {changedParamKeys.size > 0 && (
                  <span style={{ fontSize: "0.5rem", fontWeight: 700, background: "hsl(38 60% 52% / 0.12)", color: "hsl(38 50% 32%)", padding: "0.2rem 0.5rem", borderRadius: 999, border: "1px solid hsl(38 60% 52% / 0.3)" }}>
                    {changedParamKeys.size} unsaved
                  </span>
                )}
                <span style={{ fontSize: "0.5rem", fontWeight: 800, background: "hsl(152 60% 40% / 0.1)", color: "hsl(152 42% 28%)", padding: "0.25rem 0.6rem", borderRadius: 999, border: "1px solid hsl(152 60% 40% / 0.25)" }}>
                  ● ACTIVE
                </span>
                <button onClick={() => setParamExpanded(e => !e)} style={{
                  fontSize: "0.6875rem", fontWeight: 600, color: NAVY,
                  background: "hsl(213 40% 97%)", border: `1px solid hsl(213 30% 88%)`,
                  padding: "0.3rem 0.75rem", borderRadius: 6, cursor: "pointer",
                }}>
                  {paramExpanded ? "Collapse ▲" : "Edit ▼"}
                </button>
              </div>
            </div>

            {/* Collapsed: key-value summary grid */}
            {!paramExpanded && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.625rem" }}>
                {PARAM_SUMMARY_KEYS.map(({ key, label }) => {
                  const val = paramEdits[key] ?? (params.parameters as any)[key];
                  if (val === undefined) return null;
                  const display = typeof val === "boolean" ? (val ? "Included ✓" : "Excluded") : String(val);
                  return (
                    <div key={key} style={{ padding: "0.625rem 0.75rem", background: "hsl(213 30% 98%)", borderRadius: 8, border: "1px solid hsl(213 20% 91%)" }}>
                      <div style={{ fontSize: "0.5rem", color: SLATE, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 700, marginBottom: "0.25rem" }}>{label}</div>
                      <div style={{ fontSize: "0.875rem", fontWeight: 700, color: "hsl(220 35% 15%)" }}>{display}</div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Expanded: full grouped editor */}
            {paramExpanded && (
              <div>
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem", maxHeight: 380, overflowY: "auto", paddingRight: "2px" }}>
                  {PARAM_GROUPS.map(group => {
                    const groupKeys = group.keys.filter(k => (paramEdits[k] ?? (params.parameters as any)[k]) !== undefined);
                    if (groupKeys.length === 0) return null;
                    return (
                      <div key={group.label}>
                        <div style={{ fontSize: "0.5625rem", fontWeight: 800, color: NAVY, textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.6, marginBottom: "0.375rem" }}>
                          {group.label}
                        </div>
                        <div style={{ borderRadius: 8, border: "1px solid hsl(210 16% 91%)", overflow: "hidden" }}>
                          {groupKeys.map((key, idx) => {
                            const meta = PARAM_META[key];
                            if (!meta) return null;
                            const val = paramEdits[key] ?? (params.parameters as any)[key];
                            const isChanged = changedParamKeys.has(key);
                            const isLast = idx === groupKeys.length - 1;
                            return (
                              <div key={key} style={{
                                display: "flex", alignItems: "center", gap: "0.625rem",
                                padding: "0.5rem 0.75rem",
                                background: isChanged ? "hsl(213 75% 22% / 0.04)" : idx % 2 === 0 ? "#fff" : "hsl(210 20% 99%)",
                                borderLeft: `3px solid ${isChanged ? NAVY : "transparent"}`,
                                borderBottom: isLast ? "none" : "1px solid hsl(210 16% 93%)",
                                transition: "background 0.15s",
                              }}>
                                <label style={{ fontSize: "0.6875rem", flex: 1, lineHeight: 1.3, color: isChanged ? "hsl(220 40% 14%)" : "hsl(220 15% 40%)", fontWeight: isChanged ? 600 : 400 }}>
                                  {meta.label}
                                </label>
                                {meta.type === "boolean" ? (
                                  <Toggle on={!!val} onChange={v => setParamEdits(p => ({ ...p, [key]: v }))} />
                                ) : meta.type === "select" ? (
                                  <select value={String(val)} onChange={e => setParamEdits(p => ({ ...p, [key]: e.target.value }))} style={{
                                    fontSize: "0.6875rem", padding: "0.3rem 0.4rem", borderRadius: 6,
                                    border: `1px solid ${isChanged ? "hsl(213 75% 22% / 0.45)" : "hsl(210 16% 85%)"}`,
                                    background: "#fff", color: "hsl(220 35% 15%)", fontWeight: 500, cursor: "pointer", minWidth: 100,
                                  }}>
                                    {meta.options?.map(o => <option key={o} value={o}>{o}</option>)}
                                  </select>
                                ) : (
                                  <input type="number" value={Number(val)} onChange={e => setParamEdits(p => ({ ...p, [key]: Number(e.target.value) }))} style={{
                                    width: 72, fontSize: "0.6875rem", padding: "0.3rem 0.5rem", borderRadius: 6,
                                    border: `1px solid ${isChanged ? "hsl(213 75% 22% / 0.45)" : "hsl(210 16% 85%)"}`,
                                    textAlign: "right", color: "hsl(220 35% 15%)",
                                    fontWeight: isChanged ? 700 : 400,
                                    background: isChanged ? "hsl(213 75% 22% / 0.03)" : "#fff",
                                  }} />
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div style={{ marginTop: "0.875rem", paddingTop: "0.75rem", borderTop: "1px solid hsl(210 16% 92%)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <div style={{ fontSize: "0.5625rem", color: changedParamKeys.size > 0 ? "hsl(38 50% 32%)" : SLATE, fontWeight: changedParamKeys.size > 0 ? 600 : 400 }}>
                    {changedParamKeys.size > 0 ? `${changedParamKeys.size} unsaved change${changedParamKeys.size > 1 ? "s" : ""}` : "No changes"}
                  </div>
                  <button onClick={handleSaveParams} style={{
                    marginLeft: "auto", display: "flex", alignItems: "center", gap: "0.375rem",
                    padding: "0.45rem 1rem", borderRadius: 7,
                    background: changedParamKeys.size > 0 ? NAVY : "hsl(210 16% 93%)",
                    color: changedParamKeys.size > 0 ? "#fff" : SLATE,
                    border: "none", fontWeight: 700, fontSize: "0.6875rem",
                    cursor: changedParamKeys.size > 0 ? "pointer" : "default",
                    transition: "all 0.2s",
                    boxShadow: changedParamKeys.size > 0 ? "0 2px 6px hsl(213 75% 22% / 0.25)" : "none",
                  }}>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                      <polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>
                    </svg>
                    Save Parameters
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "1.5rem 1rem" }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={SLATE} strokeWidth="1.5" style={{ margin: "0 auto 0.5rem", display: "block" }}>
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
            </svg>
            <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "hsl(220 30% 35%)", marginBottom: "0.25rem" }}>Parameters not loaded</div>
            <div style={{ fontSize: "0.6875rem", color: SLATE }}>Click <b>Run</b> to fetch the active parameter set.</div>
          </div>
        )}
      </StagePanel>

      {/* ══════════════════════════════════════════════════════════════════════
          Stage 3 — Runtime Metrics (single endpoint)
      ══════════════════════════════════════════════════════════════════════ */}
      <StagePanel num={3} title="Runtime Metrics" status={stageResults[2].status} onRun={runRuntimeAll} active={activeStage === 2}>
        <div>
          {/* Endpoint badge */}
          <div style={{ marginBottom: "0.875rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <code style={{ fontSize: "0.5625rem", color: SLATE, background: "hsl(210 20% 97%)", padding: "0.25rem 0.625rem", borderRadius: 6, border: "1px solid hsl(210 16% 90%)" }}>
              POST /api/v1/metrics/runtime-metrics
            </code>
            <span style={{ fontSize: "0.5625rem", color: SLATE }}>· Beta → Rf → Ke → FV-ECF → TER → TER Alpha</span>
          </div>

          {/* Phase rows — dynamic from response, or static skeleton */}
          {runtimePhases.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
              {runtimePhases.map((phase, idx) => {
                const ok = phase.status === "success" || phase.status === "done";
                const isLast = idx === runtimePhases.length - 1;
                return (
                  <div key={phase.name} style={{
                    display: "flex", alignItems: "center", gap: "0.75rem",
                    padding: "0.5rem 0.75rem",
                    background: idx % 2 === 0 ? "#fff" : "hsl(210 20% 99%)",
                    borderBottom: isLast ? "none" : "1px solid hsl(210 16% 93%)",
                    borderRadius: idx === 0 ? "8px 8px 0 0" : isLast ? "0 0 8px 8px" : "0",
                    border: "1px solid hsl(210 16% 91%)",
                    marginTop: idx === 0 ? 0 : -1,
                  }}>
                    <PhaseDot status={ok ? "done" : "error"} />
                    <div style={{ flex: 1, fontSize: "0.6875rem", fontWeight: 600, color: "hsl(220 25% 20%)" }}>{phase.name}</div>
                    <div style={{ fontSize: "0.5625rem", color: SLATE }}>{phase.records.toLocaleString()} records</div>
                    <div style={{ fontSize: "0.5625rem", color: SLATE, minWidth: 32, textAlign: "right" }}>{phase.seconds.toFixed(1)}s</div>
                  </div>
                );
              })}
            </div>
          ) : (
            // Static skeleton before first run
            <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
              {[
                "Beta Rounding",
                "Risk-Free Rate (Rf)",
                "Cost of Equity (Ke)",
                "FV-ECF (1Y / 3Y / 5Y / 10Y)",
                "TER & TER-Ke",
                "TER Alpha",
              ].map((name, idx, arr) => (
                <div key={name} style={{
                  display: "flex", alignItems: "center", gap: "0.75rem",
                  padding: "0.5rem 0.75rem",
                  background: idx % 2 === 0 ? "#fff" : "hsl(210 20% 99%)",
                  border: "1px solid hsl(210 16% 91%)",
                  marginTop: idx === 0 ? 0 : -1,
                  borderRadius: idx === 0 ? "8px 8px 0 0" : idx === arr.length - 1 ? "0 0 8px 8px" : "0",
                }}>
                  <PhaseDot status={stageResults[2].status === "done" ? "done" : stageResults[2].status === "running" ? "running" : "pending"} />
                  <div style={{ fontSize: "0.6875rem", color: "hsl(220 15% 45%)" }}>{name}</div>
                </div>
              ))}
            </div>
          )}

          {/* ── Metric time-series chart (shown after stage completes) ─────── */}
          {stageResults[2].status === "done" && (
            <div style={{ marginTop: "1.25rem", padding: "1rem", background: "hsl(210 20% 98%)", borderRadius: 10, border: "1px solid hsl(210 16% 90%)" }}>
              {/* Controls row */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
                <select
                  value={s3Metric}
                  onChange={e => setS3Metric(e.target.value)}
                  style={{ fontSize: "0.75rem", padding: "0.3rem 0.5rem", borderRadius: 6, border: "1px solid hsl(210 16% 85%)", background: "#fff", color: "hsl(220 25% 15%)", fontWeight: 600, cursor: "pointer" }}
                >
                  {RUNTIME_METRICS.map(m => (
                    <option key={m.key} value={m.key}>{m.label}</option>
                  ))}
                </select>
                <span style={{ fontSize: "0.6875rem", color: SLATE }}>Ticker:</span>
                <input
                  value={s3Ticker}
                  onChange={e => setS3Ticker(e.target.value)}
                  placeholder="e.g. BHP AU Equity"
                  style={{ fontSize: "0.75rem", padding: "0.3rem 0.5rem", borderRadius: 6, border: "1px solid hsl(210 16% 85%)", background: "#fff", color: "hsl(220 25% 15%)", width: 160 }}
                />
                <span style={{ fontSize: "0.5625rem", color: SLATE, marginLeft: "auto" }}>
                  {s3Data.length > 0 ? `${s3Data.length} years` : "no data"}
                </span>
              </div>
              {/* Chart */}
              {s3Data.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={s3Data.map(d => ({ year: d.fiscal_year, value: d.value }))} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fill: "#94a3b8", fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 9 }} axisLine={false} tickLine={false} width={48}
                      tickFormatter={(v: number) => v == null ? "—" : v > 100 ? v.toLocaleString() : v.toFixed(2)} />
                    <ReTooltip
                      contentStyle={{ fontSize: "0.75rem", borderRadius: 6, border: "1px solid hsl(210 16% 88%)" }}
                      formatter={(v: number) => [v == null ? "—" : v.toFixed(4), RUNTIME_METRICS.find(m => m.key === s3Metric)?.label ?? s3Metric]}
                      labelFormatter={(l: number) => `FY ${l}`}
                    />
                    <Legend wrapperStyle={{ fontSize: "0.65rem" }} formatter={() => RUNTIME_METRICS.find(m => m.key === s3Metric)?.label ?? s3Metric} />
                    <Line type="monotone" dataKey="value" stroke={NAVY} strokeWidth={2} dot={{ r: 3, fill: NAVY }} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center", color: SLATE, fontSize: "0.8125rem" }}>
                  No data — run Runtime Metrics first or try a different ticker
                </div>
              )}
            </div>
          )}
        </div>
      </StagePanel>

      {/* ══════════════════════════════════════════════════════════════════════
          Stage 4 — Bow Wave Generation
      ══════════════════════════════════════════════════════════════════════ */}
      <StagePanel num={4} title="Bow Wave Generation" status={stageResults[3].status} onRun={runBowWave} active={activeStage === 3}>
        <div>
          {/* Endpoint badge */}
          <div style={{ marginBottom: "0.875rem" }}>
            <code style={{ fontSize: "0.5625rem", color: SLATE, background: "hsl(210 20% 97%)", padding: "0.25rem 0.625rem", borderRadius: 6, border: "1px solid hsl(210 16% 90%)" }}>
              GET /api/v1/metrics/economic-profitability · temporal_window=1Y|3Y|5Y|10Y
            </code>
          </div>

          {/* Progress bar */}
          {(stageResults[3].status === "running" || stageResults[3].status === "done") && (
            <div style={{ marginBottom: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.375rem" }}>
                <span style={{ fontSize: "0.5625rem", color: SLATE, fontWeight: 600 }}>Overall progress</span>
                <span style={{ fontSize: "0.5625rem", fontWeight: 700, color: NAVY }}>{bowWavePct}% · {bowWaveDone} of 4</span>
              </div>
              <div style={{ height: 8, background: "hsl(210 16% 90%)", borderRadius: 999, overflow: "hidden" }}>
                <div style={{
                  height: "100%", borderRadius: 999,
                  background: bowWavePct === 100 ? GREEN : GOLD,
                  width: `${bowWavePct}%`,
                  transition: "width 0.4s ease",
                  boxShadow: bowWavePct > 0 ? `0 0 8px ${bowWavePct === 100 ? "hsl(152 60% 40% / 0.5)" : "hsl(38 60% 52% / 0.4)"}` : "none",
                }} />
              </div>
            </div>
          )}

          {/* Window rows */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
            {bowWaveStatus.map((entry, idx) => (
              <div key={entry.window} style={{
                display: "flex", alignItems: "center", gap: "0.75rem",
                padding: "0.625rem 0.75rem",
                background: idx % 2 === 0 ? "#fff" : "hsl(210 20% 99%)",
                border: "1px solid hsl(210 16% 91%)",
                marginTop: idx === 0 ? 0 : -1,
                borderRadius: idx === 0 ? "8px 8px 0 0" : idx === 3 ? "0 0 8px 8px" : "0",
              }}>
                <PhaseDot status={entry.status} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "0.6875rem", fontWeight: 600, color: "hsl(220 25% 20%)" }}>
                    EP Bow Wave — {entry.window}
                  </div>
                  <div style={{ fontSize: "0.5rem", color: SLATE, marginTop: "0.1rem" }}>economic-profitability · temporal_window={entry.window}</div>
                </div>
                {entry.status === "done" && (
                  <>
                    <div style={{ fontSize: "0.5625rem", color: SLATE }}>{entry.count.toLocaleString()} results</div>
                    <div style={{ fontSize: "0.5625rem", color: SLATE, minWidth: 32, textAlign: "right" }}>{entry.seconds.toFixed(1)}s</div>
                  </>
                )}
                {entry.status === "error" && (
                  <div style={{ fontSize: "0.5625rem", color: RED, fontWeight: 600 }}>Failed</div>
                )}
              </div>
            ))}
          </div>

          {/* ── EP time-series chart (shown after stage completes) ────────── */}
          {stageResults[3].status === "done" && (
            <div style={{ marginTop: "1.25rem", padding: "1rem", background: "hsl(210 20% 98%)", borderRadius: 10, border: "1px solid hsl(210 16% 90%)" }}>
              {/* Controls row */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
                {/* Window tabs */}
                <div style={{ display: "flex", gap: "0.25rem" }}>
                  {(["1Y", "3Y", "5Y", "10Y"] as const).map(w => (
                    <button key={w} onClick={() => setS4Window(w)} style={{
                      padding: "0.2rem 0.5rem", borderRadius: 4, fontSize: "0.6875rem",
                      border: "1px solid hsl(210 16% 85%)",
                      background: s4Window === w ? NAVY : "#fff",
                      color: s4Window === w ? "#fff" : SLATE,
                      cursor: "pointer", fontWeight: s4Window === w ? 700 : 400,
                    }}>{w}</button>
                  ))}
                </div>
                <span style={{ fontSize: "0.6875rem", color: SLATE }}>Ticker:</span>
                <input
                  value={s4Ticker}
                  onChange={e => setS4Ticker(e.target.value)}
                  placeholder="e.g. BHP AU Equity"
                  style={{ fontSize: "0.75rem", padding: "0.3rem 0.5rem", borderRadius: 6, border: "1px solid hsl(210 16% 85%)", background: "#fff", color: "hsl(220 25% 15%)", width: 160 }}
                />
                <span style={{ fontSize: "0.5625rem", color: SLATE, marginLeft: "auto" }}>
                  {s4Data.length > 0 ? `${s4Data.length} years` : "no data"}
                </span>
              </div>
              {/* Chart */}
              {s4Data.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart
                    data={s4Data.map(d => ({ year: d.fiscal_year, value: (d as any)[`ep_${s4Window.toLowerCase()}`] ?? null }))}
                    margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fill: "#94a3b8", fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 9 }} axisLine={false} tickLine={false} width={48}
                      tickFormatter={(v: number) => v == null ? "—" : `${v.toFixed(0)}%`} />
                    <ReTooltip
                      contentStyle={{ fontSize: "0.75rem", borderRadius: 6, border: "1px solid hsl(210 16% 88%)" }}
                      formatter={(v: number) => [v == null ? "—" : `${v.toFixed(2)}%`, `EP ${s4Window}`]}
                      labelFormatter={(l: number) => `FY ${l}`}
                    />
                    <Legend wrapperStyle={{ fontSize: "0.65rem" }} formatter={() => `EP ${s4Window}`} />
                    <Line type="monotone" dataKey="value" stroke={GREEN} strokeWidth={2} dot={{ r: 3, fill: GREEN }} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center", color: SLATE, fontSize: "0.8125rem" }}>
                  No data — run Bow Wave first or try a different ticker
                </div>
              )}
            </div>
          )}
        </div>
      </StagePanel>

      {/* ══════════════════════════════════════════════════════════════════════
          Stage 5 — Results & Dashboard
      ══════════════════════════════════════════════════════════════════════ */}
      <StagePanel num={5} title="Results & Dashboard" status={stageResults[4].status} onRun={checkResults} active={activeStage === 4}>
        {stageResults[4].status === "done" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
            <div style={{ padding: "1rem", background: "hsl(152 60% 40% / 0.07)", borderRadius: 10, border: "1px solid hsl(152 60% 40% / 0.2)", textAlign: "center" }}>
              <div style={{ fontSize: "1rem", fontWeight: 800, color: "hsl(152 50% 28%)" }}>Pipeline Complete ✓</div>
              <div style={{ fontSize: "0.6875rem", color: SLATE, marginTop: "0.25rem" }}>All metrics computed and verified in database</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem" }}>
              {[
                { label: "Dashboard",   path: "/" },
                { label: "Principle 1", path: "/principles/1" },
                { label: "Principle 2", path: "/principles/2" },
                { label: "Principle 3", path: "/principles/3" },
                { label: "Principle 4", path: "/principles/4" },
                { label: "Download",    path: "/download" },
              ].map(l => (
                <Link key={l.path} href={l.path}>
                  <a style={{
                    display: "block", textAlign: "center",
                    padding: "0.5rem 0.625rem",
                    background: "hsl(213 40% 97%)", borderRadius: 8,
                    border: "1px solid hsl(213 30% 88%)",
                    fontSize: "0.6875rem", fontWeight: 600, color: NAVY,
                    textDecoration: "none", transition: "background 0.15s",
                  }}>
                    {l.label} →
                  </a>
                </Link>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ color: SLATE, fontSize: "0.75rem", textAlign: "center", padding: "1.25rem" }}>
            Complete all pipeline stages to view results
          </div>
        )}
      </StagePanel>

      {/* ── Log console ───────────────────────────────────────────────────── */}
      <div style={{
        background: "hsl(220 30% 8%)", borderRadius: 10,
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
            <button onClick={() => setLogs([])} style={{ marginLeft: "auto", fontSize: "0.5625rem", color: "hsl(220 15% 45%)", background: "none", border: "none", cursor: "pointer" }}>
              Clear
            </button>
          )}
        </div>
        <div style={{ maxHeight: 200, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.1rem" }}>
          {logs.length === 0 ? (
            <span style={{ color: "hsl(220 15% 40%)", fontSize: "0.6875rem" }}>$ awaiting pipeline run…</span>
          ) : logs.map((l, i) => (
            <div key={i} style={{
              fontSize: "0.6875rem", lineHeight: 1.6,
              color: l.type === "success" ? "hsl(120 50% 60%)" : l.type === "error" ? "hsl(0 65% 65%)" : l.type === "warn" ? "hsl(38 70% 62%)" : "hsl(210 20% 70%)",
            }}>{l.text}</div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>

      </div>{/* end content wrapper */}
    </div>
  );
}
