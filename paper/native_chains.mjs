// Compare all chains through depth three with their representatives in the JS engine.
// The appended zero-width assertion accepts exactly the endpoints in each mask.
import assert from 'node:assert/strict';

const operators = ['?', '??', '*', '*?', '+', '+?'];
const bodies = ['a', '(a?)', '(?:(a)|b)', '(?:()|a)', '(?:(?<=a)(b)|(?=(a))|a)'];
const words = ['', 'a', 'aa', 'ab', 'aba'];

function representative(chain) {
  let optional = null, plus = null;
  for (const op of chain) {
    const greedy = op.length === 1;
    if (op[0] !== '+' && optional === null) optional = greedy || plus === true;
    if (op[0] !== '?') plus = greedy || plus === true;
  }
  const form = [];
  if (optional !== null) form.push(optional ? '?' : '??');
  if (plus !== null) form.push(plus ? '+' : '+?');
  return form;
}

function wrap(body, chain) {
  return chain.reduceRight((pattern, operator) => '(?:' + pattern + ')' + operator, body);
}

function endTest(word, mask) {
  const alternatives = [];
  for (let end = 0; end <= word.length; end++) {
    if (mask & (1 << end)) alternatives.push('.{' + (word.length - end) + '}');
  }
  return alternatives.length ? '(?=(?:' + alternatives.join('|') + ')$)' : '(?!)';
}

function match(regex, word, start) {
  regex.lastIndex = start;
  const result = regex.exec(word);
  return result && [...result.indices];
}

let chains = [[]];
let count = 0;
for (let depth = 1; depth <= 3; depth++) {
  chains = chains.flatMap(prefix => operators.map(op => [...prefix, op]));
  for (const chain of chains) {
    const form = representative(chain);
    for (const body of bodies) {
      for (const word of words) {
        for (let mask = 0; mask < (1 << (word.length + 1)); mask++) {
          const test = endTest(word, mask);
          const original = new RegExp(wrap(body, chain) + test, 'dy');
          const rewritten = new RegExp(wrap(body, form) + test, 'dy');
          for (let start = 0; start <= word.length; start++) {
            assert.deepEqual(match(rewritten, word, start), match(original, word, start),
                             JSON.stringify({body, chain, word, start, mask}));
            count++;
          }
        }
      }
    }
  }
}
// A following backreference can reject the first map at an otherwise viable exit.
const capturingBodies = ['(a?)', '(?:()|a)', '(?:(a)|a)', '(?:a|(a))', '(?:(a?)|b)',
                         '(?:(?=(a))|a)', '(?:(?<=([ab]))|a)', '(?:(a)|b|)'];
const suffixes = ['\\1', '\\1$', '(?=\\1$)', '(?!\\1)a', '(?:b|\\1)a'];
const captureWords = ['', 'a', 'b', 'aa', 'ab', 'ba', 'aaa', 'aba', 'aab'];
const rules = [['*'], ['*?']];
for (const [left, right] of [[['?', '??'], ['?', '??']],
                             [['+', '+?'], ['+', '+?']],
                             [['+', '+?'], ['?', '??']]]) {
  for (const op of left) for (const inner of right) rules.push([op, inner]);
}
let captureTests = 0;
for (const body of capturingBodies) for (const chain of rules) for (const test of suffixes) {
  const original = new RegExp(wrap(body, chain) + test, 'dy');
  const rewritten = new RegExp(wrap(body, representative(chain)) + test, 'dy');
  for (const word of captureWords) for (let start = 0; start <= word.length; start++) {
    assert.deepEqual(match(original, word, start), match(rewritten, word, start),
                     JSON.stringify({body, chain, test, word, start}));
    captureTests++;
  }
}
assert.equal(captureTests, 14560);
// Each suffix accepts exactly its listed exits at the boundaries of "aa".
const exitTests = [['^', [0]], ['$', [2]], ['(?<=a)', [1, 2]], ['(?=a)', [0, 1]]];
const ranked = [
  [[1], [1, 2], [2, 1]],
  [[0, 1], [0, 1, 2], [0, 2, 1]],
  [[1, 0], [1, 2, 0], [2, 1, 0]],
];
const signatures = new Set();
let exitComparisons = 0;
for (const [i, outer] of [null, '??', '?'].entries()) {
  for (const [j, inner] of [null, '+?', '+'].entries()) {
    const pattern = wrap('a', [outer, inner].filter(op => op !== null));
    const signature = [];
    for (const [suffix, allowed] of exitTests) {
      const answer = match(new RegExp(pattern + suffix, 'dy'), 'aa', 0);
      const end = answer?.[0]?.[1] ?? null;
      assert.equal(end, ranked[i][j].find(y => allowed.includes(y)) ?? null);
      signature.push(end);
      exitComparisons++;
    }
    signatures.add(JSON.stringify(signature));
  }
}
assert.equal(signatures.size, 9);
console.log(JSON.stringify({native_chain_comparisons: count,
                            backreference_suffix_comparisons: captureTests,
                            four_suffix_comparisons: exitComparisons}));
