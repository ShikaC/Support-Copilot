import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import test from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import * as chunker from './prepare-doc2dial.mjs';

test('corpus generation needs documents only and preserves Unicode chunk identities', () => {
  // Given: documents without evaluation dialogues or an evaluation quota.
  const documents = {dmv: {sample: {doc_id: 'sample', title: 'Example', doc_text: 'A😀BCDE'}}};
  assert.equal(typeof chunker.buildCorpus, 'function');
  // When: the shared generator slices Unicode code points with overlap.
  const result = chunker.buildCorpus({documents, window: 4, stride: 3});
  const id = `d2d-dmv-${createHash('sha256').update('sample').digest('hex').slice(0, 16)}`;
  // Then: identity and content retain the existing chunking contract, with no cases.
  assert.equal(result.corpus.release_id, 'doc2dial-business-benchmark-4-3-v1');
  assert.deepEqual(result.corpus.chunks.map(c => [c.chunk_id, c.content]), [
    [`${id}-0-4`, 'A😀BC'], [`${id}-3-6`, 'CDE'],
  ]);
  assert.equal(result.cases, undefined);
});

test('fixed CLI refuses malformed input and never overwrites an existing candidate', () => {
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'corpus-cli-'));
  const script = new URL('../../services/support-copilot-ai/knowledge-tools/build-corpus.mjs', import.meta.url);
  const run = input => spawnSync(process.execPath, [script.pathname, '4', '3', output], {input, encoding: 'utf8'});
  try {
    for (const input of ['private-document-canary', '{}', '{"doc_data":{}}', Buffer.from([0xff])]) {
      const failed = run(input);
      assert.equal(failed.status, 1);
      assert.equal(failed.stderr.trim(), 'CORPUS_GENERATION_FAILED');
      assert.deepEqual(fs.readdirSync(output), []);
    }
    const source = JSON.stringify({doc_data: {dmv: {sample: {doc_id: 'sample', title: 'Example', doc_text: 'A😀BCDE'}}}});
    assert.equal(run(source).status, 0);
    const first = fs.readFileSync(path.join(output, 'corpus.json'));
    assert.equal(run(source).status, 1);
    assert.deepEqual(fs.readFileSync(path.join(output, 'corpus.json')), first);
    assert.deepEqual(fs.readdirSync(output).sort(), ['chunk-map.json', 'chunking.json', 'corpus.json', 'manifest.json']);
  } finally {
    fs.rmSync(output, {recursive: true, force: true});
  }
});

test('overlapping windows cannot expand a small document beyond the output budget', () => {
  const documents = {dmv: {sample: {doc_id: 'sample', title: 'Example', doc_text: 'x'.repeat(21000)}}};
  assert.throws(() => chunker.buildCorpus({documents, window: 1, stride: 1}), /output budget/);
});
