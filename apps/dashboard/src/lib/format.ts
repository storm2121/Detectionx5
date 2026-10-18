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

/** The interval of an estimate, "95.0–100.0%" (or plain numbers with `plain`). */
export function interval(estimate: Estimate, plain = false, digits = 1): string {
  if (plain) return `${fixed(estimate.ci_low, 2)}${DASH}${fixed(estimate.ci_high, 2)}`
  return `${(estimate.ci_low * 100).toFixed(digits)}${DASH}${percent(estimate.ci_high, digits)}`
}

export function estimateValue(estimate: Estimate, plain = false, digits = 1): string {
  return plain ? fixed(estimate.value, 2) : percent(estimate.value, digits)
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
