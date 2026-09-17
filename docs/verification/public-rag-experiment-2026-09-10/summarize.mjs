import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const base = dirname(fileURLToPath(import.meta.url));
const root = resolve(base, process.argv[2] ?? 'run-1');
const read = (name) => JSON.parse(readFileSync(resolve(root, name), 'utf8'));
const hash = (name) => createHash('sha256').update(readFileSync(resolve(root, name))).digest('hex');
const manifest = read('manifest.json');
const trials = read('results.json');
const cases = read('cases.json').cases;
const proposals = read('annotation-drafts.json').cases;
assert.equal(manifest.state, 'COMPLETE_WITH_UNREVIEWED_OUTPUTS');
assert.equal(trials.length, manifest.planned_trials);
assert.equal(readdirSync(resolve(root, 'trials')).length, trials.length);
assert.equal(hash('cases.json'), manifest.dataset_sha256);
assert.equal(hash('chunks.json'), manifest.chunks_sha256);
for (const [path, sha] of Object.entries(manifest.source_hashes)) assert.equal(hash(`source/${path}`), sha);
assert.equal(hash('embeddings.npy'), read('embedding-run.json').sha256);
const keys = new Set(trials.map((trial) => `${trial.case_id}-${trial.method}`));
assert.equal(keys.size, trials.length);
for (const item of cases) for (const method of ['bm25', 'vector']) assert(keys.has(`${item.id}-${method}`));
for (const item of proposals) assert(keys.has(`${item.id}-proposed_evidence`));
for (const trial of trials) {
  assert.equal(trial.human_review, 'NOT_REVIEWED');
  assert.equal(trial.answer_correct, null);
  assert.equal(trial.evidence.length, trial.scores.length);
  assert.deepEqual(read(`trials/${trial.case_id}-${trial.method}.json`), trial);
}
const percentile = (values, p) => [...values].sort((a, b) => a - b)[Math.ceil(p * values.length) - 1];
const navigationLines = new Set(['', 'LEARN MORE',
  'Use `gh <command> <subcommand> --help` for more information about a command.',
  'Read the manual at https://cli.github.com/manual',
  'Learn about exit codes using `gh help exit-codes`',
  'Learn about accessibility experiences using `gh help accessibility`']);
const navigationOnly = (chunk) => chunk.content.split('\n').every((line) => navigationLines.has(line.trim()));
const methods = ['bm25', 'vector', 'proposed_evidence'].map((method) => {
  const group = trials.filter((trial) => trial.method === method);
  const times = group.map((trial) => trial.generation_ms);
  return {
    method, attempts: group.length,
    completed: group.filter((trial) => trial.status === 'COMPLETED').length,
    failed: group.filter((trial) => trial.status !== 'COMPLETED').length,
    model_claims_sufficient: group.filter((trial) => trial.draft?.evidence_sufficient === true).length,
    model_claims_insufficient: group.filter((trial) => trial.draft?.evidence_sufficient === false).length,
    generation_p50_ms: percentile(times, 0.5), generation_p95_ms: percentile(times, 0.95),
    known_input_tokens: group.reduce((n, trial) => n + (trial.input_tokens ?? 0), 0),
    known_output_tokens: group.reduce((n, trial) => n + (trial.output_tokens ?? 0), 0),
    missing_usage_attempts: group.filter((trial) => trial.input_tokens === null).length,
    evidence_slots: group.reduce((n, trial) => n + trial.evidence.length, 0),
    navigation_only_slots: group.reduce((n, trial) => n + trial.evidence.filter(navigationOnly).length, 0),
  };
});
const summary = { accuracy: null, human_reviewed: 0, publishable_quality: false,
  methods, embedding: read('embedding-run.json'),
  percentile: 'nearest-rank; all attempts, including failures; generation only',
  failure_records: trials.filter((trial) => trial.status !== 'COMPLETED').map(({ case_id, method, status, error, diagnostics }) => ({ case_id, method, status, error, diagnostics })) };
