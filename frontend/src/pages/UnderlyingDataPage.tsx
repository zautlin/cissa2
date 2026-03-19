import { useState } from "react";

const capitalMarketData = [
  { company: "BHP Group", sector: "Materials", roeKe: "12.4%", terKe: "8.2%", mb: "3.1×", tsrAlpha: "5.8%", epGrowth: "15.2%", cohort: "EP Dominant" },
  { company: "Commonwealth Bank", sector: "Financials", roeKe: "11.8%", terKe: "7.6%", mb: "2.9×", tsrAlpha: "4.2%", epGrowth: "12.4%", cohort: "EP Dominant" },
  { company: "CSL Limited", sector: "Healthcare", roeKe: "18.5%", terKe: "14.2%", mb: "5.8×", tsrAlpha: "11.6%", epGrowth: "22.1%", cohort: "EP Dominant" },
  { company: "Woolworths Group", sector: "Consumer Staples", roeKe: "8.4%", terKe: "4.1%", mb: "2.4×", tsrAlpha: "1.4%", epGrowth: "8.7%", cohort: "Middle Group" },
  { company: "Telstra Group", sector: "Comm. Services", roeKe: "5.2%", terKe: "0.8%", mb: "1.8×", tsrAlpha: "-2.1%", epGrowth: "3.2%", cohort: "EPS Dominant" },
  { company: "ANZ Banking", sector: "Financials", roeKe: "7.6%", terKe: "3.4%", mb: "1.6×", tsrAlpha: "-0.8%", epGrowth: "5.8%", cohort: "EPS Dominant" },
  { company: "Rio Tinto", sector: "Materials", roeKe: "13.6%", terKe: "9.4%", mb: "2.8×", tsrAlpha: "6.2%", epGrowth: "16.4%", cohort: "EP Dominant" },
  { company: "Wesfarmers", sector: "Industrials", roeKe: "10.2%", terKe: "6.1%", mb: "2.6×", tsrAlpha: "3.2%", epGrowth: "10.8%", cohort: "Middle Group" },
  { company: "National Australia Bank", sector: "Financials", roeKe: "6.8%", terKe: "2.6%", mb: "1.4×", tsrAlpha: "-1.6%", epGrowth: "4.8%", cohort: "EPS Dominant" },
  { company: "Macquarie Group", sector: "Financials", roeKe: "15.4%", terKe: "11.2%", mb: "3.8×", tsrAlpha: "8.4%", epGrowth: "18.6%", cohort: "EP Dominant" },
];

const sectorSummary = [
  { sector: "Materials", avgRoeKe: "13.0%", avgTerKe: "8.8%", avgMb: "2.9×", companies: 42 },
  { sector: "Financials", avgRoeKe: "9.6%", avgTerKe: "5.4%", avgMb: "2.1×", companies: 38 },
  { sector: "Healthcare", avgRoeKe: "16.2%", avgTerKe: "12.1%", avgMb: "4.6×", companies: 24 },
  { sector: "Consumer Staples", avgRoeKe: "8.8%", avgTerKe: "4.6%", avgMb: "2.4×", companies: 18 },
  { sector: "Energy", avgRoeKe: "7.4%", avgTerKe: "3.2%", avgMb: "1.9×", companies: 22 },
  { sector: "Industrials", avgRoeKe: "10.4%", avgTerKe: "6.2%", avgMb: "2.7×", companies: 30 },
  { sector: "Comm. Services", avgRoeKe: "5.8%", avgTerKe: "1.6%", avgMb: "1.6×", companies: 14 },
  { sector: "Info. Technology", avgRoeKe: "14.8%", avgTerKe: "10.4%", avgMb: "4.2×", companies: 28 },
];

const cohortColor: Record<string, string> = {
  "EP Dominant": "hsl(152 60% 40%)",
  "Middle Group": "hsl(38 60% 52%)",
  "EPS Dominant": "hsl(0 72% 51%)",
};

