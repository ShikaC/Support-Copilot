import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {isMainThread, Worker} from 'node:worker_threads';
import {buildCorpus, chunkingVersion, hash} from './doc2dial-corpus.mjs';

// The Python owner supplies an immutable source snapshot on stdin and a fresh task directory.
try {
  assert(process.argv.length === 5 || process.argv.length === 6);
  const [windowArg, strideArg, output, timeoutArg = '60'] = process.argv.slice(2);
  const window = Number(windowArg);
  const stride = Number(strideArg);
  assert(window <= 8000);
  const timeout = Number(timeoutArg);
  assert(Number.isFinite(timeout) && timeout > 0 && timeout <= 120);
  if (isMainThread) {
    // Keep this event loop responsive even if parsing/slicing blocks its worker.
    // The inherited flock stays open until the whole Node process exits, including after Python dies.
    const timer = setTimeout(() => process.exit(124), timeout * 1000);
    const worker = new Worker(new URL(import.meta.url), {argv: process.argv.slice(2)});
    worker.on('error', () => {
      console.error('CORPUS_GENERATION_FAILED');
      process.exitCode = 1;
    });
    worker.on('exit', code => {
      clearTimeout(timer);
      process.exitCode = code || process.exitCode || 0;
    });
  } else {
    const source = fs.readFileSync(0);
    assert(source.length > 0 && source.length <= 64 * 1024 * 1024);
    const {corpus, chunkMap, documentCount} = buildCorpus({
      documents: JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(source)).doc_data, window, stride,
    });
    const write = (name, value) => {
      const content = `${JSON.stringify(value, null, 2)}\n`;
      assert(Buffer.byteLength(content) <= 64 * 1024 * 1024, 'output file budget exceeded');
      fs.writeFileSync(path.join(output, name), content, {flag: 'wx'});
    };
    write('corpus.json', corpus);
    write('chunk-map.json', chunkMap);
    write('chunking.json', {chunking_version: chunkingVersion(window, stride), release_id: corpus.release_id,
      window, stride, source: 'doc2dial doc_text, Unicode code points'});
    write('manifest.json', {sourceChecksum: hash(source), corpusChecksum: corpus.corpus_checksum,
      corpusFileChecksum: hash(fs.readFileSync(path.join(output, 'corpus.json'))),
      documentCount, chunkCount: corpus.chunks.length, window, stride});
  }
} catch {
  // Raw parser/OS errors may contain document text or local paths.
  console.error('CORPUS_GENERATION_FAILED');
  process.exitCode = 1;
}
