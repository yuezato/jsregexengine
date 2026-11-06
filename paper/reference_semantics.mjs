// Direct transcription of the ordered list of successes.
// Patterns are small syntax trees. The test alphabet is {a,b}, and the
// position primitive used here is the end of the word.
import assert from 'node:assert/strict';
import {compile, prepareMatches, matchAllStarts, viableStarts, hasBit, prepareWalk} from './all_starts.mjs';

function node(kind, ...parts) {
  return {kind, parts};
}

const char = value => node('character', value);
const sequence = (left, right) => node('sequence', left, right);
const choice = (left, right) => node('choice', left, right);
const capture = body => node('capture', body);
const repeat = (kind, body, lazy = false) => node('repeat', body, kind, lazy);
const assertion = (body, direction, negative = false) => node('assertion', body, direction, negative);
const atomic = body => node('atomic', body);
const empty = node('empty');
const failure = node('failure');
const end = node('end');

function numberCaptures(pattern) {
  const subtreeEnds = [];
  let count = 0;
  function visit(term) {
    const slot = term.kind === 'capture' ? count++ : undefined;
    const parts = term.parts.map(part => typeof part === 'object' ? visit(part) : part);
    if (slot !== undefined) subtreeEnds[slot] = count;
    return {kind: term.kind, parts, slot, counted: term.counted};
  }
  const root = visit(pattern);
  return {root, count, subtreeEnds};
}

// The optional count records tagged invocations only in the returned derivation.
function* runs(term, word, x, direction = 1) {
  for (const [y, h, count = 0] of emissions(term, word, x, direction)) {
    yield [y, h, count + (term.counted ? 1 : 0)];
  }
}
function* emissions(term, word, x, direction) {
  const [first, second, third] = term.parts;
  switch (term.kind) {
    case 'failure':
      return;
    case 'empty':
      yield [x, {}];
      return;
    case 'end':
      if (x === word.length) yield [x, {}];
      return;
    case 'character': {
      const index = direction === 1 ? x : x - 1;
      if (word[index] === first) yield [x + direction, {}];
      return;
    }
    case 'choice':
      yield* runs(first, word, x, direction);
      yield* runs(second, word, x, direction);
      return;
    case 'sequence': {
      const [left, right] = direction === 1 ? [first, second] : [second, first];
      for (const [y, leftMap, a] of runs(left, word, x, direction)) {
        for (const [z, rightMap, b] of runs(right, word, y, direction)) {
          yield [z, {...leftMap, ...rightMap}, a + b];
        }
      }
      return;
    }
    case 'capture':
      for (const [y, map, used] of runs(first, word, x, direction)) {
        const span = [Math.min(x, y), Math.max(x, y)];
        yield [y, {...map, [term.slot]: span}, used];
      }
      return;
    case 'assertion': {
      const child = runs(first, word, x, second).next();
      if (third) {
        if (child.done) yield [x, {}];
      } else if (!child.done) {
        yield [x, child.value[1], child.value[2]];
      }
      return;
    }
    case 'atomic': {
      const child = runs(first, word, x, direction).next();
      if (!child.done) yield child.value;
      return;
    }
    case 'repeat': {
      const [body, quantifier, lazy] = term.parts;
      function* tail(position, map, used = 0) {
        if (lazy) yield [position, map, used];
        for (const [y, nextMap, extra] of runs(body, word, position, direction)) {
          if (y !== position) yield* tail(y, nextMap, used + extra);
        }
        if (!lazy) yield [position, map, used];
      }
      if (quantifier === '*') {
        yield* tail(x, {});
      } else if (quantifier === '+') {
        for (const [y, map, used] of runs(body, word, x, direction)) yield* tail(y, map, used);
      } else {
        assert.equal(quantifier, '?');
        if (lazy) yield [x, {}];
        for (const item of runs(body, word, x, direction)) {
          if (item[0] !== x) yield item;
        }
        if (!lazy) yield [x, {}];
      }
      return;
    }
    default:
      throw new Error('Unknown term ' + term.kind);
  }
}

