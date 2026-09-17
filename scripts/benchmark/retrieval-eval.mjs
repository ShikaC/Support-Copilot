#!/usr/bin/env node
// 离线检索评测：只读取运行记录与冻结的评估集，不调用任何模型或外部服务。
//
// 目的：把「检索是否把发布者标注的文档找回来」变成可复现的数字，使后续每一个
// 检索改动（分块、混合检索、重排、top_k、阈值）都能在同一口径下比较，而不是
// 依赖生成模型的成败来判断检索好坏。
//
// 用法：
//   node scripts/benchmark/retrieval-eval.mjs <runDir> [--label 文本] [--json 路径] [--markdown 路径]
//
// 输入：
//   <runDir>/results.json              隔离运行器或业务运行的逐题结果
//   docs/verification/quality-input-audit-2026-09-10/cases.json      评估集与 gold 文档标注
//   docs/verification/business-benchmark-2026-09-10/corpus.json      当前知识语料
//
// 指标口径：
//   gold@k  前 k 个候选中是否出现 gold 文档的任一片段
//   MRR     第一个 gold 片段排名的倒数均值，未命中记 0
//   gold 文档可能被切成多个片段，命中任一片段即算命中
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const defaultCases = 'docs/verification/quality-input-audit-2026-09-10/cases.json';
export const defaultCorpus = 'docs/verification/business-benchmark-2026-09-10/corpus.json';

const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));
export const sha256File = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
export const sha256Text = (value) => crypto.createHash('sha256').update(value).digest('hex');

/** 取出 source_uri 的 fragment 并解码，它是 Doc2Dial 的原始文档标识。 */
export function sourceAnchor(uri) {
  const hash = (uri ?? '').indexOf('#');
  if (hash < 0) return null;
  const raw = uri.slice(hash + 1);
  try { return decodeURIComponent(raw); } catch { return raw; }
}

/** 建立 gold 文档到语料片段集合、以及原始文档标识到语料 document_id 的双向索引。 */
export function goldIndex(corpus) {
  const chunksByDocument = new Map();
  const documentByAnchor = new Map();
  for (const chunk of corpus.chunks) {
    if (!chunksByDocument.has(chunk.document_id)) chunksByDocument.set(chunk.document_id, new Set());
    chunksByDocument.get(chunk.document_id).add(chunk.chunk_id);
    const anchor = sourceAnchor(chunk.source_uri);
    if (anchor && !documentByAnchor.has(anchor)) documentByAnchor.set(anchor, chunk.document_id);
  }
  return {chunksByDocument, documentByAnchor};
}

/** 返回该题的 gold 文档与它的全部片段；没有可定位标注时返回 null。 */
export function goldForCase(item, index) {
  const anchor = item?.source?.document_id;
  if (!anchor) return null;
  const documentId = index.documentByAnchor.get(anchor);
  if (!documentId) return null;
  return {documentId, chunkIds: index.chunksByDocument.get(documentId) ?? new Set()};
}

/** 兼容运行记录中的 camelCase 与 snake_case 字段。 */
export function normalizeHits(hits) {
  return (hits ?? []).map((hit, position) => ({
    rank: position + 1,
    chunkId: hit.chunkId ?? hit.chunk_id ?? null,
    documentId: hit.documentId ?? hit.document_id ?? null,
    method: hit.retrievalMethod ?? hit.retrieval_method ?? null,
  }));
}

export function evaluateCase({caseId, hits, gold}) {
  const normalized = normalizeHits(hits);
  const candidateKey = normalized.map((hit) => hit.chunkId).filter(Boolean).join('|');
  const firstGoldRank = gold
    ? (normalized.find((hit) => hit.chunkId !== null && gold.chunkIds.has(hit.chunkId))?.rank ?? null)
    : null;
  return {
    caseId,
    hitCount: normalized.length,
    methods: [...new Set(normalized.map((hit) => hit.method).filter(Boolean))],
    goldDocumentId: gold?.documentId ?? null,
    goldChunkCount: gold ? gold.chunkIds.size : null,
    firstGoldRank,
    reciprocalRank: firstGoldRank === null ? 0 : 1 / firstGoldRank,
    candidates: candidateKey,
    candidateSetSha: candidateKey ? sha256Text(candidateKey).slice(0, 16) : null,
  };
}

