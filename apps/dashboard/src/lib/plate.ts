/** Plate vocabulary shared by the components (the grammar lives in plate_reader/grammar.py). */

export const DIGITS = '0123456789'
export const LETTERS = ['أ', 'ب', 'د', 'ه', 'و', 'ط'] as const
export const TEMPORARY_MARK = 'W'
export const SEPARATOR = '-'
/** The fused per-position posterior's symbol for "this candidate has nothing here". */
export const GAP = '∅'

/** Display order of symbols: digits, the six letters, W, the separator, the gap. */
export const SYMBOL_ORDER: readonly string[] = [
  ...DIGITS,
  ...LETTERS,
  TEMPORARY_MARK,
  SEPARATOR,
  GAP,
]

export function symbolRank(symbol: string): number {
  const rank = SYMBOL_ORDER.indexOf(symbol)
  return rank === -1 ? SYMBOL_ORDER.length : rank
}

export function symbolLabel(symbol: string): string {
  if (symbol === SEPARATOR) return 'separator'
  if (symbol === GAP) return 'nothing'
  return symbol
}

export const REVIEW_REASONS: Record<string, string> = {
  set_size: 'several plates in the set',
  empty_set: 'empty conformal set',
  low_confidence: 'low confidence',
  unreadable: 'no plate read',
}

export function reviewReason(reason: string | null | undefined): string {
  if (!reason) return ''
  return REVIEW_REASONS[reason] ?? reason.replace(/_/g, ' ')
}

/** Sentence-case names for the states the service reports. */
export const STATUS_LABELS: Record<string, string> = {
  accepted: 'Accepted',
  queued: 'Waiting for review',
  reviewed: 'Reviewed',
  pending: 'Waiting',
  running: 'Running',
  finished: 'Finished',
  failed: 'Failed',
}

export function statusLabel(status: string): string {
  return (
    STATUS_LABELS[status] ?? status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' ')
  )
}

export type Tone = 'ok' | 'warn' | 'bad' | 'info' | 'neutral'

export function statusTone(status: string): Tone {
  switch (status) {
    case 'accepted':
    case 'finished':
    case 'reviewed':
    case 'ok':
      return 'ok'
    case 'queued':
    case 'pending':
    case 'running':
    case 'degraded':
      return 'warn'
    case 'failed':
    case 'unavailable':
      return 'bad'
    default:
      return 'neutral'
  }
}
