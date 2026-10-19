import { describe, expect, it } from 'vitest'

import { ACCEPTED } from '@/__tests__/helpers'
import type { JobOut } from '@/api/types'

import { estimate, interval } from '../format'
import { jobRate, rateText } from '../jobs'
import { countWords } from '../labels'
import { reviewLabel } from '../nav'
import { rampOpacity, readoutColumns, readoutGroups, readoutTemplate } from '../readout'
import { judgePlate, toTokens } from '../typed'

describe('the plate readout layout', () => {
  it('has one column per character, separators included, and the plate fields as groups', () => {
    const columns = readoutColumns(ACCEPTED.positions)
    expect(columns).toHaveLength(ACCEPTED.positions.length)
    expect(columns.filter((c) => c.separator)).toHaveLength(2)
    expect(columns.some((c) => c.arabic)).toBe(true)
    for (const column of columns) {
      for (const alt of column.alternatives) {
        expect(alt.symbol).not.toBe(column.symbol)
        expect(alt.probability).toBeGreaterThanOrEqual(0.01)
      }
    }
    expect(readoutGroups(columns).map((g) => g.name)).toEqual(['Digits', 'Letter', 'Region'])
    const template = readoutTemplate(columns).split(' ')
    expect(template.filter((t) => t === 'var(--sep)')).toHaveLength(2)
  })

  it('maps confidence to a one-hue ramp that spreads small probabilities', () => {
    expect(rampOpacity(0)).toBe(0)
    expect(rampOpacity(1)).toBe(1)
    expect(rampOpacity(0.04)).toBeCloseTo(0.2)
    expect(rampOpacity(2)).toBe(1)
  })
})

describe('typed corrections', () => {
  it('accepts the spellings the service accepts and explains what it reads', () => {
    expect(toTokens('24830 ب 1')).toBe('24830-ب-1')
    expect(toTokens('24830ب1')).toBe('24830-ب-1')
    expect(toTokens('١٣ww')).toBe('13-WW')
    const standard = judgePlate('24830-ب-1')
    expect(standard.valid).toBe(true)
    expect(standard.message).toContain('letter ب')
    const temporary = judgePlate('13ww')
    expect(temporary.valid).toBe(true)
    expect(temporary.display).toBe('13 WW')
  })

  it('says what is missing while the plate is not one yet', () => {
    expect(judgePlate('').valid).toBe(false)
    const partial = judgePlate('2483')
    expect(partial.valid).toBe(false)
    expect(partial.message).toContain('Not a plate yet')
    expect(judgePlate('24830-x-1').valid).toBe(false)
  })
})

describe('words around numbers', () => {
  it('writes intervals in words and never a bare estimate', () => {
    const e = { value: 0.25, ci_low: 0, ci_high: 0.5, n: 12 }
    expect(estimate(e, false, 0)).toBe('25% (0 to 50)')
    expect(interval(e, false, 0)).toBe('(0 to 50)')
    expect(estimate({ value: 0.9, ci_low: 0.87, ci_high: 0.93, n: 1 }, true)).toBe(
      '0.90 (0.87 to 0.93)',
    )
    expect(countWords(12)).toBe('twelve')
    expect(countWords(40)).toBe('40')
  })

  it('names the review queue with its count', () => {
    expect(reviewLabel(null)).toBe('Review queue')
    expect(reviewLabel({ pending: 0, ready_to_export: 0 })).toBe('Review queue (none waiting)')
    expect(reviewLabel({ pending: 3, ready_to_export: 1 })).toBe('Review queue (3 waiting)')
  })

  it('gives a running job a count and a rate', () => {
    const job = {
      status: 'running',
      message: '12/40 photos',
      started_at: new Date(0).toISOString(),
    } as JobOut
    const rate = jobRate(job, 6000)
    expect(rate).toEqual({ done: 12, total: 40, unit: 'photos', perSecond: 2 })
    expect(rateText(rate)).toBe('12 of 40 photos · 2.0 photos per second')
    expect(jobRate({ ...job, message: 'frame 120/900' }, 6000)?.unit).toBe('frames')
    expect(jobRate({ ...job, message: 'queued' }, 6000)).toBeNull()
  })
})
