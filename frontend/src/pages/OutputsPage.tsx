import { useState, useMemo } from "react";
import { Bar, Doughnut, Line } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  ArcElement, Tooltip, Legend, LineElement, PointElement, Filler,
} from "chart.js";
import { wealthCreationDecomp, epVsEpsCohorts } from "../data/chartData";
import { useActiveContext, aggregateByYear } from "../hooks/useMetrics";
import { getOptimizationMetrics, MetricResultItem } from "../lib/api";
import { useEffect } from "react";

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend, LineElement, PointElement, Filler);

// ─── Local types for optimization metrics data layer ─────────────────────────

interface WealthPoint { year: number; value: number; }

function mapToWealthSeries(items: MetricResultItem[]): WealthPoint[] {
  return aggregateByYear(items).map(d => ({ year: d.year, value: d.value }));
}

// ─── Seeded random fallback — stable across renders ──────────────────────────
// Used only when optimization_metrics endpoint returns no data.

function seededRandom(seed: number) {
  let s = seed;
  return () => { s = (s * 16807 + 0) % 2147483647; return (s - 1) / 2147483646; };
}

const YEARS = Array.from({ length: 15 }, (_, i) => 2009 + i);

function makePlaceholderSeries(seed: number, base: number, volatility: number): WealthPoint[] {
  const rand = seededRandom(seed);
  let v = base;
  return YEARS.map(year => {
    v += (rand() - 0.48) * volatility;
    return { year, value: +v.toFixed(2) };
  });
}

const tabs = [
  "Wealth Creation Overview",
  "TSR-Ke Analysis",
  "Intrinsic Wealth",
  "Sustainable Wealth",
];

const decompositionRows = [
  { label: "TSR-Ke (Observed Wealth Creation)", value: "8.2%", color: "hsl(213 75% 22%)", desc: "Total annualised wealth creation experienced by shareholders over the measurement period" },
  { label: "Intrinsic Wealth Creation", value: "5.4%", color: "hsl(38 60% 52%)", desc: "Wealth created by engaging in innovation, new capability creation and other positive activities" },
  { label: "Sustainable Intrinsic Wealth", value: "3.8%", color: "hsl(152 60% 40%)", desc: "Arising from sound and sustainable economic endeavour in the product and service market" },
  { label: "Market Sentiment Shifts", value: "1.6%", color: "hsl(188 78% 35%)", desc: "Shifts in company-specific sentiment benefiting short-term traders at the expense of long-term investors" },
  { label: "Wealth Appropriation", value: "2.8%", color: "hsl(0 72% 51%)", desc: "Benefiting shareholders and executives at the expense of non-shareholder stakeholders" },
];

