import { describe, expect, it } from 'vitest'

import {
  bandedOffset,
  moveItem,
  nearestSlot,
  project,
  rubberband,
  slotAfterMove,
  VelocityTracker,
} from '../gesture'
import { springEase } from '../springs'

describe('direct manipulation', () => {
  it('measures release velocity over the last few samples and none after a pause', () => {
    const tracker = new VelocityTracker(80)
    for (let t = 0; t <= 100; t += 10) tracker.add(t, t * 2, -t)
    const v = tracker.velocity(100)
    expect(v.x).toBeCloseTo(2000)
    expect(v.y).toBeCloseTo(-1000)
    expect(tracker.velocity(300)).toEqual({ x: 0, y: 0 })
    tracker.reset()
    expect(tracker.velocity()).toEqual({ x: 0, y: 0 })
  })

  it('rubber-bands: follows less the further past the edge, never more than the overshoot', () => {
    const near = rubberband(10, 200)
    const far = rubberband(100, 200)
    expect(near).toBeGreaterThan(0)
    expect(near).toBeLessThan(10)
    expect(far).toBeLessThan(100)
    expect(far / 100).toBeLessThan(near / 10)
    expect(rubberband(-10, 200)).toBeCloseTo(-near)
    expect(rubberband(10, 0)).toBe(0)
  })

  it('keeps a drag 1:1 inside the zone and resists outside it', () => {
    const rect = { left: 100, top: 100, width: 50, height: 50 }
    const zone = { left: 0, top: 0, width: 400, height: 300 }
    expect(bandedOffset(rect, { x: 30, y: -40 }, zone)).toEqual({ x: 30, y: -40 })
    const past = bandedOffset(rect, { x: 300, y: 0 }, zone)
    // the right edge sits at 400: the item reaches it, then moves less than the pointer
    expect(past.x).toBeGreaterThan(250)
    expect(past.x).toBeLessThan(300)
  })

  it('projects a flick to where it would come to rest', () => {
    expect(project(0)).toBe(0)
    expect(project(1000)).toBeCloseTo(499)
    expect(project(-1000)).toBeCloseTo(-499)
  })

  it('finds the slot under the item and the order after the move', () => {
    const slots = [0, 1, 2].map((i) => ({ left: i * 100, top: 0, width: 90, height: 90 }))
    expect(nearestSlot(slots, { x: 230, y: 40 })).toBe(2)
    expect(nearestSlot(slots, { x: -50, y: 40 })).toBe(0)
    expect(moveItem(['a', 'b', 'c'], 0, 2)).toEqual(['b', 'c', 'a'])
    expect(moveItem(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b'])
    expect(moveItem(['a', 'b'], 1, 1)).toEqual(['a', 'b'])
    // during a drag from 0 to 2, the items in between shift one slot towards the gap
    expect([0, 1, 2].map((i) => slotAfterMove(i, 0, 2))).toEqual([2, 0, 1])
    expect([0, 1, 2].map((i) => slotAfterMove(i, 2, 0))).toEqual([1, 2, 0])
  })

  it('eases charts on a critically damped curve: no overshoot, lands on 1', () => {
    expect(springEase(0)).toBe(0)
    expect(springEase(1)).toBe(1)
    let last = 0
    for (let t = 0.05; t < 1; t += 0.05) {
      const value = springEase(t)
      expect(value).toBeGreaterThanOrEqual(last)
      expect(value).toBeLessThanOrEqual(1)
      last = value
    }
  })
})
