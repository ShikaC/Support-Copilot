import test from 'node:test';
import assert from 'node:assert/strict';
import {missingKeys, parseEnv, probeProvider, renderReport} from './provider-probe.mjs';

const env = {
  OPENAI_API_KEY: 'sk-test-placeholder-value',
  OPENAI_BASE_URL: 'https://gateway.invalid/v1',
  OPENAI_CHAT_MODEL: 'test-chat-model',
  OPENAI_CHAT_PROTOCOL: 'chat_completions',
  OPENAI_EMBEDDING_MODEL: 'test-embedding-model',
};

function mockFetch(routes) {
  const calls = [];
  const impl = async (url, options = {}) => {
    calls.push(`${options.method ?? 'GET'} ${url}`);
    const handler = routes[`${options.method ?? 'GET'} ${url}`] ?? routes[url] ?? {status: 404, body: '{}'};
    return {
      ok: handler.status >= 200 && handler.status < 300,
      status: handler.status,
      text: async () => handler.body ?? '',
    };
  };
  impl.calls = calls;
  return impl;
}

test('parseEnv reads keys, ignores comments, and strips quotes', () => {
  const parsed = parseEnv('# comment\nA_KEY=plain\nB_KEY="quoted"\nC_KEY=\'single\'\n\nBAD_LINE\n');
  assert.deepEqual(parsed, {A_KEY: 'plain', B_KEY: 'quoted', C_KEY: 'single'});
});

test('missingKeys reports every absent required setting', () => {
  assert.deepEqual(missingKeys(env), []);
  assert.deepEqual(missingKeys({...env, OPENAI_API_KEY: ''}), ['OPENAI_API_KEY']);
});

test('probeProvider reports READY when all three endpoints answer', async () => {
  const fetchImpl = mockFetch({
    'GET https://gateway.invalid/v1/models': {status: 200, body: JSON.stringify({data: [{id: 'test-chat-model'}]})},
    'POST https://gateway.invalid/v1/chat/completions': {status: 200, body: '{"choices":[]}'},
    'POST https://gateway.invalid/v1/embeddings': {status: 200, body: '{"data":[]}'},
  });
  const report = await probeProvider({env, fetchImpl});
  assert.equal(report.state, 'READY');
  assert.deepEqual(report.blockedBy, []);
  assert.equal(report.hasTargetModel, true);
  assert.equal(report.checks.length, 3);
  assert.equal(fetchImpl.calls.length, 3);
});

test('probeProvider reports BLOCKED when chat returns 503', async () => {
  const fetchImpl = mockFetch({
    'GET https://gateway.invalid/v1/models': {status: 200, body: JSON.stringify({data: [{id: 'test-chat-model'}]})},
    'POST https://gateway.invalid/v1/chat/completions': {status: 503, body: '{"error":{"message":"Service temporarily unavailable"}}'},
    'POST https://gateway.invalid/v1/embeddings': {status: 200, body: '{"data":[]}'},
  });
  const report = await probeProvider({env, fetchImpl});
  assert.equal(report.state, 'BLOCKED');
  assert.deepEqual(report.blockedBy, ['chat-completion']);
  const markdown = renderReport(report);
  assert.match(markdown, /Service temporarily unavailable/);
  assert.match(markdown, /BLOCKED/);
});

test('probeProvider blocks on incomplete configuration without calling the gateway', async () => {
  const fetchImpl = mockFetch({});
  const report = await probeProvider({env: {...env, OPENAI_API_KEY: ''}, fetchImpl});
  assert.equal(report.state, 'BLOCKED');
  assert.deepEqual(report.missing, ['OPENAI_API_KEY']);
  assert.equal(fetchImpl.calls.length, 0);
});

test('probeProvider flags a missing target model while still reporting endpoint health', async () => {
  const fetchImpl = mockFetch({
    'GET https://gateway.invalid/v1/models': {status: 200, body: JSON.stringify({data: [{id: 'other-model'}]})},
    'POST https://gateway.invalid/v1/chat/completions': {status: 200, body: '{}'},
    'POST https://gateway.invalid/v1/embeddings': {status: 200, body: '{}'},
  });
  const report = await probeProvider({env, fetchImpl});
  assert.equal(report.state, 'READY');
  assert.equal(report.hasTargetModel, false);
  assert.match(renderReport(report), /未找到目标 chat 模型/);
});

test('reports never contain the configured credential', async () => {
  const fetchImpl = mockFetch({
    'GET https://gateway.invalid/v1/models': {status: 503, body: '{"error":{"message":"down"}}'},
    'POST https://gateway.invalid/v1/chat/completions': {status: 503, body: '{"error":{"message":"down"}}'},
    'POST https://gateway.invalid/v1/embeddings': {status: 503, body: '{"error":{"message":"down"}}'},
  });
  const report = await probeProvider({env, fetchImpl});
  const serialized = `${JSON.stringify(report)}\n${renderReport(report)}`;
  assert.equal(serialized.includes('sk-test-placeholder-value'), false);
});

test('an unreachable endpoint is reported as a network failure rather than a status code', async () => {
  const impl = async () => { throw new TypeError('fetch failed'); };
  const report = await probeProvider({env, fetchImpl: impl});
  assert.equal(report.state, 'BLOCKED');
  assert.equal(report.checks[0].status, null);
  assert.match(report.checks[0].detail, /fetch failed/);
});
