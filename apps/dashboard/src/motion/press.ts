/**
 * `v-press`: the element presses the instant it is touched, not on release (scale 0.98 in
 * 100 ms, ease-out), and springs back when the pointer lifts, leaves or is cancelled. It
 * never blocks input: the click still fires on release, and a new press interrupts the
 * spring back from wherever it is. Under reduced motion the press is a slight dim instead.
 */
import { animate } from 'motion'
import type { Directive } from 'vue'

import { reducedMotion, SPRING } from './springs'

const PRESS_SCALE = 0.98
const RELEASES = ['pointerup', 'pointerleave', 'pointercancel', 'blur'] as const

interface Bound {
  down: (event: PointerEvent) => void
  up: () => void
}

const bound = new WeakMap<HTMLElement, Bound>()

function inactive(element: HTMLElement): boolean {
  return element.hasAttribute('disabled') || element.getAttribute('aria-disabled') === 'true'
}

export const vPress: Directive<HTMLElement, boolean | undefined> = {
  mounted(element, binding) {
    if (binding.value === false) return
    let pressed = false
    const down = (event: PointerEvent) => {
      if (event.button !== 0 || inactive(element)) return
      pressed = true
      if (reducedMotion()) animate(element, { opacity: 0.72 }, { duration: 0.1, ease: 'easeOut' })
      else animate(element, { scale: PRESS_SCALE }, { duration: 0.1, ease: 'easeOut' })
    }
    const up = () => {
      if (!pressed) return
      pressed = false
      if (reducedMotion()) animate(element, { opacity: 1 }, { duration: 0.2, ease: 'linear' })
      else animate(element, { scale: 1 }, SPRING)
    }
    element.addEventListener('pointerdown', down)
    for (const name of RELEASES) element.addEventListener(name, up)
    bound.set(element, { down, up })
  },
  beforeUnmount(element) {
    const handlers = bound.get(element)
    if (!handlers) return
    element.removeEventListener('pointerdown', handlers.down)
    for (const name of RELEASES) element.removeEventListener(name, handlers.up)
    bound.delete(element)
  },
}
