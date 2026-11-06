// Reads JSON lines {pat, word} and runs exec and matchAll on each in V8, stopping a case after
// LIMIT ms. Prints, as JSON lines, every case slower than THRESH ms, with its index in the input.
// Usage: node bench/v8_timed.js LIMIT THRESH < jobs
const vm = require('vm');
const lines = require('fs').readFileSync(0, 'utf8').split('\n').filter(Boolean);
const LIMIT = +process.argv[2] || 2000, THRESH = +process.argv[3] || 20;
const ctx = vm.createContext({});
// Construct both expressions before the clock. Warm up on an empty string
// because the engine can defer compilation until its first match.
const prepare = new vm.Script("single = new RegExp(pat, 'd'); globalRx = new RegExp(pat, 'gd'); " +
                              "single.exec(''); [...''.matchAll(globalRx)];");
const match = new vm.Script("single.exec(word); [...word.matchAll(globalRx)].length");
lines.forEach((line, i) => {
  const { pat, word } = JSON.parse(line);
  ctx.pat = pat; ctx.word = word;
  try {
    prepare.runInContext(ctx, { timeout: LIMIT });
  } catch (error) {
    console.log(JSON.stringify({ i, pat, word, ms: null, status: 'setup error: ' + error }));
    return;
  }
  const t0 = process.hrtime.bigint(); let status = 'finished';
  try {
    match.runInContext(ctx, { timeout: LIMIT });
  } catch (e) { status = /timed out/.test(String(e)) ? 'stopped' : 'error: ' + e; }
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  if (ms > THRESH || status !== 'finished') console.log(JSON.stringify({ i, pat, word, ms: Math.round(ms), status }));
});
