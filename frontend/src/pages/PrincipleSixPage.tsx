import { useState } from "react";
import { Line, Bar, Scatter } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend, Filler,
} from "chart.js";
import {
  betaDistribution, betaTimeSeries, keDecompositionData,
  fvEcfIntervals, fvEcfTimeSeries, rfRateTimeSeries, terDecompositionData,
  tsrKeVsRoeKeScatter,
} from "../data/chartData";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend, Filler);

const subSections = [
  { id: "6.1", label: "Beta Analysis" },
  { id: "6.2", label: "Ke Decomposition" },
  { id: "6.3", label: "Risk Free Rate" },
  { id: "6.4", label: "FV-ECF / Valuation" },
  { id: "6.5", label: "TER Decomposition" },
];

const helpTexts: Record<string, string> = {
  "6.1": "Beta is calculated using a rolling 60-month OLS regression on monthly returns against the market index. A 4-tier fallback is used: (1) company-specific adjusted slope (if error tolerance < 0.8), (2) sector average Beta, (3) ticker historical average, (4) market Beta of 1.0. Final Beta = (slope × 2/3) + (1/3), rounded to nearest 0.1.",
  "6.2": "Cost of Equity (Ke) = Rf + Beta × MRP. The decomposition shows the risk-free rate component vs the market risk premium component. As Rf has declined over the period, Ke has fallen even as Beta remained stable — this is a key driver of the secular rise in M:B ratios.",
  "6.3": "The Risk-Free Rate (Rf) is either FIXED (benchmark − risk_premium) or FLOATING (geometric mean of monthly government bond rates). Australia 10Y bond yields are used for AUS companies. The multi-country comparison shows how Rf divergence has created different cost-of-equity environments.",
  "6.4": "FV-ECF (Future Value Economic Cash Flow) is the cornerstone of DCF valuation in the CISSA framework. It compounds expected future ECF at the cost of equity over 1Y, 3Y, 5Y, and 10Y horizons. FV-ECF = Σ(ECF_t × (1 + Ke)^power) — capturing the present value of future wealth delivery.",
  "6.5": "The TER Decomposition waterfall shows how a starting base of Open MC × Ke grows through Dividend Yield, Capital Gains, and Franking Credit to arrive at TER, and then TER-Ke as the final excess return. TERA strips the market risk premium from TER-Ke to arrive at pure Alpha.",
};

