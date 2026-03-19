import { useState } from "react";
import {
  roeKeByIndex, terKeByIndex, mbRatioByIndex, roeKeDistribution,
  terKeDistribution, epVsEpsCohorts, eeaiRequired, eeaiIndexCount,
  terIntlUSA, terIntlUK, terIntlAUS, wealthCreationDecomp,
  epPerShareGrowth, epPerShareBySector, epHeatmapData,
  tsrKeVsRoeKeScatter, cissaIndex2DScatter, esgKpis,
  mbRatioSectorDist, mbRatioCompanyDist,
  exportableMetrics,
} from "../data/chartData";

// ─── Helper: convert chartData to CSV string ───────────────────────────────
function datasetsToCsv(labels: string[], datasets: any[]): string {
  const header = ["Year/Label", ...datasets.map((d: any) => d.label)].join(",");
  const rows = labels.map((lbl, i) =>
    [JSON.stringify(lbl), ...datasets.map((d: any) => {
      const v = d.data[i];
      return v === null || v === undefined ? "" : String(v);
    })].join(",")
  );
  return [header, ...rows].join("\n");
}

function scatterToCsv(datasets: any[]): string {
  const rows: string[] = ["Cohort,X,Y"];
  datasets.forEach((d: any) => {
    d.data.forEach((pt: any) => {
      const label = pt.label ? `,${pt.label}` : "";
      rows.push(`${JSON.stringify(d.label)},${pt.x},${pt.y}${label}`);
    });
  });
  return rows.join("\n");
}

function heatmapToCsv(): string {
  const { sectors, years, values } = epHeatmapData;
  const header = ["Sector", ...years].join(",");
  const rows = sectors.map((s, si) =>
    [JSON.stringify(s), ...values[si].map(v => String(v))].join(",")
  );
  return [header, ...rows].join("\n");
}

function esgKpisToCsv(): string {
  const header = ["Metric,EP Dominant,Middle Group,EPS Dominant,Unit"];
  const rows = esgKpis.map(r =>
    [JSON.stringify(r.metric), r.epDominant, r.middle, r.epsDominant, r.unit].join(",")
  );
  return [header[0], ...rows].join("\n");
}

