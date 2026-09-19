import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { createServer } from 'node:net'
import test from 'node:test'
import { setImmediate as nextTurn } from 'node:timers/promises'
import { ChildProcessError, ManagedChildRunner, isAddressCollision, portIsReleased, retryPortCollisions } from './managed-child.mjs'

async function availablePort() {
  const server = createServer()
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  const address = server.address()
  if (address === null || typeof address === 'string') throw new TypeError('expected TCP address')
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()))
  return address.port
}

test('terminate stops the active process group before the owned port check', async () => {
  // Given: a managed parent whose child owns a loopback HTTP port.
  const port = await availablePort()
  const runner = new ManagedChildRunner()
  let ready
  const readySignal = new Promise((resolve) => { ready = resolve })
  const script = `const {spawn}=require('node:child_process'); const child=spawn(process.execPath,['-e',${JSON.stringify(`require('node:http').createServer((_,r)=>r.end('ok')).listen(${port},'127.0.0.1',()=>console.log('READY'))`)}],{stdio:['ignore','inherit','inherit']}); setInterval(()=>{},1000);`
  const running = runner.run(process.execPath, ['-e', script], process.env, 10_000, (output) => {
    if (output.includes('READY')) ready()
  })
  await readySignal
  assert.equal(await portIsReleased(port), false)

  // When: cleanup terminates and awaits the complete process group.
  await runner.terminate('SIGTERM')
  await assert.rejects(running)

  // Then: the child server port is bindable before evidence would be written.
  assert.equal(await portIsReleased(port), true)
})

test('parent exit retains cleanup ownership until inherited pipes close', { timeout: 10_000 }, async (t) => {
  // Given: a grandchild holds both a port and the managed stdout pipe after its parent exits.
  const port = await availablePort()
  const runner = new ManagedChildRunner()
  let ready
  const readySignal = new Promise((resolve) => { ready = resolve })
  const serverScript = `process.on('SIGTERM',()=>{}); require('node:http').createServer((_,r)=>r.end('ok')).listen(${port},'127.0.0.1',()=>console.log('READY'))`
  const parentScript = `require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(serverScript)}],{stdio:['ignore','inherit','inherit']}); setInterval(()=>{},1000)`
  let settled = false
  const running = runner.run(process.execPath, ['-e', parentScript], process.env, 8_000, (output) => {
    if (output.includes('READY')) ready()
  })
  const outcome = running.then(() => { settled = true }, (error) => { settled = true; return error })
  const parent = runner.active
  const closed = once(parent, 'close')
  t.after(async () => {
    // Cleanup also works against the broken implementation, which has already lost active.
    try { process.kill(-parent.pid, 'SIGKILL') } catch (error) {
      if (error.code !== 'ESRCH') throw error
    }
    await closed
    await outcome
  })
  await readySignal

  // When: only the direct parent exits; the descendant is deliberately still alive.
  const exited = once(parent, 'exit')
  parent.kill('SIGTERM')
  await exited
  await nextTurn()

  // Then: run cannot settle or relinquish the group before resource completion.
  assert.equal(settled, false, 'direct parent exit must not complete the managed run')
  assert.equal(await portIsReleased(port), false)
  await runner.terminate('SIGTERM')
  assert.ok(await outcome instanceof ChildProcessError)
  assert.equal(await portIsReleased(port), true)
})

test('timeout remains a failure when the child handles SIGTERM with exit zero', { timeout: 10_000 }, async () => {
  // Given: a real child explicitly reports successful exit from its shutdown handler.
  const runner = new ManagedChildRunner()
  const script = `process.on('SIGTERM',()=>process.exit(0)); console.log('READY'); setInterval(()=>{},1000)`
  let ready = false

  // When/Then: expiration must still reject with a nonzero status for CLI callers.
  await assert.rejects(
    runner.run(process.execPath, ['-e', script], process.env, 5_000, (output) => { ready ||= output.includes('READY') }),
    (error) => error instanceof ChildProcessError && error.exitCode !== 0,
  )
  assert.equal(ready, true)
})

for (const signal of ['SIGINT', 'SIGTERM']) {
  test(`${signal} cleanup stops the owned process group and releases its port`, async () => {
    // Given: a separate runner process owns a child process group and loopback port.
    const port = await availablePort()
    const moduleUrl = new URL('./managed-child.mjs', import.meta.url).href
    const serverScript = `require('node:http').createServer((_,response)=>response.end('ok')).listen(${port},'127.0.0.1',()=>console.log('READY'))`
    const harnessScript = `import {ManagedChildRunner,installSignalCleanup} from ${JSON.stringify(moduleUrl)}; const runner=new ManagedChildRunner(); let received=null; const cleanup=installSignalCleanup(runner,(signal)=>{received=signal}); try { await runner.run(process.execPath,['-e',${JSON.stringify(serverScript)}],process.env,30000); } catch {} cleanup.dispose(); console.log('RECEIVED:'+received);`
    const harness = spawn(process.execPath, ['--input-type=module', '-e', harnessScript], { stdio: ['ignore', 'pipe', 'pipe'] })
    let output = ''
    harness.stdout.on('data', (chunk) => { output += chunk.toString() })
    harness.stderr.on('data', (chunk) => { output += chunk.toString() })
    while (!output.includes('READY')) await once(harness.stdout, 'data')
    assert.equal(await portIsReleased(port), false)

    // When: the runner receives the parent interruption signal.
    harness.kill(signal)
    await once(harness, 'exit')

    // Then: the shared handler records the signal and releases the complete child group.
    assert.match(output, new RegExp(`RECEIVED:${signal}`))
    assert.equal(await portIsReleased(port), true)
  })
}

test('owned port collisions retry once and then run on a newly allocated port', async () => {
  // Given: the first selected port is occupied and the second is available.
  const occupiedPort = await availablePort()
  const available = await availablePort()
  const owner = createServer()
  owner.listen(occupiedPort, '127.0.0.1')
  await once(owner, 'listening')
  const ports = [occupiedPort, available]
  const runner = new ManagedChildRunner()

  // When: the bounded retry runs a real listener command for each selected port.
  const selectedPort = await retryPortCollisions(3, async (attemptNumber) => {
    const port = ports[attemptNumber - 1]
    if (port === undefined) throw new TypeError('missing port fixture')
    const listenScript = `const server=require('node:net').createServer(); server.once('error',(error)=>{console.error(error.code); process.exit(1)}); server.listen(${port},'127.0.0.1',()=>server.close())`
    await runner.run(process.execPath, ['-e', listenScript], process.env)
    return port
  })
  await new Promise((resolve, reject) => owner.close((error) => error ? reject(error) : resolve()))

  // Then: EADDRINUSE is recognized and only the fresh owned port succeeds.
  assert.equal(selectedPort, available)
  assert.equal(await portIsReleased(occupiedPort), true)
})

test('owned port collision retries stop at the configured bound', async () => {
  // Given: every attempt reports the owned-port collision signature.
  let attempts = 0

  // When/Then: the collision escapes after exactly three attempts.
  await assert.rejects(
    retryPortCollisions(3, async () => {
      attempts += 1
      throw new ChildProcessError('fixture listener', 1, 'EADDRINUSE')
    }),
    isAddressCollision,
  )
  assert.equal(attempts, 3)
})
