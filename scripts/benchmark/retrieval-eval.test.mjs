import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  evaluateCase,
  evaluateRun,
  goldForCase,
  goldIndex,
  normalizeHits,
  readRun,
  renderMarkdown,
  sourceAnchor,
} from './retrieval-eval.mjs';

const corpus = {
  release_id: 'test-corpus',
  release_version: 1,
  corpus_checksum: 'checksum',
  chunks: [
    {chunk_id: 'c-1', document_id: 'doc-a', source_uri: 'https://example.invalid/#Doc%20A%231_0'},
    {chunk_id: 'c-2', document_id: 'doc-a', source_uri: 'https://example.invalid/#Doc%20A%231_0'},
    {chunk_id: 'c-3', document_id: 'doc-b', source_uri: 'https://example.invalid/#Doc%20B%231_0'},
  ],
};

const cases = [
  {id: 'q-1', domain: 'dmv', split: 'development', included: true, source: {document_id: 'Doc A#1_0'}},
  {id: 'q-2', domain: 'ssa', split: 'development', included: true, source: {document_id: 'Doc B#1_0'}},
  {id: 'q-3', domain: 'gh', split: 'development', included: true, source: {issue: 1}},
  {id: 'q-4', domain: 'dmv', split: 'development', included: false, source: {document_id: 'Doc B#1_0'}},
];

function writeFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'retrieval-eval-'));
  const runDir = path.join(root, 'run');
  fs.mkdirSync(runDir);
  const casesFile = path.join(root, 'cases.json');
  const corpusFile = path.join(root, 'corpus.json');
  fs.writeFileSync(casesFile, JSON.stringify(cases));
  fs.writeFileSync(corpusFile, JSON.stringify(corpus));
  fs.writeFileSync(path.join(runDir, 'results.json'), JSON.stringify([
    {
      caseId: 'q-1', outcome: 'evidenceInsufficient',
      stages: {analyze: {body: {
        status: 'FALLBACK', mode: 'fallback', fallbackReason: 'insufficient_evidence',
        retrieval: {query: 'query one', hits: [
          {chunkId: 'c-2', documentId: 'doc-a', retrievalMethod: 'VECTOR'},
          {chunkId: 'c-3', documentId: 'doc-b', retrievalMethod: 'VECTOR'},
        ]},
      }}},
    },
    {
      caseId: 'q-2', outcome: 'evidenceInsufficient',
      stages: {analyze: {body: {
        status: 'FALLBACK', mode: 'fallback', fallbackReason: 'insufficient_evidence',
        retrieval: {query: 'query two', hits: [{chunk_id: 'c-1', document_id: 'doc-a', retrieval_method: 'VECTOR'}]},
      }}},
    },
    {
      caseId: 'q-3', outcome: 'evidenceInsufficient',
      stages: {analyze: {body: {
        status: 'FALLBACK', mode: 'fallback', fallbackReason: 'insufficient_evidence',
        retrieval: {query: 'query three', hits: [{chunkId: 'c-3', documentId: 'doc-b', retrievalMethod: 'VECTOR'}]},
      }}},
    },
  ]));
  return {root, runDir, casesFile, corpusFile};
}

test('sourceAnchor decodes the Doc2Dial document fragment', () => {
  assert.equal(sourceAnchor('https://example.invalid/#Doc%20A%231_0'), 'Doc A#1_0');
  assert.equal(sourceAnchor('https://example.invalid/'), null);
});

test('goldIndex maps anchors to corpus documents and their chunks', () => {
  const index = goldIndex(corpus);
  assert.equal(index.documentByAnchor.get('Doc A#1_0'), 'doc-a');
  assert.deepEqual([...index.chunksByDocument.get('doc-a')].sort(), ['c-1', 'c-2']);
});

test('goldForCase returns null when the case has no locatable annotation', () => {
  const index = goldIndex(corpus);
  assert.equal(goldForCase(cases[0], index).documentId, 'doc-a');
  assert.equal(goldForCase(cases[2], index), null);
});

test('normalizeHits accepts camelCase and snake_case records', () => {
  assert.deepEqual(
    normalizeHits([{chunkId: 'x', documentId: 'd', retrievalMethod: 'VECTOR'}, {chunk_id: 'y'}]).map((hit) => [hit.rank, hit.chunkId]),
    [[1, 'x'], [2, 'y']],
  );
});

