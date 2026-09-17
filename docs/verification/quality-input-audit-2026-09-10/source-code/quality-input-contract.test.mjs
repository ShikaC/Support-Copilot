import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { normalLive, ticketInput, validateCase } from './quality-input-contract.mjs';

const base = 'docs/verification/quality-input-audit-2026-09-10';
const read = (name) => JSON.parse(fs.readFileSync(`${base}/${name}`, 'utf8'));
const cases = read('cases.json'); const candidates = read('candidate-inputs.json'); const source = read('source-excerpts.json');
const check = (item, candidate = candidates.find((entry) => entry.id === item.id)) => validateCase(item, candidate,
  candidate ? source.documents[`${candidate.domain}:${candidate.source.document_id}`] : undefined);

test('full prefix retains the annual recertification request before a bare Yes', () => {
  const candidate = candidates[12]; const input = ticketInput(candidate);
  assert.match(input.description, /annual recertification/);
  assert.match(input.description, /user: Yes$/);
  assert(!input.description.includes(candidate.publisher_reference.utterance));
  check(cases[12]);
});

test('DMV projection removes unsupported state routing while keeping user-supplied New York', () => {
  assert(!ticketInput(candidates[0]).description.includes('Virginia'));
  assert(!ticketInput(candidates[0]).description.includes('NY State'));
  assert.match(ticketInput(candidates[2]).description, /New york/);
  check(cases[0]);
});

test('target answer or annotation fields cannot enter ticket input', () => {
  const item = structuredClone(cases[12]); item.input.description += `\n${item.publisher_reference.utterance}`;
  assert.throws(() => check(item), /leakage/);
  const fields = structuredClone(cases[12]); fields.input.gold_spans = [];
  assert.throws(() => check(fields), /allowlisted/);
});

test('damaged reference coordinates and unsupported required points fail closed', () => {
  const item = structuredClone(cases[12]); item.audit.evidence[0].start++;
  assert.throws(() => check(item));
  const missing = structuredClone(cases[12]); missing.audit.points[0].span_ids = ['does-not-exist'];
  assert.throws(() => check(missing), /Missing point evidence/);
});

test('clarification without a specific missing condition is not accepted', () => {
  const item = structuredClone(cases[2]); item.audit.missing_slots = [];
  assert.throws(() => check(item), /specific missing slots/);
});

test('greeting-only input cannot replace an audited business request', () => {
  const item = structuredClone(cases[12]); item.input.description = 'Hi there';
  assert.throws(() => check(item), /leakage/);
  const excluded = structuredClone(cases[16]); excluded.included = true;
  assert.throws(() => check(excluded));
});

test('no-reference alone is not sufficient proof of out-of-KB', () => {
  const item = structuredClone(cases.find((entry) => entry.audit.label === 'OUT_OF_KB'));
  item.audit.coverage_basis = '';
  assert.throws(() => check(item), /proof of OUT_OF_KB/);
});

test('AI labels cannot be promoted to human review by filling a status', () => {
  const item = structuredClone(cases[12]); item.human_review.status = 'APPROVED';
  assert.throws(() => check(item), /human gold/);
});

test('HTTP and persistence success never turn fallback or timeout into normal live', () => {
  assert.equal(normalLive({ mode: 'live', status: 'SUCCEEDED', fallbackReason: null }), true);
  for (const fallbackReason of ['insufficient_evidence', 'generation_unavailable', 'processing_timeout']) {
    assert.equal(normalLive({ http: 200, persisted: true, mode: 'fallback', status: 'FALLBACK', fallbackReason }), false);
  }
  assert.equal(normalLive({ mode: 'live', status: 'SUCCEEDED' }), false);
});

test('preparation and audit builders refuse to overwrite frozen evidence', () => {
  for (const script of ['prepare-quality-inputs.mjs', 'build-quality-audit.mjs']) {
    const before = fs.readFileSync(`${base}/cases.json`);
    const result = spawnSync(process.execPath, [`scripts/benchmark/${script}`], { encoding: 'utf8' });
    assert.notEqual(result.status, 0); assert.match(result.stderr, /Frozen .* already exist/);
    assert.deepEqual(fs.readFileSync(`${base}/cases.json`), before);
  }
});

test('final builder reproduces audited projections in an isolated temporary directory', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'support-quality-audit-'));
  try {
    const destination = path.join(temp, base); fs.mkdirSync(destination, { recursive: true });
    for (const file of ['candidate-inputs.json', 'source-excerpts.json', 'audit-decisions.json', 'public-source-capture.json']) {
      fs.copyFileSync(`${base}/${file}`, path.join(destination, file));
    }
    const corpus = 'docs/verification/business-benchmark-2026-09-10/corpus.json';
    fs.mkdirSync(path.dirname(path.join(temp, corpus)), { recursive: true }); fs.copyFileSync(corpus, path.join(temp, corpus));
    const result = spawnSync(process.execPath, [path.resolve('scripts/benchmark/build-quality-audit.mjs')], { cwd: temp, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    for (const file of ['cases.json', 'inputs-development.json', 'inputs-holdout.json', 'data-summary.json', 'human-review-template.json', 'REVIEW.md']) {
      assert.deepEqual(fs.readFileSync(`${base}/${file}`), fs.readFileSync(path.join(destination, file)), `Projection drift: ${file}`);
    }
  } finally { fs.rmSync(temp, { recursive: true, force: true }); }
});