const lineOpts = (yLabel = "%") => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: "bottom" as const, labels: { boxWidth: 12, font: { size: 11 } } }, tooltip: { mode: "index" as const } },
  scales: {
    x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } },
    y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}${yLabel}` } },
  }
});

// Waterfall chart rendered as custom bars
function TERWaterfall() {
  const { labels, values, types, colors } = terDecompositionData;
  const runningBase: number[] = [];
  let current = 0;
  const bars = values.map((v, i) => {
    if (types[i] === "base" || types[i] === "total") {
      runningBase.push(0);
      current = v;
      return { base: 0, val: v, type: types[i], color: colors[i] };
    }
    const base = current;
    runningBase.push(base);
    if (types[i] === "pos") current += v;
    else current -= v;
    return { base, val: Math.abs(v), type: types[i], color: colors[i] };
  });

  const maxVal = Math.max(...values) * 1.1;

  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 200, padding: "0 8px" }}>
      {bars.map((b, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", height: "100%" }}>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", width: "100%" }}>
            <div style={{ height: `${(b.base / maxVal) * 100}%`, background: "transparent" }} />
            <div
              style={{
                height: `${(b.val / maxVal) * 100}%`,
                background: b.color,
                borderRadius: "4px 4px 0 0",
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "center",
                paddingTop: 4,
                fontSize: "0.72rem",
                fontWeight: 700,
                color: "#fff",
                minHeight: 20,
              }}
            >
              {b.type === "neg" ? `−${b.val}` : `+${b.val}`}
            </div>
          </div>
          <div style={{ fontSize: "0.65rem", color: "hsl(215 25% 45%)", textAlign: "center", marginTop: 4, lineHeight: 1.2 }}>
            {labels[i]}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function PrincipleSixPage() {
  const [activeSection, setActiveSection] = useState("6.1");
  const [indexFilter, setIndexFilter] = useState("ASX 200");
  const [periodFilter, setPeriodFilter] = useState("10Y Annualised");

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
            <option>1Y Annualised</option><option>3Y Annualised</option><option>5Y Annualised</option><option>10Y Annualised</option>
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
            Principle 6 — Valuation &amp; Beta
          </span>
        </div>
        <p style={{ margin: 0, fontSize: "0.83rem", color: "hsl(215 25% 45%)", lineHeight: 1.6 }}>{helpTexts[activeSection]}</p>
      </div>

      {/* ── 6.1 Beta Analysis ── */}
      {activeSection === "6.1" && (
        <div className="charts-grid">
          <div className="chart-card">
            <div className="chart-card-title">Beta Distribution — {indexFilter}</div>
            <div className="chart-card-subtitle">Number of companies by Beta band (4-tier fallback applied) · Rolling 60-month OLS</div>
            <div style={{ height: 260 }}>
              <Bar data={betaDistribution} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } }, title: { display: true, text: "# Companies" } } } }} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">Beta 4-Tier Fallback Logic</div>
            <div className="chart-card-subtitle">Priority order for Beta assignment when OLS regression fails error tolerance test</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", padding: "0.25rem 0" }}>
              {[
                { tier: "Tier 1", label: "Company Adjusted Beta", formula: "OLS slope × 2/3 + 1/3", cond: "if std_error < 0.8", color: "hsl(152 60% 40%)" },
                { tier: "Tier 2", label: "Sector Average Beta", formula: "Weighted avg across sector", cond: "if Tier 1 fails", color: "hsl(213 75% 40%)" },
                { tier: "Tier 3", label: "Ticker Historical Avg", formula: "Expanding mean of Spot Beta", cond: "if Tier 2 fails", color: "hsl(38 60% 52%)" },
                { tier: "Tier 4", label: "Market Beta = 1.0", formula: "Default fallback", cond: "if all tiers fail", color: "hsl(0 70% 50%)" },
              ].map(({ tier, label, formula, cond, color }) => (
                <div key={tier} style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", padding: "0.6rem 0.75rem", borderRadius: 6, background: `${color}10`, border: `1.5px solid ${color}30` }}>
                  <div style={{ minWidth: 56, fontWeight: 700, fontSize: "0.75rem", color }}>{tier}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: "0.82rem" }}>{label}</div>
                    <div style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "hsl(215 25% 45%)" }}>{formula}</div>
                    <div style={{ fontSize: "0.72rem", color: "hsl(215 25% 55%)", marginTop: 2 }}>{cond}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Beta Time Series by Sector — {indexFilter}</div>
            <div className="chart-card-subtitle">Sector-average Beta 2005–2018 · Rolling 60-month adjusted Beta (rounded to 0.1)</div>
            <div style={{ height: 280 }}>
              <Line data={betaTimeSeries} options={lineOpts("×")} />
            </div>
          </div>
        </div>
      )}

      {/* ── 6.2 Ke Decomposition ── */}
      {activeSection === "6.2" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Cost of Equity (Ke) Decomposition — Rf + Beta×MRP</div>
            <div className="chart-card-subtitle">{indexFilter} · Stacked bars = Rf (blue) + Beta×MRP (gold) · Line = Ke total · 2005–2018</div>
            <div style={{ height: 300 }}>
              <Bar data={keDecompositionData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { stacked: true, grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } }, y: { stacked: true, grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}%` } } } }} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">Ke Formula Reference</div>
            <div className="chart-card-subtitle">Capital Asset Pricing Model (CAPM) implementation in CISSA</div>
            <table className="data-table">
              <thead><tr><th>Symbol</th><th>Definition</th><th>Source</th><th>2018 Value</th></tr></thead>
              <tbody>
                {[
                  ["Ke", "Cost of Equity", "Calculated", "7.5%"],
                  ["Rf", "Risk-Free Rate", "AU 10Y Bond", "2.5%"],
                  ["Beta", "Systematic Risk", "OLS 60M Rolling", "1.0×"],
                  ["MRP", "Market Risk Premium", "Parameter", "5.0%"],
                  ["Beta×MRP", "Risk Component", "Calculated", "5.0%"],
                  ["Open Ke", "Prior Year Ke", "LAG(Ke,1)", "7.3%"],
                ].map(([sym, def, src, val]) => (
                  <tr key={sym as string}>
                    <td style={{ fontWeight: 700, fontFamily: "monospace", color: "hsl(213 75% 35%)" }}>{sym}</td>
                    <td>{def}</td>
                    <td style={{ color: "hsl(215 25% 50%)", fontSize: "0.78rem" }}>{src}</td>
                    <td style={{ fontWeight: 600, color: "hsl(152 60% 35%)" }}>{val}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">TSR-Ke vs ROE-Ke — Capital Linkage</div>
            <div className="chart-card-subtitle">{indexFilter} · Companies with higher EP% tend to command higher TSR-Ke · {periodFilter}</div>
            <div style={{ height: 240 }}>
              <Scatter data={tsrKeVsRoeKeScatter} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" }, title: { display: true, text: "ROE-Ke % (EP%)", font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, title: { display: true, text: "TSR-Ke % (Wealth Creation)", font: { size: 10 } } } } }} />
            </div>
          </div>
        </div>
      )}

      {/* ── 6.3 Risk Free Rate ── */}
      {activeSection === "6.3" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Risk-Free Rate (Rf) — Australia, USA, UK</div>
            <div className="chart-card-subtitle">Australia 10Y Government Bond · USA Fed Funds Rate · UK Base Rate · 2001–2018</div>
            <div style={{ height: 300 }}>
              <Line data={rfRateTimeSeries} options={lineOpts("%")} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">Rf Approach: FIXED vs FLOATING</div>
            <div className="chart-card-subtitle">Configuration parameter for the CISSA calculation engine</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {[
                { approach: "FIXED", formula: "Rf = Benchmark − Risk_Premium", example: "Rf = 7.5% − 5.0% = 2.5%", note: "Same Rf for all companies in a year", color: "hsl(213 75% 40%)" },
                { approach: "FLOATING", formula: "Rf = Geometric mean of monthly bond rates (12M)", example: "Rf = (∏(1 + monthly_rf))^(1/12) − 1", note: "Company-specific based on FY end date", color: "hsl(38 60% 52%)" },
              ].map(({ approach, formula, example, note, color }) => (
                <div key={approach} style={{ padding: "0.75rem", borderRadius: 6, background: `${color}08`, border: `1.5px solid ${color}25` }}>
                  <div style={{ fontWeight: 700, fontSize: "0.85rem", color, marginBottom: 4 }}>{approach} Approach</div>
                  <div style={{ fontFamily: "monospace", fontSize: "0.75rem", marginBottom: 4 }}>{formula}</div>
                  <div style={{ fontFamily: "monospace", fontSize: "0.72rem", color: "hsl(215 25% 45%)", marginBottom: 4 }}>{example}</div>
                  <div style={{ fontSize: "0.72rem", color: "hsl(215 25% 55%)" }}>{note}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">Ke Sensitivity to Rf Changes</div>
            <div className="chart-card-subtitle">Impact of 50bps Rf shift on Ke across Beta levels</div>
            <table className="data-table">
              <thead><tr><th>Beta</th><th>Rf = 2.0%</th><th>Rf = 2.5%</th><th>Rf = 3.0%</th><th>Rf = 4.0%</th></tr></thead>
              <tbody>
                {[["0.6","5.0%","5.5%","6.0%","7.0%"],["0.8","6.0%","6.5%","7.0%","8.0%"],["1.0","7.0%","7.5%","8.0%","9.0%"],["1.2","8.0%","8.5%","9.0%","10.0%"],["1.5","9.5%","10.0%","10.5%","11.5%"]].map(([b,...vals]) => (
                  <tr key={b as string}><td style={{ fontWeight: 600 }}>β={b}</td>{(vals as string[]).map((v,i) => <td key={i} style={{ fontWeight: i === 1 ? 700 : 400, color: i === 1 ? "hsl(213 75% 35%)" : undefined }}>{v}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── 6.4 FV-ECF / Valuation ── */}
      {activeSection === "6.4" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">FV-ECF by Sector — 1Y / 3Y / 5Y / 10Y ($M)</div>
            <div className="chart-card-subtitle">Future Value Economic Cash Flow: compounding ECF forward at Ke · Sector totals · {indexFilter}</div>
            <div style={{ height: 280 }}>
              <Bar data={fvEcfIntervals} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { callback: (v: any) => `$${(v/1000).toFixed(0)}B` } } } }} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">FV-ECF Multiplier Time Series — {indexFilter}</div>
            <div className="chart-card-subtitle">FV-ECF / Open MC · A value of 1.2× at 3Y means market expects 20% above Ke return compounded over 3 years</div>
            <div style={{ height: 280 }}>
              <Line data={fvEcfTimeSeries} options={lineOpts("×")} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">FV-ECF Formula — CISSA Valuation Engine</div>
            <div className="chart-card-subtitle">Vectorised implementation across 1Y, 3Y, 5Y, 10Y intervals with franking adjustment</div>
            <div style={{ background: "hsl(214 32% 97%)", borderRadius: 6, padding: "1rem", fontFamily: "monospace", fontSize: "0.78rem", overflowX: "auto" }}>
              <div style={{ color: "hsl(215 25% 45%)", marginBottom: "0.5rem" }}>/* For each interval n ∈ {"{1, 3, 5, 10}"} */</div>
              <div>scale_by = 1 <span style={{ color: "hsl(213 75% 35%)" }}>if</span> ke_open &gt; 0 <span style={{ color: "hsl(213 75% 35%)" }}>else</span> 0</div>
              <div><span style={{ color: "hsl(213 75% 35%)" }}>for</span> seq <span style={{ color: "hsl(213 75% 35%)" }}>in</span> range(n, 0, -1):</div>
              <div style={{ paddingLeft: "1.5rem" }}>power = n + (seq - 1) * (-1) - 1</div>
              <div style={{ paddingLeft: "1.5rem" }}>TEMP = (−div.shift(1-seq) + non_div_ecf.shift(1-seq)</div>
              <div style={{ paddingLeft: "3rem" }}>− (div.shift(1-seq)/(1−t)) × t × fc × frank.shift(1-seq))</div>
              <div style={{ paddingLeft: "3rem" }}>× (1 + ke_open)^power × scale_by</div>
              <div>FV_ECF_{"{n}"}Y = SUM(TEMP).shift(n-1)</div>
            </div>
          </div>
        </div>
      )}

      {/* ── 6.5 TER Decomposition ── */}
      {activeSection === "6.5" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">TER Decomposition Waterfall</div>
            <div className="chart-card-subtitle">Open MC × Ke → Dividends → Capital Gain → Franking Credit → TER → TER-Ke · {indexFilter} · {periodFilter} average</div>
            <TERWaterfall />
          </div>
          <div className="chart-card">
            <div className="chart-card-title">TER Component Definitions</div>
            <div className="chart-card-subtitle">How each component feeds into the total equity return</div>
            <table className="data-table">
              <thead><tr><th>Component</th><th>Formula</th><th>2018 Avg</th></tr></thead>
              <tbody>
                {[
                  ["TER", "Geom. mean of (ECF / Open MC)", "10.4%"],
                  ["TER-Ke", "TER − Ke", "+2.4%"],
                  ["TERA", "(div×(1+Rf) + ΔMC) / |Open EE|", "9.8%"],
                  ["RA_MM", "(Rm−Ke) × (Ke−Rf)/MRP", "+0.9%"],
                  ["TER Alpha", "TER-Ke − RA_MM", "+1.5%"],
                  ["WC ($B)", "Open MC × (1+TER)ⁿ − Open MC × (1+Ke)ⁿ", "$48.2B"],
                ].map(([c,f,v]) => (
                  <tr key={c as string}>
                    <td style={{ fontWeight: 700, color: "hsl(213 75% 35%)", fontFamily: "monospace" }}>{c}</td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>{f}</td>
                    <td style={{ fontWeight: 600, color: parseFloat(v as string) < 0 ? "hsl(0 70% 45%)" : "hsl(152 60% 35%)" }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">Franking Credit Impact on TER</div>
            <div className="chart-card-subtitle">Australian imputation credits add to effective yield — boosting real TER for domestic investors</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {[
                { label: "Dividend (gross)", value: "5.2%", color: "hsl(213 75% 40%)" },
                { label: "+ Franking Credit", value: "+0.6%", color: "hsl(152 60% 40%)" },
                { label: "= Grossed-Up Yield", value: "5.8%", color: "hsl(38 60% 52%)" },
                { label: "vs Pre-franking", value: "5.2%", color: "hsl(215 25% 50%)" },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.5rem 0.75rem", borderRadius: 5, background: `${color}10`, border: `1px solid ${color}20` }}>
                  <span style={{ fontSize: "0.82rem", color: "hsl(215 25% 40%)" }}>{label}</span>
                  <span style={{ fontWeight: 700, fontSize: "0.88rem", color }}>{value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