export default function OutputsPage() {
  const [activeTab, setActiveTab] = useState(0);

  // ─── Live data ──────────────────────────────────────────────────────────
  const ctx = useActiveContext();

  // Intrinsic + Sustainable Wealth via optimization_metrics (future endpoint)
  const [intrinsicRaw, setIntrinsicRaw] = useState<MetricResultItem[]>([]);
  const [sustainableRaw, setSustainableRaw] = useState<MetricResultItem[]>([]);

  useEffect(() => {
    if (!ctx.datasetId || !ctx.paramSetId) return;
    getOptimizationMetrics({ dataset_id: ctx.datasetId, parameter_set_id: ctx.paramSetId, metric_name: "Intrinsic Wealth" })
      .then(r => setIntrinsicRaw(r.results));
    getOptimizationMetrics({ dataset_id: ctx.datasetId, parameter_set_id: ctx.paramSetId, metric_name: "Sustainable Wealth" })
      .then(r => setSustainableRaw(r.results));
  }, [ctx.datasetId, ctx.paramSetId]);

  // Map through data layer; fall back to seeded placeholder when empty
  const intrinsicSeries  = useMemo(() => {
    const mapped = mapToWealthSeries(intrinsicRaw);
    return mapped.length ? mapped : makePlaceholderSeries(42,  5.4, 1.2);
  }, [intrinsicRaw]);

  const sustainableSeries = useMemo(() => {
    const mapped = mapToWealthSeries(sustainableRaw);
    return mapped.length ? mapped : makePlaceholderSeries(99,  3.8, 0.9);
  }, [sustainableRaw]);

  const isPlaceholder = intrinsicRaw.length === 0;

  return (
    <div style={{ padding: "1.5rem", maxWidth: "1400px" }}>
      {/* Header */}
      <div style={{ marginBottom: "1.25rem" }}>
        <h1 style={{ fontSize: "1.125rem", fontWeight: 700, color: "hsl(var(--foreground))", marginBottom: "0.25rem" }}>
          Outputs Menu — Wealth Creation Analysis
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))" }}>
          How wealth is created in the product and capital markets. Combines short-term (TSR-Ke) and long-term sustainable wealth creation perspectives.
        </p>
      </div>

      {/* Tab pills */}
      <div className="tab-pills" style={{ marginBottom: "1.25rem", width: "fit-content" }}>
        {tabs.map((t, i) => (
          <button
            key={t}
            className={`tab-pill ${activeTab === i ? "active" : ""}`}
            onClick={() => setActiveTab(i)}
            data-testid={`tab-output-${i}`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Wealth Creation Overview */}
      {activeTab === 0 && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
            {/* Decomposition chart */}
            <div className="chart-card">
              <div className="chart-card-title">Wealth Creation Components</div>
              <div className="chart-card-subtitle">ASX 300 · 10yr annualised · 2001–2024</div>
              <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: "1rem", alignItems: "center" }}>
                <div style={{ height: "180px" }}>
                  <Doughnut
                    data={{
                      labels: wealthCreationDecomp.labels,
                      datasets: [{
                        data: wealthCreationDecomp.datasets[0].data,
                        backgroundColor: wealthCreationDecomp.datasets[0].backgroundColor as string[],
                        borderWidth: 2,
                        borderColor: "white",
                      }],
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      cutout: "65%",
                      plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: (item: any) => `${item.label}: ${item.raw}%` } },
                      },
                    }}
                  />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {decompositionRows.slice(0, 4).map(row => (
                    <div key={row.label} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <div style={{ width: "10px", height: "10px", borderRadius: "2px", background: row.color, flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: "0.6875rem", fontWeight: 600, color: "hsl(var(--foreground))" }}>{row.value}</div>
                        <div style={{ fontSize: "0.625rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.3 }}>{row.label}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Decomposition table */}
            <div className="chart-card">
              <div className="chart-card-title">Wealth Creation Decomposition</div>
              <div className="chart-card-subtitle">How total TER-Ke is disaggregated</div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" }}>
                {decompositionRows.map(row => (
                  <div key={row.label} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
                    <div style={{
                      minWidth: "48px", textAlign: "center",
                      fontWeight: 700, fontSize: "1rem",
                      color: row.color,
                      fontVariantNumeric: "tabular-nums lining-nums",
                    }}>
                      {row.value}
                    </div>
                    <div>
                      <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "hsl(var(--foreground))" }}>
                        {row.label}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.4 }}>
                        {row.desc}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Short-term vs long-term wealth */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            {[
              {
                title: "Short-Term Wealth Creation Focus",
                badge: "TSR-Ke",
                color: "hsl(213 75% 22%)",
                items: [
                  "Wealth Created by outperforming the Economic Profit (EP) expectations embedded in the share price at the beginning of a measurement period",
                  "Incorporates market sentiment shifts and short-term trader gains",
                  "More volatile — particularly for 1-year measurement periods",
                ],
                metric: "TSR-Ke",
              },
              {
                title: "Long-Term Wealth Creation Focus",
                badge: "EP Growth",
                color: "hsl(38 60% 52%)",
                items: [
                  "Wealth Created by engaging in innovation, new capability creation and other positive activities during a measurement period",
                  "Creates new and higher EP expectations to be delivered beyond the measurement period",
                  "More stable — converges over 5-10 year periods",
                ],
                metric: "TER-Ke (10yr)",
              },
            ].map(panel => (
              <div key={panel.title} className="chart-card" style={{ borderLeft: `3px solid ${panel.color}` }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <span style={{
                    padding: "0.2rem 0.625rem",
                    background: `${panel.color}22`,
                    color: panel.color,
                    borderRadius: "9999px",
                    fontSize: "0.6875rem",
                    fontWeight: 700,
                  }}>
                    {panel.badge}
                  </span>
                  <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "hsl(var(--foreground))" }}>
                    {panel.title}
                  </span>
                </div>
                <ul style={{ display: "flex", flexDirection: "column", gap: "0.5rem", paddingLeft: "1.25rem" }}>
                  {panel.items.map((item, i) => (
                    <li key={i} style={{ fontSize: "0.8125rem", color: "hsl(var(--foreground))", lineHeight: 1.5 }}>
                      {item}
                    </li>
                  ))}
                </ul>
                <div style={{ marginTop: "0.875rem", padding: "0.5rem 0.75rem", background: "hsl(var(--muted))", borderRadius: "0.375rem" }}>
                  <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>Key metric: </span>
                  <span style={{ fontWeight: 700, fontSize: "0.75rem", color: panel.color }}>{panel.metric}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TSR-Ke Analysis tab */}
      {activeTab === 1 && (
        <div>
          <div className="help-panel" style={{ marginBottom: "1.25rem" }}>
            <strong>TSR-Ke</strong> (Wealth Creation) = Annualised TSR over the measurement period − Cost of Equity (Ke) at the beginning of the period.
            It is the economic return on market value experienced by an individual shareholder.
            <strong> TER-Ke</strong> is the whole-of-company equivalent.
          </div>
          <div className="chart-card">
            <div className="chart-card-title">EP Dominant vs EPS Dominant — TSR & Wealth Creation</div>
            <div className="chart-card-subtitle">ASX 500 · 10 Years to 30 June 2018</div>
            <div style={{ height: "320px" }}>
              <Bar data={epVsEpsCohorts} options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: "top" as const, labels: { boxWidth: 14, font: { size: 10 } } },
                  tooltip: { mode: "index" as const, intersect: false },
                },
                scales: {
                  x: { ticks: { font: { size: 10 } }, grid: { display: false } },
                  y: { ticks: { font: { size: 10 }, callback: (v: number | string) => `${v}%` }, grid: { color: "rgba(0,0,0,0.04)" } },
                },
              }} />
            </div>
          </div>
        </div>
      )}

      {/* Intrinsic Wealth */}
      {activeTab === 2 && (
        <div>
          {isPlaceholder && (
            <div className="help-panel" style={{ marginBottom: "1rem", fontSize: "0.8125rem" }}>
              <strong>Preview data</strong> — Intrinsic Wealth Creation will be sourced from the
              <code style={{ marginLeft: 4 }}>optimization_metrics</code> endpoint once available.
              Chart below uses illustrative values.
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="chart-card">
              <div className="chart-card-title">Intrinsic Wealth Creation — Trend</div>
              <div className="chart-card-subtitle">TER-Ke component attributable to EP-driven innovation (%)</div>
              <div style={{ height: 260 }}>
                <Line
                  data={{
                    labels: intrinsicSeries.map(d => d.year),
                    datasets: [{
                      label: "Intrinsic Wealth (%)",
                      data: intrinsicSeries.map(d => d.value),
                      borderColor: "hsl(38 60% 52%)",
                      backgroundColor: "hsl(38 60% 52% / 0.1)",
                      fill: true,
                      tension: 0.4,
                      pointRadius: 3,
                    }],
                  }}
                  options={{
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                      x: { ticks: { font: { size: 9 } }, grid: { display: false } },
                      y: { ticks: { font: { size: 9 }, callback: (v: any) => `${Number(v).toFixed(1)}%` }, grid: { color: "rgba(0,0,0,0.04)" } },
                    },
                  }}
                />
              </div>
            </div>
            <div className="chart-card">
              <div className="chart-card-title">What is Intrinsic Wealth?</div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" }}>
                {[
                  { label: "Definition", text: "Wealth created by engaging in innovation, new capability creation and other positive activities during a measurement period." },
                  { label: "Source", text: "Creates new and higher EP expectations to be delivered beyond the measurement period." },
                  { label: "Stability", text: "More stable than TSR-Ke — converges over 5–10 year periods." },
                  { label: "Metric", text: "Sourced from optimization_metrics endpoint (Intrinsic Wealth)." },
                ].map(item => (
                  <div key={item.label}>
                    <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "hsl(38 60% 35%)" }}>{item.label}</div>
                    <div style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.5 }}>{item.text}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sustainable Wealth */}
      {activeTab === 3 && (
        <div>
          {isPlaceholder && (
            <div className="help-panel" style={{ marginBottom: "1rem", fontSize: "0.8125rem" }}>
              <strong>Preview data</strong> — Sustainable Wealth Creation will be sourced from the
              <code style={{ marginLeft: 4 }}>optimization_metrics</code> endpoint once available.
              Chart below uses illustrative values.
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="chart-card">
              <div className="chart-card-title">Sustainable Wealth Creation — Trend</div>
              <div className="chart-card-subtitle">EP-driven component of Intrinsic Wealth arising from core business operations (%)</div>
              <div style={{ height: 260 }}>
                <Line
                  data={{
                    labels: sustainableSeries.map(d => d.year),
                    datasets: [{
                      label: "Sustainable Wealth (%)",
                      data: sustainableSeries.map(d => d.value),
                      borderColor: "hsl(152 60% 40%)",
                      backgroundColor: "hsl(152 60% 40% / 0.1)",
                      fill: true,
                      tension: 0.4,
                      pointRadius: 3,
                    }],
                  }}
                  options={{
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                      x: { ticks: { font: { size: 9 } }, grid: { display: false } },
                      y: { ticks: { font: { size: 9 }, callback: (v: any) => `${Number(v).toFixed(1)}%` }, grid: { color: "rgba(0,0,0,0.04)" } },
                    },
                  }}
                />
              </div>
            </div>
            <div className="chart-card">
              <div className="chart-card-title">What is Sustainable Wealth?</div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" }}>
                {[
                  { label: "Definition", text: "Arising from sound and sustainable economic endeavour in the product and service market." },
                  { label: "Relationship", text: "A sub-component of Intrinsic Wealth — represents the EP-grounded, recurring portion." },
                  { label: "Stability", text: "Most stable wealth component — least sensitive to market sentiment shifts." },
                  { label: "Metric", text: "Sourced from optimization_metrics endpoint (Sustainable Wealth)." },
                ].map(item => (
                  <div key={item.label}>
                    <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "hsl(152 60% 30%)" }}>{item.label}</div>
                    <div style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.5 }}>{item.text}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
