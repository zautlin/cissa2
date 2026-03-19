import { useState } from "react";
import { Link, useLocation } from "wouter";
import { useActiveContext } from "../hooks/useMetrics";

// ── Nav structure ─────────────────────────────────────────────────────────────
const navData = [
  {
    section: "Principles",
    items: [
      {
        label: "P1: Economic Measures",
        path: "/principles/1",
        icon: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 11h.01M12 11h.01M15 11h.01M4 19h16a2 2 0 002-2V7a2 2 0 00-2-2H4a2 2 0 00-2 2v10a2 2 0 002 2z",
        color: "hsl(213 75% 30%)",
        badge: "6",
        subItems: [
          { label: "1.1  Cost of Equity (Ke)", path: "/principles/1/1.1" },
          { label: "1.2  Financial & Capital Bridge", path: "/principles/1/1.2" },
          { label: "1.3  Products & Services Market", path: "/principles/1/1.3" },
          { label: "1.4  Capital Market Predictor", path: "/principles/1/1.4" },
          { label: "1.5  Capital Market Assessment", path: "/principles/1/1.5" },
        ],
      },
      {
        label: "P2: Long-Term Focus",
        path: "/principles/2",
        icon: "M13 17h8m0 0V9m0 8l-8-8-4 4-6-6",
        color: "hsl(213 65% 38%)",
        badge: "★",
        highlight: true,
        subItems: [
          { label: "2.1  Market Value & EP",           path: "/principles/2/2.1" },
          { label: "2.2  Bow Wave Concept",            path: "/principles/2/2.2" },
          { label: "2.3  Pair of EP Bow Waves",        path: "/principles/2/2.3" },
          { label: "2.4  Long-Term Focus Proof",       path: "/principles/2/2.4" },
          { label: "2.5  Reconciling Wealth Creation", path: "/principles/2/2.5" },
        ],
      },
      {
        label: "P3: Capital Market Returns",
        path: "/principles/3",
        icon: "M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z",
        color: "hsl(38 65% 45%)",
        badge: "5",
        subItems: [
          { label: "3.1  TER & TSR Overview",    path: "/principles/3/3.1" },
          { label: "3.2  TER Alpha",             path: "/principles/3/3.2" },
          { label: "3.3  ECF Decomposition",     path: "/principles/3/3.3" },
          { label: "3.4  International TER",     path: "/principles/3/3.4" },
          { label: "3.5  Wealth Creation ($B)",  path: "/principles/3/3.5" },
        ],
      },
      {
        label: "P4: EEAI & Sector Aggregations",
        path: "/principles/4",
        icon: "M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z",
        color: "hsl(160 55% 38%)",
        badge: "5",
        subItems: [
          { label: "4.1  EEAI Overview",               path: "/principles/4/4.1" },
          { label: "4.2  EEAI Heatmap (Companies)",    path: "/principles/4/4.2" },
          { label: "4.3  EP Delivered vs Required",    path: "/principles/4/4.3" },
          { label: "4.4  Sector Aggregations",         path: "/principles/4/4.4" },
          { label: "4.5  Sector EP Score Heatmap",     path: "/principles/4/4.5" },
        ],
      },
      {
        label: "P5: Ratio Metrics",
        path: "/principles/5",
        icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
        color: "hsl(280 55% 50%)",
        badge: "5",
        subItems: [
          { label: "5.1  Cost Structure by Sector", path: "/principles/5/5.1" },
          { label: "5.2  Revenue & EE Growth",      path: "/principles/5/5.2" },
          { label: "5.3  ROA & Profit Margin",      path: "/principles/5/5.3" },
          { label: "5.4  Asset Intensity",          path: "/principles/5/5.4" },
          { label: "5.5  ESG & Sustainability",     path: "/principles/5/5.5" },
        ],
      },
      {
        label: "P6: Valuation & Beta",
        path: "/principles/6",
        icon: "M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3",
        color: "hsl(0 60% 48%)",
        badge: "5",
        subItems: [
          { label: "6.1  Beta Distribution",        path: "/principles/6/6.1" },
          { label: "6.2  Ke Decomposition",         path: "/principles/6/6.2" },
          { label: "6.3  Risk Free Rate History",   path: "/principles/6/6.3" },
          { label: "6.4  FV-ECF & Valuation",       path: "/principles/6/6.4" },
          { label: "6.5  TER Decomposition",        path: "/principles/6/6.5" },
        ],
      },
    ],
  },
  {
    section: "Executive",
    items: [
      { label: "Executive Dashboard", path: "/executive", icon: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z", subItems: [], execHighlight: true },
    ],
  },
  {
    section: "Outputs",
    items: [
      { label: "Wealth Creation Overview",   path: "/outputs",          icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z", subItems: [] },
      { label: "TSR-Ke Analysis",            path: "/outputs",          icon: "M7 12l3-3 3 3 4-4",                                                                                                                                                                                                                                                               subItems: [] },
      { label: "Intrinsic Wealth Creation",  path: "/outputs",          icon: "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",                                                                                                                                                                    subItems: [] },
    ],
  },
  {
    section: "Data",
    items: [
      { label: "Capital Market Metrics",     path: "/underlying-data",  icon: "M3 9h18M3 15h18M9 3v18M15 3v18",                                                                                                                                                                                                                                                  subItems: [] },
      { label: "Financial Data",             path: "/underlying-data",  icon: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",                                                                                                                                               subItems: [] },
    ],
  },
  {
    section: "Reports & Export",
    items: [
      { label: "Reports & Research",         path: "/reports",          icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",                                                                                                                                                         subItems: [] },
      { label: "Metrics Download",           path: "/download",         icon: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12",                                                                                                                                                                                                                 subItems: [], downloadHighlight: true },
    ],
  },
  {
    section: "Platform",
    items: [
      { label: "ETL Pipeline",               path: "/pipeline",         icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",                                                                                                                                                                                                                                                 subItems: [], etlHighlight: true },
    ],
  },
];

export default function Sidebar() {
  const [location] = useLocation();
  const ctx = useActiveContext();
  const [openItems, setOpenItems] = useState<Record<string, boolean>>({
    "P1: Economic Measures": true,
  });

  const toggle = (label: string) =>
    setOpenItems(prev => ({ ...prev, [label]: !prev[label] }));

  // Helper: is the current location inside this principle section?
  const isInsideSection = (basePath: string) =>
    location === basePath || location.startsWith(basePath + "/");

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>

      {/* ── Logo ──────────────────────────────────────────────────────────── */}
      <div style={{
        padding: "1.125rem 1.125rem 0.875rem",
        borderBottom: "1px solid hsl(210 16% 90%)",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
          <svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-label="CISSA" xmlns="http://www.w3.org/2000/svg">
            <rect width="34" height="34" rx="7" fill="hsl(213 75% 22%)" />
            <path d="M9 17C9 11.5 12 9 17 9C20.5 9 23 10.5 24.5 13" stroke="hsl(38 60% 65%)" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
            <path d="M9 17C9 22.5 12 25 17 25C20.5 25 23 23.5 24.5 21" stroke="hsl(38 60% 65%)" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
            <circle cx="17" cy="17" r="2.5" fill="white"/>
            <path d="M17 9V7" stroke="hsl(38 60% 65%)" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M17 27V25" stroke="hsl(38 60% 65%)" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <div>
            <div style={{ fontWeight: 800, fontSize: "0.9375rem", color: "hsl(213 75% 22%)", letterSpacing: "-0.02em", lineHeight: 1.1 }}>
              CISSA<sup style={{ fontSize: "0.45rem", verticalAlign: "super", fontWeight: 700 }}>™</sup>
            </div>
            <div style={{ fontSize: "0.625rem", color: "hsl(215 20% 50%)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              Digital Platform
            </div>
          </div>
        </div>

        {/* Status row */}
        <div style={{ marginTop: "0.625rem", display: "flex", alignItems: "center", gap: "0.375rem" }}>
          {ctx.loading ? (
            <div style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "hsl(38 60% 52%)", opacity: 0.7 }} />
              <span style={{ fontSize: "0.625rem", color: "hsl(215 15% 55%)" }}>Loading…</span>
            </div>
          ) : ctx.stats ? (
            <>
              <div style={{
                width: 6, height: 6, borderRadius: "50%",
                background: ctx.hasMetrics ? "hsl(152 60% 48%)" : "hsl(38 60% 52%)",
                boxShadow: ctx.hasMetrics ? "0 0 5px hsl(152 60% 48% / 0.7)" : "none",
              }} />
              <span style={{ fontSize: "0.625rem", color: "hsl(215 15% 48%)", fontWeight: 500 }}>
                {ctx.hasMetrics ? "Metrics computed" : "Pipeline pending"} ·{" "}
                {ctx.stats.country || "AU"}
              </span>
            </>
          ) : (
            <>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "hsl(0 60% 52%)" }} />
              <span style={{ fontSize: "0.625rem", color: "hsl(0 60% 45%)" }}>No dataset loaded</span>
            </>
          )}
        </div>

        {/* Dataset info */}
        {ctx.stats && (
          <div style={{
            marginTop: "0.5rem",
            padding: "0.375rem 0.5rem",
            background: "hsl(213 40% 97%)",
            borderRadius: "0.375rem",
            border: "1px solid hsl(213 30% 90%)",
          }}>
            <div style={{ fontSize: "0.5625rem", color: "hsl(213 50% 40%)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.125rem" }}>
              Active Dataset
            </div>
            <div style={{ fontSize: "0.625rem", color: "hsl(213 50% 25%)", fontWeight: 600 }}>
              {ctx.stats.companies.count} companies · {ctx.stats.sectors.count} sectors
            </div>
            <div style={{ fontSize: "0.5625rem", color: "hsl(213 30% 50%)", marginTop: "0.125rem" }}>
              FY {ctx.stats.data_coverage.min_year}–{ctx.stats.data_coverage.max_year}
            </div>
          </div>
        )}
      </div>

      {/* ── Navigation ─────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: "auto", overscrollBehavior: "contain", padding: "0.5rem 0" }}>
        {navData.map(section => (
          <div key={section.section} style={{ marginBottom: "0.125rem" }}>
            <div style={{
              padding: "0.5rem 1.125rem 0.25rem",
              fontSize: "0.5625rem",
              fontWeight: 800,
              color: "hsl(215 15% 58%)",
              textTransform: "uppercase",
              letterSpacing: "0.07em",
            }}>
              {section.section}
            </div>

            {section.items.map((item: any) => {
              const hasChildren = item.subItems && item.subItems.length > 0;
              const isOpen = openItems[item.label];
              // Active if at the base path, or at any sub-path
              const isActive = isInsideSection(item.path);
              // Auto-open section that contains active route
              if (isActive && !isOpen && !openItems[item.label + "__checked"]) {
                setTimeout(() => setOpenItems(prev => ({ ...prev, [item.label]: true, [item.label + "__checked"]: true })), 0);
              }

              return (
                <div key={item.label}>
                  {hasChildren ? (
                    <>
                      <button
                        onClick={() => toggle(item.label)}
                        data-testid={`nav-${item.label.replace(/\s+/g, "-").toLowerCase()}`}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.5rem",
                          width: "100%",
                          padding: "0.4rem 1.125rem 0.4rem 0.875rem",
                          background: isActive
                            ? "hsl(213 75% 22% / 0.08)"
                            : isOpen ? "hsl(210 20% 97%)" : "transparent",
                          border: "none",
                          borderLeft: isActive ? "3px solid hsl(213 75% 22%)" : "3px solid transparent",
                          cursor: "pointer",
                          textAlign: "left",
                          borderRadius: "0 0.3rem 0.3rem 0",
                          transition: "background 0.15s",
                        }}
                      >
                        {/* Color dot */}
                        <div style={{
                          width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                          background: isActive ? item.color : "hsl(215 15% 75%)",
                          transition: "background 0.15s",
                        }} />
                        <span style={{
                          flex: 1,
                          fontSize: "0.75rem",
                          fontWeight: isActive ? 700 : 500,
                          color: isActive ? "hsl(213 75% 22%)" : "hsl(220 25% 25%)",
                          lineHeight: 1.35,
                        }}>
                          {item.label}
                        </span>
                        {item.highlight && (
                          <span style={{
                            fontSize: "0.5rem", fontWeight: 800, background: "hsl(38 60% 52%)",
                            color: "#fff", padding: "0.1rem 0.35rem", borderRadius: 999,
                            textTransform: "uppercase",
                          }}>★</span>
                        )}
                        {item.badge && !item.highlight && (
                          <span style={{
                            fontSize: "0.5rem", fontWeight: 700,
                            background: isActive ? item.color : "hsl(213 30% 88%)",
                            color: isActive ? "#fff" : "hsl(213 50% 35%)",
                            padding: "0.1rem 0.35rem", borderRadius: 999, minWidth: 16, textAlign: "center",
                          }}>{item.badge}</span>
                        )}
                        <svg
                          width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="hsl(215 15% 55%)" strokeWidth="2.5"
                          style={{ transform: isOpen ? "rotate(90deg)" : "none", transition: "transform 0.15s", flexShrink: 0 }}
                        >
                          <path d="m9 18 6-6-6-6"/>
                        </svg>
                      </button>

                      {isOpen && (
                        <div style={{ paddingLeft: "1.625rem", paddingBottom: "0.25rem" }}>
                          {item.subItems!.map((sub: any) => {
                            const subActive = location === sub.path;
                            return (
                              <Link
                                key={sub.label}
                                href={sub.path}
                                data-testid={`nav-sub-${sub.label.replace(/\s+/g, "-").toLowerCase()}`}
                                style={{
                                  display: "block",
                                  padding: "0.3rem 1rem 0.3rem 0.75rem",
                                  fontSize: "0.6875rem",
                                  fontWeight: subActive ? 700 : 500,
                                  color: subActive ? "hsl(213 75% 22%)" : "hsl(220 20% 38%)",
                                  textDecoration: "none",
                                  borderLeft: subActive
                                    ? "2px solid hsl(213 75% 22%)"
                                    : "1px solid hsl(213 30% 86%)",
                                  marginLeft: "0.25rem",
                                  borderRadius: "0 0.25rem 0.25rem 0",
                                  background: subActive ? "hsl(213 75% 22% / 0.06)" : "transparent",
                                  transition: "all 0.12s",
                                }}
                                onMouseEnter={e => {
                                  if (!subActive) {
                                    (e.currentTarget as HTMLElement).style.color = "hsl(213 75% 22%)";
                                    (e.currentTarget as HTMLElement).style.background = "hsl(213 40% 97%)";
                                  }
                                }}
                                onMouseLeave={e => {
                                  if (!subActive) {
                                    (e.currentTarget as HTMLElement).style.color = "hsl(220 20% 38%)";
                                    (e.currentTarget as HTMLElement).style.background = "transparent";
                                  }
                                }}
                              >
                                {subActive && (
                                  <span style={{ display: "inline-block", width: 4, height: 4, borderRadius: "50%", background: "hsl(213 75% 22%)", marginRight: 6, verticalAlign: "middle" }} />
                                )}
                                {sub.label}
                              </Link>
                            );
                          })}
                        </div>
                      )}
                    </>
                  ) : (
                    <Link
                      href={item.path}
                      data-testid={`nav-${item.label.replace(/\s+/g, "-").toLowerCase()}`}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        padding: "0.4rem 1.125rem 0.4rem 0.875rem",
                        background: item.etlHighlight
                          ? (location === item.path ? "linear-gradient(90deg,#C8922A,#a0661a)" : "hsl(38 60% 52% / 0.08)")
                          : item.downloadHighlight
                            ? (location === item.path ? "linear-gradient(90deg,hsl(152 60% 35%),hsl(152 60% 28%))" : "hsl(152 60% 40% / 0.07)")
                            : item.execHighlight
                              ? (location === item.path ? "linear-gradient(90deg,hsl(280 55% 45%),hsl(280 55% 35%))" : "hsl(280 55% 50% / 0.07)")
                              : (location === item.path ? "hsl(213 75% 22% / 0.08)" : "transparent"),
                        border: "none",
                        borderLeft: item.etlHighlight
                          ? "3px solid #C8922A"
                          : item.downloadHighlight
                            ? "3px solid hsl(152 60% 40%)"
                            : item.execHighlight
                              ? "3px solid hsl(280 55% 50%)"
                              : (location === item.path ? "3px solid hsl(213 75% 22%)" : "3px solid transparent"),
                        cursor: "pointer",
                        textAlign: "left",
                        borderRadius: "0 0.3rem 0.3rem 0",
                        textDecoration: "none",
                        transition: "background 0.15s",
                        width: "100%",
                      }}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                        stroke={
                          item.etlHighlight ? (location === item.path ? "#fff" : "#C8922A")
                          : item.downloadHighlight ? (location === item.path ? "#fff" : "hsl(152 60% 35%)")
                          : item.execHighlight ? (location === item.path ? "#fff" : "hsl(280 55% 50%)")
                          : (location === item.path ? "hsl(213 75% 22%)" : "hsl(215 15% 55%)")
                        }
                        strokeWidth="2">
                        <path d={item.icon} />
                      </svg>
                      <span style={{
                        flex: 1,
                        fontSize: "0.75rem",
                        fontWeight: item.etlHighlight || item.downloadHighlight ? 700 : (location === item.path ? 600 : 500),
                        color: item.etlHighlight
                          ? (location === item.path ? "#fff" : "#92400e")
                          : item.downloadHighlight
                            ? (location === item.path ? "#fff" : "hsl(152 60% 28%)")
                            : item.execHighlight
                              ? (location === item.path ? "#fff" : "hsl(280 55% 38%)")
                              : (location === item.path ? "hsl(213 75% 22%)" : "hsl(220 25% 25%)"),
                      }}>
                        {item.label}
                      </span>
                      {item.etlHighlight && (
                        <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                          <span style={{
                            width: 6, height: 6, borderRadius: "50%",
                            background: "#22c55e", boxShadow: "0 0 5px rgba(34,197,94,0.8)",
                            display: "inline-block",
                          }} />
                          <span style={{
                            fontSize: "0.5rem", fontWeight: 800, textTransform: "uppercase",
                            background: location === item.path ? "rgba(255,255,255,0.2)" : "rgba(200,146,42,0.18)",
                            color: location === item.path ? "#fff" : "#92400e",
                            padding: "0.1rem 0.35rem", borderRadius: 999,
                          }}>LIVE</span>
                        </span>
                      )}
                      {item.downloadHighlight && (
                        <span style={{
                          fontSize: "0.5rem", fontWeight: 800, textTransform: "uppercase",
                          background: location === item.path ? "rgba(255,255,255,0.2)" : "hsl(152 60% 40% / 0.15)",
                          color: location === item.path ? "#fff" : "hsl(152 60% 28%)",
                          padding: "0.1rem 0.4rem", borderRadius: 999,
                        }}>CSV</span>
                      )}
                    </Link>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <div style={{
        padding: "0.75rem 1.125rem",
        borderTop: "1px solid hsl(210 16% 90%)",
        flexShrink: 0,
      }}>
        <div style={{ fontSize: "0.5625rem", fontWeight: 700, color: "hsl(215 20% 45%)", marginBottom: "0.125rem" }}>
          KBA Consulting Group
        </div>
        <div style={{ fontSize: "0.5625rem", color: "hsl(215 15% 60%)" }}>in Partnership with RoZetta Technology</div>
        <div style={{ marginTop: "0.375rem" }}>
          <a href="https://www.perplexity.ai/computer" target="_blank" rel="noopener noreferrer"
            style={{ fontSize: "0.5625rem", color: "hsl(213 60% 55%)", textDecoration: "none" }}>
            Created with Perplexity Computer
          </a>
        </div>
      </div>
    </div>
  );
}
