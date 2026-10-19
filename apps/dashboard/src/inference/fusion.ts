/**
 * Probabilistic multi-view fusion, ported from plate_reader/fusion.py and
 * plate_reader/strings.py: renormalise each view over the candidates with a floor, add
 * weighted log-probabilities, normalise; per-position posteriors from a minimum-cost
 * alignment to the winner. Sums go through `fsum`, as `math.fsum` does in Python, so the
 * result does not depend on the order of the views.
 */
import { fsum } from './fsum'
import { accepts } from './grammar'
import type { Hypothesis } from './decode'

export const FLOOR = 1e-6
export const GAP = '∅'

export interface ViewReading {
  hypotheses: Hypothesis[]
}

export interface PositionPosterior {
  index: number
  symbol: string
  distribution: [string, number][]
}

export interface Fused {
  prediction: string | null
  confidence: number
  posterior: [string, number][]
  positions: PositionPosterior[]
  agreeingViews: number
  predictionSet: string[] | null
}

/** Code-point order, as Python compares strings. */
export function compare(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0
}

type Column = [number | null, number | null]

function table(a: string[], b: string[]): number[][] {
  const rows = a.length + 1
  const cols = b.length + 1
  const out = Array.from({ length: rows }, () => new Array<number>(cols).fill(0))
  for (let i = 0; i < rows; i += 1) (out[i] as number[])[0] = i
  for (let j = 0; j < cols; j += 1) (out[0] as number[])[j] = j
  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      const row = out[i] as number[]
      const above = out[i - 1] as number[]
      row[j] = Math.min(
        (above[j] as number) + 1,
        (row[j - 1] as number) + 1,
        (above[j - 1] as number) + cost,
      )
    }
  }
  return out
}

/** A minimum-cost alignment; ties prefer substitution, then deletion, then insertion. */
export function align(a: string, b: string): Column[] {
  const sa = [...a]
  const sb = [...b]
  const t = table(sa, sb)
  let i = sa.length
  let j = sb.length
  const columns: Column[] = []
  const at = (r: number, c: number) => (t[r] as number[])[c] as number
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0) {
      const cost = sa[i - 1] === sb[j - 1] ? 0 : 1
      if (at(i, j) === at(i - 1, j - 1) + cost) {
        columns.push([i - 1, j - 1])
        i -= 1
        j -= 1
        continue
      }
    }
    if (i > 0 && at(i, j) === at(i - 1, j) + 1) {
      columns.push([i - 1, null])
      i -= 1
    } else {
      columns.push([null, j - 1])
      j -= 1
    }
  }
  return columns.reverse()
}

function viewDistribution(view: ViewReading): Map<string, number> {
  const dist = new Map<string, number>()
  for (const h of view.hypotheses) {
    if (accepts(h.tokens)) dist.set(h.tokens, (dist.get(h.tokens) ?? 0) + Math.exp(h.logp))
  }
  return dist
}

export function fusedPredictionSet(
  posterior: [string, number][],
  threshold: number | null,
): string[] | null {
  if (threshold === null) return null
  if (threshold >= 1) return posterior.map(([s]) => s)
  const members: string[] = []
  posterior.forEach(([tokens], i) => {
    const others = fsum(posterior.filter((_, j) => j !== i).map(([, p]) => p))
    if (others <= threshold) members.push(tokens)
  })
  return members
}

export function perPositionPosterior(
  winner: string,
  weights: number[],
  logTilde: Map<string, number>[],
): PositionPosterior[] {
  const symbols = [...winner]
  const votes = symbols.map(() => new Map<string, number[]>())
  logTilde.forEach((lt, v) => {
    const weight = weights[v] as number
    for (const [tokens, logp] of lt) {
      const mass = weight * Math.exp(logp)
      if (mass <= 0) continue
      const chars = [...tokens]
      for (const [i, j] of align(winner, tokens)) {
        if (i === null) continue
        const symbol = j !== null ? (chars[j] as string) : GAP
        const bucket = votes[i] as Map<string, number[]>
        const list = bucket.get(symbol)
        if (list) list.push(mass)
        else bucket.set(symbol, [mass])
      }
    }
  })
  return symbols.map((symbol, index) => {
    const totals = [...(votes[index] as Map<string, number[]>).entries()].map(
      ([s, m]) => [s, fsum(m)] as [string, number],
    )
    const z = fsum(totals.map(([, v]) => v))
    const distribution: [string, number][] =
      z > 0
        ? totals
            .map(([s, v]) => [s, v / z] as [string, number])
            .sort((x, y) => y[1] - x[1] || compare(x[0], y[0]))
        : [[symbol, 1]]
    return { index, symbol, distribution }
  })
}

export function probabilisticFusion(
  views: ViewReading[],
  weights: number[] | null = null,
  threshold: number | null = null,
  floor = FLOOR,
): Fused {
  const w = weights ?? views.map(() => 1)
  const dists = views.map(viewDistribution)
  const candidates = [...new Set(dists.flatMap((d) => [...d.keys()]))].sort(compare)
  if (candidates.length === 0) {
    return {
      prediction: null,
      confidence: 0,
      posterior: [],
      positions: [],
      agreeingViews: 0,
      predictionSet: null,
    }
  }
  const logTilde = dists.map((dist) => {
    const out = new Map<string, number>()
    if (dist.size === 0) return out // a view with no hypothesis abstains
    const raw = candidates.map((s) => [s, Math.max(dist.get(s) ?? 0, floor)] as [string, number])
    const logZ = Math.log(fsum(raw.map(([, p]) => p)))
    for (const [s, p] of raw) out.set(s, Math.log(p) - logZ)
    return out
  })
  const scores = candidates.map(
    (s) =>
      [
        s,
        fsum(
          logTilde.flatMap((lt, v) =>
            lt.size > 0 ? [(w[v] as number) * (lt.get(s) as number)] : [],
          ),
        ),
      ] as [string, number],
  )
  const top = Math.max(...scores.map(([, v]) => v))
  const unnorm = scores.map(([s, v]) => [s, Math.exp(v - top)] as [string, number])
  const z = fsum(unnorm.map(([, p]) => p))
  const posterior = unnorm
    .map(([s, p]) => [s, p / z] as [string, number])
    .sort((a, b) => b[1] - a[1] || compare(a[0], b[0]))
  const [winner, confidence] = posterior[0] as [string, number]
  const positions = perPositionPosterior(winner, w, logTilde)
  let agreeing = 0
  for (const d of dists) {
    if (d.size === 0) continue
    let best: string | null = null
    let bestP = -1
    for (const [s, p] of d) {
      if (p > bestP || (p === bestP && best !== null && compare(s, best) > 0)) {
        best = s
        bestP = p
      }
    }
    if (best === winner) agreeing += 1
  }
  return {
    prediction: winner,
    confidence,
    posterior,
    positions,
    agreeingViews: agreeing,
    predictionSet: fusedPredictionSet(posterior, threshold),
  }
}
