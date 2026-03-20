import { useState, useMemo } from "react";
import { useActiveContext } from "../hooks/useMetrics";
import { useUnderlyingData } from "../hooks/useCompanies";
import { CompanyMetricRow, SectorSummaryRow, EpCohort } from "../lib/companyData";

// ─── Constants ────────────────────────────────────────────────────────────────

const cohortColor: Record<EpCohort, string> = {
  "EP Dominant":  "hsl(152 60% 40%)",
  "Middle Group": "hsl(38 60% 52%)",
  "EPS Dominant": "hsl(0 72% 51%)",
};

const tabs = ["Capital Market Metrics", "By Industry Sector", "Market Movements"];

// ─── Formatters ───────────────────────────────────────────────────────────────

const fmtPct = (v: number | null) => v !== null ? `${(v * 100).toFixed(1)}%` : "—";

function attractColor(a: "High" | "Medium" | "Low") {
  return a === "High" ? "hsl(152 60% 40%)" : a === "Medium" ? "hsl(38 60% 52%)" : "hsl(0 72% 51%)";
}

// ─── Sort helper ──────────────────────────────────────────────────────────────

type SortKey = keyof Pick<CompanyMetricRow, "ticker" | "name" | "sector" | "terKe" | "terAlpha" | "epPct" | "tsr" | "cohort">;

