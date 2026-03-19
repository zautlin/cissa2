import { useState } from "react";
import { Link, useLocation } from "wouter";

const navData = [
  {
    section: "Principles Menu",
    items: [
      {
        label: "Principle 1: Economic Measures",
        path: "/principles/1",
        badge: "6",
        subItems: [
          { label: "1.1  Cost of Equity Capital (Ke)", path: "/principles/1" },
          { label: "1.2  Financial & Capital Bridge", path: "/principles/1" },
          { label: "1.3  Products & Services Market", path: "/principles/1" },
          { label: "1.4  Capital Market Predictor", path: "/principles/1" },
          { label: "1.5  Capital Market Assessment", path: "/principles/1" },
        ],
      },
      {
        label: "Principle 2: Long-Term Focus",
        path: "/principles/2",
        badge: "5",
        highlight: true,
        subItems: [
          { label: "2.1  Market Value & EP", path: "/principles/2" },
          { label: "2.2  Bow Wave Concept", path: "/principles/2" },
          { label: "2.3  Pair of EP Bow Waves", path: "/principles/2" },
          { label: "2.4  Long-Term Focus Proof", path: "/principles/2" },
          { label: "2.5  Reconciling Wealth Creation", path: "/principles/2" },
        ],
      },
      { label: "Principle 3: Creativity & Innovation", path: "/principles/1", subItems: [] },
      { label: "A New Way to Think About Economics", path: "/principles/1", subItems: [], italic: true },
      { label: "Principle 4: All Stakeholders", path: "/principles/1", subItems: [] },
      { label: "Principle 5: Noble Intent", path: "/principles/1", subItems: [] },
      { label: "Principle 6: More is Not Always Better", path: "/principles/1", subItems: [] },
    ],
  },
  {
    section: "Outputs Menu",
    items: [
      { label: "Wealth Creation Overview", path: "/outputs", subItems: [] },
      { label: "TSR-Ke Analysis", path: "/outputs", subItems: [] },
      { label: "Intrinsic Wealth Creation", path: "/outputs", subItems: [] },
      { label: "Sustainable Wealth Creation", path: "/outputs", subItems: [] },
    ],
  },
  {
    section: "Underlying Data",
    items: [
      { label: "Capital Market Metrics", path: "/underlying-data", subItems: [] },
      { label: "Financial or Products & Services", path: "/underlying-data", subItems: [] },
      { label: "Market Movements", path: "/underlying-data", subItems: [] },
    ],
  },
  {
    section: "Reports",
    items: [
      { label: "Reports & Research", path: "/reports", subItems: [] },
      { label: "Metrics Download", path: "/download", subItems: [], badge: "CSV", downloadHighlight: true },
    ],
  },
  {
    section: "Platform",
    items: [
      { label: "ETL Pipeline", path: "/pipeline", subItems: [], badge: "NEW", etlHighlight: true },
    ],
  },
];