// Render only standardized syntax for the independent native comparisons.
const group = source => '(?:' + source + ')';
function nativeSource(term) {
  const [first, second, third] = term.parts;
  switch (term.kind) {
    case 'character': return first;
    case 'empty': return '(?:)';
    case 'failure': return '(?!)';
    case 'end': return '$';
    case 'sequence': return group(nativeSource(first) + nativeSource(second));
    case 'choice': return group(nativeSource(first) + '|' + nativeSource(second));
    case 'capture': return '(' + nativeSource(first) + ')';
    case 'repeat': return group(nativeSource(first)) + second + (third ? '?' : '');
    case 'assertion':
      return '(?' + (second === -1 ? '<' : '') + (third ? '!' : '=') + nativeSource(first) + ')';
    default: throw new Error('No standardized spelling used for ' + term.kind);
  }
}

function captureArray(item, count) {
  if (!item) return null;
  const [y, map] = item;
  return [y, Array.from({length: count}, (_, i) => map[i] ?? null)];
}

function checkSparse(index, x, row, subtreeEnds) {
  const expected = [];
  if (row) row[1].forEach((span, slot) => { if (span) expected.push([slot, ...span]); });
  const visits = index.stats.traceVisits;
  const items = [];
  const end = index.report(x, (slot, lo, hi) => { items.push([slot, lo, hi]); });
  assert.deepEqual(items, expected);
  assert.equal(end, row?.[0] ?? null);
  assert.equal(index.endpoint(x), end);
  const k = items.length;
  // Slot numbers are in preorder. If a defined descendant exists, the
  // next reported slot is still within this group's subtree.
  const leaves = expected.filter(([slot], i) =>
    i + 1 === k || expected[i + 1][0] >= subtreeEnds[slot]).length;
  assert.equal(index.stats.traceVisits - visits, k ? k + leaves - 1 : 0);
}

// To restrict the native result to B without changing captures, append a
// lookahead that tests how many text units remain. Words contain no newline.
function terminalTest(wordLength, mask) {
  const choices = [];
  for (let y = 0; y <= wordLength; y++) {
    if ((mask >> y) & 1) choices.push('.{' + (wordLength - y) + '}$');
  }
  return choices.length ? '(?=' + choices.join('|') + ')' : '(?!)';
}

const a = char('a');
const b = char('b');
const aa = sequence(a, a);
const seeds = [
  a, b, empty, failure, end, capture(a), capture(empty), choice(capture(empty), a),
  assertion(capture(a), 1), assertion(capture(aa), -1), assertion(capture(a), 1, true),
  sequence(assertion(capture(a), 1), repeat('?', capture(b))),
];
const patterns = [...seeds];
for (const s of seeds) {
  for (const quantifier of ['?', '*', '+']) {
    for (const lazy of [false, true]) {
      const t = repeat(quantifier, s, lazy);
      patterns.push(t, sequence(t, end), repeat('+', capture(t), true),
                    assertion(t, -1), sequence(t, choice(a, empty)));
    }
  }
  for (const t of seeds) patterns.push(choice(s, t), sequence(s, t));
}
const body = choice(assertion(capture(aa), 1), choice(capture(a), aa));
const suffix = sequence(repeat('?', a), sequence(b, end));
const backwardGroups = sequence(capture(repeat('+', a)), capture(repeat('+', a)));
patterns.push(sequence(repeat('+', body, true), suffix), sequence(repeat('+', body), suffix),
              repeat('+', body, true), sequence(assertion(backwardGroups, -1), b));
const words = ['', 'a', 'b', 'aa', 'ab', 'ba', 'bb', 'aaa', 'aab', 'aba', 'abb',
               'baa', 'bab', 'bba', 'bbb', 'aaab'];
// A body counts as nullable here if it has a stationary success on a test word
// in the direction assigned to the occurrence. Its surrounding pattern need not
// select that success.
function stationaryOnTestWords(body, direction) {
  for (const word of words) {
    for (let x = 0; x <= word.length; x++) {
      for (const [y] of runs(body, word, x, direction)) {
        if (y === x) return true;
      }
    }
  }
  return false;
}

