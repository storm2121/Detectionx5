import type { PositionOut } from '@/api/types'

import { LETTERS, SEPARATOR, TEMPORARY_MARK } from './plate'

/**
 * The plate readout's columns: one per character of the fused read, separators included,
 * so the plate and the per-character confidence under it share one grid and line up.
 */
export interface ReadoutColumn {
  index: number
  symbol: string
  separator: boolean
  arabic: boolean
  confidence: number
  /** Other symbols the views put here, most likely first (at least `minimum` each). */
  alternatives: { symbol: string; probability: number }[]
}

export interface ReadoutGroup {
  name: 'Digits' | 'Letter' | 'Region' | 'Temporary'
  start: number
  end: number
}

export function readoutColumns(
  positions: readonly PositionOut[],
  minimum = 0.01,
  limit = 2,
): ReadoutColumn[] {
  return positions.map((position) => {
    const others = [...position.distribution]
      .filter((d) => d.symbol !== position.symbol && d.probability >= minimum)
      .sort((a, b) => b.probability - a.probability)
      .slice(0, limit)
    return {
      index: position.index,
      symbol: position.symbol,
      separator: position.symbol === SEPARATOR,
      arabic: (LETTERS as readonly string[]).includes(position.symbol),
      confidence: position.confidence,
      alternatives: others,
    }
  })
}

/** The plate's fields as runs of columns between separators, for the captions. */
export function readoutGroups(columns: readonly ReadoutColumn[]): ReadoutGroup[] {
  const runs: { start: number; end: number; symbols: string[] }[] = []
  let current: { start: number; end: number; symbols: string[] } | null = null
  columns.forEach((column, i) => {
    if (column.separator) {
      current = null
      return
    }
    if (!current) {
      current = { start: i, end: i, symbols: [] }
      runs.push(current)
    }
    current.end = i
    current.symbols.push(column.symbol)
  })
  const temporary = runs.length === 2 && runs[1]?.symbols.every((s) => s === TEMPORARY_MARK)
  return runs.map((run, i) => {
    let name: ReadoutGroup['name'] = 'Digits'
    if (temporary && i === 1) name = 'Temporary'
    else if (!temporary && i === 1) name = 'Letter'
    else if (!temporary && i === 2) name = 'Region'
    return { name, start: run.start, end: run.end }
  })
}

/** CSS grid columns for the readout: characters share one width, separators a narrow one. */
export function readoutTemplate(columns: readonly ReadoutColumn[]): string {
  return columns.map((c) => (c.separator ? 'var(--sep)' : 'var(--cell)')).join(' ')
}

/** The ramp's intensity for a probability: the square root spreads the small ones. */
export function rampOpacity(probability: number): number {
  return Math.sqrt(Math.max(0, Math.min(1, probability)))
}
