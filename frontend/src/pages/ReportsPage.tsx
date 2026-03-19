import { useState } from "react";

const REPORT_CATEGORIES = [
  {
    id: "platform",
    label: "Platform Overview",
    icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
    color: "hsl(213 75% 22%)",
    reports: [
      {
        title: "CISSA™ Digital Platform — Proposed Screens for Initial Platform",
        date: "May 2025",
        type: "Platform Design",
        pages: 179,
        description: "Comprehensive design specification for the CISSA Digital Platform, covering all six principles, outputs menu, underlying data menu, and further development roadmap.",
        tags: ["Platform", "Design", "Overview"],
        featured: true,
      },
      {
        title: "CISSA™ Framework Introduction",
        date: "March 2025",
        type: "Overview",
        pages: 42,
        description: "An accessible introduction to the CISSA framework — six principles for corporate governance and sustainable wealth creation, with practical application guides.",
        tags: ["Framework", "Introduction"],
        featured: false,
      },
    ],
  },
  {
    id: "principles",
    label: "Principles Research",
    icon: "M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z",
    color: "hsl(213 65% 35%)",
    reports: [
      {
        title: "Economic Measures vs. Accounting Measures — Evidence from the ASX 300",
        date: "2024",
        type: "Research Paper",
        pages: 38,
        description: "Empirical analysis demonstrating superior predictive power of Economic Profit (EP) over EPS in forecasting long-term TSR across ASX 300 companies, 2001–2019.",
        tags: ["Principle 1", "EP", "Research"],
        featured: true,
      },
      {
        title: "The EP Bow Wave: Long-Term Focus and Wealth Creation",
        date: "2024",
        type: "Research Paper",
        pages: 52,
        description: "Deep-dive into the Principle 2 bow wave framework — mathematical derivation, empirical validation across ASX 300 and S&P 500, and company case studies (Cochlear, REA, Microsoft).",
        tags: ["Principle 2", "Bow Wave", "Research"],
        featured: true,
      },
      {
        title: "Creativity, Innovation, and EP — A Capital Market Perspective",
        date: "2024",
        type: "Research Paper",
        pages: 29,
        description: "Evidence that companies with high R&D intensity and innovation investment sustain longer EP bow waves, justifying higher M:B ratios over time.",
        tags: ["Principle 3", "Innovation", "Research"],
        featured: false,
      },
      {
        title: "Stakeholder Capitalism and EP — Are They Aligned?",
        date: "2023",
        type: "Research Paper",
        pages: 24,
        description: "Examining whether companies with genuine multi-stakeholder governance outperform peers on long-term EP sustainability. Evidence from ESG-rated ASX companies.",
        tags: ["Principle 4", "Stakeholders", "ESG"],
        featured: false,
      },
    ],
  },
  {
    id: "company",
    label: "Company Reports",
    icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
    color: "hsl(38 60% 52%)",
    reports: [
      {
        title: "Cochlear — EP Bow Wave Analysis 2014–2024",
        date: "Q1 2025",
        type: "Company Report",
        pages: 18,
        description: "Detailed bow wave analysis for Cochlear (COH.AX). Quantifying the $3.1b enhancement to shareholder wealth through sustained EP growth driven by hearing implant innovation and global expansion.",
        tags: ["COH", "Bow Wave", "Company"],
        featured: false,
      },
      {
        title: "REA Group — EP Bow Wave Analysis 2014–2024",
        date: "Q1 2025",
        type: "Company Report",
        pages: 16,
        description: "REA Group (REA.AX) bow wave analysis. The $8.4b wealth creation attributable to dominant digital property platform network effects and EP well above sector peers.",
        tags: ["REA", "Bow Wave", "Company"],
        featured: false,
      },
      {
        title: "CSL Limited — EP Bow Wave Analysis 2014–2024",
        date: "Q1 2025",
        type: "Company Report",
        pages: 20,
        description: "CSL (CSL.AX) bow wave deep-dive. The $12.7b shareholder wealth enhancement driven by biotherapeutics leadership, R&D reinvestment, and Seqirus integration.",
        tags: ["CSL", "Bow Wave", "Company"],
        featured: false,
      },
      {
        title: "BHP Group — EP Bow Wave Analysis 2014–2024",
        date: "Q1 2025",
        type: "Company Report",
        pages: 17,
        description: "BHP (BHP.AX) bow wave analysis. The $18.5b reduction to shareholder wealth — examining commodity cycle impact, capital allocation decisions, and EP trajectory through the resources downturn.",
        tags: ["BHP", "Bow Wave", "Company"],
        featured: false,
      },
      {
        title: "Microsoft — EP Bow Wave Analysis (Global Case Study)",
        date: "Q4 2024",
        type: "Company Report",
        pages: 22,
        description: "Microsoft's cloud transformation under Satya Nadella generated a $420b+ bow wave expansion — one of the most dramatic EP re-ratings in capital market history. Full CISSA analysis.",
        tags: ["MSFT", "Bow Wave", "Global"],
        featured: true,
      },
      {
        title: "ASX 300 Wealth Creation Report — Full Year 2024",
        date: "February 2025",
        type: "Index Report",
        pages: 64,
        description: "Annual wealth creation analysis across the ASX 300 using CISSA metrics. Includes EP ranking, bow wave scores, TSR-Ke attribution, and sector breakdowns.",
        tags: ["ASX 300", "Annual", "Index"],
        featured: true,
      },
    ],
  },
  {
    id: "methodology",
    label: "Methodology",
    icon: "M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18",
    color: "hsl(188 78% 35%)",
    reports: [
      {
        title: "CISSA Methodology Manual — Version 3.1",
        date: "January 2025",
        type: "Methodology",
        pages: 88,
        description: "Complete technical specification for the CISSA measurement system: EP calculation, Ke estimation, bow wave construction, TSR-Ke decomposition, and wealth creation reconciliation.",
        tags: ["Methodology", "Technical"],
        featured: true,
      },
      {
        title: "Cost of Equity Capital (Ke) Estimation — ASX 300 2001–2024",
        date: "2024",
        type: "Technical Note",
        pages: 12,
        description: "Technical note on the CISSA approach to estimating Ke for Australian equities — CAPM calibration, term premium adjustments, and market-wide Ke benchmark derivation.",
        tags: ["Ke", "Methodology", "Technical"],
        featured: false,
      },
      {
        title: "EP Bridge Construction — From GAAP to Economic Profit",
        date: "2024",
        type: "Technical Note",
        pages: 15,
        description: "Step-by-step guide to building the financial and capital bridge from GAAP-reported financials to Economic Profit. Covers 23 adjustments across five adjustment categories.",
        tags: ["EP", "Bridge", "Technical"],
        featured: false,
      },
    ],
  },
];

