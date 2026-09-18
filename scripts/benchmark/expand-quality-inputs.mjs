#!/usr/bin/env node
// 扩容评估集：复用质量审计的同一筛选规则，只把每 domain 的配额从 6 提高。
//
// 背景：11 道可评估题不足以验证任何检索改动（融合实验里 2 升 1 降，McNemar p=1.0）。
// 本脚本在同一份 Doc2Dial 归档、同一套筛选规则、同一套输入渲染下，取 hash 顺序的后续题目，
// 产出一个同构的扩展集，用于检索改动的相对比较。
//
// 关键约束：
//   1. 规则不变，只提高配额——所有新题都来自同一候选池的同一顺序。
//   2. 自检：用配额 6 重跑必须精确复现现有 24 个 Doc2Dial 候选（id 与渲染后的 input 都要一致）。
//   3. 新题未经 AI 审计，因此只用于检索的相对比较，不产生答案性或质量结论。
//
// 用法：
//   node scripts/benchmark/expand-quality-inputs.mjs [--per-domain 25] [--output <目录>]
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export const archiveNotice =
  'This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.';
export const oldQuota = 6;
export const defaultPerDomain = 25;
export const institutions = {
  dmv: 'Virginia DMV',
  ssa: 'US Social Security Administration',
  studentaid: 'US Federal Student Aid',
  va: 'US Department of Veterans Affairs',
};
export const sourceRoot = '.local/business-benchmark-source';
export const oldCasesFile = 'docs/verification/business-benchmark-2026-09-10/cases.json';
export const oldSelectionFile = 'docs/verification/quality-input-audit-2026-09-10/selection.json';
export const oldAuditCasesFile = 'docs/verification/quality-input-audit-2026-09-10/cases.json';
export const defaultOutput = 'docs/verification/retrieval-cases-expanded-2026-09-18';

export const sha256 = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
export const sampleKey = (dialogueId) => sha256(`support-copilot-quality-input-v1:${dialogueId}`);

/** 目标轮次：turn_id>=3 的 agent 轮，且前一转是用户。与审计脚本完全一致。 */
export function findTargetIndex(turns) {
  return turns.findIndex(
    (turn, index) => turn.turn_id >= 3 && turn.role === 'agent' && turns[index - 1]?.role === 'user',
  );
}

/**
 * 机构路由。dmv 不能猜辖区：审计修订后统一写成「未提供辖区」，其余 domain 用固定机构名。
 */
export function institutionFor(domain) {
  return domain === 'dmv'
    ? 'DMV (state/jurisdiction not provided by routing)'
    : institutions[domain];
}

/** 与 quality-input-contract.mjs 的 ticketInput 完全一致的渲染，保证新题与旧题同构。 */
export function ticketInput(domain, messages) {
  return {
    subject: 'Public support request',
    description: `${archiveNotice}\nInstitution routing: ${institutionFor(domain)}\n\n${messages
      .map((message) => `${message.role}: ${message.utterance}`)
      .join('\n')}`,
  };
}

/** 给每条对话定 reason；只排除旧实验用过的对话与文档，其余质量相同。 */
export function classify(entry, used) {
  if (used.dialogues.has(entry.dialogueId)) return 'PREVIOUS_EXPERIMENT_DIALOGUE';
  if (used.documents.has(`${entry.domain}:${entry.docId}`)) return 'PREVIOUS_EXPERIMENT_REFERENCE_DOCUMENT';
  if (entry.targetIndex < 0) return 'NO_FOLLOWUP_TARGET';
  return 'OUTSIDE_FIXED_QUOTA';
}

/** 按 sample_key 升序、每文档最多一题地取前 quota 个；规则与审计脚本逐行对齐。
 *  故意做成纯函数：扩容需要分别用旧配额与新配额各跑一次，不能互相污染 reason。 */
