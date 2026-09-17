import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn,execFileSync} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';
import assert from 'node:assert/strict';
import {budgets,corpusFile,read,sha,write} from './isolated-inputs.mjs';

function relevantFiles(root) {
  const files=execFileSync('git',['ls-files','-co','--exclude-standard','-z'],{cwd:root,encoding:'utf8'}).split('\0').filter(Boolean);
  return [...new Set(files)].filter(file=>/^(services\/support-copilot-(ai|api)\/(app\/|evaluation\/[^/]+\.py$|src\/main\/|build.gradle|settings.gradle|gradle.lockfile|gradle\/|gradlew|pyproject.toml|requirements)|scripts\/(benchmark|quality)\/)/.test(file)).sort();
}
export function sourceSnapshot(root,output) {
  const hashes={};
  for(const file of relevantFiles(root)) {
    const bytes=fs.readFileSync(path.join(root,file));hashes[file]=sha(bytes);
    const destination=path.join(output,'source',file);fs.mkdirSync(path.dirname(destination),{recursive:true});fs.writeFileSync(destination,bytes,{flag:'wx'});
  }
  return hashes;
}
export function requireSource(root,hashes) {
  assert.deepEqual(relevantFiles(root),Object.keys(hashes).sort(),'Runtime source file set drift');
  for(const [file,digest] of Object.entries(hashes))assert.equal(sha(fs.readFileSync(path.join(root,file))),digest,`Runtime source drift: ${file}`);
}

