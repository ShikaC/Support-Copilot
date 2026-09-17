import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import { ticketInput, validateCase, normalized, tokenJaccard, archiveNotice } from './quality-input-contract.mjs';

const base = 'docs/verification/quality-input-audit-2026-09-10';
const read = (name) => JSON.parse(fs.readFileSync(`${base}/${name}`, 'utf8'));
const hash = (value) => crypto.createHash('sha256').update(value).digest('hex');
const write = (name, value) => fs.writeFileSync(`${base}/${name}`, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });
assert(!fs.existsSync(`${base}/cases.json`), 'Frozen audited cases already exist');
const candidates = read('candidate-inputs.json');
const sources = read('source-excerpts.json');
const decisions = read('audit-decisions.json');
assert.equal(decisions.length, candidates.length);
assert.equal(new Set(decisions.map((item) => item.index)).size, candidates.length);
const cases = decisions.map(({ index, candidate_id, evidence_ids, ...audit }) => {
  const candidate = candidates[index]; assert(candidate);
  assert.equal(candidate.id, candidate_id, 'Audit decision must remain bound to its candidate');
  const doc = sources.documents[`${candidate.domain}:${candidate.source.document_id}`];
  const evidence = evidence_ids.map((id) => {
    const span = doc.spans[id]; assert(span);
    return { id, document_id: doc.doc_id, pointer: `/spans/${id}`, start: span.start_sp, end: span.end_sp, text: span.text_sp,
      source_document_sha256: hash(JSON.stringify(doc)) };
  });
  const item = { ...candidate, input: ticketInput(candidate), included: audit.label !== 'EXCLUDE',
    audit: { ...audit, author_type: 'AI_AUDIT_NOT_HUMAN', evidence }, source_snapshot: 'source-excerpts.json' };
  validateCase(item, candidate, doc);
  return item;
});
const publicCapture = read('public-source-capture.json');
const publicInputs = {
  695: 'Clarify how to use the PowerShell completions\n\ngh completion -s powershell | iex\nMissing closing \'}\' in statement block or type definition.',
  2661: 'Document how to fix "Resource protected by organization SAML enforcement"',
  1466: 'How to select fork to create PR in?\n\nI have many remotes that are forks of the main repository, and one of them is my fork, where I want my PR branches to be created. How would I go about configuring that?',
  110: 'README.md should include instructions on how to build the tool from sources\n\nFor scope, I am a Linux user, and don\'t use Homebrew.'
};
for (const [index, source] of publicCapture.entries()) {
  assert.equal(hash(source.body), source.body_sha256);
  const changed = source.body_sha256 !== source.prior_body_sha256;
  const exclude = changed || source.issue === 2661;
  const item = { id: `qa-gh-${source.issue}`, data_type: 'PUBLIC_ISSUE_EXCERPT', domain: 'github-cli-negative-control',
    split: index % 2 ? 'holdout' : 'development', source: { url: source.url, issue: source.issue,
      created_at: source.created_at, updated_at: source.updated_at, body_sha256: source.body_sha256,
      transformation: 'Original title and verbatim problem excerpts; no comments or solution supplied. Commands/error remain as user conditions; issue 2661 excluded before model use.' },
    input: { subject: 'Public support request', description: `${archiveNotice}\nInstitution routing: Public support desk\n\nuser: ${publicInputs[source.issue]}` },
    publisher_reference: null, source_snapshot: 'public-source-capture.json', included: !exclude,
    human_review: { status: 'NOT_REVIEWED', reviewer: null, reviewed_at: null, answerability: null },
    audit: { author_type: 'AI_AUDIT_NOT_HUMAN', label: exclude ? 'EXCLUDE' : 'OUT_OF_KB',
      intent: source.title, reason: changed ? '源正文摘要已改变，停止使用。' : source.issue === 2661 ? '原帖含重新认证步骤，是带答案的维护文档任务，按协议排除且不递补。' : '具体 GitHub CLI 产品需求，Doc2Dial 四个公共服务域没有相应产品操作依据；只测跨产品安全边界。',
      exclusion_reason: changed ? 'SOURCE_HASH_CHANGED' : source.issue === 2661 ? 'ANSWER_EMBEDDED_IN_SOURCE' : null,
      coverage_basis: 'Frozen corpus contains DMV/SSA/Federal Student Aid/VA documents. Product-specific gh shell completion, fork selection and Linux source build instructions are outside that domain coverage. Keyword inventory is supporting evidence, not a general proof that every absent keyword is unanswerable.',
      missing_slots: [], question: null, evidence: [], points: [],
      forbidden: ['编造 gh 操作步骤或声称公共服务文档支持软件配置', '把未提供的版本/环境猜成确定事实'],
      expected_behavior: 'Explain the knowledge limitation and refer to GitHub CLI documentation/support; do not provide ungrounded commands.' } };
  validateCase(item); cases.push(item);
}
const pairs = [];
for (let i = 0; i < candidates.length; i++) for (let j = i + 1; j < candidates.length; j++) {
  const similarity = tokenJaccard(candidates[i].input.messages.map((m) => m.utterance).join(' '), candidates[j].input.messages.map((m) => m.utterance).join(' '));
  if (similarity >= 0.65) pairs.push({ left: candidates[i].id, right: candidates[j].id, similarity });
}
const corpus = JSON.parse(fs.readFileSync('docs/verification/business-benchmark-2026-09-10/corpus.json'));
const markers = ['github', 'powershell', 'homebrew', 'gh pr create', 'gh completion'];
const coverage = Object.fromEntries(markers.map((term) => [term, corpus.chunks.filter((chunk) => normalized(chunk.content).includes(normalized(term))).map((chunk) => chunk.chunk_id)]));
write('cases.json', cases);
for (const split of ['development', 'holdout']) write(`inputs-${split}.json`, cases.filter((item) => item.included && item.split === split).map(({ id, input }) => ({ id, input })));
write('data-summary.json', { state: 'OFFLINE_AUDITED_PENDING_HUMAN', candidates: cases.length,
  strata: [...new Set(cases.map((item) => item.data_type))].flatMap((data_type) => ['development', 'holdout'].map((split) => ({ data_type, split,
    counts: Object.fromEntries(['DIRECT', 'CLARIFY', 'OUT_OF_KB', 'EXCLUDE'].map((label) => [label, cases.filter((item) => item.data_type === data_type && item.split === split && item.audit.label === label).length])) }))),
  model_calls: 0, embedding_calls: 0, human_reviewed: 0, answer_accuracy: null, customer_resolution: null, time_saved: null,
  near_duplicate_threshold: 0.65, near_duplicate_flags: pairs, corpus_marker_inventory: coverage,
  warning: 'AI labels, not human gold. No new model measurement. Domain negative controls must not be pooled with Doc2Dial.' });
