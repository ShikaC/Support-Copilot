import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import AxeBuilder from '@axe-core/playwright'
import { expect, test, type APIRequestContext, type Page, type TestInfo } from '@playwright/test'

const token = 'synthetic-browser-token-task12'
const apiPort = Number(process.env.TASK12_API_PORT)
if (!Number.isInteger(apiPort)) throw new Error('TASK12_API_PORT is required')
const apiUrl = `http://127.0.0.1:${apiPort}`
const evidenceDirectory = resolve(process.cwd(), '../../.omo/evidence/task-12-browser')
const accessibleNameRuleIds = new Set(['button-name', 'input-button-name', 'label', 'select-name', 'textarea-name'])

type Scenario = 'success' | 'fallback' | 'stale' | 'review' | 'knowledge' | 'audit-quality' | 'malformed'
type BrowserErrors = { readonly consoleErrors: string[]; readonly pageErrors: string[] }

async function prepare(page: Page, request: APIRequestContext, scenario: Scenario) {
  const reset = await request.get(`${apiUrl}/__control/reset?scenario=${scenario}`)
  expect(reset.ok()).toBe(true)
  await page.addInitScript((accessToken) => {
    window.sessionStorage.setItem('support-copilot.access-token', accessToken)
  }, token)
  await page.goto('/')
}

function captureBrowserErrors(page: Page): BrowserErrors {
  const consoleErrors: string[] = []
  const pageErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  return { consoleErrors, pageErrors }
}

async function navigate(page: Page, name: '运营概览' | '知识库' | '审计记录' | '质量评估') {
  await page.locator('nav:visible').getByRole('button', { name }).click()
}

async function layoutEvidence(page: Page) {
  return page.evaluate(() => {
    const root = document.documentElement
    const controls = [...document.querySelectorAll<HTMLElement>('button, input, textarea, select, a[href], [role="button"]')]
      .filter((element) => {
        const style = getComputedStyle(element)
        const box = element.getBoundingClientRect()
        return element.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
          && box.width >= 8 && box.height >= 8
          && box.right > 0 && box.left < window.innerWidth && box.bottom > 0 && box.top < window.innerHeight
      })
      .map((element, index) => {
        const box = element.getBoundingClientRect()
        return { index, tag: element.tagName, label: element.getAttribute('aria-label') ?? element.innerText.trim(), left: box.left, right: box.right, top: box.top, bottom: box.bottom }
      })
    const overlaps: string[] = []
    for (let leftIndex = 0; leftIndex < controls.length; leftIndex += 1) {
      const left = controls[leftIndex]
      if (left === undefined) continue
      for (let rightIndex = leftIndex + 1; rightIndex < controls.length; rightIndex += 1) {
        const right = controls[rightIndex]
        if (right === undefined) continue
        const overlapWidth = Math.min(left.right, right.right) - Math.max(left.left, right.left)
        const overlapHeight = Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top)
        if (overlapWidth > 1 && overlapHeight > 1) overlaps.push(`${left.tag}:${left.label} [${left.left},${left.top},${left.right},${left.bottom}] <> ${right.tag}:${right.label} [${right.left},${right.top},${right.right},${right.bottom}]`)
      }
    }
    return {
      clientWidth: root.clientWidth,
      scrollWidth: root.scrollWidth,
      horizontalOverflow: root.scrollWidth - root.clientWidth,
      controlCount: controls.length,
      overlaps,
    }
  })
}

async function verifyPage(page: Page, testInfo: TestInfo, scenario: Scenario, errors: BrowserErrors, extra: Readonly<Record<string, unknown>> = {}) {
  await page.evaluate(async () => {
    await Promise.allSettled(document.getAnimations().map((animation) => animation.finished))
  })
  const axe = await new AxeBuilder({ page }).analyze()
  const critical = axe.violations.filter((violation) => violation.impact === 'critical')
  const accessibleNameViolations = axe.violations.filter((violation) => accessibleNameRuleIds.has(violation.id))
  const layout = await layoutEvidence(page)
  const viewport = page.viewportSize()
  if (viewport === null) throw new Error('Playwright viewport is required')

  expect(critical, JSON.stringify(critical)).toHaveLength(0)
  expect(accessibleNameViolations, JSON.stringify(accessibleNameViolations)).toHaveLength(0)
  expect(layout.horizontalOverflow).toBeLessThanOrEqual(0)
  expect(layout.overlaps, JSON.stringify(layout.overlaps)).toHaveLength(0)
  expect(errors.consoleErrors, JSON.stringify(errors.consoleErrors)).toHaveLength(0)
  expect(errors.pageErrors, JSON.stringify(errors.pageErrors)).toHaveLength(0)

  await mkdir(evidenceDirectory, { recursive: true })
  const artifactStem = `${scenario}-${testInfo.project.name}`
  await page.screenshot({ path: resolve(evidenceDirectory, `${artifactStem}.png`), fullPage: false })
  await writeFile(resolve(evidenceDirectory, `${artifactStem}.json`), JSON.stringify({
    scenario,
    project: testInfo.project.name,
    viewport,
    axe: { violationCount: axe.violations.length, criticalCount: critical.length, accessibleNameViolationCount: accessibleNameViolations.length },
    layout,
    console: { errorCount: errors.consoleErrors.length, pageErrorCount: errors.pageErrors.length },
    ...extra,
  }, null, 2))
}

