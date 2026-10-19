import type { JobOut } from '@/api/types'

/**
 * A job's progress in counts and a rate, read from what the worker reports ("12/40 photos",
 * "frame 120/900", "track 2/5") and the time since it started, so a long job says how much
 * is done and how fast it goes rather than only a percentage.
 */
export interface JobRate {
  done: number
  total: number
  unit: string
  perSecond: number | null
}

const PATTERN = /(?:(frame|track)\s+)?(\d+)\s*\/\s*(\d+)(?:\s+(photos?|frames?|tracks?))?/i

export function jobRate(job: JobOut, now: number = Date.now()): JobRate | null {
  const match = PATTERN.exec(job.message ?? '')
  if (!match) return null
  const done = Number(match[2])
  const total = Number(match[3])
  const word = (match[4] ?? match[1] ?? 'items').toLowerCase()
  const unit = word.endsWith('s') ? word : `${word}s`
  const started = job.started_at ? Date.parse(job.started_at) : Number.NaN
  const seconds = (now - started) / 1000
  const perSecond =
    Number.isFinite(seconds) && seconds > 0 && job.status === 'running' ? done / seconds : null
  return { done, total, unit, perSecond }
}

export function rateText(rate: JobRate | null): string {
  if (!rate) return ''
  const count = `${rate.done} of ${rate.total} ${rate.unit}`
  if (rate.perSecond === null) return count
  const per = rate.perSecond >= 10 ? rate.perSecond.toFixed(0) : rate.perSecond.toFixed(1)
  return `${count} · ${per} ${rate.unit} per second`
}
