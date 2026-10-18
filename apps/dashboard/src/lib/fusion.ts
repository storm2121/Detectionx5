import type { Candidate, PositionOut, ReadOut } from '@/api/types'

import { GAP, SEPARATOR, symbolRank } from './plate'

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

export interface HeatCell {
  position: number
  symbol: string
  probability: number
  winner: boolean
}

export interface HeatColumn {
  position: number
  symbol: string
  confidence: number
  separator: boolean
}

export interface Heatmap {
  symbols: string[]
  columns: HeatColumn[]
  cells: HeatCell[]
}

/**
 * The character heatmap: winner positions across, symbols down. A symbol gets a row when
 * it reaches `minimum` probability at some position (winners always do), so the map stays
 * readable when the posterior is confident.
 */
export function heatmap(positions: readonly PositionOut[], minimum = 0.005): Heatmap {
  // Separator columns are drawn as spacers, so their own symbol needs no row; a separator
  // still gets a row when some hypothesis puts one where the read has a character.
  const keep = new Set<string>()
  for (const position of positions) {
    if (position.symbol === SEPARATOR) continue
    keep.add(position.symbol)
    for (const entry of position.distribution) {
      if (entry.probability >= minimum) keep.add(entry.symbol)
    }
  }
  const symbols = [...keep].sort((a, b) => symbolRank(a) - symbolRank(b) || a.localeCompare(b))
  const columns = positions.map((p) => ({
    position: p.index,
    symbol: p.symbol,
    confidence: p.confidence,
    separator: p.symbol === SEPARATOR,
  }))
  const cells: HeatCell[] = []
  for (const position of positions) {
    const lookup = new Map(position.distribution.map((d) => [d.symbol, d.probability]))
    for (const symbol of symbols) {
      cells.push({
        position: position.index,
        symbol,
        probability: lookup.get(symbol) ?? 0,
        winner: symbol === position.symbol,
      })
    }
  }
  return { symbols, columns, cells }
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
