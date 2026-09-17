import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { sha256 } from './export-reports.mjs';

const read = filename => JSON.parse(readFileSync(filename, 'utf8'));
const hash = filename => sha256(readFileSync(filename));
const baseline = read('docs/verification/product-quality-center-2026-09-10/workspace-before.json');
const allowed = new Set([
  'apps/support-copilot-web/src/App.tsx',
  'apps/support-copilot-web/src/App.css',
  'apps/support-copilot-web/src/workspace.css',
  'apps/support-copilot-web/src/App.characterization.test.tsx',
  'apps/support-copilot-web/e2e/mock-api.mjs',
  'apps/support-copilot-web/e2e/pilot-workflows.spec.ts',
  'apps/support-copilot-web/src/services/api.ts',
  'apps/support-copilot-web/src/features/quality/QualityView.tsx',
  'apps/support-copilot-web/src/features/quality/QualityView.test.tsx',
  'services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/config/SecurityConfig.java',
  'README.md', 'docs/STATUS.md', 'docs/ROADMAP.md',
  'docs/learning/READING_LOG.md', 'docs/learning/NEXT_SESSION_HANDOFF_PROMPT.md',
]);
const changed = Object.entries(baseline).filter(([filename, digest]) => !existsSync(filename) || hash(filename) !== digest).map(([filename]) => filename);
assert(changed.every(filename => allowed.has(filename)), `Out-of-scope pre-existing changes: ${changed.filter(filename => !allowed.has(filename))}`);
const audit = read('docs/verification/quality-input-audit-2026-09-10/freeze-manifest.json');
for (const [filename, digest] of Object.entries(audit.hashes)) assert.equal(hash(filename), digest, filename);
const frozenDirectories = [
  'docs/verification/business-benchmark-2026-09-10/',
  'docs/verification/ai-quality-fixes-2026-09-10/',
  'docs/verification/quality-input-audit-2026-09-10/',
];
const protectedFiles = Object.keys(baseline).filter(filename => frozenDirectories.some(prefix => filename.startsWith(prefix)));
for (const filename of protectedFiles) assert.equal(hash(filename), baseline[filename], filename);
const exported = 'docs/verification/product-quality-center-2026-09-10/reports';
const manifest = read(`${exported}/manifest.json`);
for (const file of manifest.files) {
  assert.equal(hash(`${exported}/${file.name}`), file.sha256);
  const report = read(`${exported}/${file.name}`);
  for (const source of report.sourceFiles) assert.equal(hash(source.name), source.sha256, source.name);
}
const head = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
assert.equal(head, audit.head);
console.log(JSON.stringify({ status: 'PASS', head, dirty: true, preExistingFiles: Object.keys(baseline).length,
  authorizedChanged: changed, frozenFilesUnchanged: protectedFiles.length, auditManifestEntries: Object.keys(audit.hashes).length,
  derivedReports: manifest.files, scope: 'This slice protects prior evidence and all pre-existing files outside its explicit change list; old audit whole-worktree gate remains unchanged.' }, null, 2));
