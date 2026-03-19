import { useState } from "react";
import { Line, Bar, Scatter } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend, Filler,
} from "chart.js";
import {
  eeaiHeatmapData, epDeliveredVsRequired, eeaiRequired, eeaiIndexCount,
  sectorEpVsMarketScatter, epHeatmapData, eeaiYears,
  epPerShareBySector,
} from "../data/chartData";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend, Filler);

const subSections = [
  { id: "4.1", label: "EEAI Overview" },
  { id: "4.2", label: "EEAI Heatmap" },
  { id: "4.3", label: "EP Delivered vs Required" },
  { id: "4.4", label: "Sector Aggregations" },
  { id: "4.5", label: "Sector EP Score" },
];

const helpTexts: Record<string, string> = {
  "4.1": "The EEAI (Empirical EP Alignment Index) measures how well a company's delivered EP aligns with the EP embedded in its market price. A score of 100 means exact alignment. Above 100 means over-delivering vs market expectations. Below 100 means under-delivering. The index is clipped to [0, 200].",
  "4.2": "The EEAI company heatmap shows individual company alignment across years. Deep blue = strong alignment / over-delivery. Red = significant expectation shortfall. Companies like CSL, COH, and ALU consistently over-deliver. TLS is a classic under-deliverer.",
  "4.3": "EP Required is the 3Y average EP% implied by the current market cap and Ke. EP Delivered is the actual 3Y average. The gap drives EEAI. Persistently negative gaps lead to valuation derating; persistently positive gaps drive re-rating.",
  "4.4": "Sector aggregations compute weighted-average metrics ($ metrics by SUM, rate metrics by EE-weighted average). This reveals structural sector differences in capital efficiency, cost structure, and wealth creation capacity.",
  "4.5": "The EP Score Heatmap maps normalised economic profit scores across sectors and years. Scores above zero indicate EP dominant periods; below zero indicate EP dilution. Patterns reveal sector cyclicality and structural trends.",
};

// Build a proper colour for heatmap cells
const eeaiColor = (v: number) => {
  if (v >= 160) return "hsl(152 60% 30%)";
  if (v >= 140) return "hsl(152 60% 42%)";
  if (v >= 120) return "hsl(152 60% 54%)";
  if (v >= 100) return "hsl(213 75% 55%)";
  if (v >= 80)  return "hsl(38 60% 55%)";
  if (v >= 60)  return "hsl(0 70% 55%)";
  return "hsl(0 70% 40%)";
};

const epHeatColor = (v: number) => {
  if (v >= 2)   return "hsl(152 60% 30%)";
  if (v >= 1)   return "hsl(152 60% 45%)";
  if (v >= 0)   return "hsl(213 75% 55%)";
  if (v >= -1)  return "hsl(38 60% 55%)";
  return "hsl(0 70% 50%)";
};

