import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {isDeepStrictEqual} from 'node:util';
import {randomUUID} from 'node:crypto';
import {budgets,readLedger,write} from './isolated-inputs.mjs';
import {outcome} from '../quality/report-outcomes.mjs';

export async function request(base, route, options={}) {
  const started=performance.now();const traceId=`trace_${randomUUID().replaceAll('-','').slice(0,20)}`;
  const response=await fetch(`${base}${route}`,{method:options.body===undefined?'GET':'POST',redirect:'error',
    headers:{'Content-Type':'application/json','Idempotency-Key':randomUUID(),'X-Trace-Id':traceId},
    body:options.body===undefined?undefined:JSON.stringify(options.body),signal:options.signal?AbortSignal.any([options.signal,AbortSignal.timeout(budgets.clientMs)]):AbortSignal.timeout(budgets.clientMs)});
  const body=await response.json();return {status:response.status,traceId,responseTraceId:response.headers.get('x-trace-id'),ms:performance.now()-started,body};
}
export function matches(response,history) {
  return response.status===200 && history.status===200 && Array.isArray(history.body)
    && history.body.some(item=>isDeepStrictEqual(item,response.body));
}
export function ledgerSummary(events) {
  const starts=events.filter(event=>event.phase==='STARTED');
  const ends=new Map(events.filter(event=>event.phase!=='STARTED').map(event=>[event.attempt_id,event]));
  assert.equal(new Set(starts.map(event=>event.attempt_id)).size,starts.length,'Duplicate attempt ID');
  assert.equal(ends.size,events.length-starts.length,'Duplicate attempt completion');
  assert([...ends.keys()].every(id=>starts.some(event=>event.attempt_id===id)),'Completion without start');
  return {queryEmbedding:starts.filter(event=>event.operation==='query_embedding').length,generation:starts.filter(event=>event.operation==='generation').length,
    documentEmbedding:0,unknownInterrupted:starts.filter(event=>!ends.has(event.attempt_id)||ends.get(event.attempt_id).phase==='UNKNOWN_INTERRUPTED').length,
    remoteReceived:null,cost:null};
}
export function stopReason(record,events) {
  if(record.error)return record.error;
  if(events.some(event=>[401,403,429].includes(event.http_status)))return 'PROVIDER_AUTH_OR_QUOTA';
  if(events.some(event=>event.phase==='FAILED' && event.unknown_error===true))return 'UNKNOWN_PROVIDER_PROGRAM_ERROR';
  if(record.outcome==='error')return 'UNKNOWN_AI_OUTCOME';
  return null;
}
export async function executeTrial(context,item) {
  const record={caseId:item.id,state:'STARTED',error:null,outcome:null,stages:{},persisted:false};
  const started=performance.now();
  try {
    record.stages.create=await request(context.base,'/api/tickets',{signal:context.signal,body:{channel:'WEB_FORM',customerName:'Public diagnostic',customerCompany:'Archived public input',customerTier:'STANDARD',language:'en',...item.input}});
    if(record.stages.create.status!==201){record.error='CREATE_HTTP_ERROR';return record;}
    record.ticketId=record.stages.create.body.id;
    assert(typeof record.ticketId==='string' && /^[A-Za-z0-9_-]+$/.test(record.ticketId),'Invalid ticket ID');
    record.stages.analyze=await request(context.base,`/api/tickets/${record.ticketId}/analyze`,{body:{},signal:context.signal});
    record.createToAnalysisMs=performance.now()-started;
    const analysis=record.stages.analyze;
    if(analysis.status!==200){record.error='ANALYZE_HTTP_ERROR';return record;}
    if(analysis.body.traceId!==analysis.traceId || analysis.responseTraceId!==analysis.traceId){record.error='TRACE_MISMATCH';return record;}
    record.outcome=outcome({status:analysis.body.status,mode:analysis.body.mode,reason:analysis.body.fallbackReason});
    record.stages.history=await request(context.base,`/api/tickets/${record.ticketId}/analyses`,{signal:context.signal});
    record.persisted=matches(analysis,record.stages.history);
    if(!record.persisted)record.error='PERSISTENCE_MISMATCH';
  } catch(error) {
    record.error=error.name==='TimeoutError'?'CLIENT_TIMEOUT':error.name==='AbortError'?'BATCH_ABORTED':error instanceof TypeError?'TRANSPORT_ERROR':'UNKNOWN_PROGRAM_ERROR';
    if(record.error==='UNKNOWN_PROGRAM_ERROR')throw error;
  } finally {
    record.totalWithReadbackMs=performance.now()-started;record.state=record.error?'FAILED':'RECORDED';
    write(path.join(context.output,'trials',`${item.id}.json`),record);
  }
  return record;
}
export async function runBatch(context) {
  const records=[];let consecutive=0;let stopped=null;
  for(const item of context.inputs) {
    if(stopped || context.signal.aborted){stopped??='BATCH_ABORTED';const row={caseId:item.id,state:'NOT_EXECUTED',reason:stopped};records.push(row);write(path.join(context.output,'trials',`${item.id}.json`),row);continue;}
    context.checkSource();
    const row=await executeTrial(context,item);records.push(row);
    const events=readLedger(path.join(context.output,'attempts.jsonl'));const count=ledgerSummary(events);
    assert(count.queryEmbedding<=context.perOperationLimit && count.generation<=context.perOperationLimit,'Provider budget exceeded');
    assert(count.queryEmbedding+count.generation<=context.totalProviderLimit,'Total provider budget exceeded');
    if(row.stages.analyze?.status===200){
      const relevant=events.filter(event=>event.trace_id===row.stages.analyze.body.traceId);
      if(!relevant.some(event=>event.phase==='STARTED' && event.operation==='query_embedding'))stopped='ATTEMPT_TRACE_MISSING';
    }
    stopped??=stopReason(row,events);
    consecutive=['timeout','otherFallback'].includes(row.outcome)?consecutive+1:0;
    if(consecutive>=3)stopped??='THREE_CONSECUTIVE_DEPENDENCY_FAILURES';
    console.log(JSON.stringify({caseId:item.id,state:row.state,outcome:row.outcome,error:row.error,ms:Math.round(row.createToAnalysisMs??row.totalWithReadbackMs)}));
  }
  write(path.join(context.output,'results.json'),records);
  return {records,stopped};
}
export async function restartReadback(context,records) {
  const rows=[];
  for(const record of records.filter(row=>row.ticketId && row.stages?.analyze?.status===200)) {
    const history=await request(context.base,`/api/tickets/${record.ticketId}/analyses`,{signal:context.signal});
    rows.push({caseId:record.caseId,ticketId:record.ticketId,immediateMatched:record.persisted,matched:matches(record.stages.analyze,history),history});
  }
  write(path.join(context.output,'restart-readback.json'),rows);
  assert(rows.every(row=>row.matched),'Full restart readback mismatch');return {checked:rows.length,matched:rows.filter(row=>row.matched).length};
}
