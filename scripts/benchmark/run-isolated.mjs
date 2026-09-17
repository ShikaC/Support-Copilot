import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {parseArgs} from 'node:util';
import {execFileSync} from 'node:child_process';
import {auditRoot,budgets,loadInputs,read,readLedger,requireFreePorts,runPaths,sha,write} from './isolated-inputs.mjs';
import {Runtime,sourceSnapshot,requireSource} from './isolated-runtime.mjs';
import {ledgerSummary,runBatch,restartReadback,request} from './isolated-engine.mjs';
import {loadComparisonProtocol} from './comparison-protocol.mjs';

const {values}=parseArgs({options:{id:{type:'string'},execute:{type:'boolean'},diagnostic:{type:'boolean'},review:{type:'string'},comparison:{type:'string'},'api-port':{type:'string',default:'18280'},'ai-port':{type:'string',default:'18200'},help:{type:'boolean'}},strict:true});
if(values.help){console.log('node scripts/benchmark/run-isolated.mjs --id <new-id> [--execute --diagnostic | --execute --review <human.json> | --execute --comparison <protocol.json>] [--api-port 18280 --ai-port 18200]\nDefault: offline preparation only. One fixed development batch; no resume/overwrite.');process.exit(0);}
const root=process.cwd();assert(values.id,'--id required');
const ports=[Number(values['api-port']),Number(values['ai-port'])];const paths=runPaths(root,values.id,ports);
const inputs=loadInputs(root,values.review?path.resolve(values.review):null);
assert([values.diagnostic,Boolean(values.review),Boolean(values.comparison)].filter(Boolean).length<=1,'Choose one of diagnostic, human-reviewed, or comparison mode');
const comparison=values.comparison?loadComparisonProtocol(root,values.comparison,{casesSha:inputs.casesSha,id:values.id,execute:Boolean(values.execute)}):null;
if(values.execute)assert(inputs.human==='APPROVED' || values.diagnostic || comparison,'Human review pending; explicitly authorize diagnostic-only execution');
await requireFreePorts(ports);
assert(!fs.existsSync(paths.output) && !fs.existsSync(paths.runtime),'Run ID already exists; no resume or overwrite');
fs.mkdirSync(path.dirname(paths.output),{recursive:true});fs.mkdirSync(paths.output);
fs.mkdirSync(path.dirname(paths.runtime),{recursive:true});fs.mkdirSync(paths.runtime,{mode:0o700});
for(const name of ['trials','retrieval'])fs.mkdirSync(path.join(paths.output,name));
const originals=path.join(root,'.local/business-benchmark-runtime/artifacts');const artifactRoot=path.join(paths.runtime,'artifacts');
const pointer=read(path.join(originals,'active.json'));assert(/^[a-f0-9]{64}$/.test(pointer.active_artifact_id));
fs.mkdirSync(artifactRoot);fs.copyFileSync(path.join(originals,'active.json'),path.join(artifactRoot,'active.json'),fs.constants.COPYFILE_EXCL);
fs.cpSync(path.join(originals,pointer.active_artifact_id),path.join(artifactRoot,pointer.active_artifact_id),{recursive:true,errorOnExist:true,force:false});
const artifactHashes={};for(const file of ['active.json',...['manifest.json','metadata.json','matrix.npy'].map(name=>`${pointer.active_artifact_id}/${name}`)])artifactHashes[file]=sha(fs.readFileSync(path.join(artifactRoot,file)));
const sourceHashes=sourceSnapshot(root,paths.output);write(path.join(paths.output,'source-hashes.json'),sourceHashes);
write(path.join(paths.output,'planned-inputs.json'),inputs.inputs);
const runtime=new Runtime({root,...paths,ports,corpus:inputs.corpus,artifacts:artifactRoot,perOperationLimit:inputs.perOperationLimit});
const manifest={id:values.id,state:'PREPARING',startedAt:new Date().toISOString(),head:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),dirty:Boolean(execFileSync('git',['status','--porcelain'],{encoding:'utf8'}).trim()),
  evidenceKind:values.diagnostic?'LIVE_DIAGNOSTIC_UNREVIEWED':comparison?(values.execute?'DEVELOPMENT_COMPARISON_UNREVIEWED':'PREPARATION_UNREVIEWED'):inputs.human==='APPROVED'?'HUMAN_INPUT_REVIEWED_OUTPUT_UNREVIEWED':'PREPARATION_UNREVIEWED',inputHumanReview:inputs.human,answerAccuracy:null,outputHumanReviewed:0,cost:null,
  comparison:comparison?{protocolFile:comparison.protocolFile,protocolSha:comparison.protocolSha,mode:comparison.mode,baseRunId:comparison.protocol.baseRunId,baseClaimSha256:comparison.baseClaimSha256,singleVariable:comparison.protocol.singleVariable,hypothesis:comparison.protocol.hypothesis,successCriteria:comparison.protocol.successCriteria}:null,
  casesSha:inputs.casesSha,reviewSha:inputs.reviewSha,plannedCount:inputs.inputs.length,concurrency:1,holdoutCount:0,budgets:{...budgets,perOperationLimit:inputs.perOperationLimit,totalProviderLimit:inputs.totalProviderLimit},
  sdkRetries:0,clientRetries:0,ports,database:'isolated file H2 / Flyway / no fixture tickets',artifactHashes,sourceHashesFile:'source-hashes.json',attemptMeaning:'SDK operation invocation; remote receipt and billing unknown',stopReason:null};