test('evaluateCase reports the first gold rank and its reciprocal', () => {
  const gold = goldForCase(cases[0], goldIndex(corpus));
  const hit = evaluateCase({caseId: 'q-1', hits: [{chunkId: 'c-3'}, {chunkId: 'c-2'}], gold});
  assert.equal(hit.firstGoldRank, 2);
  assert.equal(hit.reciprocalRank, 0.5);
  const miss = evaluateCase({caseId: 'q-2', hits: [{chunkId: 'c-1'}], gold: goldForCase(cases[1], goldIndex(corpus))});
  assert.equal(miss.firstGoldRank, null);
  assert.equal(miss.reciprocalRank, 0);
});

test('evaluateRun computes recall, MRR, and distinct-query diagnostics', () => {
  const fixture = writeFixture();
  const report = evaluateRun({label: 'fixture', runDir: fixture.runDir, casesFile: fixture.casesFile, corpusFile: fixture.corpusFile});
  assert.equal(report.summary.casesPlanned, 3);
  assert.equal(report.summary.casesExcluded, 1);
  assert.equal(report.summary.casesExecuted, 3);
  assert.equal(report.summary.casesEvaluable, 2);
  assert.equal(report.summary.casesWithoutGold, 1);
  assert.equal(report.summary.goldAt1, 1);
  assert.equal(report.summary.goldAt3, 1);
  assert.equal(report.summary.goldAt10, 1);
  assert.equal(report.summary.mrr, 0.5);
  assert.equal(report.summary.distinctQueries, 3);
  assert.equal(report.summary.distinctCandidateSets, 3);
  assert.equal(report.summary.emptyResults, 0);
  assert.equal(report.summary.meanGoldChunkCount, 1.5);
  assert.equal(report.byDomain.dmv.goldAt3, 1);
  assert.equal(report.byDomain.ssa.goldAt3, 0);
  assert.equal(report.perCase.find((row) => row.caseId === 'q-2').query, 'query two');
});

test('evaluateRun flags identical queries and identical candidate sets', () => {
  const fixture = writeFixture();
  const results = JSON.parse(fs.readFileSync(path.join(fixture.runDir, 'results.json'), 'utf8'));
  for (const row of results) row.stages.analyze.body.retrieval = {query: 'same query', hits: [{chunkId: 'c-3', documentId: 'doc-b', retrievalMethod: 'VECTOR'}]};
  fs.writeFileSync(path.join(fixture.runDir, 'results.json'), JSON.stringify(results));
  const report = evaluateRun({runDir: fixture.runDir, casesFile: fixture.casesFile, corpusFile: fixture.corpusFile});
  assert.equal(report.summary.distinctQueries, 1);
  assert.equal(report.summary.distinctCandidateSets, 1);
  assert.equal(report.summary.distinctFirstCandidates, 1);
});

test('evaluateRun separates not-executed cases from evaluated ones', () => {
  const fixture = writeFixture();
  const results = JSON.parse(fs.readFileSync(path.join(fixture.runDir, 'results.json'), 'utf8'));
  const without = results.find((row) => row.caseId === 'q-1');
  delete without.stages.analyze;
  fs.writeFileSync(path.join(fixture.runDir, 'results.json'), JSON.stringify(results));
  const report = evaluateRun({runDir: fixture.runDir, casesFile: fixture.casesFile, corpusFile: fixture.corpusFile});
  assert.equal(report.summary.casesExecuted, 2);
  assert.equal(report.summary.casesNotExecuted, 1);
  assert.equal(report.summary.casesEvaluable, 1);
  assert.equal(report.summary.goldAt3, 0);
});

test('readRun rejects a directory without results.json', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'retrieval-eval-empty-'));
  assert.throws(() => readRun(root), /缺少运行结果文件/);
});

test('renderMarkdown states the offline scope and the recall definition', () => {
  const fixture = writeFixture();
  const report = evaluateRun({label: 'fixture', runDir: fixture.runDir, casesFile: fixture.casesFile, corpusFile: fixture.corpusFile});
  const markdown = renderMarkdown(report);
  assert.match(markdown, /不调用任何模型/);
  assert.match(markdown, /命中任一片段即算命中/);
  assert.match(markdown, /gold@3 \| 1\/2 \(50\.0%\)/);
});
