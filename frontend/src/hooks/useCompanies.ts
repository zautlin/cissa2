/**
 * useCompanies / useUnderlyingData
 *
 * Hooks that fetch raw API data, pass through the companyData.ts data layer,
 * and return fully-typed local structures. UI never sees raw API shapes.
 */
import { useState, useEffect } from "react";
import { getCompanies, getMetrics } from "../lib/api";
import {
  CompanyInfo,
  CompanyMetricRow,
  SectorSummaryRow,
  mapApiCompanies,
  buildLatestByTicker,
  buildCompanyMetricRows,
  buildSectorSummary,
} from "../lib/companyData";

// ─── useCompanies ─────────────────────────────────────────────────────────────

export interface CompaniesState {
  data:    CompanyInfo[];
  loading: boolean;
  error:   string | null;
}

export function useCompanies(datasetId?: string): CompaniesState {
  const [state, setState] = useState<CompaniesState>({ data: [], loading: false, error: null });

  useEffect(() => {
    let cancelled = false;
    setState(s => ({ ...s, loading: true, error: null }));
    getCompanies(datasetId)
      .then(raw => {
        if (!cancelled) setState({ data: mapApiCompanies(raw), loading: false, error: null });
      })
      .catch(e => {
        if (!cancelled) setState({ data: [], loading: false, error: e.message });
      });
    return () => { cancelled = true; };
  }, [datasetId]);

  return state;
}

// ─── useUnderlyingData ────────────────────────────────────────────────────────

export interface UnderlyingDataState {
  rows:          CompanyMetricRow[];
  sectorSummary: SectorSummaryRow[];
  loading:       boolean;
  error:         string | null;
}

export function useUnderlyingData(
  datasetId:  string | null,
  paramSetId: string | null,
): UnderlyingDataState {
  const [state, setState] = useState<UnderlyingDataState>({
    rows: [], sectorSummary: [], loading: false, error: null,
  });

  useEffect(() => {
    if (!datasetId || !paramSetId) return;
    let cancelled = false;
    setState(s => ({ ...s, loading: true, error: null }));

    Promise.all([
      getCompanies(datasetId),
      getMetrics({ dataset_id: datasetId, parameter_set_id: paramSetId, metric_name: "TER-Ke" }),
      getMetrics({ dataset_id: datasetId, parameter_set_id: paramSetId, metric_name: "TERA" }),
      getMetrics({ dataset_id: datasetId, parameter_set_id: paramSetId, metric_name: "EP PCT" }),
      getMetrics({ dataset_id: datasetId, parameter_set_id: paramSetId, metric_name: "Calc FY TSR" }),
    ])
      .then(([rawCompanies, terKeRes, teraRes, epPctRes, tsrRes]) => {
        if (cancelled) return;

        // Map raw API → local types via data layer
        const companies   = mapApiCompanies(rawCompanies);
        const terKeMap    = buildLatestByTicker(terKeRes.results);
        const terAlphaMap = buildLatestByTicker(teraRes.results);
        const epPctMap    = buildLatestByTicker(epPctRes.results);
        const tsrMap      = buildLatestByTicker(tsrRes.results);

        const rows          = buildCompanyMetricRows(companies, terKeMap, terAlphaMap, epPctMap, tsrMap);
        const sectorSummary = buildSectorSummary(rows);

        setState({ rows, sectorSummary, loading: false, error: null });
      })
      .catch(e => {
        if (!cancelled) setState({ rows: [], sectorSummary: [], loading: false, error: e.message });
      });

    return () => { cancelled = true; };
  }, [datasetId, paramSetId]);

  return state;
}
