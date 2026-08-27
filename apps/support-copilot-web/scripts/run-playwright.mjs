import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import { createServer } from 'node:net'
import { chromium } from 'playwright'

const evidenceDirectory = new URL('../../../.omo/evidence/', import.meta.url)

class ChildProcessError extends Error {
  constructor(command, exitCode) {
    super(`${command} exited with ${exitCode}`)
    this.name = 'ChildProcessError'
    this.exitCode = exitCode
  }
}

async function availablePort() {
  const server = createServer()
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  const address = server.address()
  if (address === null || typeof address === 'string') {
    server.close()
    throw new ChildProcessError('allocate loopback port', 1)
  }
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()))
  return address.port
}

async function run(command, args, environment, timeoutMs = 300_000) {
  const child = spawn(command, args, { env: environment, stdio: 'inherit', signal: AbortSignal.timeout(timeoutMs) })
  const exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject)
    child.once('exit', (code) => resolve(code ?? 1))
  })
  if (exitCode !== 0) throw new ChildProcessError(`${command} ${args.join(' ')}`, exitCode)
}

async function portIsReleased(port) {
  const server = createServer()
  return new Promise((resolve) => {
    server.once('error', () => resolve(false))
    server.listen(port, '127.0.0.1', () => server.close(() => resolve(true)))
  })
}

const [appPort, apiPort] = await Promise.all([availablePort(), availablePort()])
const environment = {
  ...process.env,
  TASK12_APP_PORT: String(appPort),
  TASK12_API_PORT: String(apiPort),
  VITE_AUTH_MODE: 'secured',
}
let exitCode = 0
let detail = 'playwright completed and both isolated ports were released'
let browserProvisioning = 'existing Chromium executable'
try {
  if (!existsSync(chromium.executablePath())) {
    browserProvisioning = 'Chromium installed because no declared Playwright executable was present'
    await run('node_modules/.bin/playwright', ['install', 'chromium'], environment)
  }
  await run('npm', ['run', 'build'], environment)
  await run('node_modules/.bin/playwright', ['test'], environment)
} catch (error) {
  exitCode = error instanceof ChildProcessError ? error.exitCode : 1
  detail = error instanceof Error ? error.message : 'unknown Playwright runner failure'
} finally {
  const [appReleased, apiReleased] = await Promise.all([portIsReleased(appPort), portIsReleased(apiPort)])
  if (!appReleased || !apiReleased) {
    exitCode = 1
    detail = `cleanup failed: appReleased=${appReleased} apiReleased=${apiReleased}`
  }
  await mkdir(evidenceDirectory, { recursive: true })
  await writeFile(
    new URL('task-12-browser-cleanup.txt', evidenceDirectory),
    `app_port=${appPort}\napi_port=${apiPort}\napp_released=${appReleased}\napi_released=${apiReleased}\nbrowser_provisioning=${browserProvisioning}\nexit_code=${exitCode}\ndetail=${detail}\n`,
  )
  console.log(`Task12 cleanup: appReleased=${appReleased} apiReleased=${apiReleased}`)
}
process.exitCode = exitCode
