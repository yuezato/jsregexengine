// V8's experimental linear-time engine on nested repetitions.
// Usage: node --enable-experimental-regexp-engine bench/v8_linear.js
// 1. the largest depth d it accepts for several nestings P_d = wrap(P_{d-1}), followed by b;
// 2. its time per letter on G_d b (G_0 = a?, G_d = (?:G_{d-1})+) for the depths it accepts.
let ok = true;
try { new RegExp('a', 'l'); } catch (e) { ok = false; }
console.log(`Node.js ${process.versions.node}, V8 ${process.versions.v8}`);
if (!ok) { console.log('the linear engine is unavailable: run node with --enable-experimental-regexp-engine'); process.exit(0); }

console.log('Largest accepted depth (up to 40):');
for (const [label, base, open, q] of [['(?:P)+  over a?', 'a?', '(?:', '+'], ['(?:P)+? over a?', 'a?', '(?:', '+?'],
                                       ['(P)+    over a?', 'a?', '(', '+'], ['(P)+?   over a?', 'a?', '(', '+?'],
                                       ['(?:P)+  over a ', 'a', '(?:', '+'], ['(?:P)*  over a ', 'a', '(?:', '*'],
                                       ['(?:P)*  over a?', 'a?', '(?:', '*']]) {
  let p = base, last = 0;
  for (let d = 1; d <= 40; d++) {
    p = open + p + ')' + q;
    try { new RegExp(p + 'b', 'l'); last = d; } catch (e) { break; }
  }
  console.log(`  ${label}  ${last === 40 ? 'every depth up to 40' : 'up to depth ' + last}`);
}

console.log('Time per letter on G_d b over a^n (exec with the l flag, best of 3):');
for (let d = 1; d <= 4; d++) {
  let p = 'a?';
  for (let i = 0; i < d; i++) p = '(?:' + p + ')+';
  const r = new RegExp(p + 'b', 'l'), row = [];
  for (const n of [10000, 100000]) {
    const w = 'a'.repeat(n); let best = Infinity;
    for (let k = 0; k < 3; k++) {
      const t0 = process.hrtime.bigint(); r.exec(w); best = Math.min(best, Number(process.hrtime.bigint() - t0));
    }
    row.push(`n=${n}: ${(best / n).toFixed(1)} ns/letter`);
  }
  console.log(`  d=${d}  ${row.join('   ')}`);
}
