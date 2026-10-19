import { expect, test } from '@playwright/test'

import { display, expectAccessible, PARITY, SCENES } from './helpers'

// The browser runtime against the Python pipeline (ARCHITECTURE §13). These tests need no
// service: CI runs them against `vite preview`, and locally they also pass against Compose.

test('the browser runtime reproduces the Python pipeline on every fixture', async ({ page }) => {
  test.setTimeout(240_000)
  await page.goto('/parity')
  const summary = page.getByTestId('parity-summary')
  await expect(summary).toBeVisible({ timeout: 200_000 })
  const rows = page.getByTestId('parity-table').locator('tbody tr')
  const expected = PARITY.fixtures.length + PARITY.scenes.views.length + 1
  await expect(rows).toHaveCount(expected)
  await expect(page.locator('[data-testid="parity-table"] tr[data-ok="false"]')).toHaveCount(0)
  await expect(summary).toContainText(`passed: ${expected} of ${expected}`)
  await expect(page.getByTestId('parity-maxima')).toContainText('0 grey level(s)')
  await expectAccessible(page)
})

test('in-browser mode reads the sample photos on the device', async ({ page }) => {
  test.setTimeout(240_000)
  const posted: string[] = []
  page.on('request', (request) => {
    if (request.method() === 'POST') posted.push(request.url())
  })
  await page.goto('/read')
  await page.getByRole('radio', { name: 'In this browser' }).click()
  await expect(page.getByTestId('parity-indicator')).toContainText('parity with Python', {
    timeout: 200_000,
  })
  await page.getByTestId('photo-input').setInputFiles(SCENES)
  await page.getByTestId('read-button').click()
  const result = page.getByTestId('read-result')
  const fused = PARITY.scenes.fused
  const [digits] = (fused.prediction ?? '').split('-')
  await expect(result.locator('[data-field="digits"]')).toHaveText(digits ?? '', {
    timeout: 120_000,
  })
  for (const plate of fused.prediction_set ?? []) {
    await expect(result.getByTestId('conformal-set')).toContainText(display(plate))
  }
  await expect(page.getByTestId('plate-box')).toHaveCount(SCENES.length)
  await expect(page.getByTestId('view-card')).toHaveCount(SCENES.length)
  await expect(page.getByTestId('character-heatmap').locator('.winner')).toHaveCount(
    fused.positions.filter((p) => p.symbol !== '-').length,
  )
  await expect(result).toContainText('read in this browser')
  expect(posted.filter((url) => url.includes('/api/read'))).toEqual([])
})
