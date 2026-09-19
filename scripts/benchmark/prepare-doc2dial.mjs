// 业务基准语料的切片与选题脚本。
//
// 默认参数（2000 Unicode code points / 步长 1600 / 每领域 8 题）必须与
// docs/verification/business-benchmark-2026-09-10/ 下已冻结的产物完全一致，
// 因此本脚本提供 --verify-against <已冻结目录> 的自检模式：除 frozen_at 外
// 逐字段比对，任何漂移都会直接失败。
//
// 用法：
//   node scripts/benchmark/prepare-doc2dial.mjs                       # 生成默认产物
//   node scripts/benchmark/prepare-doc2dial.mjs --verify-against <目录>  # 自检默认规则未漂移
//   node scripts/benchmark/prepare-doc2dial.mjs --window 1000 --stride 800 --output <新目录>
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

import {buildCorpus, chunkDocument, chunkingVersion, defaultStride, defaultWindow,
  docKey, hash, releaseId, validateSlicing} from '../../services/support-copilot-ai/knowledge-tools/doc2dial-corpus.mjs';
export {buildCorpus, chunkDocument, chunkingVersion, defaultStride, defaultWindow, releaseId};
export const defaultPerDomain = 8;
export const defaultSource = '.local/business-benchmark-source';
export const defaultOutput = 'docs/verification/business-benchmark-2026-09-10';
export const dataset = 'Doc2Dial official archive named v1.0.1';

export function validateChunking({window, stride, perDomain}) {
  validateSlicing(window, stride);
  assert(Number.isInteger(perDomain) && perDomain > 0, '每领域题数必须是正整数');
}

export function buildArtifacts({documents, dialogues, sourceDir, window, stride, perDomain}) {
  validateChunking({window, stride, perDomain});
  const {corpus, chunkMap} = buildCorpus({documents, window, stride});
  const chunks = corpus.chunks;
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
        candidates.push({id: `d2d-${dial.dial_id}-2`, domain, document_id: docKey(domain, docId), original_document_id: docId,
          dialogue_id: dial.dial_id, turn_id: 2, question: user.utterance, reference_answer: agent.utterance,
          gold_spans: spans.map((span) => ({id: span.id_sp, start: span.start_sp, end: span.end_sp, text: span.text_sp})),
          sample_key: hash(`support-copilot-business-v1:${dial.dial_id}`)});
      }
    }
    candidates.sort((a, b) => a.sample_key.localeCompare(b.sample_key));
    const seen = new Set(); const selected = [];
    for (const item of candidates) {
      if (seen.has(item.document_id)) continue;
      seen.add(item.document_id); selected.push(item);
      if (selected.length === perDomain) break;
    }
    assert.equal(selected.length, perDomain, `${domain} 可用文档不足 ${perDomain} 题`);
    cases.push(...selected);
    selection.push({domain, eligible: candidates.length, selected: selected.map((item) => item.id)});
  }
  // 切片身份单独存一份，不进 corpus/protocol：那两份是被冻结的产物，字段不能变。
  const chunking = {chunking_version: chunkingVersion(window, stride), release_id: corpus.release_id,
    window, stride, per_domain: perDomain, source: 'doc2dial doc_text, Unicode code points'};
  const protocol = {dataset,
    data_nature: 'human-authored benchmark conversations; not actual customer logs', split: 'test',
    reference_nature: 'publisher-provided human response and fuzzy solution/precondition span annotations',
    source_url: 'https://raw.githubusercontent.com/doc2dial/doc2dial.github.io/main/file/doc2dial_v1.0.1.zip',
    source_git_revision: '30fa02bacefca711cc4503f118cc50365225e9b9',
    source_sha256: hash(fs.readFileSync(`${sourceDir}/doc2dial-v1.0.1.zip`)),
    raw_sha256: Object.fromEntries(['doc2dial_doc.json', 'doc2dial_dial_test.json']
      .map((name) => [name, hash(fs.readFileSync(`${sourceDir}/${name}`))])),
    selection_rule: `first user/agent pair, respond_solution with solution/precondition refs; <=3500 question characters; hash order; ${perDomain} distinct documents per domain`,
    selection, documents: Object.values(documents).reduce((total, docs) => total + Object.keys(docs).length, 0),
    chunks: chunks.length, cases: cases.length, chunking: `${window} Unicode code points, stride ${stride}, no answer-aware chunking`,
    planned_concurrency: [1, 2, 4], planned_analysis_requests: cases.length * 3, sdk_retries: 0, client_retries: 0,
    metrics: ['HTTP outcome', 'live vs business fallback vs dependency failure', 'persisted readback',
      'create-through-analysis-save latency', 'analysis HTTP latency', 'closed-loop completed operations per second',
      'gold document hit@3', 'gold span character coverage@3', 'token F1 against publisher reference'],
    quality_primary_group: 1, no_answer_accuracy: null, factual_correctness: null, human_output_reviewed: 0,
    limits: [`${cases.length} distinct questions, not ${cases.length * 3} independent quality samples`,
      'fixed group order, no causal concurrency claim',
      'published historical documents, not current policy advice',
      'token F1 is lexical overlap, not business resolution',
      'local anonymous H2 benchmark, not production capacity']};
  return {corpus, chunkMap, cases, chunking, protocol};
}

