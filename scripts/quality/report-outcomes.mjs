import assert from 'node:assert/strict';

// Transport and persistence are intentionally separate from the model outcome.
export function outcome({ status, mode, reason }) {
  if (status === 'SUCCEEDED' && mode === 'live' && reason === null) return 'normalLive';
  if (status !== 'FALLBACK' || mode !== 'fallback') return 'error';
  if (reason === 'insufficient_evidence') return 'evidenceInsufficient';
  const timeouts = new Set([
    'structured_generation_response_timeout', 'structured_generation_connection_timeout',
    'embedding_connection_timeout', 'embedding_response_timeout', 'processing_timeout', 'ai_service_timeout',
  ]);
  if (timeouts.has(reason)) return 'timeout';
  const dependencies = new Set([
    'structured_generation_api_error', 'embedding_api_error', 'invalid_model_response',
    'ai_service_unavailable', 'ai_service_error', 'invalid_ai_response',
  ]);
  return dependencies.has(reason) ? 'otherFallback' : 'error';
}

export function countOutcomes(rows) {
  const counts = { normalLive: 0, evidenceInsufficient: 0, timeout: 0, otherFallback: 0, error: 0 };
  for (const row of rows) counts[row.outcome]++;
  return counts;
}

export function failures(rows) {
  const labels = { evidenceInsufficient: 'EVIDENCE_INSUFFICIENT', timeout: 'TIMEOUT', otherFallback: 'OTHER_FALLBACK', error: 'ERROR' };
  return rows.filter(row => row.outcome !== 'normalLive').map(row => ({
    caseId: row.caseId, concurrency: row.concurrency, outcome: labels[row.outcome],
    reason: row.reason || 'unrecognized_analysis_state', traceId: row.traceId,
  }));
}

export function assertUnique(rows) {
  assert.equal(new Set(rows.map(row => `${row.concurrency}:${row.caseId}`)).size, rows.length, 'duplicate case in group');
}

export function metric(id, label, value, unit, denominator, description) {
  assert(value === null || (Number.isFinite(value) && value >= 0));
  if (unit === 'RATE' && value !== null) assert(value <= 1);
  return { id, label, value, unit, denominator, description };
}
