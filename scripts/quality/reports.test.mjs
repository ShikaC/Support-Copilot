import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { outcome } from './report-outcomes.mjs';
import { liveReport } from './live-report.mjs';
import { businessReport } from './business-report.mjs';
import { exportReports, sourcePaths, sha256 } from './export-reports.mjs';

const root = fileURLToPath(new URL('../../', import.meta.url));
const read = key => JSON.parse(readFileSync(path.join(root, sourcePaths[key]), 'utf8'));
const businessInput = () => ({ trials: read('trials'), summary: read('summary'), manifest: read('manifest') });

test('normal model output requires all three normal state markers', () => {
  assert.equal(outcome({ status: 'SUCCEEDED', mode: 'live', reason: null }), 'normalLive');
  assert.equal(outcome({ status: 'SUCCEEDED', mode: 'fallback', reason: null }), 'error');
  assert.equal(outcome({ status: 'SUCCEEDED', mode: 'live', reason: 'timeout' }), 'error');
  assert.equal(outcome({ status: 'FALLBACK', mode: 'fallback', reason: 'unknown_bug' }), 'error');
});

test('HTTP 200 and persisted timeout remains a model timeout in all 96 records', () => {
  const report = businessReport(businessInput(), []);
  assert.deepEqual(report.outcomes, { normalLive: 64, evidenceInsufficient: 14, timeout: 18, otherFallback: 0, error: 0 });
  assert.equal(report.sampleCount, 96);
  assert.equal(report.distinctCaseCount, 32);
  assert.equal(report.failures.length, 32);
  assert.equal(report.groups[2].normalLive, 16);
  assert.equal(report.groups[2].apiCompleted, 32);
  assert.equal(report.groups[2].persisted, 32);
  assert.equal(report.answerAccuracy, null);
});

test('live baseline preserves five non-normal cases and zero human reviews', () => {
  const report = liveReport(read('live'), []);
  assert.deepEqual(report.outcomes, { normalLive: 17, evidenceInsufficient: 3, timeout: 2, otherFallback: 0, error: 0 });
  assert.equal(report.humanReviewedCount, 0);
  assert.equal(report.answerAccuracy, null);
  assert.equal(report.failures.length, 5);
  assert(report.metrics.every(item => !item.label.includes('Hit@')));
});

test('unconfirmed human labels cannot be imported by this offline adapter', () => {
  const raw = read('live');
  raw.summary.human_reviewed_count = 1;
  assert.throws(() => liveReport(raw, []), /human review import/);
});

test('changed summaries and duplicate samples fail instead of silently showing stale metrics', () => {
  const input = businessInput();
  input.summary.metrics[0].live++;
  assert.throws(() => businessReport(input, []));
  const duplicate = businessInput();
  duplicate.trials[1] = duplicate.trials[0];
  assert.throws(() => businessReport(duplicate, []), /duplicate case/);
});

test('history equality checks all fields, not just id, mode or reply', () => {
  const input = businessInput();
  input.trials[0].stages.history.body[0].classification.confidence = 0;
  assert.throws(() => businessReport(input, []), /full readback/);
});

test('export is reproducible, hashes actual files and refuses an existing directory', () => {
  const temp = mkdtempSync(path.join(tmpdir(), 'quality-export-'));
  try {
    const a = path.join(temp, 'a');
    const b = path.join(temp, 'b');
    const first = exportReports({ root, output: a });
    const second = exportReports({ root, output: b });
    assert.deepEqual(first, second);
    assert.equal(first.modelCalls, 0);
    for (const file of first.files) assert.equal(sha256(readFileSync(path.join(a, file.name))), file.sha256);
    assert.throws(() => exportReports({ root, output: a }), { code: 'EEXIST' });
    assert.equal(sha256(readFileSync(path.join(a, 'live.json'))), first.files[0].sha256);
  } finally { rmSync(temp, { recursive: true, force: true }); }
});

test('invalid source fails before publishing an output directory', () => {
  const temp = mkdtempSync(path.join(tmpdir(), 'quality-invalid-'));
  try {
    for (const [key, name] of Object.entries(sourcePaths)) {
      const filename = path.join(temp, name);
      mkdirSync(path.dirname(filename), { recursive: true });
      writeFileSync(filename, key === 'live' ? '{broken' : JSON.stringify(read(key)));
    }
    assert.throws(() => exportReports({ root: temp, output: path.join(temp, 'output') }), SyntaxError);
    assert.throws(() => readFileSync(path.join(temp, 'output', 'manifest.json')), { code: 'ENOENT' });
  } finally { rmSync(temp, { recursive: true, force: true }); }
});
