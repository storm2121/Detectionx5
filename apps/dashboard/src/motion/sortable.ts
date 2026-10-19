/**
 * Reordering a grid by direct manipulation (docs/DESIGN.md §3). The dragged item tracks the
 * pointer 1:1 from where it was grabbed, rubber-bands past the edges of its zone, and on
 * release a spring carrying the pointer's velocity settles it into its slot; the items it
 * passes slide aside on critically damped springs that start from wherever they are. Touch
 * picks an item up after a short press, so a swipe still scrolls the page. Every move goes
 * through `animate`, so each animation starts from the element's current on-screen value.
 */
import { animate } from 'motion'

import {
  bandedOffset,
  nearestSlot,
  type Point,
  type Rect,
  slotAfterMove,
  VelocityTracker,
} from './gesture'
import { FADE_SECONDS, reducedMotion, SPRING, SPRING_RELEASE } from './springs'

const MOUSE_SLOP = 4
const TOUCH_SLOP = 8
const LONG_PRESS_MS = 260
const LIFT_SCALE = 1.04

export interface SortableOptions {
  /** The zone the items move in (its edges rubber-band). */
  zone: () => HTMLElement | null
  /** The item elements, in their current order. */
  items: () => HTMLElement[]
  /** Commit a move; resolves once the new order is in the document. */
  move: (from: number, to: number) => Promise<void>
  /** Told when a drag starts, moves over a new slot, ends or is cancelled. */
  announce?: (event: 'lift' | 'over' | 'drop' | 'cancel', from: number, to: number) => void
  onDragChange?: (index: number | null) => void
}

interface Drag {
  pointerId: number
  index: number
  target: number
  start: Point
  slots: Rect[]
  zone: Rect
  started: boolean
  timer: number | undefined
  touch: boolean
  tracker: VelocityTracker
  element: HTMLElement
}

function rectOf(element: HTMLElement): Rect {
  const r = element.getBoundingClientRect()
  return { left: r.left, top: r.top, width: r.width, height: r.height }
}

/** The centre an element is painted at (unchanged by a scale about its centre). */
function centreOf(element: HTMLElement): Point {
  const r = element.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
}

/** The element's current translation, read from the transform it is painted with. */
function translation(element: HTMLElement): Point {
  const transform = getComputedStyle(element).transform
  if (!transform || transform === 'none' || typeof DOMMatrixReadOnly !== 'function') {
    return { x: 0, y: 0 }
  }
  const matrix = new DOMMatrixReadOnly(transform)
  return { x: matrix.m41, y: matrix.m42 }
}

/**
 * Where an item sits at rest, in viewport coordinates: its layout box inside the zone, which
 * no transform (a slide still settling, the lift) changes. The zone is the offset parent.
 */
function restRect(element: HTMLElement, zone: HTMLElement | null): Rect {
  if (!zone) return rectOf(element)
  const z = zone.getBoundingClientRect()
  return {
    left: z.left + zone.clientLeft + element.offsetLeft,
    top: z.top + zone.clientTop + element.offsetTop,
    width: element.offsetWidth,
    height: element.offsetHeight,
  }
}

function setNow(element: HTMLElement, values: { x?: number; y?: number; scale?: number }) {
  animate(element, values, { duration: 0 })
  // Motion paints on its next frame; write the transform now so no frame shows a stale one.
  const t = translation(element)
  const x = values.x ?? t.x
  const y = values.y ?? t.y
  const scale = values.scale ?? 1
  element.style.transform = `translateX(${x}px) translateY(${y}px) scale(${scale})`
}

