import test from 'node:test';
import assert from 'node:assert/strict';
import {
  archiveNotice,
  buildCase,
  classify,
  expand,
  findTargetIndex,
  institutionFor,
  sampleKey,
  selfCheck,
  selectDomain,
  ticketInput,
} from './expand-quality-inputs.mjs';

/** 造一条对话：前两轮铺垫，第 3 轮是 agent 且前一转是 user，与真实 targetIndex 规则一致。 */
function makeDialogue(dialogueId) {
  return {
    dial_id: dialogueId,
    turns: [
      {turn_id: 1, role: 'user', utterance: `hello ${dialogueId}`, da: 'greeting'},
      {turn_id: 2, role: 'agent', utterance: 'how can I help', da: 'request'},
      {turn_id: 3, role: 'user', utterance: `question ${dialogueId}`, da: 'query'},
      {turn_id: 4, role: 'agent', utterance: `answer ${dialogueId}`, da: 'respond_solution', references: []},
    ],
  };
}

function makeDialogues(domain, count, prefix = 'doc') {
  return {
    [domain]: Object.fromEntries(
      Array.from({length: count}, (_, index) => [
        `${prefix}-${index}`,
        [makeDialogue(`${domain}-dial-${index}`)],
      ]),
    ),
  };
}

test('findTargetIndex picks the first agent turn with a user before it', () => {
  const turns = [
    {turn_id: 1, role: 'user'},
    {turn_id: 2, role: 'agent'},
    {turn_id: 3, role: 'user'},
    {turn_id: 4, role: 'agent'},
  ];
  assert.equal(findTargetIndex(turns), 3);
  // turn_id < 3 的轮次不算目标，即使前面是用户。
  assert.equal(findTargetIndex([{turn_id: 1, role: 'user'}, {turn_id: 2, role: 'agent'}]), -1);
  assert.equal(findTargetIndex([{turn_id: 1, role: 'user'}]), -1);
});

test('institutionFor never guesses the DMV jurisdiction', () => {
  assert.equal(institutionFor('dmv'), 'DMV (state/jurisdiction not provided by routing)');
  assert.equal(institutionFor('ssa'), 'US Social Security Administration');
  assert.equal(institutionFor('va'), 'US Department of Veterans Affairs');
});

test('ticketInput renders the frozen archive notice, routing and dialogue prefix', () => {
  const input = ticketInput('ssa', [
    {role: 'user', utterance: 'hi'},
    {role: 'agent', utterance: 'hello'},
  ]);
  assert.equal(input.subject, 'Public support request');
  assert.equal(
    input.description,
    `${archiveNotice}\nInstitution routing: US Social Security Administration\n\nuser: hi\nagent: hello`,
  );
});

test('classify excludes only previous-experiment dialogues and documents', () => {
  const used = {
    dialogues: new Set(['used-dialogue']),
    documents: new Set(['dmv:used-doc']),
  };
  const base = {domain: 'dmv', docId: 'fresh-doc', dialogueId: 'fresh-dialogue', targetIndex: 3};
  assert.equal(classify(base, used), 'OUTSIDE_FIXED_QUOTA');
  assert.equal(classify({...base, dialogueId: 'used-dialogue'}, used), 'PREVIOUS_EXPERIMENT_DIALOGUE');
  assert.equal(classify({...base, docId: 'used-doc'}, used), 'PREVIOUS_EXPERIMENT_REFERENCE_DOCUMENT');
  assert.equal(classify({...base, targetIndex: -1}, used), 'NO_FOLLOWUP_TARGET');
});

