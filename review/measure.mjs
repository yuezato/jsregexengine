// One isolated measurement. Tree/source preparation and validation are outside the clock.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {performance} from 'node:perf_hooks';
import vm from 'node:vm';
import {compile, prepareMatches} from '../paper/index/word_index.mjs';

const job = JSON.parse(readFileSync(0, 'utf8'));
const term = (kind, ...parts) => ({kind, parts});
const letter = c => term('character', c);
const seq = (l, r) => term('sequence', l, r);
const repeat = (body, q, lazy = false) => term('repeat', body, q, lazy);

function nested(depth, failingSuffix = true) {
  let tree = repeat(letter('a'), '?'), source = 'a?';
  for (let i = 0; i < depth; i++) {
    tree = repeat(term('capture', tree), '+', true);
    source = '(' + source + ')+?';
  }
  return failingSuffix ? {tree: seq(tree, letter('b')), source: source + 'b'} : {tree, source};
}

function globalMatches(index, n) {
  const result = [];
  let x = 0;
  while (x <= n) {
    const end = index.endpoint(x);
    if (end === null) { x++; continue; }
    result.push([x, end]);
    x = end > x ? end : end + 1;
  }
  return result;
}

function firstMatch(index, n) {
  for (let x = 0; x <= n; x++) {
    const end = index.endpoint(x);
    if (end !== null) return [x, end];
  }
  return null;
}

if (job.op === 'environment') {
  console.log(JSON.stringify({node: process.version, v8: process.versions.v8,
    flags: process.execArgv, platform: process.platform, arch: process.arch}));
} else {
  assert(['product', 'global', 'backtracking', 'admission'].includes(job.suite));
  assert(['index', 'v8', 'v8-linear'].includes(job.engine));
  const {suite, engine, n = 0, depth = 3} = job;
  assert(Number.isSafeInteger(n) && n >= 0 && Number.isSafeInteger(depth) && depth > 0);
  const spec = suite === 'global' ? {
    source: '.*a|b',
    tree: term('choice', seq(repeat(term('character', c => !'\n\r\u2028\u2029'.includes(c)), '*'),
                            letter('a')), letter('b'))
  } : nested(depth, suite !== 'product');
  const program = compile(spec.tree);
  const word = (suite === 'global' ? 'b' : 'a').repeat(n);
  const base = {suite, engine, n, N: n + 1, depth: suite === 'global' ? null : depth,
    m: program.size, mN: program.size * (n + 1), source: spec.source,
    node: process.version, v8: process.versions.v8};
  let regex;
  try {
    if (engine !== 'index') regex = new RegExp(spec.source,
      (suite === 'global' ? 'g' : '') + (engine === 'v8-linear' ? 'l' : ''));
  } catch (error) {
    if (engine !== 'v8-linear' || !(error instanceof SyntaxError)) throw error;
    console.log(JSON.stringify({...base, status: 'unsupported', reason: error.message,
      samples_ms: [], median_ms: null}));
    process.exit(0);
  }
  if (suite === 'admission') {
    console.log(JSON.stringify({...base, status: 'accepted'}));
    process.exit(0);
  }
  let task, validate;
  if (suite === 'global') {
    const expected = Array.from({length: n}, (_, x) => [x, x + 1]);
    task = engine === 'index' ? () => globalMatches(prepareMatches(program, word), n)
      : () => Array.from(word.matchAll(regex), m => [m.index, m.index + m[0].length]);
    validate = result => assert.deepEqual(result, expected);
  } else if (suite === 'product') {
    assert.equal(engine, 'index');
    task = () => prepareMatches(program, word);
    validate = index => {
      for (let x = 0; x <= n; x++) assert.equal(index.endpoint(x), Math.min(x + 1, n));
    };
  } else {
    task = engine === 'index' ? () => firstMatch(prepareMatches(program, word), n)
      : () => regex.exec(word);
    validate = result => assert.equal(result, null);
  }
  const {repeats = 3, warmups = 1, timeout_ms = 1500} = job;
  assert(Number.isSafeInteger(repeats) && repeats > 0);
  assert(Number.isSafeInteger(warmups) && warmups >= 0);
  assert(Number.isSafeInteger(timeout_ms) && timeout_ms > 0);
  // The VM only bounds a prepared call. Its entry and script compilation are not timed.
  const context = vm.createContext({task, clock: () => performance.now()});
  const sample = new vm.Script('begin = clock(); answer = task(); elapsed = clock() - begin;');
  const samples = [], warmupSamples = [];
  for (let i = -warmups; i < repeats; i++) {
    context.answer = null;
    globalThis.gc?.();
    try {
      sample.runInContext(context, {timeout: timeout_ms});
    } catch (error) {
      if (error.code !== 'ERR_SCRIPT_EXECUTION_TIMEOUT') throw error;
      console.log(JSON.stringify({...base, status: 'timeout', timeout_ms,
        phase: i < 0 ? 'warmup' : 'measurement', warmups, repeats,
        warmup_samples_ms: warmupSamples, samples_ms: samples, median_ms: null}));
      process.exit(0);
    }
    validate(context.answer);  // after the clock stops, including all failed starts
    (i >= 0 ? samples : warmupSamples).push(context.elapsed);
  }
  const sorted = [...samples].sort((a, b) => a - b);
  console.log(JSON.stringify({...base, status: 'ok', warmups, repeats,
    warmup_samples_ms: warmupSamples,
    samples_ms: samples, median_ms: sorted[Math.floor(sorted.length / 2)],
    verified: true}));
}
