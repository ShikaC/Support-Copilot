import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { validateCase, normalized, tokenJaccard, normalLive } from './quality-input-contract.mjs';

const base = 'docs/verification/quality-input-audit-2026-09-10';
const old = 'docs/verification/business-benchmark-2026-09-10';
const readPath = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));
const read = (name) => readPath(`${base}/${name}`);
const hash = (value) => crypto.createHash('sha256').update(value).digest('hex');
const fileHash = (file) => hash(fs.readFileSync(file));
const selection = read('selection.json');
assert.equal(fileHash(`${base}/PROTOCOL.md`), selection.protocol_sha256);
assert.equal(fileHash(`${old}/corpus.json`), selection.corpus_sha256);
assert.equal(fileHash(`${old}/chunk-map.json`), selection.chunk_map_sha256);
assert.equal(fileHash(`${old}/cases.json`), selection.old_cases_sha256);
assert.equal(fileHash('docs/verification/public-rag-pilot-2026-09-10/selection.json'), selection.public_selection_sha256);
for (const [name, sha] of Object.entries(selection.source_protocol.raw_sha256)) assert.equal(fileHash(`.local/business-benchmark-source/${name}`), sha);
assert.equal(fileHash('.local/business-benchmark-source/doc2dial-v1.0.1.zip'), selection.source_protocol.source_sha256);
const raw = readPath('.local/business-benchmark-source/doc2dial_dial_test.json').dial_data;
const docs = readPath('.local/business-benchmark-source/doc2dial_doc.json').doc_data;
const oldCases = readPath(`${old}/cases.json`);
const oldDocs = new Set(oldCases.map((item) => `${item.domain}:${item.original_document_id}`));
const oldIds = new Set(oldCases.map((item) => item.dialogue_id));
const rawDial = Object.entries(raw).flatMap(([domain, documents]) => Object.entries(documents).flatMap(([doc_id, ds]) => ds.map((dial) => ({ domain, doc_id, dial }))));
assert.equal(selection.pool.length, rawDial.length);
assert.equal(new Set(selection.pool.map((item) => item.dialogue_id)).size, rawDial.length);
for (const { domain, doc_id, dial } of rawDial) {
  const row = selection.pool.find((item) => item.dialogue_id === dial.dial_id); assert(row);
  assert.equal(row.domain, domain); assert.equal(row.doc_id, doc_id);
  assert.equal(row.sample_key, hash(`support-copilot-quality-input-v1:${dial.dial_id}`));
  const target = dial.turns.findIndex((turn, i) => turn.turn_id >= 3 && turn.role === 'agent' && dial.turns[i - 1]?.role === 'user');
  assert.equal(row.target_index, target);
  if (oldIds.has(dial.dial_id)) assert.equal(row.reason, 'PREVIOUS_EXPERIMENT_DIALOGUE');
  else if (oldDocs.has(`${domain}:${doc_id}`)) assert.equal(row.reason, 'PREVIOUS_EXPERIMENT_REFERENCE_DOCUMENT');
  else if (target < 0) assert.equal(row.reason, 'NO_FOLLOWUP_TARGET');
}
for (const domain of Object.keys(raw)) {
  const seen = new Set();
  const expected = selection.pool.filter((row) => row.domain === domain && !oldIds.has(row.dialogue_id) && !oldDocs.has(`${domain}:${row.doc_id}`) && row.target_index >= 0)
    .sort((a, b) => a.sample_key.localeCompare(b.sample_key)).filter((row) => { if (seen.has(row.doc_id)) return false; seen.add(row.doc_id); return true; }).slice(0, 6);
  assert.deepEqual(selection.pool.filter((row) => row.domain === domain && row.selected).map((row) => row.dialogue_id), expected.map((row) => row.dialogue_id));
}
const cases = read('cases.json'); const candidates = read('candidate-inputs.json'); const source = read('source-excerpts.json');
assert.equal(candidates.length, 24); assert.equal(cases.length, 28);
assert.equal(new Set(cases.map((item) => item.id)).size, cases.length);
const descriptions = new Set(); const newDocKeys = new Set(); const newDocTexts = new Set();
for (const item of cases) {
  const candidate = candidates.find((entry) => entry.id === item.id);
  if (candidate) {
    const { domain } = item; const { document_id, dialogue_id, target_turn_id } = item.source;
    const dial = raw[domain][document_id].find((entry) => entry.dial_id === dialogue_id);
    const targetIndex = dial.turns.findIndex((turn) => turn.turn_id === target_turn_id);
    assert.equal(selection.pool.find((row) => row.dialogue_id === dialogue_id).selected, true);
    assert.equal(targetIndex, selection.pool.find((row) => row.dialogue_id === dialogue_id).target_index);
    assert.deepEqual(source.dialogues[dialogue_id], dial);
    const doc = docs[domain][document_id]; assert.deepEqual(source.documents[`${domain}:${document_id}`], doc);
    assert.deepEqual(candidate.input.messages, dial.turns.slice(0, targetIndex).map(({ role, utterance }) => ({ role, utterance })), 'Prefix includes changed/future/annotation data');
    const target = dial.turns[targetIndex];
    assert.deepEqual(candidate.publisher_reference, { utterance: target.utterance, act: target.da, references: target.references });
    validateCase(item, candidate, doc);
    for (const evidence of item.audit.evidence) assert.equal(evidence.source_document_sha256, hash(JSON.stringify(doc)));
    assert(!oldIds.has(dialogue_id) && !oldDocs.has(`${domain}:${document_id}`));
    const docKey = `${domain}:${document_id.split('#')[0]}`; assert(!newDocKeys.has(docKey)); newDocKeys.add(docKey);
    const docText = normalized(doc.doc_text); assert(!newDocTexts.has(docText), 'Cross-split duplicate source text'); newDocTexts.add(docText);
    for (const previous of oldCases.filter((entry) => entry.domain === domain)) {
      assert.notEqual(previous.original_document_id.split('#')[0], document_id.split('#')[0], 'Old document variant');
      assert.notEqual(normalized(docs[domain][previous.original_document_id].doc_text), normalized(doc.doc_text), 'Old document duplicate');
    }
  } else validateCase(item);
  assert(!descriptions.has(normalized(item.input.description)), 'Duplicate input'); descriptions.add(normalized(item.input.description));
}
const publicSource = read('public-source-capture.json');
const previousPublic = readPath('docs/verification/public-rag-pilot-2026-09-10/cases.json').cases;
const expectedPublic = selection.public_pool.filter((row) => row.eligible).sort((a, b) => a.sample_key.localeCompare(b.sample_key)).slice(0, 4).map((row) => row.issue);
assert.deepEqual(selection.public_ids, expectedPublic); assert.deepEqual(publicSource.map((row) => row.issue), expectedPublic);
for (const entry of publicSource) {
  assert.equal(hash(entry.body), entry.body_sha256);
  const item = cases.find((row) => row.source.issue === entry.issue); assert(item);
  assert.equal(item.source.body_sha256, entry.body_sha256);
  assert(!previousPublic.some((row) => row.source.url === entry.url), 'Previously evaluated public issue');
  if (item.included) assert.equal(entry.body_sha256, entry.prior_body_sha256);
  const excerpt = item.input.description.split('\n\nuser: ')[1]; assert(excerpt);
  for (const line of excerpt.split('\n').filter(Boolean)) assert(line === entry.title || entry.body.includes(line), 'Non-verbatim public input');
}
const summary = read('data-summary.json');
assert.equal(summary.candidates, cases.length);
for (const stratum of summary.strata) for (const [label, count] of Object.entries(stratum.counts)) assert.equal(count,
  cases.filter((item) => item.data_type === stratum.data_type && item.split === stratum.split && item.audit.label === label).length);
