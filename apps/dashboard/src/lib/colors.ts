import { color, interpolateRgb } from 'd3'

/** A design token's current value (tokens.css), or `fallback` outside a browser. */
export function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined' || typeof getComputedStyle !== 'function') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function channel(value: number): number {
  const s = value / 255
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}

/** WCAG relative luminance of a CSS colour (white for anything unparsable). */
export function luminance(css: string): number {
  const rgb = color(css)?.rgb()
  if (!rgb) return 1
  return 0.2126 * channel(rgb.r) + 0.7152 * channel(rgb.g) + 0.0722 * channel(rgb.b)
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}

/** Black or white text, whichever reads better on `fill` (never below 4.5:1). */
export function readableOn(fill: string): string {
  return contrast(fill, '#ffffff') >= contrast(fill, '#000000') ? '#ffffff' : '#000000'
}

/**
 * A sequential scale between two tokens. The square root spreads the small probabilities
 * a confident model produces, so a runner-up at a few per cent is still visible.
 */
export function sequential(low: string, high: string): (t: number) => string {
  const mix = interpolateRgb(low, high)
  return (t: number) => mix(Math.sqrt(Math.max(0, Math.min(1, t))))
}
