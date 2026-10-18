import { describe, expect, it } from 'vitest'

import {
  bytes,
  dateTime,
  fixed,
  floorPercent,
  integer,
  interval,
  level,
  milliseconds,
  percent,
  probability,
  scientific,
} from '../format'

describe('number formatting', () => {
  it('formats percentages and missing values', () => {
    expect(percent(0.9873)).toBe('98.7%')
    expect(percent(1)).toBe('100.0%')
    expect(percent(null)).toBe('–')
    expect(percent(Number.NaN)).toBe('–')
  })

  it('never rounds a posterior to a certainty it is not', () => {
    expect(probability(0.99999997)).toBe('>99.9%')
    expect(probability(0.9994)).toBe('99.9%')
    expect(probability(1)).toBe('100.0%')
    expect(probability(0.00000003, 2)).toBe('<0.01%')
    expect(probability(0)).toBe('<0.1%')
    expect(probability(0.5)).toBe('50.0%')
    expect(probability(undefined)).toBe('–')
    expect(floorPercent(0.99999)).toBe('99')
    expect(floorPercent(1)).toBe('100')
    expect(floorPercent(0.29)).toBe('29')
  })

  it('formats thresholds, sizes and durations', () => {
    expect(scientific(7.244507090976478e-10)).toBe('7.24e-10')
    expect(scientific(0.25)).toBe('0.250')
    expect(scientific(0)).toBe('0')
    expect(fixed(0.88866, 3)).toBe('0.889')
    expect(integer(1440051)).toBe('1,440,051')
    expect(milliseconds(686.4)).toBe('686 ms')
    expect(milliseconds(1139400)).toBe('1139.40 s')
    expect(bytes(5766342)).toBe('5.5 MiB')
    expect(bytes(512)).toBe('512 B')
    expect(level(0.95)).toBe('95%')
  })

  it('formats bootstrap intervals', () => {
    const estimate = { value: 0.99, ci_low: 0.98, ci_high: 1, n: 300 }
    expect(interval(estimate)).toBe('98.0–100.0%')
    expect(interval({ value: 0.95, ci_low: 0.94, ci_high: 0.97, n: 2000 }, true)).toBe('0.94–0.97')
  })

  it('formats dates and rejects nonsense', () => {
    expect(dateTime('2026-10-18T21:46:00Z')).toMatch(/2026/)
    expect(dateTime('not a date')).toBe('–')
    expect(dateTime(null)).toBe('–')
  })
})