function save(){const file=path.join(paths.output,'manifest.json');fs.writeFileSync(`${file}.tmp`,JSON.stringify(manifest,null,2)+'\n');fs.renameSync(`${file}.tmp`,file);}
save();
const controller=new AbortController();const abort=()=>{controller.abort();void runtime.stop();};
process.on('SIGINT',abort);process.on('SIGTERM',abort);
let timer;
try {
  manifest.preflight=runtime.preflight();save();
  if(values.execute){
    timer=setTimeout(abort,budgets.batchMs);
    manifest.jarSha=await runtime.build();requireSource(root,sourceHashes);save();
    await runtime.launch();
    const empty=await request(runtime.base,'/api/tickets',{signal:controller.signal});
    assert.equal(empty.status,200);assert.deepEqual(empty.body,[],'Isolated database must contain no fixture tickets');
    requireSource(root,sourceHashes);
    const claim=comparison?comparison.comparisonClaimPath:path.join(root,'.local/quality-runs',`development-${inputs.casesSha}.claim.json`);
    write(claim,comparison?{id:values.id,comparisonId:comparison.protocol.comparisonId,casesSha:inputs.casesSha,protocolFile:comparison.protocolFile,protocolSha:comparison.protocolSha,baseRunId:comparison.protocol.baseRunId,baseClaimSha256:comparison.baseClaimSha256,singleVariable:comparison.protocol.singleVariable,at:new Date().toISOString()}:{id:values.id,casesSha:inputs.casesSha,authorization:values.diagnostic?'User authorized unreviewed diagnostic; no semantic score':'Human input review provided',at:new Date().toISOString()});
    manifest.state='RUNNING';save();
    const context={base:runtime.base,output:paths.output,inputs:inputs.inputs,signal:controller.signal,perOperationLimit:inputs.perOperationLimit,totalProviderLimit:inputs.totalProviderLimit,checkSource:()=>requireSource(root,sourceHashes)};
    const batch=await runBatch(context);manifest.stopReason=batch.stopped;manifest.state=batch.stopped?'STOPPED':'MEASURED_UNREVIEWED';save();
    if(!controller.signal.aborted){requireSource(root,sourceHashes);await runtime.restart();manifest.restart=await restartReadback(context,batch.records);}
    requireSource(root,sourceHashes);
    manifest.attempts=ledgerSummary(readLedger(path.join(paths.output,'attempts.jsonl')));
    if(batch.stopped)process.exitCode=2;
  }else{manifest.state='PREPARED_NO_CALLS';manifest.attempts={queryEmbedding:0,generation:0,documentEmbedding:0};}
} catch(error) {
  manifest.state='STOPPED';manifest.stopReason??=error instanceof assert.AssertionError?error.message:controller.signal.aborted?'BATCH_ABORTED':`RUNNER_${error.name}`;
  process.exitCode=1;
} finally {
  clearTimeout(timer);await runtime.stop();process.off('SIGINT',abort);process.off('SIGTERM',abort);
  if(values.execute){
    for(const item of inputs.inputs){const file=path.join(paths.output,'trials',`${item.id}.json`);if(!fs.existsSync(file))write(file,{caseId:item.id,state:'NOT_EXECUTED',reason:manifest.stopReason??'NOT_STARTED'});}
    try {
      manifest.attempts=ledgerSummary(readLedger(path.join(paths.output,'attempts.jsonl')));
      if(manifest.attempts.unknownInterrupted>0){manifest.state='STOPPED';manifest.stopReason??='UNKNOWN_IN_FLIGHT';process.exitCode??=2;}
    }catch(error){manifest.state='STOPPED';manifest.stopReason='LEDGER_CORRUPT';manifest.attempts=null;process.exitCode=1;}
  }
  manifest.finishedAt=new Date().toISOString();save();
  console.log(JSON.stringify({id:manifest.id,state:manifest.state,stopReason:manifest.stopReason,planned:manifest.plannedCount,attempts:manifest.attempts,output:path.relative(root,paths.output)}));
}
