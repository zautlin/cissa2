import { useLocation } from "wouter";
import { useActiveContext } from "../hooks/useMetrics";
import { useState } from "react";

const pageTitles: Record<string, { title: string; subtitle: string }> = {
  "/":                 { title: "Platform Overview",                         subtitle: "Economic Profitability Dashboard" },
  "/principles/1":     { title: "Principle 1 — Economic Measures are Better", subtitle: "Cost of Equity · Financial Bridge · Capital Market" },
  "/principles/2":     { title: "Principle 2 — Primary Focus on the Longer Term", subtitle: "EP Bow Wave · Market Value · Wealth Creation" },
  "/principles/3":     { title: "Principle 3 — Capital Market Returns",      subtitle: "TER · TER-Ke · TER Alpha · ECF Decomposition" },
  "/principles/4":     { title: "Principle 4 — EEAI & Sector Aggregations",  subtitle: "Economic Equity Added Index · Heatmap · Sector EP" },
  "/principles/5":     { title: "Principle 5 — Ratio Metrics & Sustainability", subtitle: "Cost Structure · ROA · Asset Intensity · ESG" },
  "/principles/6":     { title: "Principle 6 — Valuation & Beta",            subtitle: "Beta Analysis · Ke Decomposition · FV-ECF · Rf History" },
  "/outputs":          { title: "Outputs — Wealth Creation Analysis",         subtitle: "Intrinsic & Sustainable Wealth Creation" },
  "/underlying-data":  { title: "Underlying Data",                           subtitle: "Capital Market · Financial · Market Movements" },
  "/reports":          { title: "Reports & Research",                         subtitle: "Analysis · Insights · PDF Exports" },
  "/download":         { title: "Metrics Download",                           subtitle: "Export computed metrics as CSV or JSON" },
  "/pipeline":         { title: "ETL Pipeline — Data Processing Workflow",    subtitle: "Bloomberg Ingest · L1 Compute · Runtime Metrics · Results" },
};

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span style={{
      display: "inline-block",
      width: 7, height: 7,
      borderRadius: "50%",
      background: ok ? "hsl(152 60% 45%)" : "hsl(38 60% 52%)",
      boxShadow: ok ? "0 0 6px hsl(152 60% 45% / 0.7)" : "0 0 6px hsl(38 60% 52% / 0.5)",
    }} />
  );
}

export default function Topbar({
  onToggleSidebar,
  sidebarOpen,
}: { onToggleSidebar: () => void; sidebarOpen: boolean }) {
  const [location] = useLocation();
  const ctx = useActiveContext();
  const page = pageTitles[location] || { title: "CISSA™ Platform", subtitle: "KBA Consulting Group" };

  return (
    <div
      className="dashboard-topbar"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        padding: "0 1.25rem",
        height: "56px",
        background: "hsl(0 0% 100%)",
        borderBottom: "1px solid hsl(210 16% 90%)",
      }}
    >
      {/* Hamburger */}
      <button
        onClick={onToggleSidebar}
        data-testid="button-toggle-sidebar"
        title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
        style={{
          padding: "0.375rem",
          borderRadius: "0.375rem",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "hsl(215 15% 46%)",
          display: "flex",
          alignItems: "center",
          flexShrink: 0,
        }}
      >
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
          <path d="M3 6h18M3 12h18M3 18h18" />
        </svg>
      </button>

      {/* Page title block */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: "0.8125rem",
          fontWeight: 700,
          color: "hsl(220 35% 12%)",
          lineHeight: 1.2,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}>
          {page.title}
        </div>
        <div style={{
          fontSize: "0.6875rem",
          color: "hsl(215 15% 52%)",
          marginTop: "1px",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}>
          {page.subtitle}
        </div>
      </div>

      {/* Right controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexShrink: 0 }}>

        {/* Dataset badge */}
        {ctx.stats && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "0.375rem",
            padding: "0.25rem 0.625rem",
            border: "1px solid hsl(210 16% 88%)",
            borderRadius: "0.375rem",
            background: "hsl(210 20% 98%)",
            fontSize: "0.6875rem",
            color: "hsl(220 35% 20%)",
            fontWeight: 500,
          }}>
            <StatusDot ok={ctx.hasMetrics} />
            <span>{ctx.stats.companies.count} cos ·</span>
            <span>{ctx.stats.data_coverage.min_year}–{ctx.stats.data_coverage.max_year}</span>
          </div>
        )}

        {/* Param set badge */}
        {ctx.params && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "0.3rem",
            padding: "0.25rem 0.5rem",
            border: "1px solid hsl(38 60% 52% / 0.35)",
            borderRadius: "0.375rem",
            background: "hsl(38 60% 52% / 0.06)",
            fontSize: "0.6875rem",
            color: "hsl(38 60% 35%)",
            fontWeight: 600,
          }}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <circle cx="12" cy="12" r="3" /><path d="M19.07 4.93a10 10 0 010 14.14" /><path d="M4.93 4.93a10 10 0 000 14.14" />
            </svg>
            {ctx.params.cost_of_equity_approach || "CAPM"} · Ke
          </div>
        )}

        {/* Ke display */}
        {ctx.params?.equity_risk_premium && (
          <div style={{
            padding: "0.25rem 0.5rem",
            border: "1px solid hsl(213 75% 22% / 0.2)",
            borderRadius: "0.375rem",
            background: "hsl(213 75% 22% / 0.05)",
            fontSize: "0.6875rem",
            color: "hsl(213 75% 22%)",
            fontWeight: 600,
          }}>
            ERP {Number(ctx.params.equity_risk_premium).toFixed(1)}%
          </div>
        )}

        {/* Period selector */}
        <select
          data-testid="select-period"
          style={{
            fontSize: "0.6875rem",
            padding: "0.275rem 0.5rem",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.375rem",
            background: "hsl(var(--card))",
            color: "hsl(var(--foreground))",
            cursor: "pointer",
            fontWeight: 500,
          }}
        >
          <option>2001–2024</option>
          <option>2010–2024</option>
          <option>2015–2024</option>
          <option>2020–2024</option>
        </select>

        {/* Help */}
        <button
          data-testid="button-help"
          title="Documentation & Help"
          style={{
            display: "flex", alignItems: "center", gap: "0.25rem",
            padding: "0.275rem 0.625rem",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.375rem",
            background: "hsl(var(--card))",
            color: "hsl(var(--primary))",
            cursor: "pointer",
            fontSize: "0.6875rem",
            fontWeight: 600,
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" /><path d="M12 17h.01" />
          </svg>
          Docs
        </button>

        {/* User */}
        <div
          data-testid="button-user-avatar"
          title="gautam.aneel@gmail.com"
          style={{
            width: "28px", height: "28px",
            borderRadius: "50%",
            background: "linear-gradient(135deg, hsl(213 75% 22%) 0%, hsl(213 65% 35%) 100%)",
            color: "white",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "0.5625rem",
            fontWeight: 800,
            cursor: "pointer",
            letterSpacing: "0.03em",
          }}
        >
          GA
        </div>
      </div>
    </div>
  );
}
