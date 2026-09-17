import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const base = path.resolve('docs/verification/quality-input-audit-2026-09-10');
const old = path.resolve('docs/verification/business-benchmark-2026-09-10');
const raw = path.resolve('.local/business-benchmark-source');
const read = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));
const hash = (value) => crypto.createHash('sha256').update(value).digest('hex');
const write = (name, value) => fs.writeFileSync(`${base}/${name}`, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });
assert(!fs.existsSync(`${base}/selection.json`), 'Frozen selection already exists');
const protocolHash = hash(fs.readFileSync(`${base}/PROTOCOL.md`));
const protocol = read(`${old}/protocol.json`);
for (const [file, sha] of Object.entries(protocol.raw_sha256)) assert.equal(hash(fs.readFileSync(`${raw}/${file}`)), sha);
const documents = read(`${raw}/doc2dial_doc.json`).doc_data;
const dialogues = read(`${raw}/doc2dial_dial_test.json`).dial_data;
const oldCases = read(`${old}/cases.json`);
const oldDialogues = new Set(oldCases.map((item) => item.dialogue_id));
const oldDocuments = new Set(oldCases.map((item) => `${item.domain}:${item.original_document_id}`));
const institutions = { dmv: 'Virginia DMV', ssa: 'US Social Security Administration', studentaid: 'US Federal Student Aid', va: 'US Department of Veterans Affairs' };
const pool = [];
const candidates = [];
const sources = { dialogues: {}, documents: {} };
for (const domain of Object.keys(dialogues).sort()) {
  const domainPool = [];
  for (const [docId, items] of Object.entries(dialogues[domain])) for (const dial of items) {
    const targetIndex = dial.turns.findIndex((turn, i) => turn.turn_id >= 3 && turn.role === 'agent' && dial.turns[i - 1]?.role === 'user');
    const reason = oldDialogues.has(dial.dial_id) ? 'PREVIOUS_EXPERIMENT_DIALOGUE'
      : oldDocuments.has(`${domain}:${docId}`) ? 'PREVIOUS_EXPERIMENT_REFERENCE_DOCUMENT'
        : targetIndex < 0 ? 'NO_FOLLOWUP_TARGET' : 'OUTSIDE_FIXED_QUOTA';
    domainPool.push({ domain, doc_id: docId, dialogue_id: dial.dial_id, target_index: targetIndex,
      sample_key: hash(`support-copilot-quality-input-v1:${dial.dial_id}`), reason, selected: false });
  }
  domainPool.sort((a, b) => a.sample_key.localeCompare(b.sample_key));
  const seen = new Set();
  let selected = 0;
  for (const entry of domainPool) {
    if (entry.reason !== 'OUTSIDE_FIXED_QUOTA') continue;
    if (seen.has(entry.doc_id)) { entry.reason = 'SAME_DOCUMENT_AS_EARLIER_CANDIDATE'; continue; }
    if (selected === 6) continue;
    selected++; seen.add(entry.doc_id); entry.selected = true; entry.reason = 'FIXED_HASH_QUOTA';
    const dial = dialogues[domain][entry.doc_id].find((item) => item.dial_id === entry.dialogue_id);
    const target = dial.turns[entry.target_index];
    const id = `qa-${dial.dial_id}-${target.turn_id}`;
    const prefix = dial.turns.slice(0, entry.target_index).map(({ role, utterance }) => ({ role, utterance }));
    candidates.push({ id, data_type: 'HUMAN_AUTHORED_DOCUMENT_DIALOGUE', domain,
      split: selected % 2 ? 'development' : 'holdout',
      source: { dialogue_id: dial.dial_id, document_id: entry.doc_id, target_turn_id: target.turn_id,
        dialogue_pointer: `/dial_data/${domain}/${entry.doc_id.replace(/~/g, '~0').replace(/\//g, '~1')}/${dialogues[domain][entry.doc_id].indexOf(dial)}` },
      input: { institution: institutions[domain], context_origin: 'EXPERIMENT_DOMAIN_ROUTING_NOT_USER_QUOTE', messages: prefix },
      publisher_reference: { utterance: target.utterance, act: target.da, references: target.references },
      human_review: { status: 'NOT_REVIEWED', reviewer: null, reviewed_at: null, answerability: null } });
    sources.dialogues[dial.dial_id] = dial;
    sources.documents[`${domain}:${entry.doc_id}`] = documents[domain][entry.doc_id];
  }
  assert.equal(selected, 6);
  pool.push(...domainPool);
}
const publicSelection = read('docs/verification/public-rag-pilot-2026-09-10/selection.json');
const publicPool = publicSelection.candidates.map((entry) => ({ ...entry,
  eligible: !entry.selected && entry.reason === 'Not selected for this bounded purposive pilot; not judged unanswerable or invalid',
  sample_key: hash(`support-copilot-quality-ook-v1:${entry.issue}`) })).sort((a, b) => a.sample_key.localeCompare(b.sample_key));
const publicIds = publicPool.filter((entry) => entry.eligible).slice(0, 4).map((entry) => entry.issue);
assert.equal(publicIds.length, 4);
write('selection.json', { frozen_at: new Date().toISOString(), protocol_sha256: protocolHash,
  source_protocol: protocol, corpus_sha256: hash(fs.readFileSync(`${old}/corpus.json`)),
  chunk_map_sha256: hash(fs.readFileSync(`${old}/chunk-map.json`)),
  old_cases_sha256: hash(fs.readFileSync(`${old}/cases.json`)),
  public_selection_sha256: hash(fs.readFileSync('docs/verification/public-rag-pilot-2026-09-10/selection.json')),
  pool, public_pool: publicPool.map((entry) => ({ ...entry, selected_for_audit: publicIds.includes(entry.issue) })), public_ids: publicIds });
write('candidate-inputs.json', candidates);
write('source-excerpts.json', sources);
console.log(JSON.stringify({ candidates: candidates.length, pool: pool.length, public_ids: publicIds, protocol_sha256: protocolHash }));
