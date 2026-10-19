import type { Candidate, PositionOut, ReadOut } from '@/api/types'

import { GAP, SEPARATOR } from './plate'

export interface FusionRow {
  tokens: string
  plate: string
  /** The candidate's probability in each view's beam; null when the view did not propose it. */
  views: (number | null)[]
  /** Fused posterior; null when fusion dropped it. */
  fused: number | null
  inSet: boolean
  isPrediction: boolean
}

/**
 * The fusion table: one row per candidate any view proposed, the per-view probabilities
 * next to the fused posterior, sorted by the fused posterior (then by the best view).
 */
export function fusionRows(read: ReadOut, limit = 8): FusionRow[] {
  const rows = new Map<string, FusionRow>()
  const inSet = new Set(read.prediction_set ?? [])
  const ensure = (candidate: Candidate): FusionRow => {
    let row = rows.get(candidate.tokens)
    if (!row) {
      row = {
        tokens: candidate.tokens,
        plate: candidate.plate,
        views: read.views.map(() => null),
        fused: null,
        inSet: inSet.has(candidate.plate),
        isPrediction: candidate.tokens === read.tokens,
      }
      rows.set(candidate.tokens, row)
    }
    return row
  }
  for (const candidate of read.posterior) ensure(candidate).fused = candidate.probability
  read.views.forEach((view, index) => {
    for (const candidate of view.hypotheses) ensure(candidate).views[index] = candidate.probability
  })
  const best = (row: FusionRow) => Math.max(0, ...row.views.map((p) => p ?? 0))
  return [...rows.values()]
    .sort(
      (a, b) =>
        (b.fused ?? -1) - (a.fused ?? -1) || best(b) - best(a) || a.tokens.localeCompare(b.tokens),
    )
    .slice(0, limit)
}

/** The weakest non-separator character of a read, for the one-line summary. */
export function weakestCharacter(positions: readonly PositionOut[]): PositionOut | null {
  let weakest: PositionOut | null = null
  for (const position of positions) {
    if (position.symbol === SEPARATOR || position.symbol === GAP) continue
    if (!weakest || position.confidence < weakest.confidence) weakest = position
  }
  return weakest
}
