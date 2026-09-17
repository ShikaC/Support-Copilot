import { chromium, expect } from '../../../../apps/support-copilot-web/node_modules/@playwright/test/index.mjs'
import { writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { analysisResponsePayload, ticketResponsePayload, nullableMetricsResponsePayload } from '../../../../apps/support-copilot-web/src/test/apiFixtures.ts'
const directory = fileURLToPath(new URL('.', import.meta.url))
const browser = await chromium.launch({ headless: true })
const records = []
try {
 for (const width of [375, 768, 1280]) {
  for (const state of ['empty', 'unadopted', 'mixed']) {
   const context = await browser.newContext({ viewport: { width, height: 900 } })
   const page = await context.newPage()
   const errors = []
   page.on('pageerror', error => errors.push(error.message))
   const original = analysisResponsePayload('synthetic-evidence')
   const hit = original.retrieval.hits[0]
   const analysis = { ...original, status: state === 'mixed' ? 'SUCCEEDED' : 'FALLBACK', mode: state === 'mixed' ? 'mock' : 'fallback', fallbackReason: state === 'mixed' ? null : 'insufficient_evidence', retrieval: { query: '合成验证：知识候选与回复依据', hits: state === 'empty' ? [] : [{ ...hit, usedAsEvidence: state === 'mixed' }, { ...hit, chunkId: 'chunk-sync', documentTitle: '同步问题排查', section: '环境信息收集', content: '请提供客户端版本、操作系统版本与代理配置。', rerankPosition: 2, rerankScore: 0.41, usedAsEvidence: false }] }, suggestedReply: { content: state === 'mixed' ? original.suggestedReply.content : '当前没有充分证据，需要支持人员复核。', citations: state === 'mixed' ? original.suggestedReply.citations : [], warnings: ['合成 UI 状态，仅用于验证。'] } }
   const ticket = { ...ticketResponsePayload, customerName: '合成验证客户', status: 'NEEDS_ESCALATION', latestAnalysis: analysis }
   await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET') throw new Error('No writes permitted in UI capture')
    let payload
    if (path === '/api/tickets') payload = [ticket]
    else if (path === '/api/tickets/queue') payload = { items: [ticket], nextCursor: null, totalCount: 1 }
    else if (path === '/api/metrics') payload = nullableMetricsResponsePayload
    else if (path.endsWith('/activity')) payload = { items: [], nextCursor: null }
    else if (path.endsWith('/notes') || path.endsWith('/reviews')) payload = []
    else if (path === '/api/tickets/ticket-10042') payload = ticket
    else throw new Error(`Unhandled API: ${path}`)
    await route.fulfill({ json: payload })
   })
   await page.goto('http://127.0.0.1:18174/')
   await page.getByRole('tab', { name: `知识依据 ${state === 'mixed' ? 1 : 0}` }).click()
   const panel = page.getByRole('region', { name: 'AI 分析', exact: true })
   await panel.scrollIntoViewIfNeeded()
   if (state !== 'mixed') await expect(page.getByText('没有找到充分证据', { exact: true })).toBeVisible()
   if (state !== 'empty') await expect(page.getByRole('button', { name: /同步问题排查.*未作为回复依据/ })).toBeVisible()
   await page.screenshot({ path: `${directory}${width}-${state}.png`, fullPage: true })
   if (state === 'unadopted') {
    const candidate = page.getByRole('button', { name: /同步问题排查.*未作为回复依据/ })
    await candidate.click()
    await expect(candidate).toHaveAttribute('aria-expanded', 'true')
    await page.waitForTimeout(100)
    await panel.screenshot({ path: `${directory}${width}-expand-mid.png` })
    await page.waitForTimeout(160)
    await expect(page.getByText('请提供客户端版本、操作系统版本与代理配置。', { exact: true })).toBeVisible()
    await panel.screenshot({ path: `${directory}${width}-expand-settled.png` })
   }
   const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
   expect(overflow).toBeLessThanOrEqual(0)
   expect(errors).toEqual([])
   records.push({ width, state, adoptedCount: state === 'mixed' ? 1 : 0, candidateCount: analysis.retrieval.hits.length, horizontalOverflow: overflow, pageErrors: errors })
   await context.close()
  }
 }
 await writeFile(`${directory}browser-results.json`, JSON.stringify(records, null, 2))
} finally { await browser.close() }
