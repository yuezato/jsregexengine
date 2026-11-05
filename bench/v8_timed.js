// Reads JSON lines {pat, word} and runs exec and matchAll on each in V8, stopping a case after
// LIMIT ms. Prints, as JSON lines, every case slower than THRESH ms, with its index in the input.
// Usage: node bench/v8_timed.js LIMIT THRESH < jobs
const vm = require('vm');
const lines = require('fs').readFileSync(0, 'utf8').split('\n').filter(Boolean);
const LIMIT = +process.argv[2] || 2000, THRESH = +process.argv[3] || 20;
const ctx = vm.createContext({});
lines.forEach((line, i) => {
  const { pat, word } = JSON.parse(line);
  ctx.pat = pat; ctx.word = word;
  const t0 = process.hrtime.bigint(); let status = 'finished';
  try {
    vm.runInContext("new RegExp(pat, 'd').exec(word); [...word.matchAll(new RegExp(pat, 'gd'))].length",
                    ctx, { timeout: LIMIT });
  } catch (e) { status = /timed out/.test(String(e)) ? 'stopped' : 'error: ' + e; }
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  if (ms > THRESH || status !== 'finished') console.log(JSON.stringify({ i, pat, word, ms: Math.round(ms), status }));
});
