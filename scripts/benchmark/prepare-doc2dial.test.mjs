import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  buildArtifacts,
  chunkDocument,
  chunkingVersion,
  compareWithFrozen,
  defaultPerDomain,
  defaultStride,
  defaultWindow,
  releaseId,
  validateChunking,
} from './prepare-doc2dial.mjs';

/** 造一份最小但结构完整的归档：两个领域，各两个文档、一个可选题对话。 */
function makeArchive() {
  const documents = {};
  const dialogues = {};
  for (const domain of ['dmv', 'va']) {
    documents[domain] = {};
    dialogues[domain] = {};
    for (const suffix of ['a', 'b']) {
      const docId = `doc-${domain}-${suffix}`;
      const text = `Text for ${docId}. Second sentence about benefits.`;
      documents[domain][docId] = {
        doc_id: docId,
        title: `Title ${docId}`,
        doc_text: text,
        spans: {s1: {id_sp: 's1', start_sp: 0, end_sp: 4, text_sp: text.slice(0, 4)}},
      };
      dialogues[domain][docId] = [{
        dial_id: `dial-${domain}-${suffix}`,
        turns: [
          {turn_id: 1, role: 'user', utterance: `question about ${domain}`},
          {turn_id: 2, role: 'agent', utterance: 'answer', da: 'respond_solution',
            references: [{label: 'solution', sp_id: 's1'}]},
        ],
      }];
    }
  }
  return {documents, dialogues};
}

function makeSourceDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'prepare-doc2dial-'));
  fs.writeFileSync(`${dir}/doc2dial-v1.0.1.zip`, 'zip-bytes');
  fs.writeFileSync(`${dir}/doc2dial_doc.json`, '{}');
  fs.writeFileSync(`${dir}/doc2dial_dial_test.json`, '{}');
  return dir;
}

test('chunkingVersion encodes the slicing parameters', () => {
  assert.equal(chunkingVersion(2000, 1600), 'doc2dial-codepoints-2000-1600-v1');
  assert.equal(chunkingVersion(1000, 800), 'doc2dial-codepoints-1000-800-v1');
});

test('releaseId keeps the historical name only for the frozen parameters', () => {
  assert.equal(releaseId(defaultWindow, defaultStride), 'doc2dial-business-benchmark-v1');
  assert.equal(releaseId(1000, 800), 'doc2dial-business-benchmark-1000-800-v1');
});

test('validateChunking rejects gaps and non-positive numbers', () => {
  validateChunking({window: 2000, stride: 1600, perDomain: 8});
  assert.throws(() => validateChunking({window: 0, stride: 1, perDomain: 8}), /窗口/);
  assert.throws(() => validateChunking({window: 10, stride: 0, perDomain: 8}), /步长/);
  assert.throws(() => validateChunking({window: 10, stride: 20, perDomain: 8}), /静默丢掉中间内容/);
  assert.throws(() => validateChunking({window: 10, stride: 5, perDomain: 0}), /题数/);
});

test('chunkDocument slides by stride and stops at the document end', () => {
  assert.deepEqual(chunkDocument('abcdefghij', 4, 3), [
    {start: 0, end: 4, content: 'abcd'},
    {start: 3, end: 7, content: 'defg'},
    {start: 6, end: 10, content: 'ghij'},
  ]);
});

test('chunkDocument handles short and empty documents without inventing chunks', () => {
  assert.deepEqual(chunkDocument('abc', 4, 3), [{start: 0, end: 3, content: 'abc'}]);
  assert.deepEqual(chunkDocument('', 4, 3), []);
  assert.deepEqual(chunkDocument('   ', 4, 3), []);
});

test('chunkDocument never drops content when the stride is smaller than the window', () => {
  const text = 'The quick brown fox jumps over the lazy dog';
  const slices = chunkDocument(text, 10, 5);
  const covered = new Set();
  for (const slice of slices) for (let i = slice.start; i < slice.end; i += 1) covered.add(i);
  assert.equal(covered.size, text.length);
});

