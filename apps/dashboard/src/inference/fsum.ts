/**
 * Exactly rounded floating-point summation: a port of CPython's `math.fsum` (Shewchuk's
 * algorithm with CPython's half-even correction), so that fusion in the browser adds
 * probabilities exactly as the Python pipeline does, in any order.
 */
export function fsum(values: Iterable<number>): number {
  const partials: number[] = []
  let special = 0
  let infinite = 0
  for (const value of values) {
    let x = value
    if (!Number.isFinite(x)) {
      if (Number.isNaN(x)) return Number.NaN
      infinite += x
      special = 1
      continue
    }
    let i = 0
    for (let j = 0; j < partials.length; j += 1) {
      let y = partials[j] as number
      if (Math.abs(x) < Math.abs(y)) {
        const t = x
        x = y
        y = t
      }
      const hi = x + y
      const lo = y - (hi - x)
      if (lo !== 0) {
        partials[i] = lo
        i += 1
      }
      x = hi
    }
    partials.length = i
    if (x !== 0) {
      if (!Number.isFinite(x)) throw new RangeError('intermediate overflow in fsum')
      partials.push(x)
    }
  }
  if (special) return infinite
  let n = partials.length
  let hi = 0
  if (n > 0) {
    n -= 1
    hi = partials[n] as number
    let lo = 0
    while (n > 0) {
      const x = hi
      n -= 1
      const y = partials[n] as number
      hi = x + y
      const yr = hi - x
      lo = y - yr
      if (lo !== 0) break
    }
    // Make half-even rounding work across several partials (as CPython does).
    if (
      n > 0 &&
      ((lo < 0 && (partials[n - 1] as number) < 0) || (lo > 0 && (partials[n - 1] as number) > 0))
    ) {
      const y = lo * 2
      const x = hi + y
      const yr = x - hi
      if (y === yr) hi = x
    }
  }
  return hi
}