/** 从运行目录读取逐题结果，取出 caseId、query 与候选片段。 */
export function readRun(runDir) {
  const resultsFile = path.join(runDir, 'results.json');
  if (!fs.existsSync(resultsFile)) throw new Error(`缺少运行结果文件：${resultsFile}`);
  const results = readJson(resultsFile);
  if (!Array.isArray(results)) throw new Error(`${resultsFile} 不是逐题数组`);
  const records = new Map();
  for (const row of results) {
    const body = row?.stages?.analyze?.body ?? null;
    const retrieval = body?.retrieval ?? null;
    records.set(row?.caseId, {
      caseId: row?.caseId,
      executed: body !== null,
      outcome: row?.outcome ?? null,
      error: row?.error ?? null,
      status: body?.status ?? null,
      mode: body?.mode ?? null,
      fallbackReason: body?.fallbackReason ?? null,
      query: retrieval?.query ?? null,
      hits: retrieval?.hits ?? [],
    });
  }
  return {resultsFile, records};
}

export function evaluateRun({label, runDir, casesFile = defaultCases, corpusFile = defaultCorpus}) {
  const cases = readJson(casesFile);
  const includedCases = cases.filter((item) => item.included !== false);
  const corpus = readJson(corpusFile);
  const index = goldIndex(corpus);
  const {records} = readRun(runDir);

  const rows = includedCases.map((item) => {
    const record = records.get(item.id) ?? null;
    const gold = goldForCase(item, index);
    return {
      ...evaluateCase({caseId: item.id, hits: record?.hits ?? [], gold}),
      domain: item.domain,
      split: item.split,
      included: item.included !== false,
      dataType: item.data_type ?? null,
      executed: record?.executed ?? false,
      outcome: record?.outcome ?? null,
      status: record?.status ?? null,
      mode: record?.mode ?? null,
      fallbackReason: record?.fallbackReason ?? null,
      query: record?.query ?? null,
    };
  });

  const executed = rows.filter((row) => row.executed);
  const evaluable = executed.filter((row) => row.goldDocumentId !== null);
  const hitsAt = (k) => evaluable.filter((row) => row.firstGoldRank !== null && row.firstGoldRank <= k).length;
  const ratio = (value, total) => (total === 0 ? null : value / total);
  const distinct = (values) => new Set(values.filter((value) => value !== null && value !== '')).size;

  const summary = {
    casesPlanned: includedCases.length,
    casesExcluded: cases.length - includedCases.length,
    casesExecuted: executed.length,
    casesEvaluable: evaluable.length,
    casesWithoutGold: executed.filter((row) => row.goldDocumentId === null).length,
    casesNotExecuted: rows.length - executed.length,
    goldAt1: hitsAt(1),
    goldAt3: hitsAt(3),
    goldAt10: hitsAt(10),
    goldAt1Rate: ratio(hitsAt(1), evaluable.length),
    goldAt3Rate: ratio(hitsAt(3), evaluable.length),
    goldAt10Rate: ratio(hitsAt(10), evaluable.length),
    mrr: evaluable.length === 0
      ? null
      : evaluable.reduce((sum, row) => sum + row.reciprocalRank, 0) / evaluable.length,
    meanGoldChunkCount: evaluable.length === 0
      ? null
      : evaluable.reduce((sum, row) => sum + (row.goldChunkCount ?? 0), 0) / evaluable.length,
    emptyResults: executed.filter((row) => row.hitCount === 0).length,
    distinctQueries: distinct(executed.map((row) => row.query)),
    distinctCandidateSets: distinct(executed.map((row) => row.candidateSetSha)),
    distinctFirstCandidates: distinct(executed.map((row) => row.candidates.split('|')[0])),
    corpusChunks: corpus.chunks.length,
    corpusDocuments: new Set(corpus.chunks.map((chunk) => chunk.document_id)).size,
  };

  const domains = [...new Set(rows.map((row) => row.domain))].sort();
  const byDomain = Object.fromEntries(domains.map((domain) => {
    const group = evaluable.filter((row) => row.domain === domain);
    const hit = (k) => group.filter((row) => row.firstGoldRank !== null && row.firstGoldRank <= k).length;
    return [domain, {
      casesEvaluable: group.length,
      goldAt3: hit(3),
      goldAt3Rate: ratio(hit(3), group.length),
      mrr: group.length === 0 ? null : group.reduce((sum, row) => sum + row.reciprocalRank, 0) / group.length,
    }];
  }));

  return {
    label: label ?? path.basename(runDir),
    runDir,
    resultsFile: path.join(runDir, 'results.json'),
    casesFile,
    casesSha256: sha256File(casesFile),
    corpusFile,
    corpusSha256: sha256File(corpusFile),
    summary,
    byDomain,
    perCase: rows,
  };
}

