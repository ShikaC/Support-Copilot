import { existsSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import { createServer } from 'node:net'
import { chromium } from 'playwright'
import { ChildProcessError, ManagedChildRunner, installSignalCleanup, portIsReleased, retryPortCollisions } from './managed-child.mjs'

const evidenceDirectory = new URL('../../../.omo/evidence/', import.meta.url)
const maximumPortAttempts = 3

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

const runner = new ManagedChildRunner()
let receivedSignal = null
const signalCleanup = installSignalCleanup(runner, (signal) => {
  receivedSignal = signal
})

let appPort = 0
let apiPort = 0
let exitCode = 0
let detail = 'playwright completed and both isolated ports were released'
let browserProvisioning = 'existing Chromium executable'
let appReleased = false
let apiReleased = false
const baseEnvironment = { ...process.env, VITE_AUTH_MODE: 'secured' }
const playwrightArguments = process.argv.slice(2)

try {
  if (!existsSync(chromium.executablePath())) {
    browserProvisioning = 'Chromium installed because no declared Playwright executable was present'
    await runner.run('node_modules/.bin/playwright', ['install', 'chromium'], baseEnvironment)
  }
  await runner.run('npm', ['run', 'build'], baseEnvironment)
  await retryPortCollisions(maximumPortAttempts, async () => {
    if (receivedSignal !== null) throw new ChildProcessError(`interrupted by ${receivedSignal}`, 1)
    ;[appPort, apiPort] = await Promise.all([availablePort(), availablePort()])
    const environment = {
      ...baseEnvironment,
      TASK12_APP_PORT: String(appPort),
      TASK12_API_PORT: String(apiPort),
    }
    await runner.run('node_modules/.bin/playwright', ['test', ...playwrightArguments], environment)
  })
} catch (error) {
  exitCode = error instanceof ChildProcessError ? error.exitCode : 1
  detail = error instanceof Error ? error.message : 'unknown Playwright runner failure'
} finally {
  await runner.terminate('SIGTERM')
  ;[appReleased, apiReleased] = await Promise.all([
    appPort === 0 ? Promise.resolve(true) : portIsReleased(appPort),
    apiPort === 0 ? Promise.resolve(true) : portIsReleased(apiPort),
  ])
  if (!appReleased || !apiReleased) {
    exitCode = 1
    detail = `cleanup failed: appReleased=${appReleased} apiReleased=${apiReleased}`
  }
  if (receivedSignal !== null) {
    exitCode = receivedSignal === 'SIGINT' ? 130 : 143
    detail = `interrupted by ${receivedSignal}; active process group terminated before port verification`
  }
  await mkdir(evidenceDirectory, { recursive: true })
  await writeFile(
    new URL('task-12-browser-cleanup.txt', evidenceDirectory),
    `app_port=${appPort}\napi_port=${apiPort}\napp_released=${appReleased}\napi_released=${apiReleased}\nbrowser_provisioning=${browserProvisioning}\nexit_code=${exitCode}\ndetail=${detail}\n`,
  )
  signalCleanup.dispose()
  console.log(`Task12 cleanup: appReleased=${appReleased} apiReleased=${apiReleased}`)
}
process.exitCode = exitCode
