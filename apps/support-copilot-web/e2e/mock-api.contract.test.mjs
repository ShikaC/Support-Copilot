import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { createServer } from 'node:net'
import { after, before, test } from 'node:test'

const authorization = 'Bearer synthetic-browser-token-task12'
let api
let baseUrl

async function availablePort() {
  const server = createServer()
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  const address = server.address()
  if (address === null || typeof address === 'string') throw new TypeError('expected TCP address')
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()))
  return address.port
}

async function assertContractError(response, status) {
  assert.equal(response.status, status)
  const payload = await response.json()
  assert.equal(typeof payload.code, 'string')
  assert.equal(typeof payload.message, 'string')
  assert.equal(typeof payload.traceId, 'string')
}

before(async () => {
  const port = await availablePort()
  baseUrl = `http://127.0.0.1:${port}`
  api = spawn(process.execPath, ['e2e/mock-api.mjs'], {
    cwd: process.cwd(), env: { ...process.env, TASK12_API_PORT: String(port) }, stdio: ['ignore', 'pipe', 'inherit'],
  })
  await new Promise((resolve, reject) => {
    api.once('error', reject)
    api.stdout.on('data', (chunk) => {
      if (chunk.toString().includes('Task12 mock API listening')) resolve()
    })
  })
})

after(async () => {
  if (api.exitCode === null) api.kill('SIGTERM')
  if (api.exitCode === null) await once(api, 'exit')
})

test('mutable endpoints reject an incorrect method', async () => {
  // Given: an authenticated request to a mutable rejection endpoint.
  const response = await fetch(`${baseUrl}/api/tickets/ticket-10042/analyses/analysis-success/reviews/reject`, { headers: { Authorization: authorization } })

  // When/Then: the fixture rejects the method with a contract-shaped response.
  await assertContractError(response, 405)
})

test('mutable endpoints reject a missing idempotency header', async () => {
  // Given: an authenticated analysis command without an idempotency key.
  const response = await fetch(`${baseUrl}/api/tickets/ticket-10042/analyze`, { method: 'POST', headers: { Authorization: authorization, 'Content-Type': 'application/json' }, body: '{}' })

  // When/Then: the fixture rejects the command with a contract-shaped response.
  await assertContractError(response, 400)
})

test('versioned endpoints reject a missing body version', async () => {
  // Given: a release command whose DTO omits the required current version.
  const response = await fetch(`${baseUrl}/api/knowledge/releases/release-2026-08/approve`, { method: 'POST', headers: { Authorization: authorization, 'Content-Type': 'application/json' }, body: '{}' })

  // When/Then: the fixture rejects the underspecified Spring request body.
  await assertContractError(response, 422)
})

test('mutable endpoints reject an underspecified body', async () => {
  // Given: an idempotent rejection command with an empty reason.
  const response = await fetch(`${baseUrl}/api/tickets/ticket-10042/analyses/analysis-success/reviews/reject`, { method: 'POST', headers: { Authorization: authorization, 'Content-Type': 'application/json', 'Idempotency-Key': 'fixture-key' }, body: JSON.stringify({ reason: ' ' }) })

  // When/Then: the fixture rejects the invalid body contract.
  await assertContractError(response, 422)
})