const pct = (value) => (value === null ? '未测' : `${(value * 100).toFixed(1)}%`);

export function renderMarkdown(report, {baseline = null} = {}) {
  const s = report.summary;
  const lines = [
    `# 离线检索评测：${report.label}`,
    '',
    `- 运行结果：\`${report.runDir}/results.json\``,
    `- 评估集：\`${report.casesFile}\` (sha256 ${report.casesSha256.slice(0, 16)}…)`,
    `- 知识语料：\`${report.corpusFile}\` (sha256 ${report.corpusSha256.slice(0, 16)}…)`,
    `- 语料规模：${s.corpusChunks} 个片段 / ${s.corpusDocuments} 份文档`,
    '',
    '本报告由 `scripts/benchmark/retrieval-eval.mjs` 离线生成，不调用任何模型；它只判断候选片段是否属于发布者标注文档，不代表回答的事实正确率。',
    '',
    '## 汇总',
    '',
    '| 指标 | 值 |',
    '| --- | --- |',
    `| 计划题数 / 已执行 | ${s.casesPlanned} / ${s.casesExecuted} |`,
    `| 按协议排除的题数 | ${s.casesExcluded} |`,
    `| 可评估题数（有 gold 文档）| ${s.casesEvaluable} |`,
    `| 无 gold 标注（不计入指标）| ${s.casesWithoutGold} |`,
    `| gold@1 | ${s.goldAt1}/${s.casesEvaluable} (${pct(s.goldAt1Rate)}) |`,
    `| gold@3 | ${s.goldAt3}/${s.casesEvaluable} (${pct(s.goldAt3Rate)}) |`,
    `| gold@10 | ${s.goldAt10}/${s.casesEvaluable} (${pct(s.goldAt10Rate)}) |`,
    `| MRR | ${s.mrr === null ? '未测' : s.mrr.toFixed(3)} |`,
    `| gold 文档平均片段数 | ${s.meanGoldChunkCount === null ? '未测' : s.meanGoldChunkCount.toFixed(2)} |`,
    `| 空结果题数 | ${s.emptyResults} |`,
    `| 去重 query 数 | ${s.distinctQueries} |`,
    `| 去重候选集合数 | ${s.distinctCandidateSets} |`,
    `| 去重首候选数 | ${s.distinctFirstCandidates} |`,
    '',
  ];

  if (baseline) {
    lines.push(
      '## 与基线对比',
      '',
      '| 指标 | 基线 | 本次 | 变化 |',
      '| --- | ---: | ---: | ---: |',
      `| gold@3 | ${pct(baseline.summary.goldAt3Rate)} | ${pct(s.goldAt3Rate)} | ${delta(baseline.summary.goldAt3Rate, s.goldAt3Rate)} |`,
      `| MRR | ${baseline.summary.mrr === null ? '未测' : baseline.summary.mrr.toFixed(3)} | ${s.mrr === null ? '未测' : s.mrr.toFixed(3)} | ${delta(baseline.summary.mrr, s.mrr)} |`,
      '',
    );
  }

  lines.push('## 按领域', '', '| 领域 | 可评估 | gold@3 | 命中率 | MRR |', '| --- | ---: | ---: | ---: | ---: |');
  for (const [domain, entry] of Object.entries(report.byDomain)) {
    lines.push(`| ${domain} | ${entry.casesEvaluable} | ${entry.goldAt3} | ${pct(entry.goldAt3Rate)} | ${entry.mrr === null ? '未测' : entry.mrr.toFixed(3)} |`);
  }

  lines.push('', '## 逐题明细', '', '| 题号 | 领域 | 候选数 | gold 片段 | 首个 gold 排名 | query 去重键 | 状态 |', '| --- | --- | ---: | ---: | ---: | --- | --- |');
  for (const row of report.perCase) {
    const goldCells = row.goldChunkCount === null ? '无标注' : String(row.goldChunkCount);
    const rank = !row.executed
      ? '未执行'
      : (row.goldDocumentId === null ? '无标注' : (row.firstGoldRank === null ? '未命中' : String(row.firstGoldRank)));
    const state = row.executed ? (row.outcome ?? row.status ?? '已执行') : '未执行';
    const queryKey = row.query === null ? '无' : sha256Text(row.query).slice(0, 8);
    lines.push(`| ${row.caseId.slice(0, 26)} | ${row.domain} | ${row.hitCount} | ${goldCells} | ${rank} | ${queryKey} | ${state} |`);
  }

  lines.push(
    '',
    '## 口径与限制',
    '',
    '- gold@k 只表示发布者标注文档的片段出现在前 k 个候选中，不表示片段包含答案、也不表示模型正确使用了它。',
    '- 同一 gold 文档可能被切成多个片段，命中任一片段即算命中；`gold 文档平均片段数` 表示难度参考。',
    '- 无 gold 标注的题目（公开 issue 摘录）不计入召回指标，但仍报告候选数。',
    '- 评估集中 `included: false` 的题目按冻结协议排除，不参与统计。',
    '- 本工具不调用模型，因此不产生费用，也不能替代真人回答审核。',
  );
  return lines.join('\n');
}

