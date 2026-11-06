// Clients for ordinary built-in methods, initially at a text-unit boundary.
import assert from 'node:assert/strict';
import {compile, matchAllStarts, prepareWalk} from './all_starts.mjs';

// Map a matcher-unit index to a public UTF-16 offset. The Unicode view also
// retrieves a unit directly from the original string using the same index.
function indexedText(word, unicode) {
  if (!unicode) return {units: word, offset: x => x};
  let n = 0;
  for (const _ of word) n++;
  const width = Math.max(1, Math.floor(Math.log2(n + 1) / 2));
  const pop = new Uint8Array(1 << width);
  for (let i = 1; i < pop.length; i++) pop[i] = pop[i >> 1] + (i & 1);
  const blocks = Math.ceil(n / width);
  const mask = new Uint32Array(blocks), prefix = new Uint32Array(blocks + 1);
  let x = 0;
  for (const unit of word) {
    if (unit.length === 2) mask[Math.floor(x / width)] |= 1 << (x % width);
    x++;
  }
  for (let i = 0; i < blocks; i++) prefix[i + 1] = prefix[i] + pop[mask[i]];
  function offset(x) {
    const i = Math.floor(x / width);
    return x + prefix[i] + pop[(mask[i] ?? 0) & ((1 << (x % width)) - 1)];
  }
  return {units: {length: n, unitAt: i => word.slice(offset(i), offset(i + 1))}, offset};
}

function globalMatches(get, n, offset, initial) {
  const matches = [];
  for (let x = initial; x <= n;) {
    const row = get(x);
    if (!row) { x++; continue; }
    const [y, spans] = row;
    matches.push([[offset(x), offset(y)], ...spans.map(s => s && [offset(s[0]), offset(s[1])])]);
    x = x === y ? y + 1 : y;
  }
  return matches;
}

function split(get, n, word, offset, limit) {
  if (limit === 0) return [];
  if (!n) return get(0) ? [] : [''];
  const pieces = [];
  let p = 0, q = 0;
  while (q < n) {
    const row = get(q);
    if (!row || row[0] === p) { q++; continue; }
    const [y, spans] = row;
    pieces.push(word.slice(offset(p), offset(q)));
    if (pieces.length === limit) return pieces;
    for (const span of spans) {
      pieces.push(span ? word.slice(offset(span[0]), offset(span[1])) : undefined);
      if (pieces.length === limit) return pieces;
    }
    p = q = y;
  }
  pieces.push(word.slice(offset(p)));
  return pieces;
}

const term = (kind, ...parts) => ({kind, parts});
const a = term('character', 'a'), empty = term('empty');
const any = term('character', () => true);
const cap = s => term('capture', s);
const cases = [
  ['a', a], ['(?:)', empty], ['aa', term('sequence', a, a)],
  ['.', any], ['(a)?', term('repeat', cap(a), '?', false)],
  ['(?:(a)|)', term('choice', cap(a), empty)],
  ['(?:(a)|())+?', term('repeat', term('choice', cap(a), cap(empty)), '+', true)],
  ['(?=(.))', term('assertion', cap(any), 1, false)],
  ['(?<=(.))', term('assertion', cap(any), -1, false)],
  ['^', term('position', (_word, x) => x === 0)],
  ['a*b', term('sequence', term('repeat', a, '*', false), term('character', 'b'))],
  ['(?=(a+))a', term('sequence', term('assertion', cap(term('repeat', a, '+', false)), 1, false), a)],
  ['(?!(a))(.)', term('sequence', term('assertion', cap(a), 1, true), cap(any))],
  ['(?:(?=a)(a)|b)+', term('repeat', term('choice',
    term('sequence', term('assertion', a, 1, false), cap(a)), term('character', 'b')), '+', false)],
  ['(?:(?=(?=(a)))a|b)+', term('repeat', term('choice', term('sequence',
    term('assertion', term('assertion', cap(a), 1, false), 1, false), a), term('character', 'b')), '+', false)],
  ['(?:(?<=(a))a|b)+', term('repeat', term('choice', term('sequence',
    term('assertion', cap(a), -1, false), a), term('character', 'b')), '+', false)]
];
let global = 0, splits = 0, localGlobal = 0, localSplits = 0;
for (const n of [0, 1, 3, 30, 131, 300]) {
  const word = Array.from({length: n}, (_, i) => ['a', '😀', 'b', '栞'][i % 4]).join('');
  const {units, offset} = indexedText(word, true);
  let pos = 0, i = 0;
  for (const unit of word) {
    assert.equal(offset(i), pos);
    assert.equal(units.unitAt(i++), unit);
    pos += unit.length;
  }
  assert.equal(offset(i), word.length);
}
for (const [source, pattern] of cases) {
  const program = compile(pattern);
  for (const word of ['', 'a', 'aaa', 'ab', 'ba', '😀a', 'a😀😀b', '😀', '\ud83d', '\ude00a']) {
    for (const flags of ['', 'u']) {
      const {units, offset} = indexedText(word, Boolean(flags));
      const {rows} = matchAllStarts(program, units);
      const guide = prepareWalk(program, units);
      const readers = [x => rows[x], x => guide.read(x)?.row ?? null];
      for (let x = 0; x <= units.length; x++) {
        const re = new RegExp(source, flags + 'dg');
        re.lastIndex = offset(x);
        const expected = Array.from(word.matchAll(re), m => m.indices.map(span => span ?? null));
        for (const get of readers) assert.deepEqual(globalMatches(get, units.length, offset, x), expected,
                                                   JSON.stringify([word, source, flags, x]));
        if (program.localCaptures) localGlobal++;
        global++;
      }
      for (const limit of [0, 1, 2, 3, 7, 0xffffffff]) {
        const expected = word.split(new RegExp(source, flags), limit);
        for (const get of readers) assert.deepEqual(split(get, units.length, word, offset, limit), expected);
        if (program.localCaptures) localSplits++;
        splits++;
      }
    }
  }
}
console.log(JSON.stringify({global, splits, localGlobal, localSplits, readers: 2}));
