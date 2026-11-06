// Sticky matching at an explicit start. The d flag exposes half-open spans.
// An anchored suffix in selected examples expresses the endpoint test.
import assert from 'node:assert/strict';
const cases = [
  ['(a|aa)b', 'aab', 0, [3, [[0,2]]]],
  ['(?=(a|aa))aab', 'aab', 0, [3, [[0,1]]]],
  ['(?:|a)*', 'a', 0, [1, []]],
  ['(?:()|a)+?', 'a', 0, [0, [[0,0]]]],
  ['(?:()|a)+?$', 'a', 0, [1, [null]]],
  ['(?:(?=(a))|a)+?', 'a', 0, [0, [[0,1]]]],
  ['(?:(?=(a))|a)+?$', 'a', 0, [1, [null]]],
  ['(a?)?', '', 0, [0, [null]]],
  ['(?:(a?)?)+?', '', 0, [0, [null]]],
  ['(?:(a)|(b))*c', 'abc', 0, [3, [null,[1,2]]]],
  ['(?:(a)|(b))*c', 'abc', 1, [3, [null,[1,2]]]],
  ['(?:(a)|(b))*c', 'abc', 2, [3, [null,null]]],
  ['(?:(a)|(b))*c', 'abc', 3, null],
  ['(?<=(a|ba))c', 'bac', 2, [3, [[1,2]]]],
  ['(?<=(a+)(a+))b', 'aaab', 3, [4, [[0,1],[1,3]]]],
  ['(?!(a))b', 'b', 0, [1, [null]]],
  ['(?=(a|aa))b', 'aab', 0, null],
  ['^(?:(a)|b)*()$', 'ab', 0, [2, [null, [2,2]]]],
  ['(?:a*?)?', 'aa', 0, [1, []]],
  ['(?:a*?)?$', 'aa', 0, [2, []]],
  ['(?:a*?)?', '', 0, [0, []]],
  ['()*', '', 0, [0, [null]]],
  ['()+', '', 0, [0, [[0,0]]]],
  ['(?!)', '', 0, null],
  ['(?:)', '', 0, [0, []]],
  ['[ab]', 'ba', 0, [1, []]],
  ['$', 'a', 1, [1, []]],
  ['(?:(a)|a)', 'a', 0, [1, [[0, 1]]]],
  ['(?:(a)|b)*b$', 'ab', 0, [2, [[0, 1]]]],
  ['(?:(a)|b)*$', 'ab', 0, [2, [null]]],
  ['(?<!(a))b', 'cb', 1, [2, [null]]],
  ['(?<!(a))b', 'ab', 1, null],
  // A native suffix serving as a capture-sensitive external continuation.
  ['(?:(a)|a)', 'a', 0, [1, [[0,1]]]],
  ['(a)', 'a', 0, [1, [[0,1]]]],
  [/(?:(a)|a)\1/.source, 'a', 0, [1, [null]]],
  [/(a)\1/.source, 'a', 0, null],
  [/(?:(a)|a)\1$/.source, 'a', 0, [1, [null]]],
  [/(a?)a?\1$/.source, 'a', 0, [1, [[0,0]]]],
];
// A merging star body under two priorities and two terminal conditions.
for (const priority of ['*', '*?']) {
  const lazy = priority === '*?';
  for (const suffix of ['a?b$', 'b$']) {
    const first = lazy && suffix === 'a?b$' ? [[0,1], null] : [[1,2], null];
    const second = lazy && suffix === 'a?b$' ? [null, null] : [[1,2], null];
    const allStarts = [[3, first], [3, second], [3, [null, null]], null];
    for (const [start, expected] of allStarts.entries()) {
      cases.push(['(?:(a)|(aa))' + priority + suffix, 'aab', start, expected]);
    }
  }
}
// The source-size example inserts a capture between every pair of pluses.
let nested = 'a?';
for (let depth = 1; depth <= 6; depth++) {
  nested = '(' + nested + ')+?';
  for (const [word, start] of [['', 0], ['a', 0], ['a', 1]]) {
    const end = word.length;
    const captures = Array.from({ length: depth }, () => [start, end]);
    cases.push([nested, word, start, [end, captures]]);
  }
}
function anchored(source, word, start, flags = 'dy') {
  const regex = new RegExp(source, flags);
  regex.lastIndex = start;
  const match = regex.exec(word);
  return match && [regex.lastIndex, match.indices.slice(1).map(span => span ?? null)];
}

// These patterns have the same matching intervals and different captures.
for (const [source, capture] of [['(?=(a|aa))aa', [0, 1]], ['(?=(aa|a))aa', [0, 2]]]) {
  const results = [[2, [capture]], null, null];
  for (const [start, expected] of results.entries()) {
    cases.push([source, 'aa', start, expected]);
  }
}
cases.push(['(?:a|aa)b', 'aab', 0, [3, []]]);
// Counted repeats are outside the fragment. Literal copies can change both
// progress and the number and values of capture slots.
cases.push(['(?:|a){0,2}', 'aa', 0, [2, []]],
           ['(?:(?:|a)(?:(?:|a))?)?', 'aa', 0, [1, []]],
           ['(?:(a)|b){2}', 'ab', 0, [2, [null]]],
           ['(?:(a)|b)(?:(a)|b)', 'ab', 0, [2, [[0,1], null]]]);

