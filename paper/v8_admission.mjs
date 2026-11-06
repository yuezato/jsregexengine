// Run with node --enable-experimental-regexp-engine v8_admission.mjs.
// Probe admission separately from matching speed. The flag is specific to V8.
import assert from 'node:assert/strict';

new RegExp('', 'l'); // Check that the experimental flag is enabled.
for (const base of ['a?', 'a']) {
  let source = base;
  const accepted = [], rejected = [];
  for (let depth = 1; depth <= 10; depth++) {
    source = '(' + source + ')+?';
    const reference = new RegExp(source).exec('aa');
    let linear;
    try {
      linear = new RegExp(source, 'l');
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
      rejected.push(depth);
      continue;
    }
    assert.deepEqual([...linear.exec('aa')], [...reference]);
    accepted.push(depth);
  }
  console.log(JSON.stringify({node: process.version, v8: process.versions.v8, base, accepted, rejected}));
}
