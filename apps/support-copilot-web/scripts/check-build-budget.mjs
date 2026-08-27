import { readFile, readdir, stat } from 'node:fs/promises'
import { gzipSync } from 'node:zlib'

const distAssets = new URL('../dist/assets/', import.meta.url)
const budgetUrl = new URL('./bundle-budget.json', import.meta.url)

class BudgetConfigurationError extends Error {
  constructor(message) {
    super(message)
    this.name = 'BudgetConfigurationError'
  }
}

function parseLimit(value, path) {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new BudgetConfigurationError(`${path} must be a positive integer`)
  }
  return value
}

function parseBudget(value) {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new BudgetConfigurationError('bundle budget must be an object')
  }
  const entryJs = value.entryJs
  const lazyChartJs = value.lazyChartJs
  const totalJs = value.totalJs
  const totalCss = value.totalCss
  for (const [path, limit] of Object.entries({ entryJs, lazyChartJs, totalJs, totalCss })) {
    if (typeof limit !== 'object' || limit === null || Array.isArray(limit)) {
      throw new BudgetConfigurationError(`${path} must be an object`)
    }
  }
  return {
    entryJs: {
      rawBytes: parseLimit(entryJs.rawBytes, 'entryJs.rawBytes'),
      gzipBytes: parseLimit(entryJs.gzipBytes, 'entryJs.gzipBytes'),
    },
    lazyChartJs: {
      rawBytes: parseLimit(lazyChartJs.rawBytes, 'lazyChartJs.rawBytes'),
      gzipBytes: parseLimit(lazyChartJs.gzipBytes, 'lazyChartJs.gzipBytes'),
    },
    totalJs: {
      rawBytes: parseLimit(totalJs.rawBytes, 'totalJs.rawBytes'),
      gzipBytes: parseLimit(totalJs.gzipBytes, 'totalJs.gzipBytes'),
    },
    totalCss: {
      rawBytes: parseLimit(totalCss.rawBytes, 'totalCss.rawBytes'),
      gzipBytes: parseLimit(totalCss.gzipBytes, 'totalCss.gzipBytes'),
    },
  }
}

async function assetSize(fileName) {
  const fileUrl = new URL(fileName, distAssets)
  const [metadata, contents] = await Promise.all([stat(fileUrl), readFile(fileUrl)])
  return { rawBytes: metadata.size, gzipBytes: gzipSync(contents).byteLength }
}

function sumSizes(sizes) {
  return sizes.reduce(
    (total, size) => ({
      rawBytes: total.rawBytes + size.rawBytes,
      gzipBytes: total.gzipBytes + size.gzipBytes,
    }),
    { rawBytes: 0, gzipBytes: 0 },
  )
}

function assertWithinBudget(label, measured, limit) {
  const passed = measured.rawBytes <= limit.rawBytes && measured.gzipBytes <= limit.gzipBytes
  console.log(`${label}: raw=${measured.rawBytes}/${limit.rawBytes} gzip=${measured.gzipBytes}/${limit.gzipBytes} ${passed ? 'PASS' : 'FAIL'}`)
  return passed
}

const budget = parseBudget(JSON.parse(await readFile(budgetUrl, 'utf8')))
const files = await readdir(distAssets)
const jsFiles = files.filter((fileName) => fileName.endsWith('.js'))
const cssFiles = files.filter((fileName) => fileName.endsWith('.css'))
const entryFiles = jsFiles.filter((fileName) => fileName.startsWith('index-'))
const lazyChartFiles = jsFiles.filter((fileName) => fileName.startsWith('OverviewView-'))
if (entryFiles.length !== 1) {
  throw new BudgetConfigurationError(`expected one index JS entry asset, found ${entryFiles.length}`)
}
if (lazyChartFiles.length !== 1) {
  throw new BudgetConfigurationError(`expected one lazy OverviewView chart asset, found ${lazyChartFiles.length}`)
}

const [entryJs, lazyChartJs, jsSizes, cssSizes] = await Promise.all([
  assetSize(entryFiles[0]),
  assetSize(lazyChartFiles[0]),
  Promise.all(jsFiles.map(assetSize)),
  Promise.all(cssFiles.map(assetSize)),
])
const checks = [
  assertWithinBudget('entry-js', entryJs, budget.entryJs),
  assertWithinBudget('lazy-chart-js', lazyChartJs, budget.lazyChartJs),
  assertWithinBudget('total-js', sumSizes(jsSizes), budget.totalJs),
  assertWithinBudget('total-css', sumSizes(cssSizes), budget.totalCss),
]
if (checks.includes(false)) process.exitCode = 1