function corpusFeatures(root) {
  let lookbehind = false, nullableLazyPlus = false;
  function visit(term, direction) {
    const [body, operator, lazy] = term.parts;
    if (term.kind === 'assertion') {
      direction = operator;
      if (direction < 0) lookbehind = true;
    }
    if (term.kind === 'repeat' && operator === '+' && lazy && !nullableLazyPlus) {
      nullableLazyPlus = stationaryOnTestWords(body, direction);
    }
    for (const part of term.parts) {
      if (typeof part === 'object') visit(part, direction);
    }
  }
  visit(root, 1);
  return {lookbehind, nullableLazyPlus};
}

let lookbehindCases = 0, nullableLazyPlusCases = 0;
let comparisons = 0, guidedRows = 0, intervalBoundRows = 0;
for (const pattern of patterns) {
  const program = compile(pattern);
  const {root, count, subtreeEnds} = numberCaptures(pattern);
  const features = corpusFeatures(root);
  if (features.lookbehind) lookbehindCases++;
  if (features.nullableLazyPlus) nullableLazyPlusCases++;
  const source = nativeSource(root);
  for (const word of words) {
    const nPositions = word.length + 1;
    const nativeTests = Array.from({length: 1 << nPositions}, (_, mask) =>
      new RegExp(group(source) + terminalTest(word.length, mask), 'dy'));
    const computed = nativeTests.map((_, mask) => {
      const allowed = Array.from({length: nPositions}, (_, y) => (mask >> y) & 1);
      return {rows: matchAllStarts(program, word, allowed, true).rows,
              index: prepareMatches(program, word, allowed), bits: viableStarts(program, word, allowed),
              guide: prepareWalk(program, word, allowed)};
    });
    for (let x = 0; x < nPositions; x++) {
      const list = [...runs(root, word, x)];
      for (const [mask, regex] of nativeTests.entries()) {
        const selected = list.find(([y]) => (mask >> y) & 1);
        regex.lastIndex = x;
        const match = regex.exec(word);
        const observed = match && [regex.lastIndex, match.indices.slice(1).map(span => span ?? null)];
        assert.deepEqual(captureArray(selected, count), observed, JSON.stringify([source, word, x, mask]));
        assert.equal(hasBit(computed[mask].bits.success, x), Boolean(selected));
        assert.equal(hasBit(computed[mask].bits.moving, x), list.some(([y]) => y !== x && ((mask >> y) & 1)));
        assert.deepEqual(computed[mask].rows[x], observed, JSON.stringify([source, word, x, mask]));
        checkSparse(computed[mask].index, x, observed, subtreeEnds);
        const selectedRun = computed[mask].guide.read(x);
        assert.deepEqual(selectedRun?.row ?? null, observed);
        if (selectedRun) {
          const budget = program.localCaptures ? Math.max(1, selectedRun.row[0] - x) : nPositions;
          assert(selectedRun.visits <= selectedRun.visitBound);
          assert(selectedRun.visitBound <= program.size * budget);
        }
        guidedRows++;
        if (program.localCaptures) intervalBoundRows++;
        comparisons++;
      }
    }
  }
}

// The denotation retains repeated offers, including offers no position-only
// terminal test can distinguish. Compare the entire lists used in the manuscript.
const prioritized = capture(choice(a, aa));
const exactLists = [
  [choice(capture(a), a), 'a', 0, [[1, [[0, 1]]], [1, [null]]]],
  [repeat('+', choice(capture(empty), a), true), 'a', 0,
   [[0, [[0, 0]]], [1, [null]], [1, [null]]]],
  [prioritized, 'aab', 0, [[1, [[0, 1]]], [2, [[0, 2]]]]],
  [atomic(prioritized), 'aab', 0, [[1, [[0, 1]]]]],
  [assertion(prioritized, 1), 'aab', 0, [[0, [[0, 1]]]]],
  [assertion(capture(a), 1, true), 'b', 0, [[0, [null]]]],
  [assertion(capture(a), 1, true), 'a', 0, []],
];
for (const [pattern, word, start, expected] of exactLists) {
  const {root, count} = numberCaptures(pattern);
  const observed = Array.from(runs(root, word, start), item => captureArray(item, count));
  assert.deepEqual(observed, expected);
}

