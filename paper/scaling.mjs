// Deterministic counters on nested nullable lazy plus with one capture per level.
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
import {compile, prepareMatches, matchAllStarts} from './index/word_index.mjs';
import {viableStarts, hasBit} from './all_starts.mjs';
const term = (kind, ...parts) => ({kind, parts});
function medianMs(run) {
  for (let i = 0; i < 5; i++) run();
  const times = [];
  for (let i = 0; i < 11; i++) {
    const begin = performance.now();
    run();
    times.push(performance.now() - begin);
  }
  return Number(times.sort((a, b) => a - b)[5].toFixed(2));
}
for (const k of [4, 8, 16]) {
  let pattern = term('repeat', term('character', 'a'), '?', false);
  for (let i = 0; i < k; i++) pattern = term('repeat', term('capture', pattern), '+', true);
  const program = compile(pattern);
  for (const N of [129, 257, 513]) {
    const {rows, stats} = matchAllStarts(program, 'a'.repeat(N - 1));
    assert.equal(program.size, 2 + 2 * k);
    assert.equal(stats.vertices, 2 * program.size * N);
    assert.equal(stats.cells, stats.vertices);
    assert.equal(stats.outputSlots, k * N);
    assert(rows.every(([end, spans], x) => end === Math.min(x + 1, N - 1) &&
      spans.every(s => s[0] === x && s[1] === end)));
    const word = 'a'.repeat(N - 1);
    const bits = viableStarts(program, word);
    assert(rows.every((_, x) => hasBit(bits.success, x) && hasBit(bits.moving, x) === (x < N - 1)));
    const output = {k, m: program.size, N, ...stats, answerBytes: bits.success.length + bits.moving.length};
    if (process.argv.includes('--time')) {
      // The expression tree and word are constructed outside every timer.
      output.fromAstMedianMs = medianMs(() => matchAllStarts(compile(pattern), word));
      output.indexMedianMs = medianMs(() => prepareMatches(program, word));
      output.medianMs = medianMs(() => matchAllStarts(program, word));
      output.bitsMedianMs = medianMs(() => viableStarts(program, word));
    }
    console.log(JSON.stringify(output));
  }
}
