import { expect, test } from '@playwright/test'

import { display, expectAccessible, expectNoHorizontalScroll, PARITY, SCENES } from './helpers'

const PAGES = [
  { path: '/read', heading: 'Read a plate' },
  { path: '/jobs', heading: 'Jobs' },
  { path: '/review', heading: 'Review queue' },
  { path: '/evaluation', heading: 'Evaluation' },
  { path: '/models', heading: 'Models' },
  { path: '/methods', heading: 'Methods' },
]

for (const { path, heading } of PAGES) {
  for (const scheme of ['light', 'dark'] as const) {
    test(`${heading}: loads, labels synthetic numbers, fits and passes axe (${scheme})`, async ({
      page,
    }) => {
      await page.emulateMedia({ colorScheme: scheme })
      await page.goto(path)
      await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('data-theme', scheme)
      await expect(page.getByTestId('service-health')).toHaveText('Service ready')
      await expect(
        page.getByText('synthetic results are not real-world accuracy', { exact: false }).first(),
      ).toBeVisible()
      await page.waitForLoadState('networkidle')
      await expectNoHorizontalScroll(page)
      await expectAccessible(page)
    })
  }
}

test('reads three synthetic photos of one car: boxes, fields, views, fusion, set, heatmap', async ({
  page,
}) => {
  const expected = PARITY.scenes.fused
  await page.goto('/read')
  await page.getByTestId('photo-input').setInputFiles(SCENES)
  await expect(page.getByTestId('photo-frame')).toHaveCount(SCENES.length)
  await page.getByTestId('read-button').click()

  const result = page.getByTestId('read-result')
  await expect(result.getByTestId('plate-fields')).toBeVisible()
  // The service runs the same models as the Python pipeline that wrote the fixtures.
  expect(expected.prediction).not.toBeNull()
  const [digits, letter, region] = (expected.prediction ?? '').split('-')
  await expect(result.locator('[data-field="digits"]')).toHaveText(digits ?? '')
  if (region !== 'WW') {
    await expect(result.locator('[data-field="letter"]')).toHaveText(letter ?? '')
    await expect(result.locator('[data-field="region"]')).toHaveText(region ?? '')
  }
  const set = result.getByTestId('conformal-set')
  for (const plate of expected.prediction_set ?? []) await expect(set).toContainText(display(plate))

  // One box per photo the detector found a plate in, drawn over the photo.
  const boxes = PARITY.scenes.views.filter((v) => v.crop_box.length === 4).length
  await expect(page.getByTestId('plate-box')).toHaveCount(boxes)
  await expect(page.getByTestId('view-card')).toHaveCount(SCENES.length)
  await expect(page.getByTestId('fusion-table').locator('tbody tr').first()).toContainText(
    display(expected.prediction ?? ''),
  )
  const characters = expected.positions.filter((p) => p.symbol !== '-').length
  await expect(page.getByTestId('character-heatmap').locator('.winner')).toHaveCount(characters)
  await expectNoHorizontalScroll(page)
  await expectAccessible(page)
})

test('a queued read is corrected in the review queue and exported', async ({ page }) => {
  // One synthetic street photo read as if it were a plate crop: the read is uncertain and
  // goes to review.
  await page.goto('/read')
  await page.getByTestId('photo-input').setInputFiles(SCENES[1] ?? '')
  await page.getByRole('switch', { name: 'Find the plate in each photo' }).click()
  await page.getByTestId('read-button').click()
  const result = page.getByTestId('read-result')
  await expect(result.getByTestId('status-pill')).toContainText('review')
  const link = result.locator('a[href^="/reads/"]').first()
  const href = (await link.getAttribute('href')) ?? ''
  const readId = href.split('/').pop() ?? ''
  expect(readId).not.toBe('')

  await page.goto('/review')
  const item = page.locator(`[data-testid="review-item"][data-read-id="${readId}"]`)
  await expect(item).toBeVisible()
  await item.getByTestId('correction-input').fill(PARITY.scenes.truth)
  await item.getByTestId('save-correction').click()
  await expect(item).toHaveCount(0)
  await expect(page.getByTestId('decided')).toContainText(display(PARITY.scenes.truth))
  await page.getByTestId('export-button').click()
  await expect(page.getByTestId('export-result')).toContainText('Exported')
  await expectAccessible(page)

  // The stored read now reports that it was reviewed.
  await page.goto(`/reads/${readId}`)
  await expect(page.getByTestId('read-result').getByTestId('status-pill')).toHaveText('Reviewed')
})