type FilterMode = "all" | "featured";

export default function ReportsPage() {
  const [activeCategory, setActiveCategory] = useState<string>("all");
  const [filter, setFilter] = useState<FilterMode>("all");
  const [search, setSearch] = useState("");

  const allReports = REPORT_CATEGORIES.flatMap(cat =>
    cat.reports.map(r => ({ ...r, categoryId: cat.id, categoryLabel: cat.label, categoryColor: cat.color }))
  );

  const displayReports = (activeCategory === "all"
    ? allReports
    : allReports.filter(r => r.categoryId === activeCategory)
  ).filter(r => {
    if (filter === "featured" && !r.featured) return false;
    if (search) {
      const q = search.toLowerCase();
      return r.title.toLowerCase().includes(q) ||
        r.description.toLowerCase().includes(q) ||
        r.tags.some(t => t.toLowerCase().includes(q));
    }
    return true;
  });

  const totalReports = allReports.length;
  const featuredCount = allReports.filter(r => r.featured).length;

  return (
    <div style={{ padding: "1.5rem", maxWidth: "1400px" }}>

      {/* Header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "hsl(var(--primary))", margin: "0 0 0.25rem 0" }}>
          Reports &amp; Research
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))", margin: 0, lineHeight: 1.6 }}>
          CISSA platform research papers, company EP bow wave analyses, methodology documentation, and index-level reports. {totalReports} reports across {REPORT_CATEGORIES.length} categories.
        </p>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
        {[
          { label: "Total Reports", value: totalReports, note: "Across all categories", color: "hsl(213 75% 22%)" },
          { label: "Featured", value: featuredCount, note: "Recommended reading", color: "hsl(38 60% 52%)" },
          { label: "Research Papers", value: allReports.filter(r => r.type === "Research Paper").length, note: "Peer-reviewed analysis", color: "hsl(213 65% 35%)" },
          { label: "Company Reports", value: allReports.filter(r => r.type === "Company Report" || r.type === "Index Report").length, note: "Individual & index", color: "hsl(188 78% 35%)" },
        ].map(s => (
          <div key={s.label} className="kpi-card" data-testid={`stat-${s.label.toLowerCase().replace(/\s+/g, "-")}`}>
            <div className="kpi-label">{s.label}</div>
            <div className="kpi-value" style={{ color: s.color }}>{s.value}</div>
            <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginTop: "0.25rem" }}>{s.note}</div>
          </div>
        ))}
      </div>

      {/* Filters row */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.25rem", flexWrap: "wrap" }}>
        {/* Search */}
        <div style={{ position: "relative", flex: "1", minWidth: "200px", maxWidth: "320px" }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--muted-foreground))" strokeWidth="2"
            style={{ position: "absolute", left: "0.625rem", top: "50%", transform: "translateY(-50%)" }}>
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            type="text"
            placeholder="Search reports..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            data-testid="search-reports"
            style={{
              width: "100%",
              padding: "0.4375rem 0.75rem 0.4375rem 2rem",
              borderRadius: "0.375rem",
              border: "1px solid hsl(var(--border))",
              background: "hsl(var(--background))",
              color: "hsl(var(--foreground))",
              fontSize: "0.8125rem",
              boxSizing: "border-box",
            }}
          />
        </div>

        {/* Category filter pills */}
        <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
          {[{ id: "all", label: "All" }, ...REPORT_CATEGORIES.map(c => ({ id: c.id, label: c.label }))].map(cat => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              data-testid={`filter-${cat.id}`}
              style={{
                padding: "0.3125rem 0.75rem",
                borderRadius: "999px",
                border: activeCategory === cat.id ? "none" : "1px solid hsl(var(--border))",
                background: activeCategory === cat.id ? "hsl(213 75% 22%)" : "hsl(var(--background))",
                color: activeCategory === cat.id ? "#fff" : "hsl(var(--muted-foreground))",
                fontSize: "0.75rem",
                fontWeight: activeCategory === cat.id ? 700 : 400,
                cursor: "pointer",
                transition: "all 150ms",
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Featured toggle */}
        <button
          onClick={() => setFilter(f => f === "featured" ? "all" : "featured")}
          data-testid="toggle-featured"
          style={{
            padding: "0.3125rem 0.75rem",
            borderRadius: "999px",
            border: filter === "featured" ? "none" : "1px solid hsl(var(--border))",
            background: filter === "featured" ? "hsl(38 60% 52%)" : "hsl(var(--background))",
            color: filter === "featured" ? "#fff" : "hsl(var(--muted-foreground))",
            fontSize: "0.75rem",
            fontWeight: filter === "featured" ? 700 : 400,
            cursor: "pointer",
            transition: "all 150ms",
            display: "flex",
            alignItems: "center",
            gap: "0.25rem",
          }}
        >
          ★ Featured only
        </button>

        <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", marginLeft: "auto" }}>
          {displayReports.length} report{displayReports.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Report cards */}
      {displayReports.length === 0 ? (
        <div className="chart-card" style={{ textAlign: "center", padding: "3rem", color: "hsl(var(--muted-foreground))" }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"
            style={{ margin: "0 auto 1rem", opacity: 0.3, display: "block" }}>
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <p style={{ margin: 0, fontWeight: 600, fontSize: "0.875rem" }}>No reports match your filters</p>
          <p style={{ margin: "0.25rem 0 0", fontSize: "0.75rem" }}>Try adjusting the category or search query</p>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          {displayReports.map((report, i) => (
            <div
              key={i}
              className="chart-card"
              data-testid={`report-card-${i}`}
              style={{
                cursor: "pointer",
                transition: "box-shadow 150ms, transform 150ms",
                borderLeft: `3px solid ${report.categoryColor}`,
                position: "relative",
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 20px rgba(0,0,0,0.1)";
                (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = "";
                (e.currentTarget as HTMLElement).style.transform = "";
              }}
            >
              {/* Featured badge */}
              {report.featured && (
                <div style={{
                  position: "absolute", top: "0.75rem", right: "0.75rem",
                  background: "hsl(38 60% 52%)",
                  color: "#fff",
                  fontSize: "0.625rem",
                  fontWeight: 700,
                  padding: "0.1875rem 0.5rem",
                  borderRadius: "999px",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}>
                  ★ Featured
                </div>
              )}

              {/* Report type + date */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                <span style={{
                  fontSize: "0.6875rem",
                  fontWeight: 600,
                  color: report.categoryColor,
                  background: `${report.categoryColor}18`,
                  padding: "0.15rem 0.5rem",
                  borderRadius: "0.25rem",
                }}>
                  {report.type}
                </span>
                <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>{report.date}</span>
                <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>·</span>
                <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>{report.pages} pages</span>
              </div>

              {/* Title */}
              <div style={{
                fontWeight: 700,
                fontSize: "0.875rem",
                color: "hsl(var(--foreground))",
                marginBottom: "0.5rem",
                lineHeight: 1.4,
                paddingRight: report.featured ? "4.5rem" : 0,
              }}>
                {report.title}
              </div>

              {/* Description */}
              <p style={{
                fontSize: "0.75rem",
                color: "hsl(var(--muted-foreground))",
                lineHeight: 1.65,
                margin: "0 0 0.75rem 0",
              }}>
                {report.description}
              </p>

              {/* Tags + download button */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
                <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
                  {report.tags.map(tag => (
                    <span key={tag} style={{
                      fontSize: "0.625rem",
                      color: "hsl(var(--muted-foreground))",
                      background: "hsl(var(--muted))",
                      padding: "0.125rem 0.5rem",
                      borderRadius: "999px",
                      border: "1px solid hsl(var(--border))",
                    }}>
                      {tag}
                    </span>
                  ))}
                </div>

                <button
                  data-testid={`btn-download-${i}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.375rem",
                    padding: "0.375rem 0.75rem",
                    borderRadius: "0.375rem",
                    border: `1px solid ${report.categoryColor}`,
                    background: "transparent",
                    color: report.categoryColor,
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "all 150ms",
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLElement).style.background = report.categoryColor;
                    (e.currentTarget as HTMLElement).style.color = "#fff";
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.background = "transparent";
                    (e.currentTarget as HTMLElement).style.color = report.categoryColor;
                  }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                  </svg>
                  View Report
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
