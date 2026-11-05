// V8 on the nested family G_d b, where G_0 = a? and G_d = (?:G_{d-1})+, as a pure recognizer.
// Usage: node --enable-experimental-regexp-engine bench/v8_nested.js [full]
// Without "full": sizes that take about a second each (well under a minute in total).
// With "full": the sizes reported in the README (about 20 minutes).
// Each time is RegExp.prototype.test on a^n, after warming up the same RegExp object on short
// inputs; a run is stopped after LIMIT seconds. The word contains no b, so every run fails.
// Without the flag, the linear-engine column reports that the engine is unavailable.
const vm = require('vm');
const full = process.argv[2] === 'full';
const LIMIT = 1800;

const G = (d, open = '(?:', q = '+', suffix = 'b') => {
  let p = 'a?';
  for (let i = 0; i < d; i++) p = open + p + ')' + q;
  return p + suffix;
};
// D_d(k): ways in which G_d matches a^k; the suffix is tested sum_k D_d(k) (n - k + 1) times
const D = (d, k) => k === 0 ? 1n : (1n << BigInt(d)) * ((1n << BigInt(d)) - 1n) ** BigInt(k - 1);
const tests = (d, n) => { let s = 0n; for (let k = 0; k <= n; k++) s += D(d, k) * BigInt(n - k + 1); return s; };

let haveLinear = true;
try { new RegExp('a', 'l'); } catch (e) { haveLinear = false; }
const linear = src => {
  if (!haveLinear) return 'unavailable (needs --enable-experimental-regexp-engine)';
  try { new RegExp(src, 'l'); return 'accepted'; } catch (e) { return 'rejected'; }
};

function time(src, word) {
  const ctx = vm.createContext({ src, word });
  vm.runInContext("r = new RegExp(src); for (const s of ['', 'b', 'ab', '']) r.test(s);", ctx);
  const t0 = process.hrtime.bigint();
  try {
    if (vm.runInContext('r.test(word)', ctx, { timeout: LIMIT * 1000 })) return 'MATCH (unexpected)';
  } catch (e) { return '> ' + LIMIT + ' s'; }
  const s = Number(process.hrtime.bigint() - t0) / 1e9;
  return s < 1 ? (s * 1000).toFixed(0) + ' ms' : s.toFixed(1) + ' s';
}

const rows = full ? [[2, 20], [3, 11], [5, 6], [6, 5], [7, 4], [8, 4], [9, 3]]
                  : [[2, 16], [3, 9], [4, 6], [5, 5], [6, 4], [7, 3], [8, 3]];
console.log(`Node.js ${process.versions.node}, V8 ${process.versions.v8}`);
console.log('G_d b on a^n with RegExp.prototype.test (no captures, no lookaround):');
for (const [d, n] of rows) {
  const src = G(d);
  console.log(`  d=${d}  ${String(src.length).padStart(2)} chars  n=${String(n).padStart(2)}  ` +
              `V8 ${time(src, 'a'.repeat(n)).padEnd(9)}  b tested ${Number(tests(d, n)).toExponential(2)} times  ` +
              `linear engine: ${linear(src)}`);
}

const [d, n] = full ? [3, 10] : [3, 9];
console.log(`Variants at d=${d}, n=${n} (the number of matches is the same in all four):`);
for (const [label, src] of [['no captures, greedy, then b', G(d)],
                            ['captures', G(d, '(')],
                            ['no captures, lazy', G(d, '(?:', '+?')],
                            ['captures, lazy, then (?<=b)', G(d, '(', '+?', '(?<=b)')]])
  console.log(`  ${label.padEnd(30)} ${('/' + src + '/').padEnd(28)} V8 ${time(src, 'a'.repeat(n))}`);

if (haveLinear) {
  console.log('Largest depth the linear engine accepts, for P_d = wrap(P_{d-1}) followed by b (up to 40):');
  for (const [label, base, open, q] of [['(?:P)+  over a?', 'a?', '(?:', '+'], ['(?:P)+? over a?', 'a?', '(?:', '+?'],
                                         ['(P)+    over a?', 'a?', '(', '+'], ['(?:P)+  over a ', 'a', '(?:', '+'],
                                         ['(?:P)*  over a ', 'a', '(?:', '*']]) {
    let p = base, last = 0;
    for (let k = 1; k <= 40; k++) {
      p = open + p + ')' + q;
      try { new RegExp(p + 'b', 'l'); last = k; } catch (e) { break; }
    }
    console.log(`  ${label}  ${last === 40 ? 'every depth up to 40' : 'up to depth ' + last}`);
  }
}