test('the jobs page reports what the service refuses', async ({ page }) => {
  await page.goto('/jobs')
  await page.getByLabel('Path under the jobs root').fill('no-such-folder')
  await page.getByTestId('queue-job').click()
  await expect(page.getByRole('alert')).toContainText('No such folder under the jobs root.')
})

test('evaluation switches sets and recognisers', async ({ page }) => {
  await page.goto('/evaluation')
  await expect(page.getByTestId('metric-table')).toContainText('Exact match')
  await page.getByRole('radio', { name: 'Pseudo-real set' }).click()
  await expect(page).toHaveURL(/set=eval_pseudo_real/)
  await expect(page.getByText('Pseudo-real set: n =', { exact: false })).toBeVisible()
  await page.getByTestId('recognizer-choice').selectOption('easyocr')
  await expect(page.getByTestId('calibration-curve').first()).toContainText('Accuracy')
  await expect(page.getByText('not a calibrated probability', { exact: false })).toBeVisible()
})

test('models and methods show the served model and typeset the equations', async ({ page }) => {
  await page.goto('/models')
  await expect(page.getByTestId('model-version')).toContainText(PARITY.model_version)
  await expect(page.getByTestId('registry-table')).toContainText('Active')
  await page.goto('/methods')
  await expect(page.locator('.katex').first()).toBeVisible()
  expect(await page.locator('[data-testid="math"]').count()).toBeGreaterThan(8)
})

test('photos reorder by dragging: the thumbnail follows the pointer and settles in its slot', async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, 'a touch drag starts with a long press; the mouse drag covers the logic')
  await page.goto('/read')
  await page.getByTestId('photo-input').setInputFiles(SCENES)
  const items = page.getByTestId('photos').locator('li')
  await expect(items).toHaveCount(SCENES.length)
  const names = async () => items.locator('.file').allTextContents()
  const before = await names()
  const first = await items.nth(0).boundingBox()
  const last = await items.nth(SCENES.length - 1).boundingBox()
  if (!first || !last) throw new Error('no layout')
  await page.mouse.move(first.x + first.width / 2, first.y + first.height / 3)
  await page.mouse.down()
  // 1:1 tracking: the lifted thumbnail moves with the pointer while it is held
  await page.mouse.move(first.x + first.width / 2 + 40, first.y + first.height / 3, { steps: 4 })
  const held = await items.nth(0).boundingBox()
  expect(Math.abs((held?.x ?? 0) - (first.x + 40))).toBeLessThan(6)
  await page.mouse.move(last.x + last.width / 2, last.y + last.height / 3, { steps: 12 })
  await page.mouse.up()
  await expect.poll(names).toEqual([...before.slice(1), before[0]])
  // the spring settles the thumbnail into its new slot
  await expect
    .poll(async () => {
      const box = await items.nth(SCENES.length - 1).boundingBox()
      return Math.abs((box?.x ?? 0) - last.x) < 1.5
    })
    .toBe(true)
  // and the keyboard moves it back
  await items.nth(SCENES.length - 1).focus()
  await page.keyboard.press('Home')
  await expect.poll(names).toEqual(before)
})

test('under reduced motion every page still works and passes axe', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/read')
  await page.getByTestId('photo-input').setInputFiles(SCENES)
  await page.getByTestId('read-button').click()
  await expect(page.getByTestId('read-result').getByTestId('plate-fields')).toBeVisible()
  await page.getByRole('button', { name: /Views and hypotheses/ }).click()
  await expect(page.getByTestId('view-card').first()).toBeVisible()
  await expectAccessible(page)
})
