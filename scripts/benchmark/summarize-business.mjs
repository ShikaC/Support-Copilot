import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { tokenF1, spanCoverage, nearestRank, wilson } from './metrics.mjs';

const base=path.resolve('docs/verification/business-benchmark-2026-09-10');
const run=`${base}/run-1`;
const read=(file)=>JSON.parse(fs.readFileSync(file,'utf8'));
const hash=(value)=>crypto.createHash('sha256').update(value).digest('hex');
const manifest=read(`${run}/manifest.json`);const cases=read(`${base}/cases.json`);
const protocol=read(`${base}/protocol.json`);const map=read(`${base}/chunk-map.json`);
const trials=read(`${run}/results.json`);
assert.equal(manifest.state,'COMPLETE_UNREVIEWED');assert.equal(trials.length,protocol.planned_analysis_requests);
assert.equal(hash(fs.readFileSync(`${base}/cases.json`)),manifest.cases_sha256);
assert.equal(hash(fs.readFileSync(`${base}/corpus.json`)),manifest.corpus_sha256);
const keys=new Set(trials.map(t=>`${t.concurrency}:${t.case_id}`));assert.equal(keys.size,trials.length);
for(const item of cases)for(const level of protocol.planned_concurrency)assert(keys.has(`${level}:${item.id}`));
const source=read(`${run}/source-manifest.json`);
for(const[file,sha]of Object.entries(source.hashes))assert.equal(hash(fs.readFileSync(`${run}/source/${file}`)),sha);
const details=trials.map(trial=>{
  const item=cases.find(item=>item.id===trial.case_id);assert(item);
  const recordFile=`${run}/retrieval/${hash(trial.ticket_id??'')}.json`;
  const retrieval=fs.existsSync(recordFile)?read(recordFile):null;
  if(retrieval)assert.equal(retrieval.ticket_id,trial.ticket_id);
  const hits=retrieval?.hits??[];
  assert(hits.every(hit=>hit.retrieval_method==='VECTOR'));
  const relevant=hits.filter(hit=>hit.document_id===item.document_id);
  const ranges=relevant.map(hit=>map[hit.chunk_id]);assert(ranges.every(Boolean));
  const response=trial.stages.analyze?.body;
  const live=response?.mode==='live'&&response?.status==='SUCCEEDED';
  const labels=response?.suggestedReply?.citations??[];
  const citedIds=labels.map(label=>label.match(/\[chunkId:([^\]]+)\]/)?.[1]??null);
  const returned=response?.retrieval?.hits??[];
  const citationsResolved=live&&labels.length>0&&citedIds.every(id=>id&&returned.some(hit=>hit.chunkId===id&&hit.usedAsEvidence));
  const citedGold=citedIds.filter(id=>id&&map[id]&&map[id].original_document_id===item.original_document_id&&map[id].domain===item.domain);
  return {case_id:item.id,domain:item.domain,concurrency:trial.concurrency,ticket_id:trial.ticket_id,
    api_completed:trial.stages.analyze?.status===200,persisted:trial.persisted===true,live,
    mode:response?.mode??null,fallback_reason:response?.fallbackReason??null,error:trial.error,
    create_to_analysis_ms:trial.create_to_analysis_ms??null,total_with_readback_ms:trial.total_with_readback_ms??null,
    analyze_http_ms:trial.stages.analyze?.ms??null,retrieval_observed:Boolean(retrieval),
    retrieval_ms:retrieval?.duration_ms??null,gold_document_hit:relevant.length>0,
    gold_span_coverage:spanCoverage(item.gold_spans,ranges),citation_structure_valid:citationsResolved,
    cited_gold_document:citedGold.length>0,
    reply_reference_token_f1:live?tokenF1(response.suggestedReply.content,item.reference_answer):0,
    input_tokens:response?.usage?.inputTokens>0?response.usage.inputTokens:null,
    output_tokens:response?.usage?.outputTokens>0?response.usage.outputTokens:null};
});
const mean=(values)=>values.length?values.reduce((a,b)=>a+b,0)/values.length:null;
const metrics=protocol.planned_concurrency.map(concurrency=>{
  const group=details.filter(t=>t.concurrency===concurrency);const n=group.length;
  const count=(predicate)=>group.filter(predicate).length;
  const observed=group.filter(t=>t.retrieval_observed);
  const timings=group.map(t=>t.create_to_analysis_ms).filter(value=>value!==null);
  const live=count(t=>t.live);const hit=count(t=>t.gold_document_hit);
  const elapsed=manifest.groups.find(g=>g.concurrency===concurrency);
  return {concurrency,n,api_completed:count(t=>t.api_completed),persisted:count(t=>t.persisted),live,
    evidence_insufficient:count(t=>t.fallback_reason==='insufficient_evidence'),
    dependency_or_other_fallback:count(t=>t.mode==='fallback'&&t.fallback_reason!=='insufficient_evidence'),
    http_or_persistence_errors:count(t=>t.error!==null),live_rate:live/n,live_rate_wilson95:wilson(live,n),
    create_to_analysis_p50_ms:nearestRank(timings,0.5),create_to_analysis_p95_ms:nearestRank(timings,0.95),
    latency_observed:timings.length,analyze_http_p95_ms:nearestRank(group.map(t=>t.analyze_http_ms).filter(v=>v!==null),0.95),
    live_only_create_to_analysis_p95_ms:nearestRank(group.filter(t=>t.live).map(t=>t.create_to_analysis_ms).filter(v=>v!==null),0.95),
    retrieval_p50_ms:nearestRank(observed.map(t=>t.retrieval_ms),0.5),
    group_duration_ms:elapsed.duration_ms,completed_operations_per_second:elapsed.completion_throughput_per_second,
    live_operations_per_second:live/(elapsed.duration_ms/1000),retrieval_observed:observed.length,
    gold_document_hits:hit,gold_document_hit_rate_all:hit/n,gold_document_hit_rate_observed:observed.length?hit/observed.length:null,
    gold_document_hit_wilson95:wilson(hit,n),mean_gold_span_coverage_all:mean(group.map(t=>t.gold_span_coverage)),
    fully_covered_gold_spans:count(t=>t.gold_span_coverage===1),
    citations_resolved_live:count(t=>t.citation_structure_valid),cited_gold_document:count(t=>t.cited_gold_document),
    mean_reference_token_f1_all:mean(group.map(t=>t.reply_reference_token_f1)),
    mean_reference_token_f1_live:mean(group.filter(t=>t.live).map(t=>t.reply_reference_token_f1)),
    known_input_tokens:group.reduce((n,t)=>n+(t.input_tokens??0),0),known_output_tokens:group.reduce((n,t)=>n+(t.output_tokens??0),0),
    missing_usage:count(t=>t.input_tokens===null)};
});
const summary={metrics,primary_quality_concurrency:1,quality_distinct_cases:cases.length,
  labels:'publisher-provided human benchmark reference, not reviewed project model outputs',factual_correctness:null,business_resolution_rate:null,
  actual_staff_time_saved:null,cost:null,limits:protocol.limits,reference_data_warning:'fuzzy grounding labels; at least one greeting and several context-ambiguous first turns; no samples removed after seeing outputs',
  timing:'nearest-rank; all completed API results including fallback; from create start through analysis response after DB save; history read separately; first request includes cold index load',
  throughput:'finite closed-loop workloads including fallback, not saturation capacity; groups sequential 1/2/4 with same questions'};
