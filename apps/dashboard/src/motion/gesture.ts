/**
 * The arithmetic of direct manipulation, kept free of the DOM so it can be tested: a short
 * pointer history for release velocity, rubber-banding past a boundary, momentum
 * projection, and which slot of a grid a dragged item belongs in.
 */

export interface Point {
  x: number
  y: number
}

export interface Rect {
  left: number
  top: number
  width: number
  height: number
}

/**
 * Velocity from the last few pointer samples, in px/s. A single last pair of events is
 * noisy, and samples older than the window describe a motion the finger has already left.
 */
export class VelocityTracker {
  private samples: { t: number; x: number; y: number }[] = []

  constructor(private readonly windowMs = 80) {}

  add(t: number, x: number, y: number): void {
    this.samples.push({ t, x, y })
    const cutoff = t - this.windowMs * 2
    while (this.samples.length > 2 && (this.samples[0]?.t ?? t) < cutoff) this.samples.shift()
  }

  reset(): void {
    this.samples = []
  }

  velocity(now?: number): Point {
    const last = this.samples[this.samples.length - 1]
    if (!last) return { x: 0, y: 0 }
    const end = now ?? last.t
    // a finger that stopped before lifting carries no velocity into the release
    if (end - last.t > this.windowMs) return { x: 0, y: 0 }
    const start = this.samples.find((s) => s.t >= last.t - this.windowMs) ?? last
    const dt = (last.t - start.t) / 1000
    if (dt <= 0) return { x: 0, y: 0 }
    return { x: (last.x - start.x) / dt, y: (last.y - start.y) / dt }
  }
}

/**
 * The rubber-band of iOS scroll views: the further past the edge, the less the element
 * follows. `overshoot` is the distance past the boundary, `dimension` the element's size.
 */
export function rubberband(overshoot: number, dimension: number, constant = 0.55): number {
  if (dimension <= 0) return 0
  const sign = Math.sign(overshoot)
  const d = Math.abs(overshoot)
  return (sign * (d * dimension * constant)) / (dimension + constant * d)
}

/**
 * The offset of a dragged rectangle, rubber-banded where it would leave `bounds`. `rect` is
 * where the item sits at rest and `offset` the raw pointer travel since the grab.
 */
export function bandedOffset(rect: Rect, offset: Point, bounds: Rect): Point {
  const axis = (start: number, size: number, delta: number, lo: number, hi: number) => {
    const from = start + delta
    const to = from + size
    if (size >= hi - lo) return delta
    if (from < lo) return delta + (lo - from) + rubberband(from - lo, size)
    if (to > hi) return delta - (to - hi) + rubberband(to - hi, size)
    return delta
  }
  return {
    x: axis(rect.left, rect.width, offset.x, bounds.left, bounds.left + bounds.width),
    y: axis(rect.top, rect.height, offset.y, bounds.top, bounds.top + bounds.height),
  }
}

/** Where a flick comes to rest, in px from the release point (exponential deceleration). */
export function project(velocity: number, decelerationRate = 0.998): number {
  return ((velocity / 1000) * decelerationRate) / (1 - decelerationRate)
}

/** The index of the slot whose centre is nearest `point`. */
export function nearestSlot(slots: readonly Rect[], point: Point): number {
  let best = 0
  let bestDistance = Number.POSITIVE_INFINITY
  slots.forEach((slot, index) => {
    const cx = slot.left + slot.width / 2
    const cy = slot.top + slot.height / 2
    const d = (cx - point.x) ** 2 + (cy - point.y) ** 2
    if (d < bestDistance) {
      best = index
      bestDistance = d
    }
  })
  return best
}

/** `items` with the element at `from` moved to `to`. */
export function moveItem<T>(items: readonly T[], from: number, to: number): T[] {
  const next = [...items]
  if (from === to || from < 0 || from >= next.length) return next
  const [item] = next.splice(from, 1)
  next.splice(Math.max(0, Math.min(next.length, to)), 0, item as T)
  return next
}

/**
 * During a drag from `from` to `to`, the slot the item now in slot `index` should show in:
 * the dragged item takes `to`, and the ones in between shift by one into the gap it left.
 */
export function slotAfterMove(index: number, from: number, to: number): number {
  if (index === from) return to
  if (from < to && index > from && index <= to) return index - 1
  if (from > to && index >= to && index < from) return index + 1
  return index
}
