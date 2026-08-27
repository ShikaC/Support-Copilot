import { spawn } from 'node:child_process'
import { createServer } from 'node:net'

export class ChildProcessError extends Error {
  constructor(command, exitCode, output = '') {
    super(`${command} exited with ${exitCode}`)
    this.name = 'ChildProcessError'
    this.exitCode = exitCode
    this.output = output
  }
}

function waitForExit(child) {
  return new Promise((resolve, reject) => {
    child.once('error', reject)
    child.once('exit', (code, signal) => resolve({ code: code ?? 1, signal }))
  })
}

async function signalProcessGroup(pid, signal) {
  const target = process.platform === 'win32' ? pid : -pid
  try {
    process.kill(target, signal)
  } catch (error) {
    if (!(error instanceof Error) || !('code' in error) || error.code !== 'ESRCH') throw error
  }
}

export class ManagedChildRunner {
  active = null
  activeExit = null
  stopping = false

  async run(command, args, environment, timeoutMs = 300_000, onOutput = () => undefined) {
    if (this.stopping) throw new ChildProcessError(command, 1, 'runner is stopping')
    const child = spawn(command, args, {
      detached: process.platform !== 'win32',
      env: environment,
      stdio: ['inherit', 'pipe', 'pipe'],
    })
    this.active = child
    this.activeExit = waitForExit(child)
    let output = ''
    const record = (stream, chunk) => {
      const text = chunk.toString()
      stream.write(text)
      output = `${output}${text}`.slice(-65_536)
      onOutput(text)
    }
    child.stdout.on('data', (chunk) => record(process.stdout, chunk))
    child.stderr.on('data', (chunk) => record(process.stderr, chunk))
    const timeout = setTimeout(() => {
      void this.terminate('SIGTERM')
    }, timeoutMs)
    try {
      const result = await this.activeExit
      if (result.code !== 0 || result.signal !== null) {
        throw new ChildProcessError(`${command} ${args.join(' ')}`, result.code, output)
      }
    } finally {
      clearTimeout(timeout)
      if (this.active === child) {
        this.active = null
        this.activeExit = null
      }
    }
  }

  async terminate(signal = 'SIGTERM') {
    this.stopping = true
    const child = this.active
    const exit = this.activeExit
    if (child === null || exit === null) return
    if (child.pid === undefined) throw new ChildProcessError('terminate child process group', 1, 'child PID is unavailable')
    const childPid = child.pid
    await signalProcessGroup(childPid, signal)
    const stopped = await Promise.race([
      exit.then(() => true),
      new Promise((resolve) => setTimeout(() => resolve(false), 2_000)),
    ])
    if (!stopped) {
      await signalProcessGroup(childPid, 'SIGKILL')
      await exit
    }
    if (process.platform !== 'win32') await signalProcessGroup(childPid, 'SIGKILL')
  }
}

export async function portIsReleased(port) {
  const server = createServer()
  return new Promise((resolve) => {
    server.once('error', () => resolve(false))
    server.listen(port, '127.0.0.1', () => server.close(() => resolve(true)))
  })
}

export function installSignalCleanup(runner, onSignal) {
  let receivedSignal = null
  const stop = (signal) => {
    if (receivedSignal !== null) return
    receivedSignal = signal
    onSignal(signal)
    void runner.terminate('SIGTERM')
  }
  const onSigint = () => stop('SIGINT')
  const onSigterm = () => stop('SIGTERM')
  process.once('SIGINT', onSigint)
  process.once('SIGTERM', onSigterm)
  return {
    get receivedSignal() { return receivedSignal },
    dispose() {
      process.removeListener('SIGINT', onSigint)
      process.removeListener('SIGTERM', onSigterm)
    },
  }
}

export function isAddressCollision(error) {
  return error instanceof ChildProcessError && /EADDRINUSE|address already in use|port is already used/i.test(error.output)
}

export async function retryPortCollisions(maximumAttempts, attempt, collision = isAddressCollision) {
  if (!Number.isSafeInteger(maximumAttempts) || maximumAttempts <= 0) {
    throw new TypeError('maximumAttempts must be a positive integer')
  }
  for (let attemptNumber = 1; attemptNumber <= maximumAttempts; attemptNumber += 1) {
    try {
      return await attempt(attemptNumber)
    } catch (error) {
      if (attemptNumber === maximumAttempts || !collision(error)) throw error
    }
  }
  throw new TypeError('unreachable port retry state')
}
