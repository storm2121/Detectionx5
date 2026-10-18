import type { CalibrationResult, CoverageReport, FusedCalibrationResult } from '@/api/results'

export interface CoverageRow {
  key: string
  views: string | null
  report: CoverageReport
}

/** Single-view coverage rows, highest level first. */
export function singleViewRows(result: CalibrationResult): CoverageRow[] {
  return Object.entries(result.conformal.coverage)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([alpha, report]) => ({ key: `1-${alpha}`, views: null, report }))
}

/** Fused coverage rows: every calibrated number of views, highest level first within each. */
export function fusedRows(result: FusedCalibrationResult): CoverageRow[] {
  const rows: CoverageRow[] = []
  const counts = Object.keys(result.coverage).sort((a, b) => Number(a) - Number(b))
  for (const views of counts) {
    const byAlpha = result.coverage[views] ?? {}
    for (const alpha of Object.keys(byAlpha).sort((a, b) => Number(a) - Number(b))) {
      const report = byAlpha[alpha]
      if (report) rows.push({ key: `${views}-${alpha}`, views, report })
    }
  }
  return rows
}