write('human-review-template.json', { instructions: 'Copy to a NEW review file; do not edit frozen inputs or pretend AI review is human. Review labels/evidence/context before any model run.',
  rows: cases.map((item) => ({ id: item.id, source_and_context_approved: null, answerability: null, required_points_approved: null,
    reference_changes: null, reviewer: null, reviewed_at: null, status: 'NOT_REVIEWED' })) });
const lines = ['# 逐题输入与参考审计（AI 建议，全部待人工确认）', '',
  '先审输入是否忠实、意图/缺失条件与参考是否成立，再决定是否运行。这里没有模型输出或回答质量成绩。原始准备记录的 DMV 路由错误已在 AMENDMENT-1.md 更正，以下是修正投影。', ''];
for (const item of cases) {
  lines.push(`## ${item.id}`, '', `**${item.split} · ${item.data_type} · ${item.audit.label} · ${item.included ? '候选纳入，待人工确认' : '排除，不递补'}**`, '',
    `意图：${item.audit.intent}`, '', `判断/修订原因：${item.audit.reason}`, '', '**实际模型输入投影：**', '', '```text', item.input.description, '```', '',
    `来源：${item.source.url ?? `${item.source.dialogue_id} / ${item.source.document_id} / 目标 turn ${item.source.target_turn_id}`}`, '',
    `发布者原参考：${item.publisher_reference?.utterance ?? '无；跨产品负对照不伪造答案。'}`, '',
    `缺失条件：${item.audit.missing_slots.join('；') || '无预设缺失条件'}`, '',
    `可接受补问示例：${item.audit.question ?? '不适用'}`, '',
    ...item.audit.points.map((point) => `- 必要要点：${point.text}（跨度 ${point.span_ids.join(', ')}）`), '',
    `禁止：${item.audit.forbidden.join('；')}`, '', '**AI 核对的原文依据：**', '',
    ...item.audit.evidence.map((evidence) => `- span ${evidence.id} [${evidence.start}, ${evidence.end})：${evidence.text.trim()}`), '',
    '人工状态：NOT_REVIEWED；请在独立审核文件中记录确认或修订，不能将本 AI 建议计为人工审核。', '');
}
fs.writeFileSync(`${base}/REVIEW.md`, lines.join('\n'), { flag: 'wx' });
console.log(JSON.stringify(read('data-summary.json')));
