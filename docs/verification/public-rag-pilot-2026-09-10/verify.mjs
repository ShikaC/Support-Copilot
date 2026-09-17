import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(fileURLToPath(import.meta.url))
const read = path => JSON.parse(readFileSync(join(root, path), 'utf8'))
const hash = path => createHash('sha256').update(readFileSync(join(root, path))).digest('hex')
const cases = read('cases.json')
const manifest = read('corpus/manifest.json')
const provenance = read('provenance.json')
const selection = read('selection.json')
assert.equal(hash('cases.json'), provenance.cases_sha256)
assert.equal(hash('selection.json'), provenance.selection_sha256)
assert.equal(cases.case_count, cases.cases.length)
assert.equal(cases.accuracy, null)
assert.equal(cases.model_calls, 0)
assert.equal(new Set(cases.cases.map(item => item.id)).size, cases.case_count)
assert.equal(selection.candidates.filter(item => item.selected).length, cases.case_count)
const docs = new Map(manifest.documents.map(item => [item.id, item]))
assert.equal(docs.size, manifest.documents.length)
assert.match(readFileSync(join(root, 'corpus/LICENSE'), 'utf8'), /MIT License/)
for (const doc of docs.values()) {
  assert.equal(doc.file, `${doc.id}.txt`)
  assert.equal(hash(`corpus/${doc.file}`), doc.sha256, `Changed corpus document: ${doc.id}`)
  assert.equal(doc.version, cases.documentation_version)
  assert.deepEqual(doc.acquisition.slice(0, 2), ['gh', 'help'])
  assert.ok(!doc.source_url.includes('/issues/'), 'Issue answers must not enter documentation corpus')
}
for (const item of cases.cases) {
  assert.equal(item.classification, 'PUBLIC_ISSUE_ADAPTED')
  assert.equal(item.split, 'pilot-development')
  assert.equal(item.input.transformation, 'AGENT_PARAPHRASE_FROM_PUBLIC_ISSUE_BODY')
  assert.equal(item.input.fidelity_review, 'NOT_REVIEWED')
  assert.equal(item.annotation_proposal.status, 'NOT_GOLD')
  assert.equal(item.human_annotation.status, 'NOT_REVIEWED')
  assert.equal(item.human_annotation.answerability, null)
  assert.equal(item.human_annotation.reviewer, null)
  assert.equal(item.human_annotation.reviewed_at, null)
  const source = selection.candidates.find(source => source.source_url === item.source.url)
  assert.ok(source?.selected)
  assert.equal(item.source.body_sha256, source.body_sha256)
  for (const id of item.annotation_proposal.candidate_document_ids) assert.ok(docs.has(id), `Missing candidate document: ${id}`)
}
console.log(JSON.stringify({ artifact_integrity: 'PASS', public_issue_candidates: selection.candidates.length, selected_cases: cases.case_count, corpus_documents: docs.size, human_reviewed: 0, evaluated: false, accuracy: null }))
if (process.argv.includes('--require-reviewed')) {
  console.error('BLOCKED: pilot is unreviewed development material, not an approved gold test set; no quality result may be published')
  process.exitCode = 2
}
