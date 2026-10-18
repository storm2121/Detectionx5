import { describe, expect, it } from 'vitest'

import { ACCEPTED, QUEUED } from '@/__tests__/helpers'
import type { PositionOut } from '@/api/types'

import { fusionRows, heatmap, weakestCharacter } from '../fusion'
import { GAP, SEPARATOR, SYMBOL_ORDER, reviewReason, statusTone, symbolLabel } from '../plate'

describe('the fusion table', () => {
  it('puts the read first with every view next to the fused posterior', () => {
    const rows = fusionRows(ACCEPTED)
    const [top] = rows
    expect(top?.tokens).toBe(ACCEPTED.tokens)
    expect(top?.isPrediction).toBe(true)
    expect(top?.inSet).toBe(true)
    expect(top?.views).toHaveLength(ACCEPTED.views.length)
    // The first photo proposed no plate, so it has no probability for any candidate.
    expect(rows.every((row) => row.views[0] === null)).toBe(true)
    expect(rows.filter((row) => row.inSet)).toHaveLength(ACCEPTED.prediction_set?.length ?? 0)
    const fused = rows.map((row) => row.fused ?? -1)
    expect([...fused].sort((a, b) => b - a)).toEqual(fused)
  })

  it('respects the row limit and keeps candidates fusion dropped', () => {
    expect(fusionRows(ACCEPTED, 3)).toHaveLength(3)
    const single = fusionRows(QUEUED, 50)
    expect(single.length).toBeGreaterThanOrEqual(QUEUED.posterior.length)
  })
})

describe('the character heatmap', () => {
  it('has one column per position and rows for every winner', () => {
    const data = heatmap(ACCEPTED.positions)
    expect(data.columns).toHaveLength(ACCEPTED.positions.length)
    const winners = ACCEPTED.positions.filter((p) => p.symbol !== SEPARATOR).map((p) => p.symbol)
    for (const symbol of winners) expect(data.symbols).toContain(symbol)
    expect(data.cells).toHaveLength(data.columns.length * data.symbols.length)
    expect(data.cells.filter((c) => c.winner).length).toBe(winners.length)
  })

  it('drops the separator row unless a hypothesis puts one under a character', () => {
    expect(heatmap(ACCEPTED.positions).symbols).not.toContain(SEPARATOR)
    const misplaced: PositionOut[] = [
      {
        index: 0,
        symbol: '1',
        confidence: 0.6,
        distribution: [
          { symbol: '1', probability: 0.6 },
          { symbol: SEPARATOR, probability: 0.3 },
          { symbol: GAP, probability: 0.1 },
        ],
      },
    ]
    expect(heatmap(misplaced).symbols).toEqual(['1', SEPARATOR, GAP])
  })

  it('orders digits before letters and finds the weakest character', () => {
    const data = heatmap(QUEUED.positions, 0)
    const ranks = data.symbols.map((s) => SYMBOL_ORDER.indexOf(s))
    expect([...ranks].sort((a, b) => a - b)).toEqual(ranks)
    const weakest = weakestCharacter(QUEUED.positions)
    const lowest = Math.min(
      ...QUEUED.positions.filter((p) => p.symbol !== SEPARATOR).map((p) => p.confidence),
    )
    expect(weakest?.confidence).toBe(lowest)
    expect(weakestCharacter([])).toBeNull()
  })
})

describe('plate vocabulary', () => {
  it('names symbols, reasons and tones', () => {
    expect(symbolLabel(SEPARATOR)).toBe('separator')
    expect(symbolLabel(GAP)).toBe('nothing')
    expect(symbolLabel('7')).toBe('7')
    expect(reviewReason('empty_set')).toBe('empty conformal set')
    expect(reviewReason('something_new')).toBe('something new')
    expect(reviewReason(null)).toBe('')
    expect(statusTone('accepted')).toBe('ok')
    expect(statusTone('queued')).toBe('warn')
    expect(statusTone('failed')).toBe('bad')
    expect(statusTone('whatever')).toBe('neutral')
  })
})
