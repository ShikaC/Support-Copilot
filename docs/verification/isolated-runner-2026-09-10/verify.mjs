import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {isDeepStrictEqual} from 'node:util';

const report='docs/verification/isolated-runner-2026-09-10';
const run='docs/verification/quality-runs/development-live-diagnostic-20260910';
const read=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const receipt=read(`${report}/verification.json`);
assert.equal(execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),receipt.head);
for(const [file,digest] of Object.entries(receipt.hashes))assert.equal(hash(file),digest,file);
const baseline=read(`${report}/workspace-before.json`);
const changed=Object.entries(baseline.hashes).filter(([file,digest])=>!fs.existsSync(file)||hash(file)!==digest).map(([file])=>file);
assert.deepEqual(changed.sort(),receipt.authorizedPreExistingChanges.slice().sort());
const source=read(`${run}/source-hashes.json`);
for(const [file,digest] of Object.entries(source)){
  assert.equal(hash(path.join(run,'source',file)),digest,`Archived source ${file}`);
  assert.equal(hash(file),digest,`Current source ${file}`);
}
const manifest=read(`${run}/manifest.json`);const summary=read(`${run}/summary.json`);
const inputs=read(`${run}/planned-inputs.json`);
assert.deepEqual(inputs,read('docs/verification/quality-input-audit-2026-09-10/inputs-development.json'));
assert.equal(inputs.length,13);assert.equal(manifest.inputHumanReview,'PENDING');assert.equal(summary.answerAccuracy,null);
assert.equal(summary.humanOutputReviewed,0);assert.equal(summary.cost,null);
const events=fs.readFileSync(`${run}/attempts.jsonl`,'utf8').trim().split('\n').map(line=>JSON.parse(line));
const starts=events.filter(row=>row.phase==='STARTED');const ends=events.filter(row=>row.phase!=='STARTED');
assert.equal(starts.length,26);assert.equal(ends.length,26);assert.equal(new Set(starts.map(row=>row.attempt_id)).size,26);
assert(ends.every(row=>row.phase==='SUCCEEDED'));assert.equal(starts.filter(row=>row.operation==='query_embedding').length,13);
assert.equal(starts.filter(row=>row.operation==='generation').length,13);
for(const start of starts){const end=ends.filter(row=>row.attempt_id===start.attempt_id);assert.equal(end.length,1);assert.equal(end[0].trace_id,start.trace_id);assert.equal(end[0].operation,start.operation);}
const restarts=read(`${run}/restart-readback.json`);assert.equal(restarts.length,13);
const queries=new Set();const candidateLists=new Set();
for(const input of inputs){
  const row=read(`${run}/trials/${input.id}.json`);const analysis=row.stages.analyze;
  assert.equal(row.state,'RECORDED');assert.equal(row.outcome,'evidenceInsufficient');assert.equal(row.error,null);
  assert.equal(analysis.status,200);assert.equal(analysis.body.mode,'fallback');assert.equal(analysis.body.status,'FALLBACK');
  assert.equal(analysis.body.fallbackReason,'insufficient_evidence');assert.equal(analysis.body.traceId,analysis.traceId);assert.equal(analysis.responseTraceId,analysis.traceId);
  assert.equal(events.filter(event=>event.trace_id===analysis.traceId&&event.phase==='STARTED').length,2);
  assert.equal(row.stages.history.status,200);assert(row.stages.history.body.some(body=>isDeepStrictEqual(body,analysis.body)));
  const restart=restarts.find(record=>record.caseId===input.id);assert(restart.matched&&restart.immediateMatched);
  assert.equal(restart.history.status,200);assert(restart.history.body.some(body=>isDeepStrictEqual(body,analysis.body)));
  const query=analysis.body.retrieval.query;assert.equal(query,`${input.input.subject} ${input.input.description.slice(0,180)}`.trim());queries.add(query);
  candidateLists.add(JSON.stringify(analysis.body.retrieval.hits.map(hit=>hit.chunkId)));
  assert(analysis.body.retrieval.hits.every(hit=>!hit.usedAsEvidence));
}
assert.equal(queries.size,1);assert.equal(candidateLists.size,1);
assert.deepEqual(summary.normalOutcomes,{normalLive:0,evidenceInsufficient:13,timeout:0,otherFallback:0,error:0});
console.log(JSON.stringify({status:'PASS',head:receipt.head,dirty:!!execFileSync('git',['status','--porcelain'],{encoding:'utf8'}).trim(),protectedPreExistingFiles:Object.keys(baseline.hashes).length,authorizedChanged:changed,receiptFiles:Object.keys(receipt.hashes).length,runtimeSources:Object.keys(source).length,realQueries:13,realGenerations:13,normalLive:0,evidenceInsufficient:13,fullImmediateMatches:13,fullRestartMatches:13,uniqueQueries:1,qualityScores:'UNMEASURED'},null,2));