fs.writeFileSync(`${base}/summary.json`,JSON.stringify(summary,null,2));fs.writeFileSync(`${base}/scored-trials.json`,JSON.stringify(details,null,2));
const fmt=(n)=>n===null?'未测':(n/1000).toFixed(2)+'s';const pct=(n)=>n===null?'未测':(100*n).toFixed(1)+'%';
const lines=['# 完整业务 API 实测与公开参考对照','',
  '同一批 32 个 Doc2Dial 人工构建的公开对话，分别在 1/2/4 并发下运行。原始参考回复和文档标注来自数据集发布者；不是本项目 AI 生成的标准答案。全部 488 份文档参与检索。','',
  '| 并发工单 | API 返回 | 结果读回匹配 | live 成功 | 无证据降级 | 其他降级 | 创建至分析保存 p50 | p95 | 完成操作/秒 | live 操作/秒 |',
  '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
  ...metrics.map(m=>`| ${m.concurrency} | ${m.api_completed}/${m.n} | ${m.persisted}/${m.n} | ${m.live}/${m.n} | ${m.evidence_insufficient} | ${m.dependency_or_other_fallback} | ${fmt(m.create_to_analysis_p50_ms)} | ${fmt(m.create_to_analysis_p95_ms)} | ${m.completed_operations_per_second.toFixed(3)} | ${m.live_operations_per_second.toFixed(3)} |`),'',
  '完成操作吞吐包括降级结果；live 操作也不等于客户问题已解决。固定并发的短批次不是最大容量测试；顺序运行的组间差异还可能受网关负载和缓存影响。API 计时含真实 HTTP 与落库，不含浏览器渲染和人工审核；readback 原始耗时也已保存。','',
  '| 并发 | 有真实检索记录 | 命中发布者参考文档 | 标注证据字符覆盖均值 | 全覆盖题数 | 回复 token F1（全部/仅 live） |',
  '| --- | ---: | ---: | ---: | ---: | ---: |',
  ...metrics.map(m=>`| ${m.concurrency} | ${m.retrieval_observed}/${m.n} | ${m.gold_document_hits}/${m.n} (${pct(m.gold_document_hit_rate_all)}) | ${pct(m.mean_gold_span_coverage_all)} | ${m.fully_covered_gold_spans}/${m.n} | ${pct(m.mean_reference_token_f1_all)} / ${pct(m.mean_reference_token_f1_live)} |`),'',
  '质量主组为并发 1；其余是同题重复观察。文档命中是 Top 3 是否含发布者标注文档；字符覆盖为原始 Unicode 区间交并，重叠不重复计数。它们不是事实正确率。token F1 只衡量词语重叠，去除数字引用、标点和英语冠词；较长但有据的回答可能得分较低。非 live 结果的 F1 记为 0，另列仅 live 均值，避免只看幸存请求。','',
  '原始数据中存在寒暄和上下文不明确的首轮输入，例如 “Hi there” 也关联了业务文档片段。所有样本均保留，没有看过结果后删题；因此这些数字是冻结抽样协议下的参考对照，不足以证明真实客服问题解决率。','',
  '## 逐题参考与最终业务输出',''];
for(const item of cases){
  lines.push(`### ${item.id} · ${item.domain}`,'',`**问题：** ${item.question}`,'',`**发布者参考回复：** ${item.reference_answer}`,'', '**发布者标注文档片段：**','',...item.gold_spans.map(span=>`> ${span.text}`),'');
  for(const concurrency of protocol.planned_concurrency){const t=trials.find(t=>t.case_id===item.id&&t.concurrency===concurrency);const score=details.find(s=>s.case_id===item.id&&s.concurrency===concurrency);const response=t.stages.analyze?.body;
    lines.push(`**并发 ${concurrency}：** ${score.mode??score.error}；${response?.fallbackReason??'无降级原因'}；参考文档命中 ${score.gold_document_hit}；证据覆盖 ${pct(score.gold_span_coverage)}；创建至分析保存 ${fmt(score.create_to_analysis_ms)}`,'',`[原始请求结果](${run}/trials/c${concurrency}-${item.id}.json)`,'',...(response?.suggestedReply?.content??'无有效回复').split('\n').map(line=>`> ${line}`),'');}
}
fs.writeFileSync(`${base}/RESULTS.md`,lines.join('\n'));
console.log(JSON.stringify(summary,null,2));
