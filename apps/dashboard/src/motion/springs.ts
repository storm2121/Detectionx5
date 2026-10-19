/**
 * Motion presets (docs/DESIGN.md §3). Everything a person can touch moves on a critically
 * damped spring that starts from the element's current on-screen value, so a transition can
 * be interrupted and redirected; bounce appears only after a drag release. When the reader
 * asks for reduced motion, springs and slides become a short opacity cross-fade.
 */
import {
  animate,
  type AnimationOptions,
  type DOMKeyframesDefinition,
  type ValueTransition,
} from 'motion'

/** The default spring: critically damped, about a third of a second. */
export const SPRING: ValueTransition = { type: 'spring', bounce: 0, duration: 0.35 }
/** After a flick or a drag release only. */
export const SPRING_RELEASE: ValueTransition = { type: 'spring', bounce: 0.2, duration: 0.35 }
/** The cross-fade that replaces springs and slides under reduced motion, in seconds. */
export const FADE_SECONDS = 0.2

export function reducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

export type Controls = ReturnType<typeof animate>

/**
 * Spring `element` to `keyframes`; under reduced motion, set them and cross-fade instead.
 * The returned controls let a caller stop the spring when a new gesture takes over.
 */
export function springTo(
  element: Element,
  keyframes: DOMKeyframesDefinition,
  options: AnimationOptions = SPRING,
): Controls {
  if (reducedMotion()) {
    animate(element, keyframes, { duration: 0 })
    return animate(element, { opacity: [0.4, 1] }, { duration: FADE_SECONDS, ease: 'linear' })
  }
  return animate(element, keyframes, options)
}

/** An entrance: rise a few pixels into place, or only fade in under reduced motion. */
export function enter(element: Element, distance = 6): Controls {
  if (reducedMotion()) {
    return animate(element, { opacity: [0, 1] }, { duration: FADE_SECONDS, ease: 'linear' })
  }
  return animate(element, { opacity: [0, 1], y: [distance, 0] }, SPRING)
}

/** The mirror of `enter`: leave the way it came. */
export function leave(element: Element, distance = 6): Controls {
  if (reducedMotion()) {
    return animate(element, { opacity: 0 }, { duration: FADE_SECONDS, ease: 'linear' })
  }
  return animate(element, { opacity: 0, y: distance }, SPRING)
}

/**
 * A critically damped spring as an easing curve on [0, 1], for D3 transitions on data joins.
 * x(t) = 1 - (1 + wt) e^(-wt), normalised so it lands exactly on 1.
 */
export function springEase(t: number, omega = 9): number {
  if (t <= 0) return 0
  if (t >= 1) return 1
  const end = 1 - (1 + omega) * Math.exp(-omega)
  return (1 - (1 + omega * t) * Math.exp(-omega * t)) / end
}

/** The duration of a chart transition, in ms: none under reduced motion. */
export function chartDuration(ms = 450): number {
  return reducedMotion() ? 0 : ms
}