export default function Sidebar() {
  const [location] = useLocation();
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    "Principle 1: Economic Measures": true,
    "Principle 2: Long-Term Focus": false,
  });

  const toggleSection = (label: string) => {
    setOpenSections(prev => ({ ...prev, [label]: !prev[label] }));
  };

  return (
    <div>
      {/* Logo area */}
      <div className="sidebar-logo">
        <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
          {/* CISSA SVG Logo */}
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-label="CISSA" xmlns="http://www.w3.org/2000/svg">
            <rect width="32" height="32" rx="6" fill="hsl(38 60% 52%)"/>
            <path d="M8 16 C8 10.5 11 8 16 8 C19.5 8 22 9.5 23.5 12" stroke="white" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
            <path d="M8 16 C8 21.5 11 24 16 24 C19.5 24 22 22.5 23.5 20" stroke="white" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
            <circle cx="16" cy="16" r="2.5" fill="white"/>
          </svg>
          <div>
            <div style={{ fontWeight: 700, fontSize: "1rem", color: "hsl(213 75% 22%)", letterSpacing: "-0.01em", lineHeight: 1.1 }}>
              CISSA<sup style={{ fontSize: "0.5rem", verticalAlign: "super" }}>™</sup>
            </div>
            <div style={{ fontSize: "0.625rem", color: "hsl(215 20% 50%)", letterSpacing: "0.04em", textTransform: "uppercase", lineHeight: 1 }}>
              Digital Platform
            </div>
          </div>
        </div>
        <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "center", gap: "0.375rem" }}>
          <div style={{
            width: "6px", height: "6px", borderRadius: "50%", background: "hsl(152 60% 55%)",
            boxShadow: "0 0 6px hsl(152 60% 55% / 0.8)"
          }} />
          <span style={{ fontSize: "0.6875rem", color: "hsl(215 20% 50%)" }}>Live data — ASX 300</span>
        </div>
      </div>

      {/* Navigation */}
      {navData.map(section => (
        <div key={section.section} className="sidebar-nav-section">
          <div className="sidebar-section-label">{section.section}</div>
          {section.items.map(item => {
            const hasChildren = item.subItems && item.subItems.length > 0;
            const isOpen = openSections[item.label];
            const isActive = location === item.path || (hasChildren && item.subItems!.some(s => location === s.path));

            return (
              <div key={item.label}>
                {hasChildren ? (
                  <button
                    className={`sidebar-nav-item ${isActive ? "active" : ""} ${isOpen ? "open" : ""}`}
                    onClick={() => toggleSection(item.label)}
                    data-testid={`nav-${item.label.replace(/\s+/g, "-").toLowerCase()}`}
                    style={(item as any).highlight ? { position: "relative" } : undefined}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/>
                    </svg>
                    <span style={{ flex: 1, fontStyle: (item as any).italic ? "italic" : undefined }}>{item.label}</span>
                    {(item as any).highlight && (
                      <span style={{
                        fontSize: "0.5625rem", fontWeight: 700,
                        background: "hsl(38 60% 52%)", color: "#fff",
                        padding: "0.1rem 0.35rem", borderRadius: "999px",
                        textTransform: "uppercase", letterSpacing: "0.02em",
                        marginRight: "0.125rem",
                      }}>★</span>
                    )}
                    {item.badge && <span className="nav-badge">{item.badge}</span>}
                    <svg className="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="m9 18 6-6-6-6"/>
                    </svg>
                  </button>
                ) : (
                  <Link
                    href={item.path}
                    className={`sidebar-nav-item ${location === item.path && !hasChildren ? "active" : ""}`}
                    data-testid={`nav-${item.label.replace(/\s+/g, "-").toLowerCase()}`}
                    style={(item as any).downloadHighlight ? {
                      background: location === item.path
                        ? "linear-gradient(90deg, hsl(152 60% 35%) 0%, hsl(152 60% 28%) 100%)"
                        : "linear-gradient(90deg, hsl(152 60% 40% / 0.1) 0%, hsl(152 60% 40% / 0.05) 100%)",
                      border: "1px solid hsl(152 60% 40% / 0.3)",
                      borderLeft: "3px solid hsl(152 60% 40%)",
                      borderRadius: 7,
                      marginLeft: "0.25rem",
                      marginRight: "0.25rem",
                      color: location === item.path ? "#fff" : "hsl(152 60% 28%)",
                      fontWeight: 700,
                    } : (item as any).etlHighlight ? {
                      background: location === item.path
                        ? "linear-gradient(90deg, #C8922A 0%, #a0661a 100%)"
                        : "linear-gradient(90deg, rgba(200,146,42,0.12) 0%, rgba(200,146,42,0.06) 100%)",
                      border: "1px solid rgba(200,146,42,0.35)",
                      borderLeft: "3px solid #C8922A",
                      borderRadius: 7,
                      marginLeft: "0.25rem",
                      marginRight: "0.25rem",
                      color: location === item.path ? "#fff" : "#92400e",
                      fontWeight: 700,
                      boxShadow: "0 2px 8px rgba(200,146,42,0.18)",
                    } : undefined}
                  >
                    {(item as any).downloadHighlight ? (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={location === item.path ? "#fff" : "hsl(152 60% 35%)"} strokeWidth="2">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                      </svg>
                    ) : (item as any).etlHighlight ? (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={location === item.path ? "#fff" : "#C8922A"} strokeWidth="2">
                        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                      </svg>
                    ) : (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>
                      </svg>
                    )}
                    <span style={{ fontStyle: (item as any).italic ? "italic" : undefined, flex: 1 }}>{item.label}</span>
                    {(item as any).downloadHighlight && (
                      <span style={{
                        fontSize: "0.5rem", fontWeight: 800,
                        textTransform: "uppercase" as const, letterSpacing: "0.06em",
                        background: location === item.path ? "rgba(255,255,255,0.3)" : "hsl(152 60% 40% / 0.15)",
                        color: location === item.path ? "#fff" : "hsl(152 60% 28%)",
                        padding: "0.1rem 0.4rem", borderRadius: 999,
                        border: location === item.path ? "1px solid rgba(255,255,255,0.3)" : "1px solid hsl(152 60% 40% / 0.3)",
                      }}>CSV</span>
                    )}
                    {(item as any).etlHighlight && (
                      <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                        <span style={{
                          width: 7, height: 7, borderRadius: "50%",
                          background: "#22c55e",
                          boxShadow: "0 0 6px rgba(34,197,94,0.8)",
                          animation: "pipeline-pulse 1.8s ease-in-out infinite",
                          display: "inline-block",
                        }} />
                        <span style={{
                          fontSize: "0.5rem", fontWeight: 800,
                          textTransform: "uppercase" as const, letterSpacing: "0.06em",
                          background: location === item.path ? "rgba(255,255,255,0.25)" : "rgba(200,146,42,0.18)",
                          color: location === item.path ? "#fff" : "#92400e",
                          padding: "0.1rem 0.4rem", borderRadius: 999,
                          border: location === item.path ? "1px solid rgba(255,255,255,0.3)" : "1px solid rgba(200,146,42,0.3)",
                        }}>NEW</span>
                      </span>
                    )}
                    {!(item as any).etlHighlight && !(item as any).downloadHighlight && (item as any).badge && <span className="nav-badge">{(item as any).badge}</span>}
                  </Link>
                )}

                {hasChildren && isOpen && (
                  <div>
                    {item.subItems!.map(sub => (
                      <Link
                        key={sub.label}
                        href={sub.path}
                        className={`sidebar-nav-item sub`}
                        data-testid={`nav-sub-${sub.label.replace(/\s+/g, "-").toLowerCase()}`}
                      >
                        {sub.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}

      {/* Footer */}
      <div style={{
        padding: "1rem 1.25rem",
        borderTop: "1px solid hsl(var(--sidebar-border))",
        marginTop: "auto",
        fontSize: "0.625rem",
        color: "hsl(210 15% 40%)",
        lineHeight: 1.5,
      }}>
        <div style={{ marginBottom: "0.25rem", fontWeight: 600, fontSize: "0.6875rem", color: "hsl(210 15% 50%)" }}>
          KBA Consulting Group
        </div>
        <div>in Partnership with RoZetta Technology</div>
        <div style={{ marginTop: "0.5rem" }}>
          <a href="https://www.perplexity.ai/computer" target="_blank" rel="noopener noreferrer"
             style={{ color: "hsl(213 60% 55%)", textDecoration: "none" }}>
            Created with Perplexity Computer
          </a>
        </div>
      </div>
    </div>
  );
}
