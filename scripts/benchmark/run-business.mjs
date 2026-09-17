import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import assert from 'node:assert/strict';

const root = process.cwd();
const evidence = path.resolve('docs/verification/business-benchmark-2026-09-10');
const runtime = path.resolve('.local/business-benchmark-runtime');
const run = `${evidence}/run-1`;
fs.mkdirSync(run);
fs.mkdirSync(`${run}/retrieval`); fs.mkdirSync(`${run}/trials`);
const read = (name) => JSON.parse(fs.readFileSync(`${evidence}/${name}`, 'utf8'));
const cases = read('cases.json'); const corpus = read('corpus.json'); const protocol = read('protocol.json');
const base = 'http://127.0.0.1:18180';
const ai = 'http://127.0.0.1:18100';
for (const url of [base, ai]) {
  let occupied = false;
  try { await fetch(url, { signal: AbortSignal.timeout(1000) }); occupied = true; }
  catch (error) { if (!(error instanceof TypeError || error.name === 'TimeoutError')) throw error; }
  assert(!occupied, `Benchmark port is occupied: ${url}`);
}
const env = { ...process.env, SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN: crypto.randomBytes(32).toString('hex'),
  AI_MODE:'live', AI_SERVICE_BASE_URL:ai, KNOWLEDGE_PATH:`${evidence}/corpus.json`,
  SUPPORT_COPILOT_KNOWLEDGE_CORPUS_PATH:`${evidence}/corpus.json`,
  KNOWLEDGE_BASELINE_RELEASE_ID:corpus.release_id, KNOWLEDGE_BASELINE_RELEASE_VERSION:'1',
  KNOWLEDGE_BASELINE_CORPUS_CHECKSUM:corpus.corpus_checksum,
  EMBEDDING_ARTIFACT_ROOT:`${runtime}/artifacts`, EMBEDDING_VECTOR_DIMENSION:'1024',
  EMBEDDING_CHUNKING_VERSION:'doc2dial-codepoints-2000-1600-v1', BENCHMARK_RETRIEVAL_OUTPUT:`${run}/retrieval` };
const hashFile = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const manifest = { started_at:new Date().toISOString(), state:'STARTING', planned:protocol.planned_analysis_requests,
  concurrency:protocol.planned_concurrency, host:{os:os.type(),release:os.release(),arch:os.arch(),cpu:os.cpus()[0]?.model,logical_cpus:os.cpus().length,memory_bytes:os.totalmem()},
  runtime:{node:process.version,java_profile:'demo',database:'isolated file H2 / MySQL compatibility / Flyway',api_port:18180,ai_port:18100,
    sdk_retries:0,client_retries:0,java_service_max_attempts:2,client_deadline_ms:130000,observation:'writes live retrieval snapshot before generation; small disk overhead included'},
  jar_sha256:hashFile('services/support-copilot-api/build/libs/support-copilot-api-0.0.1-SNAPSHOT.jar'),
  corpus_sha256:hashFile(`${evidence}/corpus.json`),cases_sha256:hashFile(`${evidence}/cases.json`),
  scope:'local Java API create → Python production workflow → live providers → analysis persistence → GET history; excludes browser rendering and human review/issue resolution',
  groups:[] };
const writeManifest = () => fs.writeFileSync(`${run}/manifest.json`, JSON.stringify(manifest,null,2));
writeManifest();
const children = [];
const start = (command,args,cwd,log) => {
  const fd=fs.openSync(`${runtime}/${log}`,'w');
  const child=spawn(command,args,{cwd,env,stdio:['ignore',fd,fd]}); fs.closeSync(fd); children.push(child); return child;
};
const stop = () => { for(const child of children) if(child.exitCode===null) child.kill('SIGTERM'); };
process.on('SIGINT',stop); process.on('SIGTERM',stop); process.on('exit',stop);

