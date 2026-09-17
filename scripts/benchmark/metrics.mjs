import assert from 'node:assert/strict';

function tokens(text) {
  return text.toLowerCase().replace(/\[\d+\]/g,'').replace(/[^\p{L}\p{N}\s]/gu,'')
    .replace(/\b(a|an|the)\b/g,' ').trim().split(/\s+/).filter(Boolean);
}

export function tokenF1(prediction, reference) {
  const predicted=tokens(prediction); const expected=tokens(reference);
  if(!predicted.length||!expected.length)return Number(predicted.length===expected.length);
  const remaining=new Map();
  for(const token of expected)remaining.set(token,(remaining.get(token)??0)+1);
  let common=0;
  for(const token of predicted)if(remaining.get(token)>0){common++;remaining.set(token,remaining.get(token)-1);}
  return 2*common/(predicted.length+expected.length);
}

function merge(ranges) {
  const result=[];
  for(const range of [...ranges].sort((a,b)=>a.start-b.start)) {
    assert(Number.isInteger(range.start)&&Number.isInteger(range.end)&&range.end>=range.start);
    const last=result.at(-1);
    if(last&&range.start<=last.end)last.end=Math.max(last.end,range.end);
    else result.push({...range});
  }
  return result;
}

export function spanCoverage(gold, retrieved) {
  const expected=merge(gold); const evidence=merge(retrieved);
  const total=expected.reduce((n,range)=>n+range.end-range.start,0);
  if(!total)return null;
  let covered=0;
  for(const target of expected)for(const source of evidence)
    covered+=Math.max(0,Math.min(target.end,source.end)-Math.max(target.start,source.start));
  return covered/total;
}

export function nearestRank(values, p) {
  assert(p>0&&p<=1&&values.every(Number.isFinite));
  return values.length?[...values].sort((a,b)=>a-b)[Math.ceil(values.length*p)-1]:null;
}

export function wilson(successes, total) {
  assert(Number.isInteger(successes)&&Number.isInteger(total)&&successes>=0&&successes<=total);
  if(!total)return null;
  const z=1.959963984540054; const p=successes/total; const denominator=1+z*z/total;
  const center=(p+z*z/(2*total))/denominator;
  const half=z*Math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator;
  return {lower:successes===0?0:Math.max(0,center-half),upper:successes===total?1:Math.min(1,center+half)};
}