// Work through the same single expression as the technical overview.
const word = 'aab';
const positions = [0, 1, 2, 3];
const branches = ['(?=(aa))', '(a)', 'aa'];
const body = '(?:(?=(aa))|(a)|aa)';
const suffix = 'a?b$';
// A greedy optional exposes the moving answer of its product when it exists.
cases.push(['(?:' + body + 'a?)?', word, 0, [1, [[0, 2], null]]],
           ['(?:' + body + '(?:))?', word, 0, [1, [null, [0, 1]]]]);
const offers = positions.map(x => branches.flatMap(source => {
  const result = anchored(source, word, x);
  return result ? [result[0]] : [];
}));
assert.deepEqual(offers, [[0, 1, 2], [2], [], []]);

const stops = positions.filter(x => anchored(suffix, word, x));
assert.deepEqual(stops, [1, 2]);
const viable = new Set(stops);
for (const x of [...positions].reverse()) {
  if (offers[x].some(y => x !== y && viable.has(y))) viable.add(x);
}
assert.deepEqual(positions.filter(x => viable.has(x)), [0, 1, 2]);
const first = offers.map(row => row.find(y => viable.has(y)) ?? null);
const moving = offers.map((row, x) => row.find(y => y !== x && viable.has(y)) ?? null);
assert.deepEqual(first, [0, 2, null, null]);
assert.deepEqual(moving, [1, 2, null, null]);

for (const [priority, firstExit, firstSpan] of [['+?', 1, [0, 1]], ['+', 2, [1, 2]]]) {
  for (const [start, exit] of [firstExit, 2, null, null].entries()) {
    const spans = [null, start === 0 ? firstSpan : [1, 2]];
    cases.push([body + priority + suffix, word, start, exit === null ? null : [3, spans]]);
    // A test for the same suffix exposes the preferred exit of the plus itself.
    cases.push([body + priority + '(?=' + suffix + ')', word, start, exit === null ? null : [exit, spans]]);
  }
}
const noSuffix = [[0, [[0, 2], null]], [2, [null, [1, 2]]], null, null];
for (const [start, expected] of noSuffix.entries()) {
  cases.push([body + '+?', word, start, expected]);
}

// Opening suffix captures, the two shapes of readout, and mixed priorities.
for (let start = 0; start <= 4; start++) {
  const expected = start < 4 ? [start + 1, [[start, 4]]] : null;
  cases.push(['(?=(a+))a', 'aaaa', start, expected]);
}
cases.push(['(a)(b)', 'ab', 0, [2, [[0, 1], [1, 2]]]],
           ['((ab))', 'ab', 0, [2, [[0, 2], [0, 2]]]],
           ['(?:(a)?)+', 'aa', 0, [2, [[1, 2]]]],
           ['(?:(a)?)+?', 'aa', 0, [1, [[0, 1]]]],
           ['(?:(a)?)+?', '', 0, [0, [null]]],
           ['a|aa', 'aa', 0, [1, []]],
           ['(a)*?', 'aa', 0, [0, [null]]]);
for (const [source, input, start, expected] of cases) {
  assert.deepEqual(anchored(source, input, start), expected, JSON.stringify([source, input, start]));
}
// The ordered expansion of a Unicode string class is tried against the
// suffix. Public indices are UTF-16 offsets, including in Unicode mode.
const modernCases = [
  [String.raw`[\q{a|ab|}]`, 'v', 'ab', 0, [2, []]],
  [String.raw`([\q{a|ab|}])b$`, 'v', 'ab', 0, [2, [[0,1]]]],
  [String.raw`[\q{}]`, 'v', 'x', 0, [0, []]],
  [String.raw`([\q{}])+`, 'v', 'x', 0, [0, [[0,0]]]],
  [String.raw`([\q{}])*`, 'v', 'x', 0, [0, [null]]],
  [String.raw`(?<=a([\q{ab|b|}]))`, 'v', 'ab', 2, [2, [[1,2]]]],
  [String.raw`(\p{RGI_Emoji})!`, 'v', '👩‍💻!', 0, [6, [[0,5]]]],
  [String.raw`(?i:([\q{ab|cd}]))b`, 'v', 'ABb', 0, [3, [[0,2]]]],
  ['(?i:a)b', '', 'AB', 0, null],
  ['(?i:a(?-i:b))', '', 'Ab', 0, [2, []]],
  ['(?m:^a)', '', '\na', 1, [2, []]],
  ['(?s:.)', '', '\n', 0, [1, []]],
];
for (const [source, flags, input, start, expected] of modernCases) {
  assert.deepEqual(anchored(source, input, start, 'dy' + flags), expected,
                   JSON.stringify([source, flags, input, start]));
}
// A separate conformance probe for single-character \q alternatives under
// /iv. Its expected result follows from CompileAtom and CharacterSetMatcher.
if (process.argv.includes('--unicode-fold')) {
  const classMatch = anchored(String.raw`[\q{a}]`, 'A', 0, 'dyiv');
  const literalMatch = anchored('[a]', 'A', 0, 'dyiv');
  assert.deepEqual(literalMatch, [1, []]);
  const scoped = anchored(String.raw`(?i:([\q{a|ab|}]))b`, 'Ab', 0, 'dyv');
  assert.deepEqual({classMatch, scoped}, {classMatch: literalMatch, scoped: [2, [[0,1]]]},
                   'ECMAScript: folding of a one-character class string, alone and after fallback');
  console.log(JSON.stringify({unicode_folding_probes: 2}));
}
console.log(JSON.stringify({native_anchored_examples: cases.length,
                            class_and_modifier_examples: modernCases.length,
                            overview_rows: offers.length}));