test('buildArtifacts keeps the frozen shape for the default parameters', () => {
  const {documents, dialogues} = makeArchive();
  const sourceDir = makeSourceDir();
  const built = buildArtifacts({documents, dialogues, sourceDir, window: 2000, stride: 1600, perDomain: 1});
  assert.equal(built.corpus.release_id, 'doc2dial-business-benchmark-v1');
  assert.equal(built.corpus.release_version, 1);
  assert.equal(built.chunking.chunking_version, 'doc2dial-codepoints-2000-1600-v1');
  assert.equal(built.cases.length, 2);
  assert.equal(built.protocol.chunking, '2000 Unicode code points, stride 1600, no answer-aware chunking');
  assert.equal(built.protocol.selection_rule.includes('1 distinct documents per domain'), true);
  assert.equal(built.protocol.limits[0], '2 distinct questions, not 6 independent quality samples');
  assert.equal(Object.keys(built.chunkMap).length, built.corpus.chunks.length, '每个切片都要有映射');
  for (const item of built.cases) {
    const slices = Object.keys(built.chunkMap).filter((key) => key.startsWith(item.document_id));
    assert.equal(slices.length, 1, '短文档应只产生一个切片');
    assert.equal(built.chunkMap[slices[0]].domain, item.domain);
  }
});

test('buildArtifacts derives a new release id when the slicing changes', () => {
  const {documents, dialogues} = makeArchive();
  const sourceDir = makeSourceDir();
  const built = buildArtifacts({documents, dialogues, sourceDir, window: 8, stride: 4, perDomain: 2});
  assert.equal(built.corpus.release_id, 'doc2dial-business-benchmark-8-4-v1');
  assert.equal(built.chunking.chunking_version, 'doc2dial-codepoints-8-4-v1');
  assert.equal(built.corpus.chunks.length > 2, true);
  // 更细的切片必须让每份文档产生更多片段。
  const coarse = buildArtifacts({documents, dialogues, sourceDir, window: 2000, stride: 1600, perDomain: 2});
  assert.equal(built.corpus.chunks.length > coarse.corpus.chunks.length, true);
});

test('buildArtifacts refuses a domain that cannot fill the per-domain quota', () => {
  const {documents, dialogues} = makeArchive();
  const sourceDir = makeSourceDir();
  assert.throws(
    () => buildArtifacts({documents, dialogues, sourceDir, window: 2000, stride: 1600, perDomain: 5}),
    /可用文档不足/,
  );
});

test('compareWithFrozen detects any drift from the frozen artefacts', () => {
  const {documents, dialogues} = makeArchive();
  const sourceDir = makeSourceDir();
  const built = buildArtifacts({documents, dialogues, sourceDir, window: 2000, stride: 1600, perDomain: 1});
  const frozenDir = fs.mkdtempSync(path.join(os.tmpdir(), 'prepare-doc2dial-frozen-'));
  const write = (name, value) => fs.writeFileSync(`${frozenDir}/${name}`, `${JSON.stringify(value, null, 2)}\n`);
  write('corpus.json', built.corpus);
  write('chunk-map.json', built.chunkMap);
  write('cases.json', built.cases);
  write('protocol.json', {frozen_at: '2020-01-01T00:00:00.000Z', ...built.protocol});
  const result = compareWithFrozen(built, frozenDir);
  assert.equal(result.chunks, built.corpus.chunks.length);
  assert.equal(result.chunkingVersion, 'doc2dial-codepoints-2000-1600-v1');
  // 切片参数一变，corpus 就不再匹配。
  const drifted = buildArtifacts({documents, dialogues, sourceDir, window: 8, stride: 4, perDomain: 1});
  assert.throws(() => compareWithFrozen(drifted, frozenDir), /corpus 与冻结产物不一致/);
});

test('compareWithFrozen tolerates a frozen directory without chunking.json', () => {
  const {documents, dialogues} = makeArchive();
  const sourceDir = makeSourceDir();
  const built = buildArtifacts({documents, dialogues, sourceDir, window: 2000, stride: 1600, perDomain: 1});
  const frozenDir = fs.mkdtempSync(path.join(os.tmpdir(), 'prepare-doc2dial-old-'));
  fs.writeFileSync(`${frozenDir}/corpus.json`, `${JSON.stringify(built.corpus)}\n`);
  fs.writeFileSync(`${frozenDir}/chunk-map.json`, `${JSON.stringify(built.chunkMap)}\n`);
  fs.writeFileSync(`${frozenDir}/cases.json`, `${JSON.stringify(built.cases)}\n`);
  fs.writeFileSync(`${frozenDir}/protocol.json`, `${JSON.stringify(built.protocol)}\n`);
  assert.equal(compareWithFrozen(built, frozenDir).cases, 2);
});

test('defaultPerDomain stays at the frozen quota', () => {
  assert.equal(defaultPerDomain, 8);
});
