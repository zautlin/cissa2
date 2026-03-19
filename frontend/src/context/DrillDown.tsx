/**
 * DrillDown Context
 * -----------------
 * Global state for:
 *  - selectedTicker: string | null  — drill into one company
 *  - selectedSector: string | null  — drill into one sector
 *  - drillMode: "ticker" | "sector" | null
 *
 * Any chart or table can call useDrillDown() to:
 *  - Read the current filter
 *  - drillIntoTicker(ticker) — filter all charts to that company
 *  - drillIntoSector(sector) — filter all charts to that sector
 *  - clearDrill() — go back to full view
 */
import { createContext, useContext, useState, ReactNode } from "react";

export type DrillMode = "ticker" | "sector" | null;

export interface DrillDownState {
  selectedTicker: string | null;
  selectedSector: string | null;
  drillMode: DrillMode;
  drillLabel: string | null;
  drillIntoTicker: (ticker: string, label?: string) => void;
  drillIntoSector: (sector: string) => void;
  clearDrill: () => void;
}

const DrillDownContext = createContext<DrillDownState>({
  selectedTicker: null,
  selectedSector: null,
  drillMode: null,
  drillLabel: null,
  drillIntoTicker: () => {},
  drillIntoSector: () => {},
  clearDrill: () => {},
});

export function DrillDownProvider({ children }: { children: ReactNode }) {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [drillMode, setDrillMode] = useState<DrillMode>(null);
  const [drillLabel, setDrillLabel] = useState<string | null>(null);

  const drillIntoTicker = (ticker: string, label?: string) => {
    setSelectedTicker(ticker);
    setSelectedSector(null);
    setDrillMode("ticker");
    setDrillLabel(label ?? ticker);
  };

  const drillIntoSector = (sector: string) => {
    setSelectedSector(sector);
    setSelectedTicker(null);
    setDrillMode("sector");
    setDrillLabel(sector);
  };

  const clearDrill = () => {
    setSelectedTicker(null);
    setSelectedSector(null);
    setDrillMode(null);
    setDrillLabel(null);
  };

  return (
    <DrillDownContext.Provider value={{
      selectedTicker, selectedSector, drillMode, drillLabel,
      drillIntoTicker, drillIntoSector, clearDrill,
    }}>
      {children}
    </DrillDownContext.Provider>
  );
}

export function useDrillDown(): DrillDownState {
  return useContext(DrillDownContext);
}

// ─── DrillDownBanner — shown at top of any page when a filter is active ───────
const NAV = "#0E2D5C";
const GOLD = "#C8922A";

export function DrillDownBanner() {
  const { drillMode, drillLabel, selectedSector, clearDrill } = useDrillDown();
  if (!drillMode) return null;

  const icon = drillMode === "ticker" ? "🏢" : "🏗";
  const typeLabel = drillMode === "ticker" ? "Company" : "Sector";

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "10px 20px",
      background: `${NAV}0d`,
      border: `1px solid ${NAV}22`,
      borderRadius: 10,
      marginBottom: 20,
    }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <div style={{ flex: 1 }}>
        <span style={{ fontSize: 11, color: GOLD, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5 }}>
          {typeLabel} Drill-Down
        </span>
        <div style={{ fontSize: 14, fontWeight: 700, color: NAV }}>{drillLabel}</div>
        <div style={{ fontSize: 11, color: "#6B7894" }}>
          All charts are filtered to this {typeLabel.toLowerCase()}.
          {drillMode === "sector" && " Click a company bar to drill into a single company."}
        </div>
      </div>
      <button
        onClick={clearDrill}
        style={{
          padding: "6px 16px", borderRadius: 8, border: `1px solid ${NAV}33`,
          background: "#fff", cursor: "pointer", fontSize: 12,
          fontWeight: 700, color: NAV,
        }}
      >
        ✕ Clear Filter
      </button>
    </div>
  );
}

// ─── Filter helpers ───────────────────────────────────────────────────────────

/** Filter a flat array of {ticker, sector, ...} by current drill selection */
export function applyDrillFilter<T extends { ticker?: string; sector?: string }>(
  data: T[],
  drill: Pick<DrillDownState, "drillMode" | "selectedTicker" | "selectedSector">
): T[] {
  if (!drill.drillMode) return data;
  if (drill.drillMode === "ticker" && drill.selectedTicker) {
    return data.filter(r => r.ticker === drill.selectedTicker);
  }
  if (drill.drillMode === "sector" && drill.selectedSector) {
    return data.filter(r => r.sector === drill.selectedSector);
  }
  return data;
}