// The extension is checked against its specified outcomes, separately from
// Node.js. Possessive star is an atomic greedy star in the syntax tree.
const extensionCases = [
  [sequence(atomic(prioritized), b), 'aab', 0, null],
  [atomic(prioritized), 'aab', 0, [1, [[0, 1]]]],
  [sequence(atomic(repeat('*', a)), a), 'a', 0, null],
  [sequence(atomic(repeat('?', a)), a), 'a', 0, null],
  [sequence(atomic(repeat('+', a)), a), 'aa', 0, null],
  [assertion(atomic(prioritized), -1), 'aa', 2, [2, [[1, 2]]]],
];
for (const [pattern, word, start, expected] of extensionCases) {
  const {root, count} = numberCaptures(pattern);
  assert.deepEqual(captureArray(runs(root, word, start).next().value, count), expected);
  assert.deepEqual(matchAllStarts(compile(pattern), word).rows[start], expected);
}
// The proposed atomic extension has no standardized native oracle.
let atomicRows = 0;
for (const seed of [choice(capture(empty), a), choice(capture(a), aa), assertion(capture(aa), -1)]) {
  const atom = atomic(seed);
  for (const p of [atom, atomic(atomic(seed)), sequence(atom, a), choice(atom, capture(empty)),
                   repeat('+', atom, true), assertion(repeat('*', atom), -1),
                   atomic(repeat('+', seed, true)), sequence(atomic(repeat('?', seed)), a)]) {
    const program = compile(p), {root, count, subtreeEnds} = numberCaptures(p);
    for (const w of words) {
      const N = w.length + 1;
      const lists = Array.from({length: N}, (_, x) => [...runs(root, w, x)]);
      for (let mask = 0; mask < 2 ** N; mask++) {
        const allowed = Array.from({length: N}, (_, y) => (mask >> y) & 1);
        const {rows} = matchAllStarts(program, w, allowed, true);
        const index = prepareMatches(program, w, allowed);
        for (let x = 0; x < N; x++) {
          assert.deepEqual(rows[x], captureArray(lists[x].find(([y]) => allowed[y]), count));
          checkSparse(index, x, rows[x], subtreeEnds);
          atomicRows++;
        }
      }
    }
  }
}
// An atomic endpoint may decrease with increasing entrance, or jump backwards
// inside a lookbehind. Exits at different distances must consult their own bit.
for (const reverse of [false, true]) {
  const inner = atomic(choice(sequence(a, aa), a));
  const scope = reverse ? assertion(sequence(inner, b), -1) : sequence(inner, b);
  const {root, count} = numberCaptures(scope), program = compile(scope);
  for (const w of ['aaab', 'baaa', 'aabaa', 'aaaaab', 'abaaa']) {
    const N = w.length + 1;
    for (let mask = 0; mask < 2 ** N; mask++) {
      const B = Array.from({length: N}, (_, y) => (mask >> y) & 1);
      const expected = B.map((_, x) => captureArray([...runs(root, w, x)].find(([y]) => B[y]), count));
      assert.deepEqual(matchAllStarts(program, w, B, true).rows, expected);
    }
  }
}
// Literal winning derivations can revisit a single occurrence many times.
const tagged = s => ({...s, counted: true});
let G = tagged(capture(empty)), P = choice(empty, a), witnessChecks = 0;
for (let k = 0; k <= 7; k++) {
  for (let n = 1; n <= 6; n++) {
    const word = 'a'.repeat(n), {root, count} = numberCaptures(G);
    const item = runs(root, word, 0).next().value;
    let expected = 1;
    for (let j = 1; j <= k; j++) expected = expected * (n + j - 1) / j;
    assert.equal(item[2], expected);
    const program = compile(G), expectedRow = captureArray(item, count);
    assert.deepEqual(matchAllStarts(program, word).rows[0], expectedRow);
    const packed = prepareWalk(program, word).read(0);
    assert.deepEqual(packed.row, expectedRow);
    assert(packed.visits <= program.size * (n + 1));
    witnessChecks++;
  }
  const {root} = numberCaptures(P);
  const list = runs(root, 'a', 0);
  assert.equal(list.next().value[2], k);
  let movingCount = null;
  for (const item of list) if (item[0] === 1) { movingCount = item[2]; break; }
  assert.equal(movingCount, k * (k + 3) / 2);
  const program = compile(P), compact = prepareWalk(program, 'a', [false, true]).read(0);
  assert.deepEqual(compact.row, matchAllStarts(program, 'a', [false, true]).rows[0]);
  assert(compact.visits <= program.size);
  G = repeat('*', sequence(assertion(G, 1), a));
  P = repeat('+', tagged(capture(P)), true);
}
// Distinct one-unit matches request overlapping captured suffixes.
const overlap = sequence(assertion(capture(repeat('+', a)), 1), a);
for (const n of [2, 7, 32]) {
  const guide = prepareWalk(compile(overlap), 'a'.repeat(n));
  let visits = 0;
  for (let x = 0; x < n; x++) {
    const selected = guide.read(x);
    assert.deepEqual(selected.row, [x + 1, [[x, n]]]);
    visits += selected.visits;
  }
  assert(visits >= n * (n + 1) / 2);
  assert.equal(guide.read(n), null);
}
// Overlapping lookaheads of growing explicit width, with no repeated body.
for (const k of [4, 16, 64]) {
  let literal = a;
  for (let j = 1; j < k; j++) literal = sequence(literal, a);
  const program = compile(sequence(assertion(capture(literal), 1), a));
  const n = 3 * k, guide = prepareWalk(program, 'a'.repeat(n));
  assert.deepEqual(program.repeatBodyCounts, [0, 0]);
  for (let x = 0; x <= n; x++) {
    const selected = guide.read(x);
    if (x + k > n) { assert.equal(selected, null); continue; }
    assert.deepEqual(selected.row, [x + 1, [[x, x + k]]]);
    assert.equal(selected.visitBound, program.size);
    assert(selected.visits <= selected.visitBound);
  }
}
// All sparse entries in the lower-bound example are distinct across starts.
for (const g of [1, 2, 3, 8]) {
  const n = 2 * g;
  let nested = capture(a);
  for (let j = 1; j < g; j++) nested = capture(sequence(nested, a));
  const index = prepareMatches(compile(nested), 'a'.repeat(n)), distinct = new Set();
  const {subtreeEnds} = numberCaptures(nested);
  for (let x = 0; x <= n; x++) {
    const expected = x + g <= n ? [x + g, Array.from({length: g}, (_, j) => [x, x + g - j])] : null;
    checkSparse(index, x, expected, subtreeEnds);
    index.report(x, (_slot, lo, hi) => distinct.add(lo + ',' + hi));
  }
  assert.equal(distinct.size, g * (n - g + 1));
}

// One positive capture is reconstructed once per disjoint run of a's.
const grouped = sequence(assertion(capture(repeat('+', a)), 1), repeat('+', a));
for (const w of ['aaaaa', 'aaaaabaaaabaaaa']) {
  const program = compile(grouped), guide = prepareWalk(program, w);
  let weighted = 0;
  for (let x = 0; x < w.length;) {
    const read = guide.read(x);
    if (!read) { x++; continue; }
    assert.deepEqual(read.row, [read.row[0], [[x, read.row[0]]]]);
    weighted += read.visitBound;
    x = read.row[0];
  }
  assert(weighted <= program.size * w.length);
}
console.log(JSON.stringify({three_way_comparisons: comparisons, viability_bit_tests: 2 * comparisons, witnessChecks, guidedRows, intervalBoundRows, pattern_cases: patterns.length,
                            words: words.length, lookbehind_cases: lookbehindCases, nullable_lazy_plus_cases: nullableLazyPlusCases,
                            exact_lists: exactLists.length,
                            specified_atomic_cases: extensionCases.length, atomic_rows: atomicRows}));
