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
    for (const [index, name] of ['工单工作台', '运营概览', '知识库', '审计记录', '质量评估'].entries()) {
      await page.getByRole('button', { name, exact: true }).click();
      await page.getByRole('heading', { name, exact: true }).waitFor();
      await page.locator('.data-loading[role="status"]').waitFor({ state: 'hidden' });
      await page.screenshot({ path: path.join(output, `${width}-${index}.png`), fullPage: true, animations: 'disabled' });
      const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      checks.push({ width, name, image: `${width}-${index}.png`, overflow, axeViolations: axe.violations });
      writeFileSync(path.join(output, 'checks.json'), JSON.stringify({ checks, errors }, null, 2));
      assert.equal(overflow, false, `${name}/${width} overflow`);
      assert.equal(axe.violations.length, 0, `${name}/${width} axe`);
    }
    await context.close();
  }
  assert.deepEqual(errors, []);
} finally {
  await browser.close();
  writeFileSync(path.join(output, 'checks.json'), JSON.stringify({ baseURL, browser: 'Chrome via Playwright', checks, errors }, null, 2));
}
