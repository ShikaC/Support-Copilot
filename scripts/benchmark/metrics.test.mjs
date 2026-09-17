import test from 'node:test';
import assert from 'node:assert/strict';
import { tokenF1, spanCoverage, nearestRank, wilson } from './metrics.mjs';

test('reference F1 counts repeated tokens and penalizes extra content',()=>{
  // Given one shared word and an extra predicted word; when scoring; then precision reduces F1.
  assert.equal(tokenF1('New York','York'),2/3);
  assert.equal(tokenF1('York York','York'),2/3);
  assert.equal(tokenF1('THE, York. [1]','York'),1);
  assert.equal(tokenF1('unrelated','York'),0);
});
test('span coverage merges overlapping gold and retrieved ranges',()=>{
  // Given overlapping evidence; when measuring coverage; then no character is double counted.
  assert.equal(spanCoverage([{start:10,end:30},{start:20,end:40}],[{start:0,end:25},{start:20,end:35}]),25/30);
  assert.equal(spanCoverage([{start:10,end:20}],[{start:20,end:30}]),0);
});
test('nearest-rank percentile preserves slow failure observations',()=>{
  // Given four fast returns and a timeout; when computing p95; then the timeout remains visible.
  assert.equal(nearestRank([5,2,3,1,20],0.95),20);
  assert.equal(nearestRank([5,2,3,1,20],0.5),3);
  assert.equal(nearestRank([],0.95),null);
});
test('Wilson intervals expose uncertainty even with perfect observed success',()=>{
  // Given a small all-success sample; when estimating the binomial interval; then the lower bound is below 1.
  const interval=wilson(10,10);
  assert(interval.lower>0.72&&interval.lower<0.73);
  assert.equal(interval.upper,1);
  assert.equal(wilson(0,0),null);
});