/** 除 frozen_at 外逐字段比对，证明默认参数仍能复现冻结产物。 */
export function compareWithFrozen(built, frozenDir) {
  const frozen = (name) => JSON.parse(fs.readFileSync(`${frozenDir}/${name}`, 'utf8'));
  assert.deepEqual(built.corpus, frozen('corpus.json'), 'corpus 与冻结产物不一致');
  assert.deepEqual(built.chunkMap, frozen('chunk-map.json'), 'chunk-map 与冻结产物不一致');
  assert.deepEqual(built.cases, frozen('cases.json'), 'cases 与冻结产物不一致');
  const {frozen_at: _frozenAt, ...rest} = frozen('protocol.json');
  assert.deepEqual(built.protocol, rest, 'protocol 其余字段与冻结产物不一致');
  // chunking.json 是后加的辅助文件，冻结目录未必有；有则一并比对。
  if (fs.existsSync(`${frozenDir}/chunking.json`)) {
    assert.deepEqual(built.chunking, frozen('chunking.json'), 'chunking 与冻结产物不一致');
  }
  return {chunks: built.corpus.chunks.length, cases: built.cases.length, corpusChecksum: built.corpus.corpus_checksum,
    chunkingVersion: built.chunking.chunking_version};
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function main() {
  const argv = process.argv.slice(2);
  const option = (name, fallback) => {
    const index = argv.indexOf(name);
    return index < 0 ? fallback : argv[index + 1];
  };
  const window = Number(option('--window', defaultWindow));
  const stride = Number(option('--stride', defaultStride));
  const perDomain = Number(option('--per-domain', defaultPerDomain));
  const sourceDir = path.resolve(option('--source', defaultSource));
  const output = path.resolve(option('--output', defaultOutput));
  const verifyAgainst = option('--verify-against', null);
  validateChunking({window, stride, perDomain});

  const built = buildArtifacts({
    documents: readJson(`${sourceDir}/doc2dial_doc.json`).doc_data,
    dialogues: readJson(`${sourceDir}/doc2dial_dial_test.json`).dial_data,
    sourceDir, window, stride, perDomain,
  });

  if (verifyAgainst) {
    const result = compareWithFrozen(built, path.resolve(verifyAgainst));
    console.log(JSON.stringify({verified: true, against: path.resolve(verifyAgainst), ...result}));
    return;
  }

  fs.mkdirSync(output, {recursive: true});
  assert(!fs.existsSync(`${output}/cases.json`), '冻结产物已存在，拒绝覆盖');
  const write = (name, value) => fs.writeFileSync(`${output}/${name}`, `${JSON.stringify(value, null, 2)}\n`, {flag: 'wx'});
  write('corpus.json', built.corpus);
  write('chunk-map.json', built.chunkMap);
  write('cases.json', built.cases);
  write('chunking.json', built.chunking);
  write('protocol.json', {frozen_at: new Date().toISOString(), ...built.protocol});
  console.log(JSON.stringify({cases: built.cases.length, chunks: built.corpus.chunks.length,
    documents: built.protocol.documents, corpus_checksum: built.corpus.corpus_checksum,
    chunking_version: built.chunking.chunking_version, release_id: built.corpus.release_id, output}));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