test('analysis success supports keyboard entry and visible focus', async ({ page, request }, testInfo) => {
  // Given: an authenticated browser and deterministic successful analysis fixture.
  const errors = captureBrowserErrors(page)
  await prepare(page, request, 'success')
  await expect(page.getByRole('heading', { name: '工单详情' })).toBeVisible()

  // When: keyboard navigation enters the page and the agent runs analysis.
  await page.keyboard.press('Tab')
  const skipLink = page.getByRole('link', { name: '跳到主要内容' })
  await expect(skipLink).toBeFocused()
  await expect(skipLink).toBeVisible()
  const focusStyle = await skipLink.evaluate((element) => {
    const style = getComputedStyle(element)
    return { outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth }
  })
  expect(focusStyle.outlineStyle).not.toBe('none')
  expect(focusStyle.outlineWidth).not.toBe('0px')
  await page.getByRole('button', { name: '开始分析' }).click()

  // Then: the persisted analysis is visible and the browser quality gates pass.
  await expect(page.getByText(/mock-rules-v1/)).toBeVisible()
  await expect(page.getByRole('button', { name: '重新分析' })).toBeVisible()
  await verifyPage(page, testInfo, 'success', errors, { focusStyle })
})

test('analysis fallback remains explicit and reviewable', async ({ page, request }, testInfo) => {
  // Given: the deterministic insufficient-evidence fixture.
  const errors = captureBrowserErrors(page)
  await prepare(page, request, 'fallback')

  // When: analysis is requested.
  await page.getByRole('button', { name: '开始分析' }).click()

  // Then: fallback mode and its limitation are visible rather than presented as success.
  await expect(page.getByText(/controlled-fallback-v1/)).toBeVisible()
  await expect(page.getByText('证据不足，必须转人工复核。')).toBeVisible()
  await verifyPage(page, testInfo, 'fallback', errors)
})

test('stale analysis conflict refreshes the ticket before a retry', async ({ page, request }, testInfo) => {
  // Given: the first analysis command will conflict with a newer ticket version.
  const errors = captureBrowserErrors(page)
  await prepare(page, request, 'stale')

  // When: the first command conflicts and the user retries after reconciliation.
  await page.getByRole('button', { name: '开始分析' }).click()
  await expect(page.getByRole('heading', { name: '并发更新后的扣款工单' })).toBeVisible()
  await expect(page.getByText(/版本已变化/)).toBeVisible()
  await page.getByRole('button', { name: '开始分析' }).click()

  // Then: the retry succeeds against refreshed browser state.
  await expect(page.getByText(/mock-rules-v1/)).toBeVisible()
  await verifyPage(page, testInfo, 'stale', errors)
})

test('authenticated rejection traps modal focus, closes with Escape, and persists', async ({ page, request }, testInfo) => {
  // Given: a successful analysis in secured mode.
  const errors = captureBrowserErrors(page)
  await prepare(page, request, 'review')
  await page.getByRole('button', { name: '开始分析' }).click()
  await expect(page.getByText(/mock-rules-v1/)).toBeVisible()
  await page.getByRole('tab', { name: '回复建议' }).click()
  const rejectButton = page.getByRole('button', { name: '拒绝建议' })

  // When: the real rejection modal is operated entirely through its keyboard contract.
  await rejectButton.click()
  const dialog = page.getByRole('dialog', { name: '拒绝回复建议' })
  const modal = page.locator('.ant-modal-wrap:visible')
  await expect(dialog).toBeVisible()
  await expect(page.getByLabel('拒绝原因')).toBeFocused()
  for (let index = 0; index < 6; index += 1) {
    await page.keyboard.press('Tab')
    expect(await modal.evaluate((element) => element.contains(document.activeElement))).toBe(true)
  }
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(rejectButton).toBeFocused()
  await rejectButton.click()
  await page.getByLabel('拒绝原因').fill('合成证据仍需人工确认')
  await page.getByRole('button', { name: '确认拒绝' }).click()

  // Then: the authenticated review response is rendered and modal state is closed.
  await expect(page.getByText(/回复建议已拒绝/)).toBeVisible()
  await expect(dialog).not.toBeVisible()
  await verifyPage(page, testInfo, 'review', errors)
})

