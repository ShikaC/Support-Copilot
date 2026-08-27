import { readFile, readdir, stat } from 'node:fs/promises'
import { pathToFileURL } from 'node:url'
import { gzipSync } from 'node:zlib'

const distUrl = new URL('../dist/', import.meta.url)
const distAssets = new URL('./assets/', distUrl)
const manifestUrl = new URL('./.vite/manifest.json', distUrl)
const budgetUrl = new URL('./bundle-budget.json', import.meta.url)

class BudgetConfigurationError extends Error {
  constructor(message) {
    super(message)
    this.name = 'BudgetConfigurationError'
  }
}

function integer(value, path, positive = false) {
  if (!Number.isSafeInteger(value) || (positive && value <= 0)) {
    throw new BudgetConfigurationError(`${path} must be ${positive ? 'a positive' : 'an'} integer`)
  }
  return value
}

function size(value, path, positive = false) {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new BudgetConfigurationError(`${path} must be an object`)
  }
  return {
    rawBytes: integer(value.rawBytes, `${path}.rawBytes`, positive),
    gzipBytes: integer(value.gzipBytes, `${path}.gzipBytes`, positive),
  }
}

function parseBudget(value) {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new BudgetConfigurationError('bundle budget must be an object')
  }
  const parsed = {}
  for (const label of ['initialJs', 'lazyChartJs', 'totalJs', 'totalCss']) {
    const policy = value[label]
    if (typeof policy !== 'object' || policy === null || Array.isArray(policy) || typeof policy.rationale !== 'string' || policy.rationale.length === 0) {
      throw new BudgetConfigurationError(`${label} must contain a rationale`)
    }
    const baseline = size(policy.baseline, `${label}.baseline`)
    const permittedDelta = size(policy.permittedDelta, `${label}.permittedDelta`)
    const limit = size(policy.limit, `${label}.limit`, true)
    if (baseline.rawBytes + permittedDelta.rawBytes !== limit.rawBytes || baseline.gzipBytes + permittedDelta.gzipBytes !== limit.gzipBytes) {
      throw new BudgetConfigurationError(`${label}.limit must equal baseline plus permittedDelta`)
    }
    parsed[label] = { baseline, permittedDelta, limit, rationale: policy.rationale }
  }
  return parsed
}

function parseManifest(value) {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new BudgetConfigurationError('Vite manifest must be an object')
  }
  return value
}

export function collectStaticEntryFiles(manifest, entryKey = 'index.html') {
  const entry = manifest[entryKey]
  if (typeof entry !== 'object' || entry === null || Array.isArray(entry) || entry.isEntry !== true) {
    throw new BudgetConfigurationError(`missing Vite HTML entry ${entryKey}`)
  }
  const visited = new Set()
  const files = new Set()
  const visit = (key) => {
    if (visited.has(key)) return
    visited.add(key)
    const record = manifest[key]
    if (typeof record !== 'object' || record === null || Array.isArray(record) || typeof record.file !== 'string') {
      throw new BudgetConfigurationError(`invalid manifest record ${key}`)
    }
    if (record.file.endsWith('.js')) files.add(record.file)
    if (record.imports !== undefined) {
      if (!Array.isArray(record.imports) || record.imports.some((item) => typeof item !== 'string')) {
        throw new BudgetConfigurationError(`invalid imports for ${key}`)
      }
      for (const importedKey of record.imports) visit(importedKey)
    }
  }
  visit(entryKey)
  return [...files]
}

async function assetSize(relativeFile) {
  const fileUrl = new URL(relativeFile.startsWith('assets/') ? relativeFile : `assets/${relativeFile}`, distUrl)
  const [metadata, contents] = await Promise.all([stat(fileUrl), readFile(fileUrl)])
  return { rawBytes: metadata.size, gzipBytes: gzipSync(contents).byteLength }
}

function sumSizes(sizes) {
  return sizes.reduce((total, current) => ({
    rawBytes: total.rawBytes + current.rawBytes,
    gzipBytes: total.gzipBytes + current.gzipBytes,
  }), { rawBytes: 0, gzipBytes: 0 })
}

export async function measureStaticEntryGraph(manifest, sizeOf, entryKey = 'index.html') {
  const files = collectStaticEntryFiles(manifest, entryKey)
  const sizes = await Promise.all(files.map(sizeOf))
  return { files, measured: sumSizes(sizes) }
}

export function isWithinLimit(measured, limit) {
  return measured.rawBytes <= limit.rawBytes && measured.gzipBytes <= limit.gzipBytes
}

function report(label, measured, policy) {
  const passed = isWithinLimit(measured, policy.limit)
  console.log(`${label}: raw=${measured.rawBytes}/${policy.limit.rawBytes} gzip=${measured.gzipBytes}/${policy.limit.gzipBytes} ${passed ? 'PASS' : 'FAIL'}`)
  return passed
}

async function main() {
  const [budgetValue, manifestValue, assetNames] = await Promise.all([
    readFile(budgetUrl, 'utf8').then(JSON.parse),
    readFile(manifestUrl, 'utf8').then(JSON.parse),
    readdir(distAssets),
  ])
  const budget = parseBudget(budgetValue)
  const manifest = parseManifest(manifestValue)
  const chartKey = Object.keys(manifest).find((key) => key.endsWith('/OverviewView.tsx'))
  if (chartKey === undefined) throw new BudgetConfigurationError('missing lazy OverviewView manifest entry')
  const chartManifest = { ...manifest, 'index.html': { ...manifest[chartKey], isEntry: true } }
  const jsFiles = assetNames.filter((name) => name.endsWith('.js'))
  const cssFiles = assetNames.filter((name) => name.endsWith('.css'))
  const initialGraph = await measureStaticEntryGraph(manifest, assetSize)
  const initialFileSet = new Set(initialGraph.files)
  const lazyChartFiles = collectStaticEntryFiles(chartManifest).filter((file) => !initialFileSet.has(file))
  const [chartSizes, jsSizes, cssSizes] = await Promise.all([
    Promise.all(lazyChartFiles.map(assetSize)),
    Promise.all(jsFiles.map(assetSize)),
    Promise.all(cssFiles.map(assetSize)),
  ])
  console.log(`initial-js-files: ${initialGraph.files.join(',')}`)
  console.log(`lazy-chart-js-files: ${lazyChartFiles.join(',')}`)
  const checks = [
    report('initial-js', initialGraph.measured, budget.initialJs),
    report('lazy-chart-js', sumSizes(chartSizes), budget.lazyChartJs),
    report('total-js', sumSizes(jsSizes), budget.totalJs),
    report('total-css', sumSizes(cssSizes), budget.totalCss),
  ]
  if (checks.includes(false)) process.exitCode = 1
}

if (process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href) await main()