function sortRows(rows: CompanyMetricRow[], col: SortKey, dir: "asc" | "desc"): CompanyMetricRow[] {
  return [...rows].sort((a, b) => {
    const av = a[col], bv = b[col];
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return dir === "asc" ? cmp : -cmp;
  });
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function UnderlyingDataPage() {
  const ctx  = useActiveContext();
  const { rows, sectorSummary, loading, error } = useUnderlyingData(ctx.datasetId, ctx.paramSetId);

  const [activeTab,    setActiveTab]    = useState(0);
  const [sortCol,      setSortCol]      = useState<SortKey>("name");
  const [sortDir,      setSortDir]      = useState<"asc" | "desc">("asc");
  const [search,       setSearch]       = useState("");
  const [cohortFilter, setCohortFilter] = useState<"All" | EpCohort>("All");

  const toggleSort = (col: SortKey) => {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir("asc"); }
  };

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return rows.filter(r =>
      (cohortFilter === "All" || r.cohort === cohortFilter) &&
      (q === "" || r.name.toLowerCase().includes(q) || r.ticker.toLowerCase().includes(q) || r.sector.toLowerCase().includes(q))
    );
  }, [rows, cohortFilter, search]);

  const sorted = useMemo(() => sortRows(filtered, sortCol, sortDir), [filtered, sortCol, sortDir]);

  const SortIcon = ({ col }: { col: SortKey }) =>
    sortCol !== col ? null : (
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        {sortDir === "asc" ? <path d="m18 15-6-6-6 6"/> : <path d="m6 9 6 6 6-6"/>}
      </svg>
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
          <button key={t} className={`tab-pill ${activeTab === i ? "active" : ""}`}
            onClick={() => setActiveTab(i)} data-testid={`tab-data-${i}`}>
            {t}
          </button>
        ))}
      </div>

      {/* ── Tab 0: Capital Market Metrics ─────────────────────────────────── */}
      {activeTab === 0 && (
        <div>
          {/* Filter bar */}
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap", alignItems: "center" }}>
            <input
              type="text"
              placeholder="Search company, ticker or sector…"
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
              {(["All", "EP Dominant", "Middle Group", "EPS Dominant"] as const).map(c => (
                <button
                  key={c}
                  className={`select-btn ${cohortFilter === c ? "active" : ""}`}
                  style={{
                    background: cohortFilter === c ? (c === "All" ? "hsl(var(--primary))" : cohortColor[c as EpCohort]) : undefined,
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
              {loading ? "Loading…" : `${sorted.length} of ${rows.length} companies`}
            </div>
          </div>

          {error && (
            <div style={{ padding: "0.75rem", background: "hsl(0 72% 51% / 0.08)", border: "1px solid hsl(0 72% 51% / 0.3)", borderRadius: "0.375rem", fontSize: "0.8125rem", color: "hsl(0 72% 40%)", marginBottom: "1rem" }}>
              {error}
            </div>
          )}

          <div className="chart-card" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    {([
                      ["name",     "Company"],
                      ["ticker",   "Ticker"],
                      ["sector",   "Sector"],
                      ["terKe",    "TER-Ke"],
                      ["terAlpha", "TER Alpha"],
                      ["epPct",    "EP Margin"],
                      ["tsr",      "TSR"],
                      ["cohort",   "EP Cohort"],
                    ] as [SortKey, string][]).map(([col, label]) => (
                      <th key={col} style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                        onClick={() => toggleSort(col)} data-testid={`sort-${col}`}>
                        <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                          {label}<SortIcon col={col} />
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={8} style={{ textAlign: "center", padding: "2rem", color: "hsl(var(--muted-foreground))" }}>Loading…</td></tr>
                  ) : sorted.length === 0 ? (
                    <tr><td colSpan={8} style={{ textAlign: "center", padding: "2rem", color: "hsl(var(--muted-foreground))" }}>No results</td></tr>
                  ) : sorted.map((row, i) => (
                    <tr key={i} style={{ cursor: "default" }}
                      data-testid={`row-company-${row.ticker.replace(/\s+/g, "-").toLowerCase()}`}>
                      <td style={{ fontWeight: 600 }}>{row.name}</td>
                      <td style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", fontFamily: "monospace" }}>{row.ticker}</td>
                      <td style={{ color: "hsl(var(--muted-foreground))", fontSize: "0.75rem" }}>{row.sector}</td>
                      <td style={{ color: row.terKe !== null && row.terKe > 0 ? "hsl(152 60% 40%)" : row.terKe !== null && row.terKe < 0 ? "hsl(0 72% 51%)" : undefined, fontVariantNumeric: "tabular-nums" }}>
                        {fmtPct(row.terKe)}
                      </td>
                      <td style={{ color: row.terAlpha !== null && row.terAlpha > 0 ? "hsl(152 60% 40%)" : row.terAlpha !== null && row.terAlpha < 0 ? "hsl(0 72% 51%)" : undefined, fontVariantNumeric: "tabular-nums" }}>
                        {fmtPct(row.terAlpha)}
                      </td>
                      <td style={{ fontVariantNumeric: "tabular-nums" }}>{fmtPct(row.epPct)}</td>
                      <td style={{ color: row.tsr !== null && row.tsr > 0 ? "hsl(152 60% 40%)" : row.tsr !== null && row.tsr < 0 ? "hsl(0 72% 51%)" : undefined, fontVariantNumeric: "tabular-nums" }}>
                        {fmtPct(row.tsr)}
                      </td>
                      <td>
                        <span style={{
                          padding: "0.15rem 0.5rem", borderRadius: "9999px",
                          fontSize: "0.6875rem", fontWeight: 600,
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

      {/* ── Tab 1: By Industry Sector ──────────────────────────────────────── */}
      {activeTab === 1 && (
        <div>
          <div className="chart-card" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Industry Sector</th>
                    <th>Companies</th>
                    <th>Avg TER-Ke</th>
                    <th>Avg TER Alpha</th>
                    <th>Avg EP Margin</th>
                    <th>Attractiveness</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={6} style={{ textAlign: "center", padding: "2rem", color: "hsl(var(--muted-foreground))" }}>Loading…</td></tr>
                  ) : (sectorSummary as SectorSummaryRow[]).map((row, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{row.sector}</td>
                      <td>{row.companyCount}</td>
                      <td style={{ color: row.avgTerKe !== null && row.avgTerKe > 0 ? "hsl(152 60% 40%)" : undefined }}>{fmtPct(row.avgTerKe)}</td>
                      <td style={{ color: row.avgTerAlpha !== null && row.avgTerAlpha > 0 ? "hsl(152 60% 40%)" : undefined }}>{fmtPct(row.avgTerAlpha)}</td>
                      <td>{fmtPct(row.avgEpPct)}</td>
                      <td>
                        <span style={{ padding: "0.15rem 0.5rem", borderRadius: "9999px", fontSize: "0.6875rem", fontWeight: 600, background: `${attractColor(row.attractiveness)}22`, color: attractColor(row.attractiveness) }}>
                          {row.attractiveness}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="help-panel" style={{ marginTop: "1rem" }}>
            Economic profitability by industry sector can serve as an indicator of its economic attractiveness.
            Economic profitability by company within a sector can serve as an indicator of a company's competitive position.
            <strong> TER-Ke &gt; 0%</strong> indicates the sector is generating positive economic returns above the cost of equity.
          </div>
        </div>
      )}

      {/* ── Tab 2: Market Movements ────────────────────────────────────────── */}
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
