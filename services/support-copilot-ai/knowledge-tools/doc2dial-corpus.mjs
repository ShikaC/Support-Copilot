import assert from 'node:assert/strict';
import crypto from 'node:crypto';

export const defaultWindow = 2000;
export const defaultStride = 1600;
export const hash = value => crypto.createHash('sha256').update(value).digest('hex');
export const docKey = (domain, id) => `d2d-${domain}-${hash(id).slice(0, 16)}`;
const canonical = value => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) : item);

export function chunkingVersion(window, stride) {
  return `doc2dial-codepoints-${window}-${stride}-v1`;
}

export function releaseId(window, stride) {
  return window === defaultWindow && stride === defaultStride
    ? 'doc2dial-business-benchmark-v1'
    : `doc2dial-business-benchmark-${window}-${stride}-v1`;
}

export function validateSlicing(window, stride) {
  assert(Number.isSafeInteger(window) && window > 0, '窗口必须是正整数');
  assert(Number.isSafeInteger(stride) && stride > 0, '步长必须是正整数');
  assert(stride <= window, '步长不能大于窗口，否则会静默丢掉中间内容');
}

function* documentSlices(docText, window, stride) {
  const points = [...docText];
  for (let start = 0; start < points.length; start += stride) {
    const end = Math.min(start + window, points.length);
    const content = points.slice(start, end).join('').trim();
    if (content) yield {start, end, content};
    if (end === points.length) break;
  }
}

export function chunkDocument(docText, window, stride) {
  validateSlicing(window, stride);
  return [...documentSlices(docText, window, stride)];
}

export function buildCorpus({documents, window, stride}) {
  validateSlicing(window, stride);
  assert(documents && typeof documents === 'object' && !Array.isArray(documents));
  const chunks = [];
  const chunkMap = {};
  let documentCount = 0;
  let contentBytes = 0;
  for (const [domain, docs] of Object.entries(documents)) {
    assert(docs && typeof docs === 'object' && !Array.isArray(docs));
    for (const [id, doc] of Object.entries(docs)) {
      assert.equal(doc.doc_id, id);
      assert(typeof doc.title === 'string' && doc.title.trim());
      assert(typeof doc.doc_text === 'string');
      documentCount += 1;
      for (const slice of documentSlices(doc.doc_text, window, stride)) {
        contentBytes += Buffer.byteLength(slice.content);
        assert(chunks.length < 20_000 && contentBytes <= 32 * 1024 * 1024, 'corpus output budget exceeded');
        const chunkId = `${docKey(domain, id)}-${slice.start}-${slice.end}`;
        chunks.push({chunk_id: chunkId, document_id: docKey(domain, id), document_title: doc.title,
          section: `Unicode code points ${slice.start}:${slice.end}`, content: slice.content,
          source_uri: `https://doc2dial.github.io/#${encodeURIComponent(id)}`,
          categories: ['GENERAL'], keywords: [domain], allowed_scopes: ['GENERAL'],
          document_version: 'doc2dial-archive-v1.0.1', status: 'PUBLISHED', updated_at: '2021-02-26'});
        chunkMap[chunkId] = {domain, original_document_id: id, start: slice.start, end: slice.end};
      }
    }
  }
  assert(chunks.length > 0, 'empty corpus');
  return {corpus: {release_id: releaseId(window, stride), release_version: 1,
    corpus_checksum: hash(canonical(chunks)), chunks}, chunkMap, documentCount};
}
