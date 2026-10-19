/**
 * CTC decoding, ported line for line from plate_reader/crnn/decode.py and the posterior and
 * conformal helpers of plate_reader/crnn/calibrate.py and conformal.py, so the browser and
 * the Python pipeline produce the same hypotheses (ADR 0003). Everything is float64.
 */
import { fsum } from './fsum'
import { DEAD, GRAMMAR, isAccepting, step, SYMBOLS } from './grammar'

export const BLANK = 0
export const DEFAULT_BEAM = 10
export const DEFAULT_PRUNE = -14.0

export interface Hypothesis {
  tokens: string
  logp: number
}

/** Row-wise log-softmax of `logits / temperature` for a `(frames, classes)` array. */
export function logSoftmax(
  logits: ArrayLike<number>,
  frames: number,
  classes: number,
  temperature = 1,
): Float64Array {
  const out = new Float64Array(frames * classes)
  for (let t = 0; t < frames; t += 1) {
    let max = Number.NEGATIVE_INFINITY
    for (let c = 0; c < classes; c += 1) {
      const v = (logits[t * classes + c] as number) / temperature
      out[t * classes + c] = v
      if (v > max) max = v
    }
    let sum = 0
    for (let c = 0; c < classes; c += 1) {
      const shifted = (out[t * classes + c] as number) - max
      out[t * classes + c] = shifted
      sum += Math.exp(shifted)
    }
    const log = Math.log(sum)
    for (let c = 0; c < classes; c += 1)
      out[t * classes + c] = (out[t * classes + c] as number) - log
  }
  return out
}

function logaddexp(a: number, b: number): number {
  if (a === Number.NEGATIVE_INFINITY) return b
  if (b === Number.NEGATIVE_INFINITY) return a
  if (a > b) return a + Math.log1p(Math.exp(b - a))
  return b + Math.log1p(Math.exp(a - b))
}

interface Beam {
  blank: number
  symbol: number
  state: number
}

function total(beam: Beam): number {
  return logaddexp(beam.blank, beam.symbol)
}

function decodeIndices(prefix: readonly number[]): string {
  return prefix
    .filter((c) => c !== BLANK)
    .map((c) => SYMBOLS[c - 1] ?? '')
    .join('')
}

/** Top grammar-valid prefixes with their summed alignment log-probabilities, best first. */
export function constrainedBeamSearch(
  logProbs: Float64Array,
  frames: number,
  classes: number,
  beamWidth = DEFAULT_BEAM,
  prune = DEFAULT_PRUNE,
): Hypothesis[] {
  const key = (prefix: readonly number[]) => prefix.join(',')
  let beams = new Map<string, { prefix: number[]; beam: Beam }>([
    [
      '',
      { prefix: [], beam: { blank: 0, symbol: Number.NEGATIVE_INFINITY, state: GRAMMAR.start } },
    ],
  ])
  for (let t = 0; t < frames; t += 1) {
    const row = (c: number) => logProbs[t * classes + c] as number
    const candidates: number[] = []
    for (let c = 1; c < classes; c += 1) if (row(c) > prune) candidates.push(c)
    const next = new Map<string, { prefix: number[]; beam: Beam }>()
    const slot = (prefix: number[], state: number): Beam => {
      const k = key(prefix)
      let entry = next.get(k)
      if (!entry) {
        entry = {
          prefix,
          beam: { blank: Number.NEGATIVE_INFINITY, symbol: Number.NEGATIVE_INFINITY, state },
        }
        next.set(k, entry)
      }
      return entry.beam
    }
    for (const { prefix, beam } of beams.values()) {
      const all = total(beam)
      const stay = slot(prefix, beam.state)
      stay.blank = logaddexp(stay.blank, all + row(BLANK))
      const last = prefix.length > 0 ? (prefix[prefix.length - 1] as number) : null
      if (last !== null) stay.symbol = logaddexp(stay.symbol, beam.symbol + row(last))
      for (const c of candidates) {
        const state = step(beam.state, c - 1)
        if (state === DEAD) continue
        const extended = slot([...prefix, c], state)
        const source = c === last ? beam.blank : all
        extended.symbol = logaddexp(extended.symbol, source + row(c))
      }
    }
    // A stable sort keeps insertion order among equal totals, as Python's sorted does.
    const ranked = [...next.entries()].sort((a, b) => total(b[1].beam) - total(a[1].beam))
    beams = new Map(ranked.slice(0, beamWidth))
  }
  const results: Hypothesis[] = []
  for (const { prefix, beam } of beams.values()) {
    if (prefix.length === 0 || !isAccepting(beam.state)) continue
    results.push({ tokens: decodeIndices(prefix), logp: total(beam) })
  }
  results.sort(
    (a, b) => b.logp - a.logp || (a.tokens < b.tokens ? -1 : a.tokens > b.tokens ? 1 : 0),
  )
  return results
}

/** The beam renormalised over its strings, best first (calibrate.posterior). */
export function posterior(hypotheses: readonly Hypothesis[]): [string, number][] {
  if (hypotheses.length === 0) return []
  const top = Math.max(...hypotheses.map((h) => h.logp))
  const weights = hypotheses.map((h) => Math.exp(h.logp - top))
  let sum = 0
  for (const w of weights) sum += w // Python's built-in sum: left to right
  return hypotheses.map((h, i) => [h.tokens, (weights[i] as number) / sum])
}

/** Nonconformity of every beam string: the summed posterior of the others. */
export function scoresOf(hypotheses: readonly Hypothesis[]): [string, number][] {
  const dist = posterior(hypotheses)
  return dist.map(([tokens], i) => [tokens, fsum(dist.filter((_, j) => j !== i).map(([, p]) => p))])
}

/** The conformal set at `threshold` (every string when the threshold reaches 1). */
export function predictionSet(hypotheses: readonly Hypothesis[], threshold: number): string[] {
  if (threshold >= 1) return hypotheses.map((h) => h.tokens)
  return scoresOf(hypotheses)
    .filter(([, score]) => score <= threshold)
    .map(([tokens]) => tokens)
}
