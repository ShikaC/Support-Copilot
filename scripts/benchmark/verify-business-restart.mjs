import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import assert from 'node:assert/strict';

const root=process.cwd();const base=path.resolve('docs/verification/business-benchmark-2026-09-10');
const runtime=path.resolve('.local/business-benchmark-runtime');
const read=(name)=>JSON.parse(fs.readFileSync(`${base}/${name}`,'utf8'));
const corpus=read('corpus.json');const manifest=read('run-1/manifest.json');
assert.equal(manifest.state,'COMPLETE_UNREVIEWED');
const trials=read('run-1/results.json');
const env={...process.env,SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN:crypto.randomBytes(32).toString('hex'),
  AI_SERVICE_BASE_URL:'http://127.0.0.1:18100',SUPPORT_COPILOT_KNOWLEDGE_CORPUS_PATH:`${base}/corpus.json`,
  KNOWLEDGE_BASELINE_RELEASE_ID:corpus.release_id,KNOWLEDGE_BASELINE_RELEASE_VERSION:'1',KNOWLEDGE_BASELINE_CORPUS_CHECKSUM:corpus.corpus_checksum};
const fd=fs.openSync(`${runtime}/restart-api.log`,'w');
const processHandle=spawn('java',['-jar','build/libs/support-copilot-api-0.0.1-SNAPSHOT.jar','--spring.profiles.active=demo',
  '--server.port=18180','--server.address=127.0.0.1','--spring.config.additional-location=classpath:workspace-defaults.properties',
  `--spring.datasource.url=jdbc:h2:file:${runtime}/database;MODE=MySQL;DB_CLOSE_ON_EXIT=FALSE`,
  '--spring.jpa.hibernate.ddl-auto=validate','--spring.flyway.enabled=true','--spring.h2.console.enabled=false','--support-copilot.demo-fixtures.enabled=false'],
  {cwd:`${root}/services/support-copilot-api`,env,stdio:['ignore',fd,fd]});fs.closeSync(fd);
const report={started_at:new Date().toISOString(),scope:'Java stopped then restarted with same isolated file H2; GET-only verification; no new model calls',records:[]};
try{
  let ready=false;
  for(let i=0;i<60;i++){
    assert.equal(processHandle.exitCode,null,'Restarted Java exited; inspect runtime log');
    try{ready=(await fetch('http://127.0.0.1:18180/actuator/health',{signal:AbortSignal.timeout(2000)})).ok;}
    catch(error){if(!(error instanceof TypeError||error.name==='TimeoutError'))throw error;}
    if(ready)break;await delay(1000);
  }
  assert(ready,'Java restart readiness timeout');
  for(const trial of trials){
    const response=await fetch(`http://127.0.0.1:18180/api/tickets/${trial.ticket_id}/analyses`,{signal:AbortSignal.timeout(10000)});
    const history=await response.json();const original=trial.stages.analyze?.body;
    const matches=response.ok&&Array.isArray(history)&&history.some(item=>item.id===original.id&&item.traceId===original.traceId
      &&item.mode===original.mode&&item.suggestedReply?.content===original.suggestedReply?.content);
    report.records.push({ticket_id:trial.ticket_id,http_status:response.status,matches});
  }
  report.passed=report.records.every(record=>record.matches);report.finished_at=new Date().toISOString();
  console.log(`Java restart readback: ${report.records.filter(record=>record.matches).length}/${report.records.length}`);
  assert(report.passed,'Stored analyses differ after restart');
}finally{
  fs.writeFileSync(`${base}/restart-verification.json`,JSON.stringify(report,null,2));
  if(processHandle.exitCode===null){processHandle.kill('SIGTERM');await new Promise(resolve=>processHandle.once('exit',resolve));}
}