export function createSortable(options: SortableOptions) {
  let drag: Drag | null = null

  function slideSiblings(from: number, to: number) {
    const items = options.items()
    const zone = options.zone()
    const slots = drag?.slots ?? items.map((element) => restRect(element, zone))
    items.forEach((element, index) => {
      if (index === from) return
      const slot = slots[slotAfterMove(index, from, to)]
      const own = slots[index]
      if (!slot || !own) return
      const x = slot.left - own.left
      const y = slot.top - own.top
      if (reducedMotion()) setNow(element, { x, y })
      else animate(element, { x, y }, SPRING)
    })
  }

  function begin(state: Drag) {
    state.started = true
    const zone = options.zone()
    state.slots = options.items().map((element) => restRect(element, zone))
    state.zone = zone ? rectOf(zone) : (state.slots[state.index] ?? state.zone)
    try {
      state.element.setPointerCapture(state.pointerId)
    } catch {
      // the pointer is already gone; the drag ends on its own
    }
    if (!reducedMotion()) animate(state.element, { scale: LIFT_SCALE }, SPRING)
    options.onDragChange?.(state.index)
    options.announce?.('lift', state.index, state.index)
  }

  function onPointerDown(event: PointerEvent, index: number) {
    if (drag || event.button !== 0) return
    const target = event.target as HTMLElement | null
    if (target?.closest('button, a, input, select, textarea')) return
    const element = event.currentTarget as HTMLElement
    const touch = event.pointerType === 'touch' || event.pointerType === 'pen'
    const state: Drag = {
      pointerId: event.pointerId,
      index,
      target: index,
      start: { x: event.clientX, y: event.clientY },
      slots: [],
      zone: rectOf(element),
      started: false,
      timer: undefined,
      touch,
      tracker: new VelocityTracker(),
      element,
    }
    state.tracker.add(event.timeStamp, event.clientX, event.clientY)
    drag = state
    if (touch) {
      state.timer = window.setTimeout(() => {
        if (drag === state && !state.started) begin(state)
      }, LONG_PRESS_MS)
    }
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', onPointerCancel)
    window.addEventListener('keydown', onKeyDuringDrag)
  }

  function onPointerMove(event: PointerEvent) {
    const state = drag
    if (!state || event.pointerId !== state.pointerId) return
    const raw = { x: event.clientX - state.start.x, y: event.clientY - state.start.y }
    if (!state.started) {
      const distance = Math.hypot(raw.x, raw.y)
      if (state.touch) {
        // moved before the press became a pick-up: it is a scroll, leave it to the page
        if (distance > TOUCH_SLOP) end()
        return
      }
      if (distance < MOUSE_SLOP) return
      begin(state)
    }
    event.preventDefault()
    state.tracker.add(event.timeStamp, event.clientX, event.clientY)
    const rest = state.slots[state.index]
    if (!rest) return
    const offset = bandedOffset(rest, raw, state.zone)
    setNow(state.element, {
      x: offset.x,
      y: offset.y,
      scale: reducedMotion() ? 1 : LIFT_SCALE,
    })
    const centre = {
      x: rest.left + rest.width / 2 + raw.x,
      y: rest.top + rest.height / 2 + raw.y,
    }
    const next = nearestSlot(state.slots, centre)
    if (next !== state.target) {
      state.target = next
      slideSiblings(state.index, next)
      options.announce?.('over', state.index, next)
    }
  }

  async function settle(velocity: Point, from: number, to: number) {
    const items = options.items()
    // where everything is painted now, before the new order reaches the document
    const before = new Map(items.map((element) => [element, centreOf(element)]))
    const dragged = items[from]
    await options.move(from, to)
    const after = options.items()
    after.forEach((element) => setNow(element, { x: 0, y: 0, scale: 1 }))
    after.forEach((element) => {
      const was = before.get(element)
      if (!was) return
      const now = centreOf(element)
      const x = was.x - now.x
      const y = was.y - now.y
      const isDragged = element === dragged
      setNow(element, { x, y, scale: isDragged && !reducedMotion() ? LIFT_SCALE : 1 })
      if (reducedMotion()) {
        setNow(element, { x: 0, y: 0, scale: 1 })
        if (isDragged) animate(element, { opacity: [0.4, 1] }, { duration: FADE_SECONDS })
        return
      }
      if (isDragged) {
        animate(
          element,
          { x: 0, y: 0, scale: 1 },
          {
            x: { ...SPRING_RELEASE, velocity: velocity.x },
            y: { ...SPRING_RELEASE, velocity: velocity.y },
            scale: SPRING,
          },
        )
      } else if (x !== 0 || y !== 0) {
        animate(element, { x: 0, y: 0 }, SPRING)
      }
    })
  }

  function onPointerUp(event: PointerEvent) {
    const state = drag
    if (!state || event.pointerId !== state.pointerId) return
    if (!state.started) {
      end()
      return
    }
    const velocity = state.tracker.velocity(event.timeStamp)
    const { index, target } = state
    end()
    options.announce?.('drop', index, target)
    void settle(velocity, index, target)
  }

  function cancel() {
    const state = drag
    if (!state) return
    const started = state.started
    const index = state.index
    end()
    if (!started) return
    for (const element of options.items()) {
      if (reducedMotion()) setNow(element, { x: 0, y: 0, scale: 1 })
      else animate(element, { x: 0, y: 0, scale: 1 }, SPRING)
    }
    options.announce?.('cancel', index, index)
  }

  function onPointerCancel(event: PointerEvent) {
    if (drag && event.pointerId === drag.pointerId) cancel()
  }

  function onKeyDuringDrag(event: KeyboardEvent) {
    if (event.key === 'Escape' && drag?.started) {
      event.preventDefault()
      cancel()
    }
  }

  function end() {
    if (drag?.timer !== undefined) window.clearTimeout(drag.timer)
    try {
      if (drag?.started) drag.element.releasePointerCapture(drag.pointerId)
    } catch {
      // capture already released
    }
    drag = null
    options.onDragChange?.(null)
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', onPointerUp)
    window.removeEventListener('pointercancel', onPointerCancel)
    window.removeEventListener('keydown', onKeyDuringDrag)
  }

  /** Keep a touch drag from scrolling the page once the item is picked up. */
  function onTouchMove(event: TouchEvent) {
    if (drag?.started) event.preventDefault()
  }

  /** The keyboard's move: the same springs, without a pointer to follow. */
  async function moveBy(from: number, to: number) {
    const count = options.items().length
    const target = Math.max(0, Math.min(count - 1, to))
    if (target === from) return
    await settle({ x: 0, y: 0 }, from, target)
  }

  function dispose() {
    end()
  }

  return { onPointerDown, onTouchMove, moveBy, dispose, isDragging: () => Boolean(drag?.started) }
}
