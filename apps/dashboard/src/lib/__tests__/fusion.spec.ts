import { describe, expect, it } from 'vitest'

import { ACCEPTED, QUEUED } from '@/__tests__/helpers'
import { fusionRows, weakestCharacter } from '../fusion'
import { GAP, SEPARATOR, reviewReason, statusLabel, statusTone, symbolLabel } from '../plate'

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

describe('the weakest character', () => {
  it('is the least confident character, separators aside', () => {
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
    expect(statusLabel('queued')).toBe('Waiting for review')
    expect(statusLabel('something_new')).toBe('Something new')
  })
})