const lineOpts = (yLabel = "%") => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: "bottom" as const, labels: { boxWidth: 12, font: { size: 11 } } }, tooltip: { mode: "index" as const } },
  scales: {
    x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } },
    y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}${yLabel}` } },
  }
});

export default function PrincipleFourPage() {
  const [activeSection, setActiveSection] = useState("4.1");
  const [indexFilter, setIndexFilter] = useState("ASX 200");
  const [periodFilter, setPeriodFilter] = useState("3Y Average");

  return (
    <div className="principle-page">
      <div className="filter-bar">
        <div className="filter-group">
          <label className="filter-label">Index</label>
          <select className="filter-select" value={indexFilter} onChange={e => setIndexFilter(e.target.value)}>
            <option>ASX 200</option><option>ASX 300</option><option>ASX 100</option>
          </select>
        </div>
        <div className="filter-group">
          <label className="filter-label">Period</label>
          <select className="filter-select" value={periodFilter} onChange={e => setPeriodFilter(e.target.value)}>
            <option>3Y Average</option><option>1Y</option><option>5Y Average</option><option>10Y Average</option>
          </select>
        </div>
      </div>

      <div className="breadcrumb-nav">
        {subSections.map(s => (
          <button key={s.id} className={`breadcrumb-step ${activeSection === s.id ? "active" : ""}`}
            onClick={() => setActiveSection(s.id)} data-testid={`tab-section-${s.id}`}>
            <span className="breadcrumb-id">{s.id}</span>
            <span className="breadcrumb-label">{s.label}</span>
          </button>
        ))}
      </div>

      <div className="section-panel" style={{ marginBottom: "1rem" }}>
        <div className="section-panel-header">
          <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "hsl(var(--primary))", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Principle 4 — EEAI &amp; Sector Aggregations
          </span>
        </div>
        <p style={{ margin: 0, fontSize: "0.83rem", color: "hsl(215 25% 45%)", lineHeight: 1.6 }}>{helpTexts[activeSection]}</p>
      </div>

      {/* ── 4.1 EEAI Overview ── */}
      {activeSection === "4.1" && (
        <div className="charts-grid">
          <div className="chart-card">
            <div className="chart-card-title">EEAI — EP Alignment Index by Year</div>
            <div className="chart-card-subtitle">EP Required vs EP Delivered (3Y avg) · {indexFilter} · {periodFilter}</div>
            <div style={{ height: 260 }}>
              <Line data={eeaiRequired} options={lineOpts()} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">Count of Companies in Each EEAI Band</div>
            <div className="chart-card-subtitle">Companies with EEAI &gt;100 (over-delivering) vs &lt;100 (under-delivering)</div>
            <div style={{ height: 260 }}>
              <Bar data={eeaiIndexCount} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } } } }} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">EEAI Formula Reference</div>
            <div className="chart-card-subtitle">How the Empirical EP Alignment Index is constructed</div>
            <table className="data-table">
              <thead><tr><th>Step</th><th>Formula</th><th>Description</th></tr></thead>
              <tbody>
                {[
                  ["3Y Avg EP%", "rolling_mean(EP%, 3)", "3-year rolling average of EP as % of EE"],
                  ["Implied EP%", "BW optimisation output", "EP% implied by current market cap (from Bow Wave)"],
                  ["EEAI Raw", "100 − (implied_epy − 3Y_avg_ep%) × scale", "Alignment index (100 = perfect alignment)"],
                  ["EEAI", "clip(EEAI_Raw, 0, 200)", "Final index clipped to valid range"],
                  ["EP Delivered", "3Y_avg_ep% × Open_EE", "Dollar EP delivered (actual)"],
                  ["EP Required", "implied_epy × Open_EE", "Dollar EP required (market expects)"],
                ].map(([s,f,d]) => (
                  <tr key={s as string}><td style={{ fontWeight: 600, color: "hsl(var(--primary))" }}>{s}</td><td style={{ fontFamily: "monospace", fontSize: "0.78rem" }}>{f}</td><td>{d}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── 4.2 EEAI Heatmap ── */}
      {activeSection === "4.2" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">EEAI Company Heatmap — Top 20 ASX Companies</div>
            <div className="chart-card-subtitle">EEAI Score (0–200) · 2011–2018 · Green = over-delivering vs market expectations · Red = under-delivering</div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ borderCollapse: "collapse", fontSize: "0.75rem", width: "100%", minWidth: 640 }}>
                <thead>
                  <tr>
                    <th style={{ padding: "6px 10px", textAlign: "left", background: "hsl(213 75% 22%)", color: "#fff", borderRadius: "4px 0 0 0" }}>Company</th>
                    {eeaiHeatmapData.years.map(y => (
                      <th key={y} style={{ padding: "6px 8px", textAlign: "center", background: "hsl(213 75% 22%)", color: "#fff", fontSize: "0.72rem" }}>{y}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {eeaiHeatmapData.companies.map((co, ri) => (
                    <tr key={co}>
                      <td style={{ padding: "5px 10px", fontWeight: 600, background: "hsl(214 32% 97%)", borderBottom: "1px solid hsl(214 32% 92%)" }}>{co}</td>
                      {eeaiHeatmapData.values[ri].map((v, ci) => (
                        <td key={ci} style={{ padding: "5px 8px", textAlign: "center", background: eeaiColor(v), color: "#fff", fontWeight: 600, fontSize: "0.72rem", borderBottom: "1px solid rgba(255,255,255,0.3)" }}>
                          {v}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.75rem", flexWrap: "wrap", fontSize: "0.72rem" }}>
              {[["≥160 — Exceptional", "hsl(152 60% 30%)"], ["140–160 — Strong", "hsl(152 60% 42%)"], ["120–140 — Good", "hsl(152 60% 54%)"], ["100–120 — On Target", "hsl(213 75% 55%)"], ["80–100 — Slight Deficit", "hsl(38 60% 55%)"], ["60–80 — Deficit", "hsl(0 70% 55%)"]].map(([l, c]) => (
                <div key={l as string} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <div style={{ width: 14, height: 14, borderRadius: 3, background: c as string }} />
                  <span style={{ color: "hsl(215 25% 40%)" }}>{l}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 4.3 EP Delivered vs Required ── */}
      {activeSection === "4.3" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">EP Delivered vs EP Required — {indexFilter}</div>
            <div className="chart-card-subtitle">EP Required (orange) = market-implied EP% · EP Delivered (blue) = 3Y average actual · Gap = EEAI deficit</div>
            <div style={{ height: 320 }}>
              <Line data={epDeliveredVsRequired} options={{
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" as const }, tooltip: { mode: "index" as const } },
                scales: {
                  x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } },
                  y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}%` }, title: { display: true, text: "EP% of Open EE" } },
                  y2: { position: "right" as const, grid: { drawOnChartArea: false }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}%` }, title: { display: true, text: "EEAI Gap (%)" } },
                }
              }} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">EP Required Sensitivity</div>
            <div className="chart-card-subtitle">How EP Required changes with M:B Ratio and Ke</div>
            <table className="data-table">
              <thead><tr><th>M:B Ratio</th><th>Ke = 7%</th><th>Ke = 8%</th><th>Ke = 10%</th><th>Ke = 12%</th></tr></thead>
              <tbody>
                {[[1.5,"3.5%","4.0%","5.0%","6.0%"],[2.0,"7.0%","8.0%","10.0%","12.0%"],[2.5,"10.5%","12.0%","15.0%","18.0%"],[3.0,"14.0%","16.0%","20.0%","24.0%"]].map(([mb,...vals]) => (
                  <tr key={mb as string}><td style={{ fontWeight: 600 }}>{mb}×</td>{(vals as string[]).map(v => <td key={v} style={{ color: parseFloat(v) > 12 ? "hsl(0 70% 45%)" : "hsl(213 75% 35%)", fontWeight: 500 }}>{v}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">EP Delivered Distribution — {periodFilter}</div>
            <div className="chart-card-subtitle">Distribution of companies by EP% delivered vs required</div>
            <div style={{ height: 220 }}>
              <Bar data={{ labels: ["<−4%","−4 to −2%","−2 to 0%","0 to 2%","2 to 4%","4 to 6%","6 to 8%",">8%"], datasets: [{ label: "EP% vs Required", data: [14, 28, 52, 78, 94, 68, 42, 24], backgroundColor: ["hsl(0 70% 45%)","hsl(0 70% 45%)","hsl(38 60% 52%)","hsl(213 75% 50%)","hsl(152 60% 45%)","hsl(152 60% 38%)","hsl(152 60% 32%)","hsl(152 60% 26%)"] }]}} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 9 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } } } }} />
            </div>
          </div>
        </div>
      )}

      {/* ── 4.4 Sector Aggregations ── */}
      {activeSection === "4.4" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">EP% vs Market Return — Sector Scatter ({indexFilter})</div>
            <div className="chart-card-subtitle">Each point = sector × year · X = EP% (Economic Profitability) · Y = TER% (Capital Market Return)</div>
            <div style={{ height: 320 }}>
              <Scatter data={sectorEpVsMarketScatter} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" }, title: { display: true, text: "EP% (Economic Profitability)", font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, title: { display: true, text: "TER % p.a.", font: { size: 10 } } } } }} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">EP per Share by Sector — {periodFilter}</div>
            <div className="chart-card-subtitle">Sector EP per share growth · Healthcare, Technology, Consumer Staples, Materials</div>
            <div style={{ height: 280 }}>
              <Line data={epPerShareBySector} options={lineOpts()} />
            </div>
          </div>
        </div>
      )}

      {/* ── 4.5 Sector EP Score Heatmap ── */}
      {activeSection === "4.5" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">EP Score Heatmap — Sector × Year</div>
            <div className="chart-card-subtitle">Normalised EP score [−3, +3] · Sector × Fiscal Year · {indexFilter} · Positive = EP dominant · Negative = EPS dominant period</div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ borderCollapse: "collapse", fontSize: "0.78rem", width: "100%" }}>
                <thead>
                  <tr>
                    <th style={{ padding: "6px 12px", textAlign: "left", background: "hsl(213 75% 22%)", color: "#fff" }}>Sector</th>
                    {epHeatmapData.years.map(y => (
                      <th key={y} style={{ padding: "6px 10px", textAlign: "center", background: "hsl(213 75% 22%)", color: "#fff", fontSize: "0.72rem" }}>{y}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {epHeatmapData.sectors.map((sector, si) => (
                    <tr key={sector}>
                      <td style={{ padding: "6px 12px", fontWeight: 600, background: "hsl(214 32% 97%)", borderBottom: "1px solid hsl(214 32% 92%)" }}>{sector}</td>
                      {epHeatmapData.values[si].map((v, ci) => (
                        <td key={ci} style={{ padding: "6px 10px", textAlign: "center", background: epHeatColor(v), color: "#fff", fontWeight: 600, fontSize: "0.78rem", borderBottom: "1px solid rgba(255,255,255,0.3)" }}>
                          {v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.75rem", flexWrap: "wrap", fontSize: "0.72rem" }}>
              {[["≥2.0 — Strong EP Dominant", "hsl(152 60% 30%)"], ["1.0–2.0 — EP Dominant", "hsl(152 60% 45%)"], ["0–1.0 — Slight Positive", "hsl(213 75% 55%)"], ["−1 to 0 — Slight Negative", "hsl(38 60% 55%)"], ["<−1 — EPS Dominant", "hsl(0 70% 50%)"]].map(([l,c]) => (
                <div key={l as string} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <div style={{ width: 14, height: 14, borderRadius: 3, background: c as string }} />
                  <span style={{ color: "hsl(215 25% 40%)" }}>{l}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
