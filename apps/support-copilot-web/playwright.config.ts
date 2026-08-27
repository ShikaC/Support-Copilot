import { defineConfig } from '@playwright/test'

function requiredPort(name: 'TASK12_APP_PORT' | 'TASK12_API_PORT') {
  const value = process.env[name]
  const port = value === undefined ? Number.NaN : Number(value)
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    throw new Error(`${name} must be an unprivileged TCP port`)
  }
  return port
}

const appPort = requiredPort('TASK12_APP_PORT')
const apiPort = requiredPort('TASK12_API_PORT')
const appUrl = `http://127.0.0.1:${appPort}`
const apiUrl = `http://127.0.0.1:${apiPort}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  outputDir: '../../.omo/evidence/task-12-playwright-results',
  reporter: [
    ['line'],
    ['json', { outputFile: '../../.omo/evidence/task-12-playwright-report.json' }],
  ],
  use: {
    baseURL: appUrl,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'off',
  },
  webServer: [
    {
      command: 'node e2e/mock-api.mjs',
      env: { ...process.env, TASK12_API_PORT: String(apiPort) },
      url: `${apiUrl}/__health`,
      reuseExistingServer: false,
      timeout: 20_000,
    },
    {
      command: `npm run preview -- --host 127.0.0.1 --port ${appPort}`,
      env: { ...process.env, VITE_DEV_API_TARGET: apiUrl },
      url: appUrl,
      reuseExistingServer: false,
      timeout: 20_000,
    },
  ],
  projects: [
    { name: 'mobile-375x812', use: { viewport: { width: 375, height: 812 } } },
    { name: 'tablet-768x1024', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'desktop-1280x800', use: { viewport: { width: 1280, height: 800 } } },
  ],
})
