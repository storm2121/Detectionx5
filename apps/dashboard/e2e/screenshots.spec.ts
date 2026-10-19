import { join } from 'node:path'

import { expect, test } from '@playwright/test'

import { REPO, SCENES } from './helpers'

// The console's screenshots in docs/images: every page in both themes, at the width of each
// project (1440 px desktop, 390 px phone), the whole page in one image with the top bar at
// the top and the phone's tab bar at the bottom. Opt-in: `SCREENSHOTS=1 pnpm screenshots`.
test.skip(
  !process.env.SCREENSHOTS && process.env.npm_lifecycle_event !== 'screenshots',
  'run `pnpm screenshots` (or set SCREENSHOTS=1) to write docs/images',
)
test.use({ deviceScaleFactor: 1 })

const PAGES = ['read', 'review', 'jobs', 'evaluation', 'models', 'methods', 'parity'] as const
const OUT = join(REPO, 'docs', 'images')

/** One uncertain read for the review queue: a street photo read as if it were a plate crop. */
async function queueOne(page: import('@playwright/test').Page) {
  await page.goto('/read')
  await page.getByTestId('photo-input').setInputFiles(SCENES[1] ?? '')
  await page.getByRole('switch', { name: 'Find the plate in each photo' }).click()
  await page.getByTestId('read-button').click()
  await expect(page.getByTestId('read-result').getByTestId('status-pill')).toBeVisible()
}

for (const scheme of ['light', 'dark'] as const) {
  for (const name of PAGES) {
    test(`${name} (${scheme})`, async ({ page }, info) => {
      test.setTimeout(240_000)
      await page.emulateMedia({ colorScheme: scheme })
      if (name === 'review') await queueOne(page)
      await page.goto(`/${name}`)
      if (name === 'read') {
        await page.getByTestId('photo-input').setInputFiles(SCENES)
        await page.getByTestId('read-button').click()
        await expect(page.getByTestId('read-result').locator('[data-field="digits"]')).toBeVisible()
      }
      if (name === 'parity') {
        await expect(page.getByTestId('parity-summary')).toBeVisible({ timeout: 200_000 })
      }
      await page.waitForLoadState('networkidle')
      // main keeps a viewport-high minimum so a short page's footer sits low on a normal screen;
      // a capture sized to the whole page would chase that minimum, so it is dropped here only
      await page.addStyleTag({ content: 'main { min-height: 0 !important; }' })
      await page.evaluate(() => window.scrollTo(0, 0))
      const width = page.viewportSize()?.width ?? 1440
      const height = await page.evaluate(() => document.documentElement.scrollHeight)
      await page.setViewportSize({ width, height: Math.min(height, 9000) })
      // let springs and entrances settle after the resize
      await page.waitForTimeout(900)
      const file = `console-${name}-${scheme}-${width}.png`
      await page.screenshot({ path: join(OUT, file) })
      info.annotations.push({ type: 'screenshot', description: file })
    })
  }
}
