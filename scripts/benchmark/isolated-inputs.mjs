import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import net from 'node:net';

export const auditRoot = 'docs/verification/quality-input-audit-2026-09-10';
export const corpusFile = 'docs/verification/business-benchmark-2026-09-10/corpus.json';
export const budgets = Object.freeze({sdkSeconds:20,pythonSeconds:90,javaMs:105000,clientMs:130000,batchMs:2100000,maxAnalyses:14,maxServiceAttempts:2});
export const sha = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
export const read = (file) => JSON.parse(fs.readFileSync(file,'utf8'));
export const write = (file,value) => fs.writeFileSync(file,JSON.stringify(value,null,2)+'\n',{flag:'wx'});

export function validateReview(cases, review, casesSha) {
  assert.equal(review.cases_sha256,casesSha,'Review must bind the frozen cases SHA');
  assert.equal(review.attestation,'HUMAN_INPUT_REVIEW','Human input review attestation required');
  assert(Array.isArray(review.rows),'Review rows required');
  const rows=new Map(review.rows.map(row=>[row.id,row]));
  assert.equal(rows.size,review.rows.length,'Duplicate review row');
  assert(review.rows.every(row=>cases.some(item=>item.id===row.id)),'Unknown review row');
  for(const item of cases.filter(item=>item.included && item.split==='development')) {
    const row=rows.get(item.id);assert(row,`Missing review: ${item.id}`);
    assert.equal(row.status,'APPROVED',`Pending human review: ${item.id}`);
    assert.equal(row.source_and_context_approved,true);
    assert.equal(row.required_points_approved,true);
    assert.equal(row.answerability,item.audit.label,'Changed labels require a new dataset version');
    assert(row.reference_changes===null || row.reference_changes==='','Changed references require a new dataset version');
    assert(typeof row.reviewer==='string' && row.reviewer.trim(),'Reviewer required');
    assert(typeof row.reviewed_at==='string' && /^\d{4}-\d\d-\d\dT.*Z$/.test(row.reviewed_at) && Number.isFinite(Date.parse(row.reviewed_at)) && Date.parse(row.reviewed_at)<=Date.now(),'Review needs a past/current UTC timestamp');
  }
}

export function loadInputs(root, reviewFile) {
  const resolve=file=>path.join(root,file);
  const freeze=read(resolve(`${auditRoot}/freeze-manifest.json`));
  for(const [file,digest] of Object.entries(freeze.hashes)) assert.equal(sha(fs.readFileSync(resolve(file))),digest,`Frozen input drift: ${file}`);
  const selection=read(resolve(`${auditRoot}/selection.json`));
  assert.equal(sha(fs.readFileSync(resolve(corpusFile))),selection.corpus_sha256,'Corpus drift');
  const cases=read(resolve(`${auditRoot}/cases.json`));
  const planned=cases.filter(item=>item.included && item.split==='development');
  const inputs=read(resolve(`${auditRoot}/inputs-development.json`));
  assert.deepEqual(inputs,planned.map(item=>({id:item.id,input:item.input})),'Input allowlist/projection mismatch');
  assert(inputs.length>0 && inputs.length<=budgets.maxAnalyses,'Analysis budget exceeded');
  assert.equal(new Set(inputs.map(item=>item.id)).size,inputs.length,'Duplicate input');
  const casesSha=sha(fs.readFileSync(resolve(`${auditRoot}/cases.json`)));
  let human='PENDING';
  if(reviewFile){validateReview(cases,read(reviewFile),casesSha);human='APPROVED';}
  return {inputs,casesSha,human,reviewSha:reviewFile?sha(fs.readFileSync(reviewFile)):null,corpus:read(resolve(corpusFile)),perOperationLimit:inputs.length*budgets.maxServiceAttempts,totalProviderLimit:inputs.length*budgets.maxServiceAttempts*2};
}

export function runPaths(root,id,ports) {
  assert(/^[a-z0-9][a-z0-9-]{2,63}$/.test(id),'Run ID must be 3–64 lowercase letters/digits/hyphens');
  assert.equal(new Set(ports).size,2,'API and AI ports must differ');
  for(const port of ports) assert(Number.isInteger(port) && port>=18200 && port<=18999,'Use isolated ports 18200–18999');
  return {output:path.join(root,'docs/verification/quality-runs',id),runtime:path.join(root,'.local/quality-runs',id)};
}

export async function requireFreePorts(ports) {
  const servers=[];
  try {
    for(const port of ports){const server=net.createServer();servers.push(server);await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,'127.0.0.1',resolve);});}
  } finally {await Promise.all(servers.map(server=>new Promise(resolve=>server.close(resolve))));}
}

export class LedgerCorruptError extends Error { constructor(){super('Provider ledger is corrupt; raw bytes preserved');this.name='LedgerCorruptError';} }
export function readLedger(file) {
  if(!fs.existsSync(file))return [];
  try{return fs.readFileSync(file,'utf8').split('\n').filter(Boolean).map(line=>JSON.parse(line));}
  catch(error){if(error instanceof SyntaxError)throw new LedgerCorruptError();throw error;}
}
