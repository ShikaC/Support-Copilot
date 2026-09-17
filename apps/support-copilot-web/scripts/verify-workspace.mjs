import { chromium } from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const output = path.join(project, 'docs/enterprise-workspace/screenshots')
const baseUrl = process.env.SUPPORT_WORKSPACE_URL ?? 'http://127.0.0.1:18173'
if (!['127.0.0.1', 'localhost'].includes(new URL(baseUrl).hostname)) throw new Error('This synthetic-data verification is restricted to a local workspace.')
await fs.mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, reducedMotion: 'reduce' })
const page = await context.newPage()
const pageErrors = []
page.on('pageerror', (error) => pageErrors.push(error.message))
const results = []
try {
  await page.goto(baseUrl)
  await page.getByText('业务 API 已连接').waitFor()
  for (const [name, slug] of [['工单工作台','workbench'], ['运营概览','overview'], ['知识库','knowledge'], ['审计记录','audit'], ['质量评估','quality']]) {
    await page.locator('nav:visible').getByRole('button', { name, exact: true }).click()
    await page.locator('.data-loading').waitFor({ state: 'hidden' })
    await page.waitForTimeout(1200)
    for (const viewport of [{width:1600,height:1000},{width:1280,height:900},{width:768,height:1024},{width:375,height:812}]) {
      await page.setViewportSize(viewport)
      await page.waitForTimeout(250)
      await page.screenshot({ path: path.join(output, `${slug}-${viewport.width}.png`), fullPage: true })
      const axe = await new AxeBuilder({ page }).analyze()
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)
      const violations = axe.violations.map(({ id, impact, nodes }) => ({id, impact, nodes: nodes.map(({target}) => target)}))
      results.push({ surface: name, viewport, overflow, violations })
      console.log(name, viewport.width, 'overflow', overflow, 'violations', JSON.stringify(violations))
      await fs.writeFile(path.join(output, 'surface-results.json'), JSON.stringify({ results, pageErrors }, null, 2))
    }
    await page.setViewportSize({width:1600,height:1000})
  }
  if (pageErrors.length || results.some((row) => row.overflow > 0 || row.violations.some((v) => ['critical', 'serious'].includes(v.impact)))) process.exitCode = 1
} finally { await browser.close() }
