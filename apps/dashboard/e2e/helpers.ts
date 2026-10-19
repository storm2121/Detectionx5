import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'

const here = dirname(fileURLToPath(import.meta.url))
export const REPO = resolve(here, '..', '..', '..')

interface SceneFixtures {
  truth: string
  views: { image: string; crop_box: number[]; prediction: string | null }[]
  fused: {
    prediction: string | null
    prediction_set: string[] | null
    positions: { symbol: string }[]
  }
}

/** What the Python pipeline made of the synthetic scenes (results/parity_fixtures.json). */
export const PARITY = JSON.parse(
  readFileSync(join(REPO, 'results', 'parity_fixtures.json'), 'utf-8'),
) as { model_version: string; fixtures: { image: string }[]; scenes: SceneFixtures }

export const SCENES = PARITY.scenes.views.map((view) => join(REPO, view.image))

/** The display spelling of a token string (`72173-WW` reads `72173 WW`). */
export function display(tokens: string): string {
  return tokens.endsWith('-WW') ? `${tokens.slice(0, -3)} WW` : tokens
}

/** No WCAG 2.1 A or AA violation on the current page. */
export async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()
  const found = results.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`,
  )
  expect(found).toEqual([])
}

/** The page fits the viewport: no horizontal scrolling. */
export async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
}