export function selectDomain(entries, quota) {
  const ordered = entries.map((entry) => ({...entry}));
  ordered.sort((left, right) => left.sampleKey.localeCompare(right.sampleKey));
  const seen = new Set();
  const selected = [];
  for (const entry of ordered) {
    if (entry.reason !== 'OUTSIDE_FIXED_QUOTA') continue;
    if (seen.has(entry.docId)) {
      entry.reason = 'SAME_DOCUMENT_AS_EARLIER_CANDIDATE';
      continue;
    }
    if (selected.length === quota) continue;
    seen.add(entry.docId);
    entry.reason = 'FIXED_HASH_QUOTA';
    selected.push(entry);
  }
  return {ordered, selected};
}

export function buildCase(entry, split, dialogue) {
  const target = dialogue.turns[entry.targetIndex];
  return {
    id: `qa-${entry.dialogueId}-${target.turn_id}`,
    data_type: 'HUMAN_AUTHORED_DOCUMENT_DIALOGUE',
    domain: entry.domain,
    split,
    source: {dialogue_id: entry.dialogueId, document_id: entry.docId, target_turn_id: target.turn_id},
    input: ticketInput(entry.domain, dialogue.turns.slice(0, entry.targetIndex)),
    publisher_reference: {utterance: target.utterance, act: target.da, references: target.references},
    audit: {author_type: 'NONE', label: 'PENDING', note: '扩容题未做 AI 审计，只用于检索相对比较'},
    included: true,
  };
}

function collectCandidates(dialogues, used) {
  const byDomain = new Map();
  for (const domain of Object.keys(dialogues).sort()) {
    const entries = [];
    for (const [docId, items] of Object.entries(dialogues[domain])) {
      for (const dial of items) {
        const entry = {
          domain,
          docId,
          dialogueId: dial.dial_id,
          targetIndex: findTargetIndex(dial.turns),
          sampleKey: sampleKey(dial.dial_id),
        };
        entry.reason = classify(entry, used);
        entries.push({entry, dial});
      }
    }
    byDomain.set(domain, entries);
  }
  return byDomain;
}

export function selfCheck(audits, reproduced) {
  const expected = audits
    .filter((item) => item.domain !== 'github-cli-negative-control')
    .map((item) => item.id)
    .sort();
  const actual = reproduced.map((entry) => entry.id).sort();
  assert.deepEqual(actual, expected, '配额 6 必须精确复现现有 Doc2Dial 候选');
  const byId = new Map(audits.map((item) => [item.id, item]));
  for (const item of reproduced) {
    assert.deepEqual(item.input, byId.get(item.id).input, `渲染出的 input 必须与冻结输入一致：${item.id}`);
  }
}