for (const key of ['answer_accuracy', 'customer_resolution', 'time_saved']) assert.equal(summary[key], null);
for (const key of ['model_calls', 'embedding_calls', 'human_reviewed']) assert.equal(summary[key], 0);
const near = [];
for (let i = 0; i < candidates.length; i++) for (let j = i + 1; j < candidates.length; j++) {
  const similarity = tokenJaccard(candidates[i].input.messages.map((m) => m.utterance).join(' '), candidates[j].input.messages.map((m) => m.utterance).join(' '));
  if (similarity >= summary.near_duplicate_threshold) near.push({ left: candidates[i].id, right: candidates[j].id, similarity });
}
assert.deepEqual(summary.near_duplicate_flags, near);
for (const split of ['development', 'holdout']) assert.deepEqual(read(`inputs-${split}.json`), cases.filter((item) => item.included && item.split === split).map(({ id, input }) => ({ id, input })));
const oldVerification = readPath(`${old}/verification.json`);
for (const [key, sha] of Object.entries(oldVerification.artifacts)) assert.equal(fileHash(`${old}/${key === 'source_manifest_sha256' ? 'run-1/source-manifest.json' : key.replace('_sha256', '.json')}`), sha);
const runtime = readPath(`${old}/run-1/source-manifest.json`);
for (const [file, sha] of Object.entries(runtime.hashes)) assert.equal(fileHash(`${old}/run-1/source/${file}`), sha);
const trials = readPath(`${old}/run-1/results.json`); const restart = readPath(`${old}/restart-verification.json`);
assert.equal(trials.length, 96); assert.equal(new Set(trials.map((trial) => `${trial.case_id}:${trial.concurrency}`)).size, 96);
for (const item of oldCases) for (const level of [1, 2, 4]) assert(trials.some((trial) => trial.case_id === item.id && trial.concurrency === level));
for (const trial of trials) {
  assert.equal(trial.persisted, true); assert.equal(trial.stages.history.status, 200);
  assert.deepEqual(trial.stages.history.body.find((entry) => entry.id === trial.stages.analyze.body.id), trial.stages.analyze.body);
  assert(restart.records.some((entry) => entry.ticket_id === trial.ticket_id && entry.http_status === 200 && entry.matches === true));
}
const groups = readPath(`${old}/summary.json`).metrics;
for (const group of groups) {
  const rows = trials.filter((trial) => trial.concurrency === group.concurrency);
  assert.equal(group.live, rows.filter((trial) => normalLive(trial.stages.analyze.body)).length);
  assert.equal(group.evidence_insufficient, rows.filter((trial) => trial.stages.analyze.body.fallbackReason === 'insufficient_evidence').length);
}
if (fs.existsSync(`${base}/freeze-manifest.json`)) {
  for (const [file, sha] of Object.entries(read('freeze-manifest.json').hashes)) assert.equal(fileHash(file), sha, `Frozen artifact changed: ${file}`);
}
const baseline = read('workspace-before.json');
const allowed = new Set(['docs/STATUS.md', 'docs/ROADMAP.md', 'docs/learning/NEXT_SESSION_HANDOFF_PROMPT.md', 'docs/learning/READING_LOG.md']);
const changed = Object.entries(baseline.hashes).filter(([file, sha]) => !fs.existsSync(file) || fileHash(file) !== sha).map(([file]) => file);
assert(changed.every((file) => allowed.has(file)), `Pre-existing file changed: ${changed.filter((file) => !allowed.has(file))}`);
const head = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(); assert.equal(head, baseline.head);
console.log(JSON.stringify({ offline_integrity: 'PASS', head, dirty: Boolean(execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim()),
  candidates: cases.length, included_pending_human: cases.filter((item) => item.included).length, old_trials_checked: trials.length,
  runtime_snapshot_files_checked: Object.keys(runtime.hashes).length,
  runtime_workspace_differences: Object.entries(runtime.hashes).filter(([file, sha]) => fileHash(file) !== sha).map(([file]) => file),
  preexisting_files_changed: changed, human_reviewed: 0, publishable: false }));
if (process.argv.includes('--require-human')) {
  console.error('BLOCKED: input labels and required points have no human confirmation; no model quality or publishable gold claim.');
  process.exitCode = 2;
}
