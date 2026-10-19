import type { Estimate } from '@/api/results'

const DASH = '–'

/** 0.9873 -> "98.7%"; null and NaN -> an en dash. */
export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return `${(value * 100).toFixed(digits)}%`
}

/**
 * A model probability as a percentage that never rounds to a certainty it is not: a
 * posterior of 0.99999997 reads ">99.9%", not "100.0%". Empirical rates use `percent`.
 */
export function probability(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  const scaled = value * 100
  const step = 10 ** -digits
  if (value < 1 && scaled >= 100 - step / 2) return `>${(100 - step).toFixed(digits)}%`
  // A posterior is never exactly zero (fusion floors it); a zero here is rounding.
  if (scaled < step / 2) return `<${step.toFixed(digits)}%`
  return `${scaled.toFixed(digits)}%`
}

/** Whole per cent rounded down, for compact cells (a posterior under 1 never shows 100). */
export function floorPercent(value: number): string {
  return Math.floor(value * 100 + 1e-9).toString()
}

/** A number with fixed decimals, or an en dash. */
export function fixed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return value.toFixed(digits)
}

/** Small thresholds (they reach 1e-16 for five fused views) in scientific notation. */
export function scientific(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  if (value === 0) return '0'
  return Math.abs(value) >= 0.01 && Math.abs(value) < 1000
    ? value.toPrecision(digits + 1)
    : value.toExponential(digits)
}

export function integer(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return Math.round(value).toLocaleString('en-US')
}

export function milliseconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value.toFixed(0)} ms`
}

export function bytes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`
  return `${(value / 1024 / 1024).toFixed(1)} MiB`
}

/** The interval alone, in words: "(0 to 50)" for rates, "(0.87 to 0.93)" with `plain`. */
export function interval(value: Estimate, plain = false, digits = 1): string {
  if (plain) return `(${fixed(value.ci_low, 2)} to ${fixed(value.ci_high, 2)})`
  return `(${(value.ci_low * 100).toFixed(digits)} to ${(value.ci_high * 100).toFixed(digits)})`
}

/**
 * A value with its interval, "25% (0 to 50)": the console never shows a bare point
 * estimate. `plain` writes a number that is not a rate, "0.90 (0.87 to 0.93)".
 */
export function estimate(value: Estimate, plain = false, digits = 1): string {
  if (plain) return `${fixed(value.value, 2)} ${interval(value, true)}`
  return `${percent(value.value, digits)} ${interval(value, false, digits)}`
}

const DATE = new Intl.DateTimeFormat('en-GB', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function dateTime(value: string | null | undefined): string {
  if (!value) return DASH
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? DASH : DATE.format(date)
}

export function level(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH
  return `${Math.round(value * 100)}%`
}
