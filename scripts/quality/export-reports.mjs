import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { liveReport } from './live-report.mjs';
import { businessReport } from './business-report.mjs';

export const sourcePaths = {
  live: 'docs/verification/ai-quality-fixes-2026-09-10/final-2/live-latest.json',
  trials: 'docs/verification/business-benchmark-2026-09-10/run-1/results.json',
  summary: 'docs/verification/business-benchmark-2026-09-10/summary.json',
  manifest: 'docs/verification/business-benchmark-2026-09-10/run-1/manifest.json',
};
export const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

export function exportReports({ root, output }) {
  const sources = Object.fromEntries(Object.entries(sourcePaths).map(([key, name]) => {
    const bytes = readFileSync(path.join(root, name));
    return [key, { raw: JSON.parse(bytes.toString('utf8')), file: { name, sha256: sha256(bytes) } }];
  }));
  const live = liveReport(sources.live.raw, [sources.live.file]);
  const business = businessReport({ trials: sources.trials.raw, summary: sources.summary.raw, manifest: sources.manifest.raw },
    [sources.trials.file, sources.summary.file, sources.manifest.file]);
  const reports = { 'live.json': live, 'business.json': business };
  // Exclusive directory creation protects every prior export, including partial ones.
  mkdirSync(output);
  const files = Object.entries(reports).map(([name, report]) => {
    const bytes = JSON.stringify(report, null, 2) + '\n';
    writeFileSync(path.join(output, name), bytes, { flag: 'wx' });
    return { name, sha256: sha256(bytes) };
  });
  const manifest = { schemaVersion: 1, modelCalls: 0, embeddingCalls: 0, files };
  writeFileSync(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n', { flag: 'wx' });
  return manifest;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  assert.equal(process.argv.length, 3, 'Usage: node scripts/quality/export-reports.mjs <new-output-directory>');
  const root = fileURLToPath(new URL('../../', import.meta.url));
  const output = path.resolve(process.argv[2]);
  const manifest = exportReports({ root, output });
  process.stdout.write(JSON.stringify({ output, ...manifest }, null, 2) + '\n');
}
