import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const destination = resolve(process.argv[2] ?? '')
if (!process.argv[2]) throw new Error('Usage: node capture-corpus.mjs NEW_OUTPUT_DIRECTORY')
const env = { ...process.env, GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1', NO_COLOR: '1', GH_PAGER: 'cat' }
const run = args => execFileSync('gh', args, { encoding: 'utf8', env, timeout: 10000, maxBuffer: 4 * 1024 * 1024 })
const version = run(['--version'])
if (!version.startsWith('gh version 2.100.0 ')) throw new Error('This corpus requires gh 2.100.0; create a new versioned pilot for another version')
const reference = run(['help', 'reference'])
const families = new Set(['auth', 'pr', 'issue', 'repo', 'release', 'extension', 'project', 'api', 'completion'])
const commands = new Map()
for (const line of reference.split('\n')) {
  const match = /^#{2,3} gh (.+)$/.exec(line)
  if (!match) continue
  const parts = []
  for (const token of match[1].split(/\s+/)) {
    if (!/^[a-z][a-z0-9-]*$/.test(token)) break
    parts.push(token)
  }
  if (families.has(parts[0])) commands.set(parts.join('_'), ['help', ...parts])
}
for (const topic of ['environment', 'formatting', 'reference']) commands.set(`help_${topic}`, ['help', topic])
mkdirSync(destination)
const hash = value => createHash('sha256').update(value).digest('hex')
const documents = []
for (const [name, args] of [...commands].sort(([left], [right]) => left.localeCompare(right))) {
  const text = run(args)
  if (!text.trim()) throw new Error(`Empty help: ${name}`)
  const id = `gh_${name}`
  const file = `${id}.txt`
  writeFileSync(join(destination, file), text)
  documents.push({ id, file, sha256: hash(text), source_url: `https://cli.github.com/manual/${id}`, acquisition: ['gh', ...args], origin: 'OFFICIAL_CLI_BUILTIN_HELP', license: 'MIT', version: '2.100.0' })
}
writeFileSync(join(destination, 'manifest.json'), JSON.stringify({ captured_at: new Date().toISOString(), version_output: version.trim(), release_url: 'https://github.com/cli/cli/releases/tag/v2.100.0', upstream_commit: '45437bc7eeeb3359bbfddd1742f79de7652fd3e2', selection: 'All commands in official reference under auth/pr/issue/repo/release/extension/project/api/completion, plus environment/formatting/reference. Not selected by answer relevance.', documents }, null, 2) + '\n')
console.log(JSON.stringify({ documents: documents.length, destination }))
