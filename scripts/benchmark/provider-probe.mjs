#!/usr/bin/env node
// Provider 可达性前置检查：在执行任何一次性付费运行之前，确认 chat 与 embedding
// 端点真的可用。它只做最小探测（模型列表 + 一次极短补全 + 一次极短嵌入），
// 不写入仓库，也不修改任何生产配置。
//
// 背景：一次性 comparison claim 不可重跑。若 chat 端点返回 503 时启动运行，
// 整批生成会失败并浪费掉唯一的执行机会，因此把这件事提前到运行之前判断。
//
// 用法：
//   node scripts/benchmark/provider-probe.mjs [--env-file services/support-copilot-ai/.env] [--json 路径]
//
// 退出码：0 = READY，1 = BLOCKED，2 = 用法错误。
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const defaultEnvFile = 'services/support-copilot-ai/.env';
export const requiredKeys = [
  'OPENAI_API_KEY',
  'OPENAI_BASE_URL',
  'OPENAI_CHAT_MODEL',
  'OPENAI_CHAT_PROTOCOL',
  'OPENAI_EMBEDDING_MODEL',
];

export const sha256 = (value) => crypto.createHash('sha256').update(value).digest('hex');

/** 解析 dotenv 风格的键值文件；只返回键值，调用方负责不打印敏感值。 */
export function parseEnv(text) {
  const values = {};
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (trimmed === '' || trimmed.startsWith('#')) continue;
    const index = trimmed.indexOf('=');
    if (index <= 0) continue;
    const key = trimmed.slice(0, index).trim();
    let value = trimmed.slice(index + 1).trim();
    if (value.length >= 2 && ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'")))) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

export function missingKeys(env) {
  return requiredKeys.filter((key) => !env[key]);
}

async function request({url, headers, method = 'GET', body, timeoutMs, fetchImpl}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await response.text();
    return {
      status: response.status,
      ok: response.ok,
      text,
      detail: response.ok ? `body-bytes=${text.length}` : text.replace(/\s+/g, ' ').slice(0, 200),
    };
  } catch (error) {
    return {status: null, ok: false, text: '', detail: `${error.name}: ${error.message}`.slice(0, 200)};
  } finally {
    clearTimeout(timer);
  }
}

/** 探测 chat 与 embedding 端点，返回可序列化结论；不会输出任何密钥。 */
export async function probeProvider({env, timeoutMs = 20000, fetchImpl = fetch}) {
  const missing = missingKeys(env);
  if (missing.length > 0) {
    return {state: 'BLOCKED', blockedBy: ['env-incomplete'], missing, endpoints: {}, checks: []};
  }
  const chatBase = env.OPENAI_BASE_URL.replace(/\/+$/, '');
  const embeddingBase = (env.OPENAI_EMBEDDING_BASE_URL || env.OPENAI_BASE_URL).replace(/\/+$/, '');
  const chatHeaders = {Authorization: `Bearer ${env.OPENAI_API_KEY}`, 'Content-Type': 'application/json'};
  const embeddingHeaders = {Authorization: `Bearer ${env.OPENAI_EMBEDDING_API_KEY || env.OPENAI_API_KEY}`, 'Content-Type': 'application/json'};

  const checks = [];
  const models = await request({url: `${chatBase}/models`, headers: chatHeaders, timeoutMs, fetchImpl});
  let hasTargetModel = null;
  if (models.ok) {
    try {
      const listed = JSON.parse(models.text === '' ? '{}' : models.text);
      hasTargetModel = Array.isArray(listed.data) && listed.data.some((item) => item?.id === env.OPENAI_CHAT_MODEL);
    } catch { hasTargetModel = null; }
  }
  checks.push({name: 'chat-models', status: models.status, ok: models.ok, detail: models.detail});

  const chat = await request({
    url: `${chatBase}/chat/completions`,
    headers: chatHeaders,
    method: 'POST',
    body: {model: env.OPENAI_CHAT_MODEL, messages: [{role: 'user', content: 'ok'}]},
    timeoutMs,
    fetchImpl,
  });
  checks.push({name: 'chat-completion', status: chat.status, ok: chat.ok, detail: chat.detail});

  const embedding = await request({
    url: `${embeddingBase}/embeddings`,
    headers: embeddingHeaders,
    method: 'POST',
    body: {model: env.OPENAI_EMBEDDING_MODEL, input: 'ok'},
    timeoutMs,
    fetchImpl,
  });
  checks.push({name: 'embedding', status: embedding.status, ok: embedding.ok, detail: embedding.detail});

  const blockedBy = checks.filter((check) => !check.ok).map((check) => check.name);
  return {
    state: blockedBy.length === 0 ? 'READY' : 'BLOCKED',
    checkedAt: new Date().toISOString(),
    blockedBy,
    missing: [],
    endpoints: {chat: sha256(chatBase), embedding: sha256(embeddingBase)},
    model: env.OPENAI_CHAT_MODEL,
    protocol: env.OPENAI_CHAT_PROTOCOL,
    hasTargetModel,
    checks,
  };
}

export function renderReport(report) {
  const lines = [
    `# Provider 可达性检查：${report.state}`,
    '',
    `- 检查时间：${report.checkedAt ?? '未记录'}`,
    `- chat 端点 sha256：${report.endpoints.chat ? `${report.endpoints.chat.slice(0, 16)}…` : '未检查'}`,
    `- embedding 端点 sha256：${report.endpoints.embedding ? `${report.endpoints.embedding.slice(0, 16)}…` : '未检查'}`,
    `- chat 模型：${report.model ?? '未配置'}（协议 ${report.protocol ?? '未配置'}）`,
    '',
    '| 检查 | HTTP | 结果 | 响应摘要 |',
    '| --- | ---: | --- | --- |',
  ];
  for (const check of report.checks) {
    lines.push(`| ${check.name} | ${check.status ?? '无响应'} | ${check.ok ? '通过' : '失败'} | ${check.detail === '' ? '（空）' : check.detail.replace(/\|/g, '\\|')} |`);
  }
  if (report.hasTargetModel === false) lines.push('', '注意：模型列表中未找到目标 chat 模型，即使补全成功也应先确认模型名。');
  if (report.missing.length > 0) lines.push('', `缺少配置项：${report.missing.join(', ')}`);
  lines.push(
    '',
    '本检查只做最小探测，`READY` 不保证整批运行成功，也不代表模型质量；`BLOCKED` 时不要启动一次性付费运行。',
  );
  return lines.join('\n');
}

function parseArgs(argv) {
  const options = {envFile: defaultEnvFile, json: null, timeoutMs: 20000};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const value = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`${arg} 缺少参数值`);
      return argv[index];
    };
    if (arg === '--env-file') options.envFile = value();
    else if (arg === '--json') options.json = value();
    else if (arg === '--timeout') options.timeoutMs = Number(value());
    else throw new Error(`未知参数：${arg}`);
  }
  return options;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const env = fs.existsSync(options.envFile) ? parseEnv(fs.readFileSync(options.envFile, 'utf8')) : {};
  const report = await probeProvider({env, timeoutMs: options.timeoutMs});
  if (options.json !== null) {
    fs.mkdirSync(path.dirname(options.json), {recursive: true});
    fs.writeFileSync(options.json, `${JSON.stringify(report, null, 2)}\n`);
  }
  console.log(renderReport(report));
  process.exitCode = report.state === 'READY' ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 2;
  });
}