test('selectDomain honours the quota and keeps one case per document', () => {
  const entries = Array.from({length: 10}, (_, index) => ({
    domain: 'dmv',
    docId: `doc-${index}`,
    dialogueId: `dial-${index}`,
    sampleKey: sampleKey(`dial-${index}`),
    reason: 'OUTSIDE_FIXED_QUOTA',
  }));
  const {selected} = selectDomain(entries, 6);
  assert.equal(selected.length, 6);
  assert.equal(new Set(selected.map((entry) => entry.docId)).size, 6);
  // 每文档最多一题：重复文档会被跳过，因此 11 个条目只能选出 10 个。
  const duplicated = [...entries, {...entries[0], dialogueId: 'dial-dup', sampleKey: sampleKey('dial-dup')}];
  const second = selectDomain(duplicated, 10);
  assert.equal(second.selected.length, 10);
  assert.equal(new Set(second.selected.map((entry) => entry.docId)).size, 10);
  // 纯函数：调用方传入的数组不得被临时标记污染，否则第二次调用会看不到剩余候选。
  assert(entries.every((entry) => entry.reason === 'OUTSIDE_FIXED_QUOTA'));
});

test('selectDomain is deterministic for the same input', () => {
  const entries = Array.from({length: 12}, (_, index) => ({
    domain: 'va',
    docId: `doc-${index}`,
    dialogueId: `dial-${index}`,
    sampleKey: sampleKey(`dial-${index}`),
    reason: 'OUTSIDE_FIXED_QUOTA',
  }));
  const first = selectDomain(entries, 5).selected.map((entry) => entry.docId);
  const second = selectDomain(entries, 5).selected.map((entry) => entry.docId);
  assert.deepEqual(first, second);
});

test('buildCase produces a case shaped like the frozen audit cases', () => {
  const dialogue = makeDialogue('dial-1');
  const entry = {domain: 'dmv', docId: 'doc-1', dialogueId: 'dial-1', targetIndex: 3};
  const item = buildCase(entry, 'holdout', dialogue);
  assert.equal(item.id, 'qa-dial-1-4');
  assert.equal(item.split, 'holdout');
  assert.deepEqual(item.source, {dialogue_id: 'dial-1', document_id: 'doc-1', target_turn_id: 4});
  assert.equal(item.audit.author_type, 'NONE');
  assert.equal(item.publisher_reference.act, 'respond_solution');
  assert.match(item.input.description, /^This evaluation uses historical archived documents/);
  assert.match(item.input.description, /user: hello dial-1\nagent: how can I help\nuser: question dial-1$/);
});

test('expand reproduces the original quota and then adds only new cases', () => {
  const dialogues = makeDialogues('dmv', 10);
  const used = {dialogues: new Set(), documents: new Set()};
  const {reproduced, expanded} = expand({dialogues, used, perDomain: 8});
  assert.equal(reproduced.length, 6);
  assert.equal(expanded.length, 2);
  const reproducedIds = new Set(reproduced.map((item) => item.id));
  assert.equal(expanded.some((item) => reproducedIds.has(item.id)), false);
});

test('expand never reuses documents taken by the previous experiment', () => {
  const dialogues = makeDialogues('ssa', 10);
  const used = {
    dialogues: new Set(['ssa-dial-0']),
    documents: new Set(['ssa:doc-1']),
  };
  const {reproduced, expanded} = expand({dialogues, used, perDomain: 6});
  const all = [...reproduced, ...expanded];
  assert.equal(all.some((item) => item.source.dialogue_id === 'ssa-dial-0'), false);
  assert.equal(all.some((item) => item.source.document_id === 'doc-1'), false);
});

test('selfCheck fails when a reproduced case drifts from the frozen input', () => {
  const dialogue = makeDialogue('dial-1');
  const entry = {domain: 'dmv', docId: 'doc-1', dialogueId: 'dial-1', targetIndex: 3};
  const item = buildCase(entry, 'development', dialogue);
  selfCheck([item], [item]);
  const tampered = {...item, input: {subject: 'Public support request', description: 'changed'}};
  assert.throws(() => selfCheck([tampered], [item]), /渲染出的 input/);
});

test('selfCheck fails when the reproduced set does not match the audits', () => {
  const dialogue = makeDialogue('dial-1');
  const entry = {domain: 'dmv', docId: 'doc-1', dialogueId: 'dial-1', targetIndex: 3};
  const item = buildCase(entry, 'development', dialogue);
  assert.throws(() => selfCheck([], [item]), /必须精确复现/);
});
