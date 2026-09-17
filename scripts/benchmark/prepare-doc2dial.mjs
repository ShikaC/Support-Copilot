import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';

const source = path.resolve('.local/business-benchmark-source');
const output = path.resolve('docs/verification/business-benchmark-2026-09-10');
fs.mkdirSync(output, { recursive: true });
assert(!fs.existsSync(`${output}/cases.json`), 'Frozen cases already exist');
const read = (name) => JSON.parse(fs.readFileSync(`${source}/${name}`, 'utf8'));
const hash = (text) => crypto.createHash('sha256').update(text).digest('hex');
const canonical = (value) => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) : item);
const documents = read('doc2dial_doc.json').doc_data;
const dialogues = read('doc2dial_dial_test.json').dial_data;
const chunks = [];
const metadata = {};
const docKey = (domain, id) => `d2d-${domain}-${hash(id).slice(0, 16)}`;
for (const [domain, docs] of Object.entries(documents)) {
  for (const [id, doc] of Object.entries(docs)) {
    assert.equal(doc.doc_id, id);
    const points = [...doc.doc_text];
    for (let start = 0; start < points.length; start += 1600) {
      const end = Math.min(start + 2000, points.length);
      const chunkId = `${docKey(domain, id)}-${start}-${end}`;
      const content = points.slice(start, end).join('').trim();
      if (content) {
        chunks.push({ chunk_id: chunkId, document_id: docKey(domain, id), document_title: doc.title,
          section: `Unicode code points ${start}:${end}`, content, source_uri: `https://doc2dial.github.io/#${encodeURIComponent(id)}`,
          categories: ['GENERAL'], keywords: [domain], allowed_scopes: ['GENERAL'], document_version: 'doc2dial-archive-v1.0.1',
          status: 'PUBLISHED', updated_at: '2021-02-26' });
        metadata[chunkId] = { domain, original_document_id: id, start, end };
      }
      if (end === points.length) break;
    }
  }
}
const cases = [];
const selection = [];
for (const domain of Object.keys(dialogues).sort()) {
  const candidates = [];
  for (const [docId, items] of Object.entries(dialogues[domain])) {
    for (const dial of items) {
      const user = dial.turns[0]; const agent = dial.turns[1];
      if (user?.role !== 'user' || agent?.role !== 'agent' || agent.da !== 'respond_solution') continue;
      const refs = agent.references.filter((ref) => ['solution', 'precondition'].includes(ref.label));
      if (!refs.length || user.utterance.length > 3500) continue;
      const doc = documents[domain][docId];
      const spans = refs.map((ref) => doc.spans[ref.sp_id]);
      assert(spans.every(Boolean));
      const points = [...doc.doc_text];
      for (const span of spans) assert.equal(points.slice(span.start_sp, span.end_sp).join(''), span.text_sp);
      candidates.push({ id: `d2d-${dial.dial_id}-2`, domain, document_id: docKey(domain, docId), original_document_id: docId,
        dialogue_id: dial.dial_id, turn_id: 2, question: user.utterance, reference_answer: agent.utterance,
        gold_spans: spans.map((span) => ({ id: span.id_sp, start: span.start_sp, end: span.end_sp, text: span.text_sp })),
        sample_key: hash(`support-copilot-business-v1:${dial.dial_id}`) });
    }
  }
  candidates.sort((a, b) => a.sample_key.localeCompare(b.sample_key));
  const seen = new Set(); const selected = [];
  for (const item of candidates) {
    if (seen.has(item.document_id)) continue;
    seen.add(item.document_id); selected.push(item);
    if (selected.length === 8) break;
  }
  assert.equal(selected.length, 8);
  cases.push(...selected);
  selection.push({ domain, eligible: candidates.length, selected: selected.map((item) => item.id) });
}
const corpus = { release_id: 'doc2dial-business-benchmark-v1', release_version: 1,
  corpus_checksum: hash(canonical(chunks)), chunks };
const write = (name, value) => fs.writeFileSync(`${output}/${name}`, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });
write('corpus.json', corpus); write('chunk-map.json', metadata); write('cases.json', cases);
write('protocol.json', { frozen_at: new Date().toISOString(), dataset: 'Doc2Dial official archive named v1.0.1',
  data_nature: 'human-authored benchmark conversations; not actual customer logs', split: 'test',
  reference_nature: 'publisher-provided human response and fuzzy solution/precondition span annotations',
  source_url: 'https://raw.githubusercontent.com/doc2dial/doc2dial.github.io/main/file/doc2dial_v1.0.1.zip',
  source_git_revision: '30fa02bacefca711cc4503f118cc50365225e9b9',
  source_sha256: hash(fs.readFileSync(`${source}/doc2dial-v1.0.1.zip`)),
  raw_sha256: Object.fromEntries(['doc2dial_doc.json','doc2dial_dial_test.json'].map(name=>[name,hash(fs.readFileSync(`${source}/${name}`))])),
  selection_rule: 'first user/agent pair, respond_solution with solution/precondition refs; <=3500 question characters; hash order; 8 distinct documents per domain',
  selection, documents: Object.values(documents).reduce((n,docs)=>n+Object.keys(docs).length,0), chunks: chunks.length,
  cases: cases.length, chunking: '2000 Unicode code points, stride 1600, no answer-aware chunking',
  planned_concurrency: [1,2,4], planned_analysis_requests: cases.length*3, sdk_retries:0, client_retries:0,
  metrics: ['HTTP outcome','live vs business fallback vs dependency failure','persisted readback','create-through-analysis-save latency','analysis HTTP latency','closed-loop completed operations per second','gold document hit@3','gold span character coverage@3','token F1 against publisher reference'],
  quality_primary_group:1, no_answer_accuracy:null, factual_correctness:null, human_output_reviewed:0,
  limits:['32 distinct questions, not 96 independent quality samples','fixed group order, no causal concurrency claim','published historical documents, not current policy advice','token F1 is lexical overlap, not business resolution','local anonymous H2 benchmark, not production capacity'] });
console.log(JSON.stringify({ cases: cases.length, chunks: chunks.length, documents: Object.values(documents).reduce((n,docs)=>n+Object.keys(docs).length,0), corpus_checksum:corpus.corpus_checksum }));
