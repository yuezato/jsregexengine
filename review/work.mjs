// Count work in the modular word index. Node provides exact function-call
// counts. Iterating the existing predecessor lists counts the inner graph loop.
import assert from 'node:assert/strict';
import {Session} from 'node:inspector/promises';
import {compile, prepareMatches} from '../paper/index/word_index.mjs';

const term = (kind, ...parts) => ({kind, parts});
const letter = c => term('character', c);
const capture = body => term('capture', body);
const repeat = (body, q, lazy = false) => term('repeat', body, q, lazy);
const seq = (left, right) => term('sequence', left, right);
const choice = (left, right) => term('choice', left, right);
const span = (i, j) => [i, j];

function example(name, depth, n) {
  let pattern = repeat(letter('a'), '?');
  if (name === 'nullable-plus' || name === 'failing-suffix') {
    for (let i = 0; i < depth; i++) pattern = repeat(capture(pattern), '+', true);
    if (name === 'failing-suffix') return {pattern: seq(pattern, letter('b')), end: () => null};
    return {pattern, end: x => Math.min(x + 1, n), captured: (x, y) => span(x, y)};
  }
  if (name === 'sparse-choice') {
    pattern = capture(letter('a'));
    for (let i = 1; i < depth; i++) pattern = choice(capture(letter('b')), pattern);
    pattern = choice(pattern, term('empty'));
    return {pattern, end: x => x < n ? x + 1 : n,
            captured: (x, y, slot) => x < n && slot === depth - 1 ? span(x, y) : null};
  }
  if (name === 'sibling-captures') {
    const test = () => term('assertion', capture(letter('a')), 1, false);
    pattern = test();
    for (let i = 1; i < depth; i++) pattern = seq(pattern, test());
    return {pattern, end: x => x < n ? x : null, captured: x => span(x, x + 1)};
  }
  pattern = repeat(letter('a'), '+');
  for (let i = 0; i < depth; i++) pattern = capture(pattern);
  if (name === 'lookbehind') {
    return {pattern: term('assertion', pattern, -1, false), end: x => x ? x : null,
            captured: x => span(0, x)};
  }
  if (name === 'atomic') {
    const allowed = new Uint8Array(n + 1);
    allowed[n] = 1;
    return {pattern: seq(term('atomic', pattern), repeat(letter('a'), '?')), allowed,
            end: x => x < n ? n : null, captured: x => span(x, n)};
  }
  assert.equal(name, 'lookahead');
  return {pattern: seq(term('assertion', pattern, 1, false), letter('a')),
          end: x => x < n ? x + 1 : null, captured: x => span(x, n)};
}

function observeGraph(program) {
  const visits = {pops: 0, predecessors: 0};
  for (const layout of program.layouts) {
    layout.pred = layout.pred.map(original => ({
      *[Symbol.iterator]() {
        visits.pops++;
        for (const predecessor of original) {
          visits.predecessors++;
          yield predecessor;
        }
      }
    }));
  }
  return visits;
}

async function trial(session, name, depth, N) {
  const n = N - 1;
  const spec = example(name, depth, n);
  const program = compile(spec.pattern);
  const graph = observeGraph(program);
  const m = program.size;
  const budget = m * N;
  const staticEdges = program.layouts.reduce((sum, layout) => sum + layout.edges, 0);
  const word = 'a'.repeat(n);
  await session.post('Profiler.takePreciseCoverage');  // reset just before indexing
  const index = prepareMatches(program, word, spec.allowed);
  const {result} = await session.post('Profiler.takePreciseCoverage');
  const modules = ['pattern', 'layers', 'word_index'].map(name =>
    new URL('../paper/index/' + name + '.mjs', import.meta.url).href);
  const sources = result.filter(script => modules.includes(script.url));
  assert.equal(sources.length, modules.length, 'Missing coverage for an index module');
  const functions = sources.flatMap(script => script.functions);
  const calls = name => functions.filter(f => f.functionName === name)
    .reduce((count, f) => count + f.ranges[0].count, 0);
  assert.equal(calls('selectCell'), budget);
  assert.equal(calls('movingAt'), 0);  // moving results are already stored in the child tables
  assert.equal(calls('markLayer'), program.layouts.length * N);
  assert(calls('primitiveExit') <= budget);
  assert(graph.pops <= 2 * budget);
  assert(graph.predecessors <= staticEdges * N && staticEdges <= 4 * m);
  assert.equal(index.stats.vertices, 2 * budget);
  assert.equal(index.stats.cells, 2 * budget);

  // Read the prebuilt index in reverse order. Check slot order, coordinates,
  // and the per-query bound, including failures and zero defined captures.
  let emitted = 0;
  for (let x = n; x >= 0; x--) {
    const end = spec.end(x), expected = [];
    if (end !== null) {
      for (let slot = 0; slot < program.count; slot++) {
        const interval = spec.captured(x, end, slot);
        if (interval) expected.push([slot, ...interval]);
      }
    }
    assert.equal(index.endpoint(x), end);
    const before = index.stats.traceVisits, actual = [];
    assert.equal(index.report(x, (...item) => actual.push(item)), end);
    assert.deepEqual(actual, expected);
    const visits = index.stats.traceVisits - before;
    assert(visits >= expected.length && visits <= Math.max(0, 2 * expected.length - 1));
    if (name === 'sibling-captures') assert.equal(visits, Math.max(0, 2 * expected.length - 1));
    emitted += actual.length;
  }
  return {family: name, depth, m, N, mN: budget, selectCalls: calls('selectCell'),
          pops: graph.pops, predecessors: graph.predecessors, emitted, traceVisits: index.stats.traceVisits};
}

const session = new Session();
session.connect();
try {
  await session.post('Profiler.enable');
  await session.post('Profiler.startPreciseCoverage', {callCount: true, detailed: false});
  console.log('family           cases   select/mN   max pops/mN   max predecessor scans/mN');
  let total = 0;
  for (const name of ['nullable-plus', 'failing-suffix', 'lookahead', 'lookbehind', 'atomic', 'sparse-choice', 'sibling-captures']) {
    const rows = [];
    for (const depth of [4, 8, 16]) {
      for (const N of [129, 257, 513]) {
        rows.push(await trial(session, name, depth, N));
      }
    }
    const maxRatio = key => Math.max(...rows.map(row => row[key] / row.mN)).toFixed(2);
    console.log(name.padEnd(17), String(rows.length).padStart(3), maxRatio('selectCalls').padStart(10),
                maxRatio('pops').padStart(13), maxRatio('predecessors').padStart(25));
    if (process.argv.includes('--rows')) for (const row of rows) console.log(JSON.stringify(row));
    total += rows.length;
  }
  console.log('PASS: ' + total + ' indexed instances, every endpoint and ordered sparse result checked.');
} finally {
  await session.post('Profiler.stopPreciseCoverage');
  session.disconnect();
}
