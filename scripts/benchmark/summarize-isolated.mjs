import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {read,write,readLedger,sha} from './isolated-inputs.mjs';
import {ledgerSummary} from './isolated-engine.mjs';
import {countOutcomes,outcome} from '../quality/report-outcomes.mjs';

const root=process.cwd();const id=process.argv[2];assert(id && /^[a-z0-9][a-z0-9-]{2,63}$/.test(id),'Run ID required');
const dir=path.join(root,'docs/verification/quality-runs',id);const manifest=read(`${dir}/manifest.json`);assert(['MEASURED_UNREVIEWED','STOPPED'].includes(manifest.state),'Run is not terminal');
const inputs=read(`${dir}/planned-inputs.json`);const records=inputs.map(item=>read(`${dir}/trials/${item.id}.json`));
const events=readLedger(`${dir}/attempts.jsonl`);const attempts=ledgerSummary(events);
assert.equal(inputs.length,manifest.plannedCount);assert.equal(new Set(records.map(row=>row.caseId)).size,inputs.length);
const analyzed=records.filter(row=>row.stages?.analyze?.status===200);
for(const row of analyzed){const response=row.stages.analyze.body;assert.equal(row.outcome,outcome({status:response.status,mode:response.mode,reason:response.fallbackReason}));}
const elapsed=records.map(row=>row.createToAnalysisMs).filter(value=>Number.isFinite(value)).sort((a,b)=>a-b);
const percentile=fraction=>elapsed.length?elapsed[Math.max(0,Math.ceil(elapsed.length*fraction)-1)]:null;
const summary={id,state:manifest.state,stopReason:manifest.stopReason,planned:inputs.length,executed:records.filter(row=>row.state!=='NOT_EXECUTED').length,
  notExecuted:records.filter(row=>row.state==='NOT_EXECUTED').length,apiCompleted:analyzed.length,normalOutcomes:countOutcomes(analyzed),
  runnerErrors:records.filter(row=>row.error).map(row=>({id:row.caseId,error:row.error})),immediateReadbackMatched:records.filter(row=>row.persisted).length,
  restart:manifest.restart??null,attempts,latency:{scope:'create through analysis response, including save/fallback/timeout; history separate',samples:elapsed.length,p50Ms:percentile(.5),p95Ms:percentile(.95),method:'nearest-rank'},
  humanInputReview:manifest.inputHumanReview,humanOutputReviewed:0,answerAccuracy:null,resolutionRate:null,timeSaved:null,cost:null,
  knownResponseTokens:{scope:'Only responses with a successfully completed generation operation; timeout/cancel/remote billing usage unknown',input:0,output:0,responses:0}};
for(const row of analyzed){if(events.some(event=>event.trace_id===row.stages.analyze.body.traceId && event.operation==='generation' && event.phase==='SUCCEEDED')){const usage=row.stages.analyze.body.usage;summary.knownResponseTokens.input+=usage.inputTokens;summary.knownResponseTokens.output+=usage.outputTokens;summary.knownResponseTokens.responses++;}}
const quote=text=>String(text??'').split('\n').map(line=>'> '+line.replaceAll('<','&lt;').replaceAll('>','&gt;')).join('\n');
const lines=[`# ${id} 真实调用诊断`, '', '固定公开输入；真实模型与Embedding；未经真人质量审核。正常生成不是回答正确，未执行仍保留在计划分母中。', '', '```json',JSON.stringify(summary,null,2),'```',''];
for(const [index,item] of inputs.entries()){
 const row=records[index];const response=row.stages?.analyze?.body;
 lines.push(`## ${index+1}. ${item.id}`,'',`状态：${row.state}；产出：${row.outcome??'无'}；错误/停止：${row.error??row.reason??'无'}`,'','### 原始输入','',quote(item.input.description),'','### 实际回答','',quote(response?.suggestedReply?.content??'本次没有取得回答。'),'');
 if(response?.traceId)lines.push(`Trace：\`${response.traceId}\`；fallbackReason：\`${response.fallbackReason??'null'}\``,'');
 for(const hit of response?.retrieval?.hits??[])lines.push(`### 实际返回依据：${hit.chunkId}`,'',`采用为证据：${hit.usedAsEvidence}；来源：${hit.sourceUri}`,'',quote(hit.content),'');
}
write(`${dir}/summary.json`,summary);fs.writeFileSync(`${dir}/RESULTS.md`,lines.join('\n'),{flag:'wx'});
write(`${dir}/output-review-working.json`,{runId:id,manifestSha:sha(fs.readFileSync(`${dir}/manifest.json`)),instructions:'真人逐题检查实际回答和实际采用证据；AI不得代填。输入仍待确认时不能发布语义分数。',rows:records.map(row=>({caseId:row.caseId,status:'NOT_REVIEWED',reviewer:null,reviewedAt:null,factualSupport:null,requestCompleted:null,note:null}))});
console.log(JSON.stringify(summary,null,2));