// ─── Map metric ID → CSV generator ────────────────────────────────────────
function generateCsv(metricId: string): string {
  switch (metricId) {
    case "roe_ke_by_index":
      return datasetsToCsv(roeKeByIndex.labels as string[], roeKeByIndex.datasets);
    case "ter_ke_by_index":
      return datasetsToCsv(terKeByIndex.labels as string[], terKeByIndex.datasets);
    case "mb_ratio_by_index":
      return datasetsToCsv(mbRatioByIndex.labels as string[], mbRatioByIndex.datasets);
    case "roe_ke_distribution":
      return datasetsToCsv(roeKeDistribution.labels as string[], roeKeDistribution.datasets);
    case "ep_vs_eps_cohorts":
      return datasetsToCsv(epVsEpsCohorts.labels as string[], epVsEpsCohorts.datasets);
    case "ep_per_share_growth":
      return datasetsToCsv(epPerShareGrowth.labels as string[], epPerShareGrowth.datasets);
    case "ep_per_share_by_sector":
      return datasetsToCsv(epPerShareBySector.labels as string[], epPerShareBySector.datasets);
    case "ep_heatmap":
      return heatmapToCsv();
    case "eeai_required":
      return datasetsToCsv(eeaiRequired.labels as string[], [...eeaiRequired.datasets, ...eeaiIndexCount.datasets]);
    case "ter_intl_comparison": {
      const usaCsv = datasetsToCsv(terIntlUSA.labels as string[], terIntlUSA.datasets);
      const ukCsv = datasetsToCsv(terIntlUK.labels as string[], terIntlUK.datasets);
      const ausCsv = datasetsToCsv(terIntlAUS.labels as string[], terIntlAUS.datasets);
      return `# USA\n${usaCsv}\n\n# UK\n${ukCsv}\n\n# Australia\n${ausCsv}`;
    }
    case "bow_wave_companies":
      return "Company,Wealth Creation,Direction,Description\nCOH,$3.1b,positive,Cochlear\nREA,$8.4b,positive,REA Group\nCSL,$12.7b,positive,CSL Limited\nBHP,$18.5b,negative,BHP Group\nMSFT,$420b,positive,Microsoft\nIDX,$85b,positive,ASX 300 Aggregate";
    case "wealth_waterfall":
      return datasetsToCsv(wealthCreationDecomp.labels as string[], wealthCreationDecomp.datasets);
    case "cissa_index_2d":
      return scatterToCsv(cissaIndex2DScatter.datasets);
    case "esg_metrics":
      return esgKpisToCsv();
    case "mb_ratio_distribution":
      return datasetsToCsv(mbRatioSectorDist.labels as string[], [...mbRatioSectorDist.datasets, ...mbRatioCompanyDist.datasets]);
    default:
      return "No data available";
  }
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

type PrincipleFilter = "all" | "Principle 1" | "Principle 2" | "All Principles" | "Principle 4";

const PRINCIPLE_COLORS: Record<string, string> = {
  "Principle 1": "hsl(213 75% 22%)",
  "Principle 2": "hsl(38 60% 52%)",
  "Principle 4": "hsl(152 60% 40%)",
  "All Principles": "hsl(188 78% 35%)",
};

export default function MetricsDownloadPage() {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [principleFilter, setPrincipleFilter] = useState<PrincipleFilter>("all");
  const [search, setSearch] = useState("");
  const [downloading, setDownloading] = useState<string | null>(null);
  const [bulkDownloading, setBulkDownloading] = useState(false);

  const filtered = exportableMetrics.filter(m => {
    if (principleFilter !== "all" && m.principle !== principleFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return m.name.toLowerCase().includes(q) || m.description.toLowerCase().includes(q) || m.section.toLowerCase().includes(q);
    }
    return true;
  });

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(filtered.map(m => m.id)));
  const clearAll = () => setSelected(new Set());

  const handleDownloadSingle = (metricId: string, format: "CSV" | "JSON") => {
    setDownloading(metricId);
    const metric = exportableMetrics.find(m => m.id === metricId)!;
    setTimeout(() => {
      if (format === "CSV") {
        const csv = generateCsv(metricId);
        downloadFile(csv, `cissa_${metricId}.csv`, "text/csv");
      } else {
        const csv = generateCsv(metricId);
        const lines = csv.split("\n");
        const headers = lines[0].split(",").map(h => h.replace(/^"|"$/g, ""));
        const rows = lines.slice(1).map(line => {
          const cells = line.split(",");
          const obj: Record<string, string> = {};
          headers.forEach((h, i) => { obj[h] = (cells[i] || "").replace(/^"|"$/g, ""); });
          return obj;
        });
        const json = JSON.stringify({ metric: metric.name, description: metric.description, data: rows }, null, 2);
        downloadFile(json, `cissa_${metricId}.json`, "application/json");
      }
      setDownloading(null);
    }, 200);
  };

  const handleBulkDownload = () => {
    setBulkDownloading(true);
    const toDownload = filtered.filter(m => selected.has(m.id));
    let i = 0;
    const next = () => {
      if (i >= toDownload.length) { setBulkDownloading(false); return; }
      const m = toDownload[i++];
      const csv = generateCsv(m.id);
      downloadFile(csv, `cissa_${m.id}.csv`, "text/csv");
      setTimeout(next, 300);
    };
    setTimeout(next, 100);
  };

  const handleDownloadAll = () => {
    selectAll();
    setTimeout(() => {
      setBulkDownloading(true);
      let i = 0;
      const metrics = exportableMetrics;
      const next = () => {
        if (i >= metrics.length) { setBulkDownloading(false); return; }
        const m = metrics[i++];
        const csv = generateCsv(m.id);
        downloadFile(csv, `cissa_${m.id}.csv`, "text/csv");
        setTimeout(next, 300);
      };
      setTimeout(next, 100);
    }, 100);
  };

  const totalRows = exportableMetrics.reduce((s, m) => s + m.rows, 0);

  return (
    <div style={{ padding: "1.5rem", maxWidth: "1400px" }}>

      {/* Header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "hsl(var(--primary))", margin: "0 0 0.25rem 0" }}>
              Metrics &amp; Data Download
            </h1>
            <p style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))", margin: 0, lineHeight: 1.6 }}>
              Export CISSA platform metrics, chart data, and analysis outputs. Select individual datasets or bulk-download all metrics as CSV or JSON.
            </p>
          </div>
          {/* Download All button */}
          <button
            onClick={handleDownloadAll}
            disabled={bulkDownloading}
            data-testid="btn-download-all"
            style={{
              display: "flex", alignItems: "center", gap: "0.5rem",
              padding: "0.625rem 1.25rem",
              background: bulkDownloading ? "hsl(var(--muted))" : "hsl(213 75% 22%)",
              color: bulkDownloading ? "hsl(var(--muted-foreground))" : "#fff",
              border: "none", borderRadius: "0.5rem",
              fontSize: "0.8125rem", fontWeight: 700, cursor: bulkDownloading ? "not-allowed" : "pointer",
              transition: "background 150ms",
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
            </svg>
            {bulkDownloading ? "Downloading..." : `Download All (${exportableMetrics.length} CSVs)`}
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
        {[
          { label: "Total Datasets", value: exportableMetrics.length, note: "Exportable metrics", color: "hsl(213 75% 22%)" },
          { label: "Total Data Rows", value: totalRows.toLocaleString(), note: "Across all datasets", color: "hsl(38 60% 52%)" },
          { label: "Formats", value: "CSV + JSON", note: "Both available", color: "hsl(152 60% 40%)" },
          { label: "Selected", value: selected.size, note: "Ready for bulk export", color: "hsl(188 78% 35%)" },
        ].map(s => (
          <div key={s.label} className="kpi-card" data-testid={`dl-stat-${s.label.toLowerCase().replace(/\s+/g, "-")}`}>
            <div className="kpi-label">{s.label}</div>
            <div className="kpi-value" style={{ color: s.color }}>{s.value}</div>
            <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginTop: "0.25rem" }}>{s.note}</div>
          </div>
        ))}
      </div>

      {/* Filters + bulk actions */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.25rem", flexWrap: "wrap" }}>
        {/* Search */}
        <div style={{ position: "relative", flex: "1", minWidth: "180px", maxWidth: "280px" }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--muted-foreground))" strokeWidth="2"
            style={{ position: "absolute", left: "0.625rem", top: "50%", transform: "translateY(-50%)" }}>
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            type="text"
            placeholder="Search datasets..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            data-testid="search-datasets"
            style={{
              width: "100%", padding: "0.4375rem 0.75rem 0.4375rem 2rem",
              borderRadius: "0.375rem", border: "1px solid hsl(var(--border))",
              background: "hsl(var(--background))", color: "hsl(var(--foreground))",
              fontSize: "0.8125rem", boxSizing: "border-box",
            }}
          />
        </div>

        {/* Principle filter */}
        <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
          {(["all", "Principle 1", "Principle 2", "Principle 4", "All Principles"] as PrincipleFilter[]).map(p => (
            <button
              key={p}
              onClick={() => setPrincipleFilter(p)}
              data-testid={`filter-principle-${p}`}
              style={{
                padding: "0.3125rem 0.625rem", borderRadius: "999px",
                border: principleFilter === p ? "none" : "1px solid hsl(var(--border))",
                background: principleFilter === p ? "hsl(213 75% 22%)" : "hsl(var(--background))",
                color: principleFilter === p ? "#fff" : "hsl(var(--muted-foreground))",
                fontSize: "0.75rem", fontWeight: principleFilter === p ? 700 : 400, cursor: "pointer",
              }}
            >{p === "all" ? "All Principles" : p}</button>
          ))}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <button onClick={selectAll} data-testid="btn-select-all"
            style={{ padding: "0.3125rem 0.625rem", borderRadius: "0.375rem", border: "1px solid hsl(var(--border))", background: "transparent", color: "hsl(var(--foreground))", fontSize: "0.75rem", cursor: "pointer" }}>
            Select All
          </button>
          <button onClick={clearAll} data-testid="btn-clear-all"
            style={{ padding: "0.3125rem 0.625rem", borderRadius: "0.375rem", border: "1px solid hsl(var(--border))", background: "transparent", color: "hsl(var(--muted-foreground))", fontSize: "0.75rem", cursor: "pointer" }}>
            Clear
          </button>
          {selected.size > 0 && (
            <button
              onClick={handleBulkDownload}
              disabled={bulkDownloading}
              data-testid="btn-bulk-download"
              style={{
                display: "flex", alignItems: "center", gap: "0.375rem",
                padding: "0.375rem 0.875rem",
                background: "hsl(38 60% 52%)", color: "#fff",
                border: "none", borderRadius: "0.375rem",
                fontSize: "0.75rem", fontWeight: 700, cursor: "pointer",
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
              </svg>
              Download {selected.size} CSV{selected.size !== 1 ? "s" : ""}
            </button>
          )}
          <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>
            {filtered.length} dataset{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Dataset table */}
      <div className="chart-card" style={{ padding: 0, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}>
          <thead>
            <tr style={{ background: "hsl(var(--muted))" }}>
              <th style={{ padding: "0.625rem 0.75rem", width: "36px", textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={selected.size === filtered.length && filtered.length > 0}
                  onChange={e => e.target.checked ? selectAll() : clearAll()}
                  style={{ cursor: "pointer" }}
                />
              </th>
              <th style={{ padding: "0.625rem 0.75rem", textAlign: "left", fontWeight: 700, color: "hsl(var(--foreground))" }}>Dataset Name</th>
              <th style={{ padding: "0.625rem 0.75rem", textAlign: "left", fontWeight: 700, color: "hsl(var(--foreground))", minWidth: "180px" }}>Description</th>
              <th style={{ padding: "0.625rem 0.75rem", textAlign: "center", fontWeight: 700, color: "hsl(var(--foreground))" }}>Principle</th>
              <th style={{ padding: "0.625rem 0.75rem", textAlign: "center", fontWeight: 700, color: "hsl(var(--foreground))" }}>Section</th>
              <th style={{ padding: "0.625rem 0.75rem", textAlign: "center", fontWeight: 700, color: "hsl(var(--foreground))" }}>Rows</th>
              <th style={{ padding: "0.625rem 0.75rem", textAlign: "center", fontWeight: 700, color: "hsl(var(--foreground))" }}>Export</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "2.5rem", textAlign: "center", color: "hsl(var(--muted-foreground))" }}>
                  No datasets match your filters
                </td>
              </tr>
            ) : filtered.map((metric, i) => {
              const isSelected = selected.has(metric.id);
              const isDownloading = downloading === metric.id;
              const principleColor = PRINCIPLE_COLORS[metric.principle] || "hsl(var(--primary))";
              return (
                <tr
                  key={metric.id}
                  data-testid={`dataset-row-${metric.id}`}
                  style={{
                    borderTop: "1px solid hsl(var(--border))",
                    background: isSelected ? "hsl(213 75% 22% / 0.04)" : i % 2 === 0 ? "transparent" : "hsl(var(--muted) / 0.3)",
                    transition: "background 100ms",
                  }}
                >
                  <td style={{ padding: "0.5rem 0.75rem", textAlign: "center" }}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(metric.id)}
                      style={{ cursor: "pointer" }}
                    />
                  </td>
                  <td style={{ padding: "0.5rem 0.75rem" }}>
                    <div style={{ fontWeight: 600, color: "hsl(var(--foreground))", marginBottom: "0.125rem" }}>{metric.name}</div>
                    <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", fontFamily: "monospace" }}>{metric.id}</div>
                  </td>
                  <td style={{ padding: "0.5rem 0.75rem", color: "hsl(var(--muted-foreground))", fontSize: "0.75rem", lineHeight: 1.5, maxWidth: "260px" }}>
                    {metric.description}
                  </td>
                  <td style={{ padding: "0.5rem 0.75rem", textAlign: "center" }}>
                    <span style={{
                      fontSize: "0.6875rem", fontWeight: 600,
                      color: principleColor,
                      background: `${principleColor}18`,
                      padding: "0.15rem 0.5rem", borderRadius: "0.25rem",
                      whiteSpace: "nowrap",
                    }}>
                      {metric.principle}
                    </span>
                  </td>
                  <td style={{ padding: "0.5rem 0.75rem", textAlign: "center", fontFamily: "monospace", fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>
                    {metric.section}
                  </td>
                  <td style={{ padding: "0.5rem 0.75rem", textAlign: "center", fontFamily: "monospace", fontSize: "0.75rem", fontWeight: 600, color: "hsl(var(--foreground))" }}>
                    {metric.rows}
                  </td>
                  <td style={{ padding: "0.5rem 0.75rem", textAlign: "center" }}>
                    <div style={{ display: "flex", gap: "0.375rem", justifyContent: "center" }}>
                      <button
                        onClick={() => handleDownloadSingle(metric.id, "CSV")}
                        disabled={!!isDownloading}
                        data-testid={`btn-csv-${metric.id}`}
                        style={{
                          display: "flex", alignItems: "center", gap: "0.25rem",
                          padding: "0.3rem 0.625rem",
                          background: isDownloading ? "hsl(var(--muted))" : "hsl(213 75% 22%)",
                          color: isDownloading ? "hsl(var(--muted-foreground))" : "#fff",
                          border: "none", borderRadius: "0.3rem",
                          fontSize: "0.6875rem", fontWeight: 700, cursor: "pointer",
                          transition: "background 150ms",
                        }}
                      >
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                        </svg>
                        CSV
                      </button>
                      <button
                        onClick={() => handleDownloadSingle(metric.id, "JSON")}
                        disabled={!!isDownloading}
                        data-testid={`btn-json-${metric.id}`}
                        style={{
                          display: "flex", alignItems: "center", gap: "0.25rem",
                          padding: "0.3rem 0.625rem",
                          background: "transparent",
                          color: "hsl(213 75% 35%)",
                          border: "1px solid hsl(213 75% 35%)",
                          borderRadius: "0.3rem",
                          fontSize: "0.6875rem", fontWeight: 700, cursor: "pointer",
                          transition: "all 150ms",
                        }}
                        onMouseEnter={e => {
                          (e.currentTarget as HTMLElement).style.background = "hsl(213 75% 35%)";
                          (e.currentTarget as HTMLElement).style.color = "#fff";
                        }}
                        onMouseLeave={e => {
                          (e.currentTarget as HTMLElement).style.background = "transparent";
                          (e.currentTarget as HTMLElement).style.color = "hsl(213 75% 35%)";
                        }}
                      >
                        JSON
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer note */}
      <div className="help-panel" style={{ marginTop: "1.25rem" }}>
        <strong>Data Notes:</strong> All metrics are derived from CISSA platform calculations using publicly available ASX 300 / S&amp;P 500 financial data. EP = Economic Profit = (ROE − Ke) × Book Equity. Ke = Cost of Equity estimated via CAPM with term premium adjustments. Historical data covers 2001–2024. CSV files are UTF-8 encoded, comma-delimited. JSON files contain structured objects with metadata headers.
      </div>
    </div>
  );
}