function delta(before, after) {
  if (before === null || after === null) return '未测';
  const value = after - before;
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}pp`;
}

function parseArgs(argv) {
  const options = {runDir: null, label: null, casesFile: defaultCases, corpusFile: defaultCorpus, json: null, markdown: null, baseline: null};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const value = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`${arg} 缺少参数值`);
      return argv[index];
    };
    if (arg === '--label') options.label = value();
    else if (arg === '--cases') options.casesFile = value();
    else if (arg === '--corpus') options.corpusFile = value();
    else if (arg === '--json') options.json = value();
    else if (arg === '--markdown') options.markdown = value();
    else if (arg === '--baseline') options.baseline = value();
    else if (arg.startsWith('--')) throw new Error(`未知参数：${arg}`);
    else if (options.runDir === null) options.runDir = arg;
    else throw new Error(`多余的位置参数：${arg}`);
  }
  if (options.runDir === null) throw new Error('用法：node scripts/benchmark/retrieval-eval.mjs <runDir> [--label 文本] [--json 路径] [--markdown 路径] [--baseline 报告.json]');
  return options;
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const report = evaluateRun(options);
  const baseline = options.baseline === null ? null : readJson(options.baseline);
  const json = JSON.stringify(report, null, 2);
  const markdown = renderMarkdown(report, {baseline});
  if (options.json !== null) {
    fs.mkdirSync(path.dirname(options.json), {recursive: true});
    fs.writeFileSync(options.json, `${json}\n`);
  }
  if (options.markdown !== null) {
    fs.mkdirSync(path.dirname(options.markdown), {recursive: true});
    fs.writeFileSync(options.markdown, `${markdown}\n`);
  }
  if (options.json === null && options.markdown === null) console.log(markdown);
  else console.log(JSON.stringify(report.summary));
}

if (import.meta.url === `file://${process.argv[1]}`) main();