async function request(route, body) {
  const started=performance.now();
  const response=await fetch(`${base}${route}`,{method:body===undefined?'GET':'POST',
    headers:body===undefined?{}:{'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},
    body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(130000)});
  const text=await response.text();
  return {status:response.status,ms:performance.now()-started,body:JSON.parse(text)};
}

async function trial(item,concurrency) {
  const record={case_id:item.id,concurrency,started_at:new Date().toISOString(),stages:{},error:null};
  const started=performance.now();
  try {
    record.stages.create=await request('/api/tickets',{channel:'WEB_FORM',customerName:'Public benchmark',customerCompany:'Offline evaluation',customerTier:'STANDARD',
      language:'en',subject:item.question.slice(0,200),description:`${item.question}\n\nThis is an offline evaluation using archived documents. Answer from the supplied archive; do not claim current policy was verified.`});
    if(record.stages.create.status!==201) {record.error='CREATE_HTTP_ERROR';return record;}
    record.ticket_id=record.stages.create.body.id;
    record.stages.analyze=await request(`/api/tickets/${record.ticket_id}/analyze`,{});
    record.create_to_analysis_ms=performance.now()-started;
    record.stages.history=await request(`/api/tickets/${record.ticket_id}/analyses`);
    record.total_with_readback_ms=performance.now()-started;
    record.persisted=record.stages.history.status===200 && Array.isArray(record.stages.history.body)
      && record.stages.history.body.some(entry=>entry.id===record.stages.analyze.body.id && entry.traceId===record.stages.analyze.body.traceId
        && entry.mode===record.stages.analyze.body.mode && entry.suggestedReply?.content===record.stages.analyze.body.suggestedReply?.content);
    if(record.stages.analyze.status!==200) record.error='ANALYZE_HTTP_ERROR';
    else if(!record.persisted) record.error='PERSISTENCE_MISMATCH';
  } catch(error) {
    if(!(error instanceof TypeError || error.name==='TimeoutError')) throw error;
    record.error=error.name==='TimeoutError'?'CLIENT_TIMEOUT':'CLIENT_TRANSPORT_ERROR';
    record.total_with_readback_ms=performance.now()-started;
  } finally {
    fs.writeFileSync(`${run}/trials/c${concurrency}-${item.id}.json`,JSON.stringify(record,null,2));
    console.log(`c=${concurrency} ${item.id} ${record.error??record.stages.analyze?.body.mode??'incomplete'} ${Math.round(record.create_to_analysis_ms??record.total_with_readback_ms??0)}ms`);
  }
  return record;
}

try {
  start('.venv/bin/python',['-m','uvicorn','evaluation.business_benchmark_app:app','--host','127.0.0.1','--port','18100'],`${root}/services/support-copilot-ai`,'ai.log');
  start('java',['-jar','build/libs/support-copilot-api-0.0.1-SNAPSHOT.jar','--spring.profiles.active=demo','--server.port=18180','--server.address=127.0.0.1',
    '--spring.config.additional-location=classpath:workspace-defaults.properties',`--spring.datasource.url=jdbc:h2:file:${runtime}/database;MODE=MySQL;DB_CLOSE_ON_EXIT=FALSE`,
    '--spring.jpa.hibernate.ddl-auto=validate','--spring.flyway.enabled=true','--spring.h2.console.enabled=false','--support-copilot.demo-fixtures.enabled=false'],`${root}/services/support-copilot-api`,'api.log');
  let ready=false;
  for(let i=0;i<60;i++) {
    assert(children.every(child=>child.exitCode===null),'Benchmark service exited; see runtime logs');
    try {const responses=await Promise.all([fetch(`${base}/actuator/health`),fetch(`${ai}/health`)]);ready=responses.every(response=>response.ok);}
    catch(error) {if(!(error instanceof TypeError))throw error;}
    if(ready)break; await delay(1000);
  }
  assert(ready,'Benchmark service startup timeout');
  manifest.health=await (await fetch(`${ai}/health`)).json();
  assert.equal(manifest.health.mode,'live');
  manifest.state='RUNNING';writeManifest();
  const results=[];
  for(const concurrency of protocol.planned_concurrency) {
    const started=performance.now();let cursor=0;const group=[];
    async function worker(){while(cursor<cases.length){const item=cases[cursor++];group.push(await trial(item,concurrency));}}
    await Promise.all(Array.from({length:concurrency},worker));
    const duration_ms=performance.now()-started;results.push(...group);
    manifest.groups.push({concurrency,count:group.length,duration_ms,completion_throughput_per_second:group.length/(duration_ms/1000)});writeManifest();
  }
  fs.writeFileSync(`${run}/results.json`,JSON.stringify(results,null,2));
  manifest.state='COMPLETE_UNREVIEWED';manifest.finished_at=new Date().toISOString();writeManifest();
} finally {
  stop();await Promise.all(children.filter(child=>child.exitCode===null).map(child=>new Promise(resolve=>child.once('exit',resolve))));
}
