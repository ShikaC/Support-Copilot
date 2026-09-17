import assert from 'node:assert/strict';

export const archiveNotice = 'This evaluation uses historical archived documents, not verified current policy. Use only retrieved evidence. Previous agent messages are conversation context, not authoritative evidence.';

export function ticketInput(candidate) {
  const institution = candidate.domain === 'dmv' ? 'DMV (state/jurisdiction not provided by routing)' : candidate.input.institution;
  return { subject: 'Public support request', description: `${archiveNotice}\nInstitution routing: ${institution}\n\n${candidate.input.messages.map((message) => `${message.role}: ${message.utterance}`).join('\n')}` };
}

export function validateCase(item, candidate, doc) {
  assert.deepEqual(Object.keys(item.input).sort(), ['description', 'subject'], 'Input fields must be allowlisted');
  assert(item.input.subject.length > 0 && item.input.subject.length <= 240);
  assert(item.input.description.length > 0 && [...item.input.description].length <= 4000, 'Input length');
  assert.equal(item.human_review.status, 'NOT_REVIEWED', 'Frozen AI audit cannot become human gold');
  for (const key of ['reviewer', 'reviewed_at', 'answerability']) assert.equal(item.human_review[key], null);
  const audit = item.audit;
  assert.equal(audit.author_type, 'AI_AUDIT_NOT_HUMAN');
  assert(['DIRECT', 'CLARIFY', 'OUT_OF_KB', 'EXCLUDE'].includes(audit.label));
  assert.equal(item.included, audit.label !== 'EXCLUDE');
  assert(audit.reason.trim() && audit.intent.trim());
  assert(audit.forbidden.length > 0);
  if (candidate) {
    assert.deepEqual(item.input, ticketInput(candidate), 'Context/target/annotation leakage or changed input');
    assert.deepEqual(item.source, candidate.source);
    assert.equal(item.split, candidate.split);
    assert.deepEqual(item.publisher_reference, candidate.publisher_reference);
    const evidenceIds = new Set();
    for (const evidence of audit.evidence) {
      assert(!evidenceIds.has(evidence.id), 'Duplicate evidence'); evidenceIds.add(evidence.id);
      const span = doc.spans[evidence.id]; assert(span, 'Missing source span');
      assert.equal(evidence.start, span.start_sp); assert.equal(evidence.end, span.end_sp);
      assert.equal(evidence.text, span.text_sp);
      assert.equal([...doc.doc_text].slice(evidence.start, evidence.end).join(''), evidence.text, 'Span mismatch');
      assert.equal(evidence.pointer, `/spans/${evidence.id}`);
      assert.equal(evidence.document_id, candidate.source.document_id);
    }
    for (const point of audit.points) {
      assert(point.text.trim() && point.span_ids.length > 0, 'Unsupported required point');
      assert(point.span_ids.every((id) => evidenceIds.has(id)), 'Missing point evidence');
    }
  }
  if (audit.label === 'DIRECT') {
    assert(candidate && audit.points.length > 0, 'DIRECT needs source-backed points');
    assert.equal(audit.missing_slots.length, 0);
  }
  if (audit.label === 'CLARIFY') {
    assert(audit.missing_slots.length > 0 && audit.question?.trim(), 'CLARIFY needs specific missing slots');
    assert(audit.evidence.length > 0, 'Clarification branch needs evidence');
  }
  if (audit.label === 'OUT_OF_KB') assert(audit.coverage_basis?.trim(), 'No reference is not proof of OUT_OF_KB');
  if (audit.label === 'EXCLUDE') assert(audit.exclusion_reason?.trim(), 'Excluded cases need a reason');
}

export function normalLive(response) {
  return response?.mode === 'live' && response?.status === 'SUCCEEDED' && response?.fallbackReason === null;
}

export function normalized(text) {
  return text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
}

export function tokenJaccard(left, right) {
  const a = new Set(normalized(left).split(' ')); const b = new Set(normalized(right).split(' '));
  return [...a].filter((word) => b.has(word)).length / new Set([...a, ...b]).size;
}
