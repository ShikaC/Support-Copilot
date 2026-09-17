import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {budgets,sha} from './isolated-inputs.mjs';

export const claimDir = '.local/quality-runs';
export const baseClaimName = (casesSha) => `development-${casesSha}.claim.json`;
export const comparisonClaimName = (comparisonId) => `comparison-${comparisonId}.claim.json`;

function insideRepo(root, file) {
  const absolute = path.resolve(root, file);
  assert(absolute.startsWith(`${path.resolve(root)}${path.sep}`), `Path escapes repository: ${file}`);
  return absolute;
}

export function recordComparisonClaim(file, value) {
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, {flag: 'wx'});
}

export function loadComparisonProtocol(root, protocolFile, {casesSha, id, execute}) {
  const absolute = insideRepo(root, protocolFile);
  assert(fs.existsSync(absolute), `Comparison protocol missing: ${protocolFile}`);
  const bytes = fs.readFileSync(absolute);
  const protocolSha = sha(bytes);
  let protocol;
  try {
    protocol = JSON.parse(bytes.toString('utf8'));
  } catch {
    assert.fail(`Comparison protocol is not valid JSON: ${protocolFile}`);
  }
  assert.equal(protocol.protocolVersion, 1, 'Unsupported comparison protocol version');
  assert.match(protocol.comparisonId ?? '', /^[a-z0-9][a-z0-9-]{2,63}$/, 'Comparison ID must be 3-64 lowercase letters/digits/hyphens');
  assert.equal(protocol.casesSha, casesSha, 'Protocol must bind the frozen development cases SHA');
  assert.equal(protocol.holdoutCount, 0, 'Holdout must stay unused in a development comparison');
  assert.equal(protocol.humanInputReview, 'PENDING', 'Do not pre-fill human labels in the comparison protocol');
  assert.equal(protocol.qualityScore, null, 'Comparison must not pre-register a quality score');
  assert(typeof protocol.hypothesis === 'string' && protocol.hypothesis.trim(), 'Hypothesis required');
  assert(typeof protocol.singleVariable === 'string' && protocol.singleVariable.trim(), 'Single-variable statement required');
  assert(Array.isArray(protocol.successCriteria) && protocol.successCriteria.length > 0 && protocol.successCriteria.every((item) => typeof item === 'string' && item.trim()), 'Success criteria required');
  assert(Array.isArray(protocol.notAllowed) && protocol.notAllowed.length > 0, 'notAllowed list required');
  assert.deepEqual(protocol.budgets, {...budgets}, 'Comparison budgets must match the frozen runner budgets');
  const baseClaimPath = path.join(root, claimDir, baseClaimName(casesSha));
  assert(fs.existsSync(baseClaimPath), 'Base development claim is missing; do not delete or replace it');
  const baseClaimSha256 = sha(fs.readFileSync(baseClaimPath));
  assert.equal(baseClaimSha256, protocol.baseClaimSha256, 'Base claim hash mismatch; the original claim must not be replaced');
  const baseClaim = JSON.parse(fs.readFileSync(baseClaimPath, 'utf8'));
  assert.equal(baseClaim.id, protocol.baseRunId, 'Base claim belongs to a different run');
  const baseManifestPath = path.join(root, 'docs/verification/quality-runs', protocol.baseRunId, 'manifest.json');
  assert(fs.existsSync(baseManifestPath), `Base run manifest missing: ${protocol.baseRunId}`);
  const baseManifest = JSON.parse(fs.readFileSync(baseManifestPath, 'utf8'));
  assert.equal(baseManifest.id, protocol.baseRunId, 'Base manifest ID mismatch');
  assert.equal(baseManifest.casesSha, casesSha, 'Base run used a different development dataset');
  const expected = protocol.expectedSourceHashes;
  assert(expected && typeof expected === 'object' && Object.keys(expected).length > 0, 'expectedSourceHashes required');
  for (const [file, digest] of Object.entries(expected)) {
    assert(/^(services|scripts)\//.test(file), `Unexpected expected source path: ${file}`);
    const target = insideRepo(root, file);
    assert(fs.existsSync(target), `Expected source missing: ${file}`);
    assert.equal(sha(fs.readFileSync(target)), digest, `Source hash mismatch: ${file}`);
  }
  const preflightId = protocol.preflightId;
  const validIds = [protocol.comparisonId, preflightId].filter(Boolean);
  assert(validIds.includes(id), 'Run ID must be the pre-registered comparisonId or preflightId');
  if (execute) assert.equal(id, protocol.comparisonId, 'Only the comparisonId may execute; preflight IDs cannot call providers');
  const comparisonClaimPath = path.join(root, claimDir, comparisonClaimName(protocol.comparisonId));
  assert(!fs.existsSync(comparisonClaimPath), 'Comparison claim already exists; a comparison runs exactly once');
  return {protocolFile: path.relative(root, absolute), protocolSha, protocol, baseClaimPath, baseClaimSha256, comparisonClaimPath, mode: id === protocol.comparisonId ? 'comparison' : 'preflight'};
}