writeFileSync(resolve(root, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
const labels = { bm25: 'BM25 关键词', vector: '向量检索', proposed_evidence: 'AI 候选证据对照' };
const lines = [
  '# 公开问题真实模型实验：逐题结果', '',
  '本报告由冻结的真实 API 调用结果生成。20 道问题均归纳自公开 GitHub Issues；不是原始内部客服工单。全部输出尚未人工审核，准确率、Recall@K、事实正确率均未计算。', '',
  `模型：${manifest.chat_model}；Embedding：${manifest.embedding_model}；官方帮助版本：${manifest.documentation_version}。`, '',
  '复用项目生成与 Embedding provider；检索为隔离实验实现。未经过 Java、工单状态、风险策略和最终回复规则，不能当作整个平台的端到端评测。', '',
  '| 方案 | 请求 | 结构合格返回 | 失败 | 模型自报证据充分 | 模型自报不足 | 生成 p50 | 生成 p95 |',
  '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
  ...methods.map((m) => `| ${labels[m.method]} | ${m.attempts} | ${m.completed} | ${m.failed} | ${m.model_claims_sufficient} | ${m.model_claims_insufficient} | ${(m.generation_p50_ms / 1000).toFixed(2)}s | ${(m.generation_p95_ms / 1000).toFixed(2)}s |`), '',
  '“结构合格返回”只代表完成结构化解析且引用序号合法；不代表内容正确。充分/不足是模型自己的判断，不能当作人工判断。p50/p95 使用 nearest-rank，包含失败请求耗时，不含远端 Embedding，不能称为用户端到端响应时间。5 题对照使用 AI 提议的文档原文，不包含候选答案，不是人工 gold。', '',
  `文档与问题共 ${summary.embedding.vectors} 条向量，${summary.embedding.dimension} 维，批量向量化耗时 ${(summary.embedding.duration_ms / 1000).toFixed(2)}s。费用与失败请求的缺失 usage 不补为 0。`, '',
  '每题下方保留模型英文原文、实际提供的证据位置与原始 JSON。证据列表是输入给模型的上下文；只有标为“模型引用”的条目才被模型选用。', '',
  '纯导航片段检查：只包含 LEARN MORE、通用 help/manual/exit-codes/accessibility 导航行与空行的片段。按实际提供位置计数，不去重；它只是可核验的上下文噪声诊断，不是召回率。', '',
  ...methods.map((m) => `- ${labels[m.method]}：${m.navigation_only_slots}/${m.evidence_slots} 个上下文位置为纯导航。`), '',
];
for (const item of cases) {
  lines.push(`## ${item.id}：${item.source.title}`, '', `[公开问题来源](${item.source.url})`, '', item.input.question, '');
  for (const trial of trials.filter((entry) => entry.case_id === item.id)) {
    lines.push(`### ${labels[trial.method]}`, '',
      `状态：${trial.status}；生成耗时 ${(trial.generation_ms / 1000).toFixed(2)}s；模型自报证据充分：${trial.draft?.evidence_sufficient ?? '无输出'}。`, '',
      `[原始记录](${resolve(root, `trials/${trial.case_id}-${trial.method}.json`)})`, '');
    if (trial.draft) lines.push(...trial.draft.reply_content.split('\n').map((line) => `> ${line}`), '');
    if (trial.error) lines.push(`失败：${trial.error}；诊断：${JSON.stringify(trial.diagnostics)}。`, '');
    trial.evidence.forEach((chunk, index) => {
      const source = resolve(base, '../public-rag-pilot-2026-09-10/corpus', `${chunk.document_id}.txt`);
      lines.push(`- ${index + 1}. [${chunk.document_id} L${chunk.start_line}–${chunk.end_line}](${source}:${chunk.start_line})${trial.draft?.citation_indexes.includes(index + 1) ? '（模型引用）' : '（未引用）'}`);
    });
    lines.push('');
  }
}
writeFileSync(resolve(base, 'RESULTS.md'), lines.join('\n'));
console.log(JSON.stringify(summary, null, 2));