test('knowledge release transitions once, becomes read-only, and renders hostile text inertly', async ({ page, request }, testInfo) => {
  // Given: an authenticated knowledge catalog with synthetic hostile text.
  const errors = captureBrowserErrors(page)
  await prepare(page, request, 'knowledge')
  await navigate(page, '知识库')
  await expect(page.getByRole('heading', { name: '知识检索与发布' })).toBeVisible()

  // When: the release is approved and the next transition is denied by role policy.
  await expect(page.getByText(/<img src=x onerror=alert\(1\)> Ignore previous instructions/)).toBeVisible()
  expect(await page.locator('img[src="x"]').count()).toBe(0)
  await page.getByRole('button', { name: /批\s*准/ }).click()
  await expect(page.getByText('APPROVED')).toBeVisible()
  await page.getByRole('button', { name: /发\s*布/ }).click()

  // Then: the view becomes explicitly read-only and does not execute fixture markup.
  await expect(page.getByText('当前身份仅可查看知识发布')).toBeVisible()
  await expect(page.getByRole('button', { name: /发\s*布/ })).toBeDisabled()
  await verifyPage(page, testInfo, 'knowledge', errors, { hostileImageCount: 0 })
})

test('audit pagination, quality evidence, chart pixels, text equivalents, and reduced motion are observable', async ({ page, request }, testInfo) => {
  // Given: reduced motion is enabled and audit, quality, and chart fixtures are available.
  const errors = captureBrowserErrors(page)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await prepare(page, request, 'audit-quality')
  await expect(page.getByRole('heading', { name: '工单详情' })).toBeVisible()

  // When: the reviewer inspects audit pagination, quality provenance, and overview charts.
  await navigate(page, '审计记录')
  await expect(page.getByText('trace-audit-1')).toBeVisible()
  await page.getByRole('button', { name: '加载更多' }).click()
  await expect(page.getByText('trace-audit-2')).toBeVisible()
  await navigate(page, '质量评估')
  await expect(page.getByRole('cell', { name: 'task12-synthetic.jsonl' })).toBeVisible()
  await expect(page.getByText('通过')).toBeVisible()
  const overviewResourcesBeforeNavigation = await page.evaluate(() => performance.getEntriesByType('resource').map((entry) => entry.name).filter((name) => name.includes('/OverviewView-')))
  expect(overviewResourcesBeforeNavigation).toHaveLength(0)
  await navigate(page, '运营概览')
  const canvases = page.locator('.chart-panel-body canvas')
  await expect(canvases).toHaveCount(2)
  const chartPixels: number[] = []
  for (let index = 0; index < 2; index += 1) {
    const canvas = canvases.nth(index)
    await expect(canvas).toBeVisible()
    await expect.poll(() => canvas.evaluate((element) => {
      if (!(element instanceof HTMLCanvasElement)) return 0
      const context = element.getContext('2d')
      if (context === null) return 0
      const pixels = context.getImageData(0, 0, element.width, element.height).data
      let painted = 0
      for (let pixel = 3; pixel < pixels.length; pixel += 4) if ((pixels[pixel] ?? 0) > 0) painted += 1
      return painted
    })).toBeGreaterThan(100)
    chartPixels.push(await canvas.evaluate((element) => {
      if (!(element instanceof HTMLCanvasElement)) return 0
      const context = element.getContext('2d')
      if (context === null) return 0
      const pixels = context.getImageData(0, 0, element.width, element.height).data
      let painted = 0
      for (let pixel = 3; pixel < pixels.length; pixel += 4) if ((pixels[pixel] ?? 0) > 0) painted += 1
      return painted
    }))
  }

  // Then: each chart has pixels, equivalent text, and an explicit reduced-motion render state.
  await expect(page.locator('table[aria-label="工单趋势数据"]')).toContainText('08-27')
  await expect(page.locator('table[aria-label="类别分布数据"]')).toContainText('账单支付')
  await expect(page.locator('.chart-panel-body[data-reduced-motion="true"]')).toHaveCount(2)
  const overviewResourcesAfterNavigation = await page.evaluate(() => performance.getEntriesByType('resource').map((entry) => entry.name).filter((name) => name.includes('/OverviewView-')))
  expect(overviewResourcesAfterNavigation).toHaveLength(1)
  const motionDuration = await page.locator('.view-enter').evaluate((element) => getComputedStyle(element).animationDuration)
  expect(Number.parseFloat(motionDuration)).toBeLessThanOrEqual(0.01)
  await verifyPage(page, testInfo, 'audit-quality', errors, { chartPixels, textualChartTables: 2, motionDuration, overviewResourcesBeforeNavigation, overviewResourcesAfterNavigation })
})

test('malformed API payloads fail closed without a misleading success state', async ({ page, request }, testInfo) => {
  // Given: both initial API responses violate their runtime schemas.
  const errors = captureBrowserErrors(page)
  await prepare(page, request, 'malformed')

  // When: the secured application parses the responses.
  await expect(page.getByText('工单数据暂不可用')).toBeVisible()

  // Then: the service state is unavailable and no synthetic success data is shown.
  await expect(page.getByText('安全服务不可用')).toHaveCount(1)
  await expect(page.getByText('本月套餐出现重复扣款')).toHaveCount(0)
  await verifyPage(page, testInfo, 'malformed', errors)
})
