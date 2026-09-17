import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const require = createRequire(path.join(root, 'apps/support-copilot-web/package.json'));
const { chromium } = require('playwright');
const { default: AxeBuilder } = require('@axe-core/playwright');
const output = path.resolve(process.argv[2]);
const baseURL = process.argv[3] ?? 'http://127.0.0.1:18174';
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome' });
const checks = [];
const errors = [];
try {
  for (const width of [375, 768, 1280]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(baseURL);
    await page.getByRole('button', { name: '质量评估', exact: true }).click();
    const business = page.getByRole('region', { name: '公开文档业务链路基准', exact: true });
    await business.getByRole('heading', { name: '公开文档业务链路基准', exact: true }).waitFor();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const response = await page.request.get(`${baseURL}/api/quality-reports`);
    assert.equal(response.status(), 200);
    const reports = await response.json();
    assert.equal(reports.liveEvaluation.status, 'AVAILABLE');
    assert.equal(reports.businessBenchmark.report.outcomes.normalLive, 64);
    const capture = async (state, fullPage = false) => {
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      assert.equal(overflow, false, `page overflow at ${width}/${state}`);
      await page.screenshot({ path: path.join(output, `${width}-${state}.png`), fullPage, animations: 'disabled' });
      const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
      checks.push({ width, state, overflow, axeViolations: axe.violations, image: `${width}-${state}.png` });
      writeFileSync(path.join(output, 'checks.json'), JSON.stringify({ checks, errors }, null, 2));
      assert.equal(axe.violations.length, 0, `axe violations at ${width}/${state}`);
    };
    await capture('reports', true);
    await business.getByText('失败与降级明细 · 32', { exact: true }).click();
    await business.getByRole('button', { name: '模型超时', exact: true }).click();
    await business.getByText('显示 18 / 32 条', { exact: true }).waitFor();
    assert.equal(await business.locator('.quality-failures tbody tr').count(), 18);
    await business.locator('.quality-failures').scrollIntoViewIfNeeded();
    await capture('timeouts');
    await business.getByRole('button', { name: '错误', exact: true }).click();
    await business.getByText('该分类没有记录。', { exact: true }).waitFor();
    await capture('empty-filter');
    await business.getByRole('button', { name: '全部', exact: true }).click();
    assert.equal(await business.locator('.quality-failures tbody tr').count(), 32);
    await business.getByText('失败与降级明细 · 32', { exact: true }).click();
    await business.locator('.quality-source summary').click();
    await business.locator('.quality-source').scrollIntoViewIfNeeded();
    await capture('source');
    await page.route('**/api/quality-reports', route => route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }));
    await page.getByRole('button', { name: '刷新报告', exact: true }).click();
    await page.getByText('评估报告请求失败', { exact: true }).waitFor();
    await capture('request-error', true);
    await page.unroute('**/api/quality-reports');
    await page.getByRole('button', { name: '重试加载报告', exact: true }).click();
    await business.waitFor();
    const partial = { ...reports, liveEvaluation: { status: 'INVALID', report: null } };
    await page.route('**/api/quality-reports', route => route.fulfill({ json: partial }));
    await page.getByRole('button', { name: '刷新报告', exact: true }).click();
    await page.getByText('报告校验失败', { exact: true }).waitFor();
    await business.waitFor();
    await capture('partial-invalid', true);
    await context.close();
  }
  assert.deepEqual(errors, []);
} finally {
  await browser.close();
  writeFileSync(path.join(output, 'checks.json'), JSON.stringify({ baseURL, browser: 'Chrome via Playwright', checks, errors }, null, 2));
}
