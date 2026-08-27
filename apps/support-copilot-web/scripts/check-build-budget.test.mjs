import assert from 'node:assert/strict'
import test from 'node:test'
import { collectStaticEntryFiles, isWithinLimit, measureStaticEntryGraph } from './check-build-budget.mjs'

test('collectStaticEntryFiles traverses every transitive static import', () => {
  // Given: an HTML entry whose dependency is only reachable through another import.
  const manifest = {
    'index.html': { file: 'assets/index.js', isEntry: true, imports: ['shared', 'transitive'] },
    shared: { file: 'assets/shared.js', imports: ['transitive'] },
    transitive: { file: 'assets/transitive.js' },
    lazy: { file: 'assets/lazy.js', isDynamicEntry: true },
  }

  // When: the initial static graph is collected.
  const files = collectStaticEntryFiles(manifest)

  // Then: the transitive import is initial and the lazy entry is excluded.
  assert.deepEqual(files, ['assets/index.js', 'assets/shared.js', 'assets/transitive.js'])
})

test('transitive static imports make the initial graph fail its budget', async () => {
  // Given: a direct entry fits, but a duplicated transitive modulepreload pushes its graph over budget.
  const manifest = {
    'index.html': { file: 'assets/index.js', isEntry: true, imports: ['shared', 'transitive'] },
    shared: { file: 'assets/shared.js', imports: ['transitive'] },
    transitive: { file: 'assets/transitive.js' },
  }
  const sizes = new Map([
    ['assets/index.js', { rawBytes: 90, gzipBytes: 40 }],
    ['assets/shared.js', { rawBytes: 80, gzipBytes: 20 }],
    ['assets/transitive.js', { rawBytes: 60, gzipBytes: 21 }],
  ])
  const limit = { rawBytes: 220, gzipBytes: 80 }

  // When: the complete static graph is measured from the manifest entry.
  const graph = await measureStaticEntryGraph(manifest, async (file) => {
    const measured = sizes.get(file)
    if (measured === undefined) throw new TypeError(`missing fixture size for ${file}`)
    return measured
  })

  // Then: each asset is counted once and the transitive aggregate fails closed.
  assert.deepEqual(graph.files, ['assets/index.js', 'assets/shared.js', 'assets/transitive.js'])
  assert.deepEqual(graph.measured, { rawBytes: 230, gzipBytes: 81 })
  assert.equal(isWithinLimit(graph.measured, limit), false)
})