const tabs = ["Capital Market Metrics", "By Industry Sector", "Market Movements"];

export default function UnderlyingDataPage() {
  const [activeTab, setActiveTab] = useState(0);
  const [sortCol, setSortCol] = useState("company");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [search, setSearch] = useState("");
  const [cohortFilter, setCohortFilter] = useState("All");

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir("asc"); }
  };

  const filtered = capitalMarketData.filter(r =>
    (cohortFilter === "All" || r.cohort === cohortFilter) &&
    (search === "" || r.company.toLowerCase().includes(search.toLowerCase()) || r.sector.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div style={{ padding: "1.5rem", maxWidth: "1400px" }}>
      <div style={{ marginBottom: "1.25rem" }}>
        <h1 style={{ fontSize: "1.125rem", fontWeight: 700, color: "hsl(var(--foreground))", marginBottom: "0.25rem" }}>
          Underlying Data Menu
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))" }}>
          Raw underlying data organised by the components of performance achieved in the product &amp; service market and capital market.
          For most users, the underlying data screens will only be meaningful after traversing the Principles Menu.
        </p>
      </div>

      {/* Tabs */}
      <div className="tab-pills" style={{ marginBottom: "1.25rem", width: "fit-content" }}>
        {tabs.map((t, i) => (
          <button key={t} className={`tab-pill ${activeTab === i ? "active" : ""}`} onClick={() => setActiveTab(i)}
            data-testid={`tab-data-${i}`}>
            {t}
          </button>
        ))}
      </div>

      {/* Capital Market Metrics */}
      {activeTab === 0 && (
        <div>
          {/* Filter bar */}
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap", alignItems: "center" }}>
            <input
              type="text"
              placeholder="Search company or sector…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              data-testid="input-search"
              style={{
                padding: "0.375rem 0.75rem",
                border: "1px solid hsl(var(--border))",
                borderRadius: "0.375rem",
                fontSize: "0.8125rem",
                background: "hsl(var(--card))",
                color: "hsl(var(--foreground))",
                minWidth: "220px",
              }}
            />
            <div style={{ display: "flex", gap: "0.375rem" }}>
              {["All", "EP Dominant", "Middle Group", "EPS Dominant"].map(c => (
                <button
                  key={c}
                  className={`select-btn ${cohortFilter === c ? "active" : ""}`}
                  style={{
                    background: cohortFilter === c ? (c === "All" ? "hsl(var(--primary))" : cohortColor[c] || "hsl(var(--primary))") : undefined,
                    color: cohortFilter === c ? "#fff" : undefined,
                    borderColor: cohortFilter === c ? "transparent" : undefined,
                  }}
                  onClick={() => setCohortFilter(c)}
                  data-testid={`filter-cohort-${c.replace(/\s+/g, "-")}`}
                >
                  {c}
                </button>
              ))}
            </div>
            <div style={{ marginLeft: "auto", fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>
              {filtered.length} companies · ASX 300 · 2001–2024
            </div>
          </div>

          <div className="chart-card" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    {[
                      ["company", "Company"],
                      ["sector", "Sector"],
                      ["roeKe", "ROE-Ke"],
                      ["terKe", "TER-Ke"],
                      ["mb", "M:B Ratio"],
                      ["tsrAlpha", "TSR Alpha"],
                      ["epGrowth", "EP/Share Growth"],
                      ["cohort", "EP Cohort"],
                    ].map(([col, label]) => (
                      <th key={col}
                        style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                        onClick={() => toggleSort(col)}
                        data-testid={`sort-${col}`}
                      >
                        <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                          {label}
                          {sortCol === col && (
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                              {sortDir === "asc"
                                ? <path d="m18 15-6-6-6 6"/>
                                : <path d="m6 9 6 6 6-6"/>}
                            </svg>
                          )}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row, i) => (
                    <tr key={i} style={{ cursor: "pointer" }}
                      data-testid={`row-company-${row.company.replace(/\s+/g, "-").toLowerCase()}`}
                    >
                      <td style={{ fontWeight: 600 }}>{row.company}</td>
                      <td style={{ color: "hsl(var(--muted-foreground))", fontSize: "0.75rem" }}>{row.sector}</td>
                      <td style={{ color: parseFloat(row.roeKe) > 10 ? "hsl(152 60% 40%)" : undefined, fontVariantNumeric: "tabular-nums" }}>{row.roeKe}</td>
                      <td style={{ color: parseFloat(row.terKe) > 5 ? "hsl(152 60% 40%)" : undefined, fontVariantNumeric: "tabular-nums" }}>{row.terKe}</td>
                      <td style={{ fontVariantNumeric: "tabular-nums" }}>{row.mb}</td>
                      <td style={{ color: row.tsrAlpha.startsWith("-") ? "hsl(0 72% 51%)" : "hsl(152 60% 40%)", fontVariantNumeric: "tabular-nums" }}>{row.tsrAlpha}</td>
                      <td style={{ fontVariantNumeric: "tabular-nums" }}>{row.epGrowth}</td>
                      <td>
                        <span style={{
                          padding: "0.15rem 0.5rem",
                          borderRadius: "9999px",
                          fontSize: "0.6875rem",
                          fontWeight: 600,
                          background: `${cohortColor[row.cohort]}22`,
                          color: cohortColor[row.cohort],
                        }}>
                          {row.cohort}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Sector summary */}
      {activeTab === 1 && (
        <div>
          <div className="chart-card" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Industry Sector</th>
                    <th>Companies</th>
                    <th>Avg ROE-Ke</th>
                    <th>Avg TER-Ke</th>
                    <th>Avg M:B</th>
                    <th>Attractiveness</th>
                  </tr>
                </thead>
                <tbody>
                  {sectorSummary.map((row, i) => {
                    const roeVal = parseFloat(row.avgRoeKe);
                    const attractive = roeVal > 12 ? "High" : roeVal > 9 ? "Medium" : "Low";
                    const attractColor = roeVal > 12 ? "hsl(152 60% 40%)" : roeVal > 9 ? "hsl(38 60% 52%)" : "hsl(0 72% 51%)";
                    return (
                      <tr key={i}>
                        <td style={{ fontWeight: 600 }}>{row.sector}</td>
                        <td>{row.companies}</td>
                        <td style={{ color: parseFloat(row.avgRoeKe) > 10 ? "hsl(152 60% 40%)" : undefined }}>{row.avgRoeKe}</td>
                        <td style={{ color: parseFloat(row.avgTerKe) > 5 ? "hsl(152 60% 40%)" : undefined }}>{row.avgTerKe}</td>
                        <td>{row.avgMb}</td>
                        <td>
                          <span style={{ padding: "0.15rem 0.5rem", borderRadius: "9999px", fontSize: "0.6875rem", fontWeight: 600, background: `${attractColor}22`, color: attractColor }}>
                            {attractive}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="help-panel" style={{ marginTop: "1rem" }}>
            Economic profitability by industry sector can serve as an indicator of its economic attractiveness.
            Economic profitability by company within a sector can serve as an indicator of a company's competitive position.
            <strong> ROE-Ke &gt; 10%</strong> (i.e. ROE-Ke &gt; 0) indicates the sector is generating positive economic returns above the cost of equity.
          </div>
        </div>
      )}

      {/* Market Movements */}
      {activeTab === 2 && (
        <div className="help-panel" style={{ textAlign: "center", padding: "3rem" }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.5"
            style={{ margin: "0 auto 1rem" }}>
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
          <div style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Market Movements Data</div>
          <div style={{ color: "hsl(var(--muted-foreground))", fontSize: "0.875rem" }}>
            TER Alpha = TER-Ke minus the Risk-Adjusted Impact of Underlying Market Movements.
            This screen is in development. Navigate to Principle 1 → Section 1.1 for TER Alpha analysis.
          </div>
        </div>
      )}

    </div>
  );
}
