import { describe, expect, it } from 'vitest'

import { contrast, cssVar, luminance, readableOn, sequential } from '../colors'

describe('colour helpers', () => {
  it('computes WCAG luminance and contrast', () => {
    expect(luminance('#ffffff')).toBeCloseTo(1)
    expect(luminance('#000000')).toBeCloseTo(0)
    expect(contrast('#ffffff', '#000000')).toBeCloseTo(21)
    expect(luminance('not a colour')).toBe(1)
  })

  it('picks text that reads at 4.5:1 or better on every heatmap fill', () => {
    for (const [low, high] of [
      ['#f1f5f9', '#0f766e'],
      ['#111c30', '#5eead4'],
    ] as const) {
      const scale = sequential(low, high)
      for (let i = 0; i <= 20; i += 1) {
        const fill = scale(i / 20)
        expect(contrast(fill, readableOn(fill))).toBeGreaterThanOrEqual(4.5)
      }
    }
  })

  it('maps the ends of the scale to the two tokens', () => {
    const scale = sequential('#000000', '#ffffff')
    expect(scale(0)).toBe('rgb(0, 0, 0)')
    expect(scale(1)).toBe('rgb(255, 255, 255)')
    expect(scale(2)).toBe('rgb(255, 255, 255)')
  })

  it('falls back when a token is not defined', () => {
    expect(cssVar('--dx-not-defined', '#123456')).toBe('#123456')
  })
})
