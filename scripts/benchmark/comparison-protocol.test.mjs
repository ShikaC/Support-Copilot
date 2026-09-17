import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {budgets,sha} from './isolated-inputs.mjs';
import {loadComparisonProtocol,comparisonClaimName} from './comparison-protocol.mjs';

const CASES_SHA='a'.repeat(64);
const COMPARISON_ID='development-comparison-fixture';
const PREFLIGHT_ID='preflight-development-comparison-fixture';

function fixture(overrides={}) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'comparison-protocol-'));
  const appDir=path.join(root,'services/support-copilot-ai/app');fs.mkdirSync(appDir,{recursive:true});
  const workflow=path.join(appDir,'workflow.py');fs.writeFileSync(workflow,'print("repaired")\n');
  const claimDir=path.join(root,'.local/quality-runs');fs.mkdirSync(claimDir,{recursive:true});
  const baseClaimPath=path.join(claimDir,`development-${CASES_SHA}.claim.json`);
  fs.writeFileSync(baseClaimPath,`${JSON.stringify({id:'base-run',casesSha:CASES_SHA,authorization:'fixture',at:'2026-09-10T00:00:00.000Z'},null,2)}\n`);
  const baseClaimSha256=sha(fs.readFileSync(baseClaimPath));
  const manifestDir=path.join(root,'docs/verification/quality-runs/base-run');fs.mkdirSync(manifestDir,{recursive:true});
  fs.writeFileSync(path.join(manifestDir,'manifest.json'),`${JSON.stringify({id:'base-run',casesSha:CASES_SHA},null,2)}\n`);
  const protocol={protocolVersion:1,comparisonId:COMPARISON_ID,preflightId:PREFLIGHT_ID,baseRunId:'base-run',baseClaimSha256,casesSha:CASES_SHA,hypothesis:'保留完整 query 上下文应改变检索',singleVariable:'仅 _build_query 由前180字符改为完整已校验标题与正文',successCriteria:['逐题 query 不再全部相同'],notAllowed:['删除或绕过 development claim'],expectedSourceHashes:{'services/support-copilot-ai/app/workflow.py':sha(fs.readFileSync(workflow))},budgets:{...budgets},holdoutCount:0,humanInputReview:'PENDING',qualityScore:null,...overrides};
  const protocolFile=path.join(root,'protocol.json');fs.writeFileSync(protocolFile,`${JSON.stringify(protocol,null,2)}\n`);
  return {root,protocolFile,workflow,baseClaimPath,claimDir,protocol};
}

function withFixture(run,overrides) {
  const fixtureRoot=fixture(overrides);
  try {return run(fixtureRoot);} finally {fs.rmSync(fixtureRoot.root,{recursive:true,force:true});}
}

const load=(f,extra={})=>loadComparisonProtocol(f.root,f.protocolFile,{casesSha:CASES_SHA,id:COMPARISON_ID,execute:false,...extra});

test('pre-registered comparison binds the existing base claim and repaired source',()=>{
  withFixture((f)=>{
    const result=load(f);
    assert.equal(result.mode,'comparison');
    assert.equal(result.protocolSha,sha(fs.readFileSync(f.protocolFile)));
    assert.equal(result.baseClaimSha256,sha(fs.readFileSync(f.baseClaimPath)));
    assert.equal(result.comparisonClaimPath,path.join(f.root,'.local/quality-runs',comparisonClaimName(COMPARISON_ID)));
  });
});

test('comparison rejects wrong run ID, dataset, and protocol version',()=>{
  withFixture((f)=>assert.throws(()=>loadComparisonProtocol(f.root,f.protocolFile,{casesSha:CASES_SHA,id:'other-run',execute:false}),/pre-registered comparisonId/));
  withFixture((f)=>assert.throws(()=>loadComparisonProtocol(f.root,f.protocolFile,{casesSha:'b'.repeat(64),id:COMPARISON_ID,execute:false}),/frozen development cases SHA/));
  withFixture((f)=>assert.throws(()=>load(f),/Unsupported comparison protocol version/),{protocolVersion:2});
});

test('comparison refuses budget, holdout, label, or score changes',()=>{
  withFixture((f)=>assert.throws(()=>load(f),/frozen runner budgets/),{budgets:{...budgets,sdkSeconds:30}});
  withFixture((f)=>assert.throws(()=>load(f),/Holdout must stay unused/),{holdoutCount:1});
  withFixture((f)=>assert.throws(()=>load(f),/pre-fill human labels/),{humanInputReview:'APPROVED'});
  withFixture((f)=>assert.throws(()=>load(f),/pre-register a quality score/),{qualityScore:0.8});
});

test('comparison fails closed on drifted source, replaced claim, or reused comparison',()=>{
  withFixture((f)=>{fs.writeFileSync(f.workflow,'print("drifted")\n');assert.throws(()=>load(f),/Source hash mismatch/);});
  withFixture((f)=>{fs.writeFileSync(f.baseClaimPath,`${JSON.stringify({id:'base-run',casesSha:CASES_SHA,authorization:'replaced',at:'2026-09-11T00:00:00.000Z'},null,2)}\n`);assert.throws(()=>load(f),/Base claim hash mismatch/);});
  withFixture((f)=>{fs.writeFileSync(path.join(f.claimDir,comparisonClaimName(COMPARISON_ID)),'{}\n');assert.throws(()=>load(f),/runs exactly once/);});
});

test('comparison protocol and expected sources stay inside the repository',()=>{
  withFixture((f)=>assert.throws(()=>loadComparisonProtocol(f.root,path.join('..','outside.json'),{casesSha:CASES_SHA,id:COMPARISON_ID,execute:false}),/escapes repository/));
  withFixture((f)=>assert.throws(()=>load(f),/Unexpected expected source path/),{expectedSourceHashes:{'/etc/hostname':'x'}});
  withFixture((f)=>assert.throws(()=>load(f),/expectedSourceHashes required/),{expectedSourceHashes:{}});
});

test('preflight IDs may prepare but never execute a paid comparison',()=>{
  withFixture((f)=>{
    assert.equal(loadComparisonProtocol(f.root,f.protocolFile,{casesSha:CASES_SHA,id:PREFLIGHT_ID,execute:false}).mode,'preflight');
    assert.throws(()=>loadComparisonProtocol(f.root,f.protocolFile,{casesSha:CASES_SHA,id:PREFLIGHT_ID,execute:true}),/Only the comparisonId may execute/);
  });
});

test('comparison rejects invalid JSON instead of guessing the protocol',()=>{
  withFixture((f)=>{fs.writeFileSync(f.protocolFile,'{not json');assert.throws(()=>load(f),/not valid JSON/);});
});

test('runner CLI refuses mixed modes before preparing a run directory',()=>{
  const result=spawnSync(process.execPath,['scripts/benchmark/run-isolated.mjs','--id','mixed-mode-contract-test','--diagnostic','--comparison','docs/verification/development-comparison-2026-09-11/protocol.json'],{cwd:process.cwd(),encoding:'utf8'});
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/Choose one of diagnostic, human-reviewed, or comparison mode/);
  assert(!fs.existsSync(path.join(process.cwd(),'docs/verification/quality-runs/mixed-mode-contract-test')));
});