export function expand({dialogues, used, perDomain}) {
  const byDomain = collectCandidates(dialogues, used);
  const reproduced = [];
  const expanded = [];
  const perDomainSummary = [];
  for (const [domain, entries] of byDomain) {
    const {selected} = selectDomain(
      entries.map(({entry}) => entry),
      oldQuota,
    );
    const dialoguesById = new Map(entries.map(({entry, dial}) => [entry.dialogueId, dial]));
    const firstSix = selected.map((entry) =>
      buildCase(entry, 'development', dialoguesById.get(entry.dialogueId)),
    );
    reproduced.push(...firstSix);
    const {selected: chosen} = selectDomain(entries.map(({entry}) => entry), perDomain);
    const extra = chosen.slice(oldQuota);
    extra.forEach((entry, index) => {
      expanded.push(buildCase(entry, index % 2 === 0 ? 'development' : 'holdout', dialoguesById.get(entry.dialogueId)));
    });
    perDomainSummary.push({
      domain,
      availableDocuments: new Set(entries.map(({entry}) => entry.docId)).size,
      reproduced: firstSix.length,
      added: extra.length,
    });
  }
  return {reproduced, expanded, perDomainSummary};
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function main() {
  const argv = process.argv.slice(2);
  const option = (name, fallback) => {
    const index = argv.indexOf(name);
    return index < 0 ? fallback : argv[index + 1];
  };
  const perDomain = Number(option('--per-domain', defaultPerDomain));
  const output = path.resolve(option('--output', defaultOutput));
  assert(perDomain > oldQuota, '扩容配额必须高于原有配额');
  assert(!fs.existsSync(`${output}/cases.json`), '扩展集已存在，不允许覆盖');

  const source = path.resolve(sourceRoot);
  const documents = readJson(`${source}/doc2dial_doc.json`).doc_data;
  const dialogues = readJson(`${source}/doc2dial_dial_test.json`).dial_data;
  const oldCases = readJson(oldCasesFile);
  const audits = readJson(oldAuditCasesFile);
  const used = {
    dialogues: new Set(oldCases.map((item) => item.dialogue_id)),
    documents: new Set(oldCases.map((item) => `${item.domain}:${item.original_document_id}`)),
  };
  const {reproduced, expanded, perDomainSummary} = expand({dialogues, used, perDomain});
  selfCheck(audits, reproduced);
  if (expanded.length === 0) throw new Error('扩容没有产生任何新题');

  const cases = expanded.map((item) => ({...item, included: true}));
  const documentIds = new Set(cases.map((item) => item.source.document_id));
  assert.equal(documentIds.size, cases.length, '每份文档最多一题');
  for (const item of cases) {
    assert(item.input.description.length <= 4000, `输入过长：${item.id}`);
    assert(documents[item.domain][item.source.document_id], `缺少源文档：${item.id}`);
  }
  // 与旧集同构的白名单投影，让检索工具能按 split 单独运行，天然避免误用 holdout。
  const projection = (split) =>
    cases.filter((item) => item.split === split).map((item) => ({id: item.id, input: item.input}));
  const manifest = {
    frozen_at: new Date().toISOString(),
    purpose: '为检索改动提供统计效力更高、且与冻结开发集同构的扩展题集',
    dataset: 'Doc2Dial official archive named v1.0.1 (test split)',
    rule: `与 quality-input-audit-2026-09-10 相同的筛选规则，每 domain 配额由 ${oldQuota} 提高到 ${perDomain}`,
    source_sha256: Object.fromEntries(
      ['doc2dial_doc.json', 'doc2dial_dial_test.json'].map((name) => [name, sha256(fs.readFileSync(`${source}/${name}`))]),
    ),
    inputs_sha256: {
      [oldCasesFile]: sha256(fs.readFileSync(oldCasesFile)),
      [oldAuditCasesFile]: sha256(fs.readFileSync(oldAuditCasesFile)),
    },
    self_check: `配额 ${oldQuota} 精确复现现有 ${reproduced.length} 个 Doc2Dial 候选（id 与渲染 input 均一致）`,
    per_domain: perDomainSummary,
    cases: cases.length,
    splits: {
      development: cases.filter((item) => item.split === 'development').length,
      holdout: cases.filter((item) => item.split === 'holdout').length,
    },
    audit_status: 'PENDING',
    limits: [
      '扩容题未经 AI 审计，也没有真人确认，不产生答案性或质量结论',
      '只用于检索的相对比较；绝对命中率不能与冻结开发集混算',
      'gold 仍是文档级标注：命中文档不代表片段包含完整答案',
      '语料是归档文档，不代表当前政策或真实客服知识库',
    ],
  };
  fs.mkdirSync(output, {recursive: true});
  fs.writeFileSync(`${output}/cases.json`, `${JSON.stringify(cases, null, 2)}\n`, {flag: 'wx'});
  for (const split of ['development', 'holdout']) {
    fs.writeFileSync(`${output}/inputs-${split}.json`, `${JSON.stringify(projection(split), null, 2)}\n`, {flag: 'wx'});
  }
  fs.writeFileSync(`${output}/freeze-manifest.json`, `${JSON.stringify(manifest, null, 2)}\n`, {flag: 'wx'});
  console.log(
    JSON.stringify({
      cases: cases.length,
      splits: manifest.splits,
      reproduced: reproduced.length,
      perDomain: perDomainSummary,
      output,
    }),
  );
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