export class Runtime {
  constructor(config) {
    Object.assign(this,config);this.children=[];this.apiDir=path.join(this.root,'services/support-copilot-api');this.aiDir=path.join(this.root,'services/support-copilot-ai');
    this.base=`http://127.0.0.1:${this.ports[0]}`;this.ai=`http://127.0.0.1:${this.ports[1]}`;
    this.env={...process.env,AI_MODE:'live',SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN:crypto.randomBytes(32).toString('hex'),
      AI_SERVICE_BASE_URL:this.ai,KNOWLEDGE_PATH:path.join(this.root,corpusFile),SUPPORT_COPILOT_KNOWLEDGE_CORPUS_PATH:path.join(this.root,corpusFile),
      KNOWLEDGE_BASELINE_RELEASE_ID:this.corpus.release_id,KNOWLEDGE_BASELINE_RELEASE_VERSION:String(this.corpus.release_version),KNOWLEDGE_BASELINE_CORPUS_CHECKSUM:this.corpus.corpus_checksum,
      EMBEDDING_ARTIFACT_ROOT:this.artifacts,EMBEDDING_ARTIFACT_BUILD_POLICY:'require-active',EMBEDDING_VECTOR_DIMENSION:'1024',EMBEDDING_CHUNKING_VERSION:'doc2dial-codepoints-2000-1600-v1',
      ISOLATED_BENCHMARK_OUTPUT:this.output,ISOLATED_PROVIDER_LIMIT:String(this.perOperationLimit),
      OPENAI_TIMEOUT_SECONDS:String(budgets.sdkSeconds),AI_PROCESSING_TIMEOUT_SECONDS:String(budgets.pythonSeconds),OPENAI_MAX_RETRIES:'0',
      AI_SERVICE_TIMEOUT_MS:String(budgets.javaMs),AI_SERVICE_RETRY_MAX_ATTEMPTS:'2',AI_SERVICE_RETRY_WAIT_MS:'100'};
  }
  preflight() {
    const raw=execFileSync(path.join(this.aiDir,'.venv/bin/python'),['-m','evaluation.isolated_preflight'],{cwd:this.aiDir,env:this.env,encoding:'utf8',timeout:30000,stdio:['ignore','pipe','pipe']});
    const info=JSON.parse(raw);assert.equal(info.mode,'live');assert.equal(info.sdk_seconds,budgets.sdkSeconds);assert.equal(info.python_seconds,budgets.pythonSeconds);assert.equal(info.configured_sdk_retries,0);
    assert(info.chat_base_url && info.embedding_base_url,'Explicit provider endpoints required for this benchmark');
    Object.assign(this.env,{OPENAI_CHAT_MODEL:info.model,OPENAI_EMBEDDING_MODEL:info.embedding_model,OPENAI_CHAT_PROTOCOL:info.protocol,OPENAI_BASE_URL:info.chat_base_url,OPENAI_EMBEDDING_BASE_URL:info.embedding_base_url});
    const {chat_base_url,embedding_base_url,...safe}=info;return {...safe,chatEndpointSha:sha(chat_base_url),embeddingEndpointSha:sha(embedding_base_url)};
  }
  async build() {
    const init=path.join(this.runtime,'build.gradle');
    fs.writeFileSync(init,`allprojects { afterEvaluate { tasks.named('bootJar') { destinationDirectory=file(System.getenv('ISOLATED_JAR_OUTPUT')) } } }\n`,{flag:'wx'});
    const child=this.start('./gradlew',['bootJar','--max-workers=1','--init-script',init],this.apiDir,'build.log',{ISOLATED_JAR_OUTPUT:path.join(this.runtime,'jar')});
    const code=await this.exit(child);assert.equal(code,0,'Isolated Java build failed');
    const jars=fs.readdirSync(path.join(this.runtime,'jar')).filter(name=>name.endsWith('.jar'));assert.equal(jars.length,1);
    this.jar=path.join(this.runtime,'jar',jars[0]);return sha(fs.readFileSync(this.jar));
  }
  start(command,args,cwd,log,extra={}) {
    const fd=fs.openSync(path.join(this.runtime,log),'wx',0o600);
    const child=spawn(command,args,{cwd,env:{...this.env,...extra},stdio:['ignore',fd,fd]});fs.closeSync(fd);
    child.launchError=null;child.on('error',error=>{child.launchError=error;});this.children.push(child);return child;
  }
  exit(child) {
    if(child.launchError)return Promise.reject(child.launchError);
    if(child.exitCode!==null || child.signalCode!==null)return Promise.resolve(child.exitCode);
    return new Promise((resolve,reject)=>{child.once('exit',resolve);child.once('error',reject);});
  }
  async stopChild(child) {
    if(!child || child.exitCode!==null || child.signalCode!==null || child.launchError)return;
    child.kill('SIGTERM');const timeout=setTimeout(()=>child.kill('SIGKILL'),10000);
    try {await this.exit(child);} finally {clearTimeout(timeout);}
  }
  async stop(){await Promise.all(this.children.map(child=>this.stopChild(child)));}
  startJava(log) {
    this.java=this.start('java',['-jar',this.jar,'--spring.profiles.active=demo',`--server.port=${this.ports[0]}`,'--server.address=127.0.0.1',
      '--spring.config.additional-location=classpath:workspace-defaults.properties',`--spring.datasource.url=jdbc:h2:file:${this.runtime}/database;MODE=MySQL;DB_CLOSE_ON_EXIT=FALSE`,
      '--spring.jpa.hibernate.ddl-auto=validate','--spring.flyway.enabled=true','--spring.h2.console.enabled=false','--support-copilot.demo-fixtures.enabled=false',
      '--ai.service.timeout-ms=105000','--ai.service.retry-max-attempts=2','--ai.service.retry-wait-ms=100'],this.apiDir,log);
  }
  async ready(url,child) {
    const end=Date.now()+90000;
    while(Date.now()<end){assert(!child.launchError && child.exitCode===null && child.signalCode===null,'Owned service exited');
      try {const response=await fetch(url,{signal:AbortSignal.timeout(1000)});if(response.ok)return;}catch(error){if(!(error instanceof TypeError || error.name==='TimeoutError'))throw error;}
      await delay(300);
    }throw new Error('Owned service startup deadline exceeded');
  }
  async launch() {
    this.python=this.start('.venv/bin/python',['-m','uvicorn','evaluation.isolated_benchmark_app:app','--host','127.0.0.1','--port',String(this.ports[1]),'--workers','1'],this.aiDir,'ai.log');
    this.startJava('api.log');await Promise.all([this.ready(`${this.ai}/health`,this.python),this.ready(`${this.base}/actuator/health`,this.java)]);
  }
  async restart(){await this.stopChild(this.java);this.startJava('api-restart.log');await this.ready(`${this.base}/actuator/health`,this.java);}
}
