# bitre: JavaScript-style regex matching from every start

## Reproducing the paper

From the repository root, run `python3 reproduce.py quick` for the deterministic product-linearity checks or `python3 reproduce.py full` for the paper's Section 9 and the public correctness suite. Use Python 3.11+ and Node.js 24+; these commands run offline. The expected work counts, theorem-to-code map and cost model are in [REPRODUCING.md](REPRODUCING.md).

## Two implementations

| Goal | Entry point | Guarantee in the paper |
|---|---|---|
| Choose a starting position after preprocessing and enumerate only its defined captures | JavaScript, `paper/index/word_index.mjs`: `compile`, `prepareMatches`, `index.report` | Theorem 1.2. O(mN) time and machine words to build the index; O(1) for the endpoint, O(1+k) for the k defined spans. |
| Write a dense match result at every start once | Python, `bitre.py`: `Regex.all_starts`; compact position maps in `bitcolumns.py` | Theorem 7.4. O(mN) time and O(mN) bits of working space in the stated RAM model, excluding delivered output. |

The complete word index, including tree preparation, spans three modules and 296 nonblank, noncomment JavaScript lines (323 physical lines). Run `python3 review/size.py` to count them. The packed reporter retains columns at piece boundaries and rebuilds one piece at a time. It returns a failure or the preferred endpoint and all capture slots at each start.

Run `node paper/scaling.mjs --time` on a prebuilt occurrence tree. The `fromAstMedianMs` field includes tree preparation, text indexing and all dense output. Other fields isolate index construction or reuse a prepared pattern.

The Python `match_all` client uses the batch computation for global matches. For the original leftmost-match experiments, `exec` builds a decision table and walks the chosen path. Python `index(text, B).match_at(x)` also walks one selected match; the output-sensitive index is the JavaScript entry point in the table above.

## Requirements

- Python 3.11 or later, which provides the CPython regex parser `re._parser` used by the front end. The original measurements used CPython 3.13.18. The v59 correctness results below were obtained on CPython 3.12.14.
- Node.js, for the comparisons with V8. The archived runs used v22.23.4 and v25.9.0. The v59 comparison used v24.22.1. Choose the binary with the environment variable `NODE` (default `node`).
- Optionally RE2 (`pip install google-re2`), for one comparison in `bench/nested.py`.

## Quick start

```sh
sh run_tests.sh
python3 bench/bench_batch.py quick    # overlapping starts, forward and backward
python3 bench/bench_regelk.py quick   # leftmost-match benchmark
```

```python
from bitre import Regex

rx = Regex(r'(?=(a+))a')
rx.all_starts('aaa')
# [(0, 1, [None, (0, 3)]), (1, 2, [None, (1, 3)]),
#  (2, 3, [None, (2, 3)]), None]
rx.match_all('aaa')                  # the three successful global matches
rx.index('aaa', B={2}).match_at(1)   # (1, 2, [None, (1, 3)])

Regex('a*+a').all_starts('a')         # [None, None]: the possessive star commits
Regex('a*a').all_starts('a')[0]      # (0, 1, [None])
```

Each successful row is `(start, end, slots)`. Slots are numbered from 1, in the order of the capturing parentheses. The first array element is an unused placeholder. A capture that did not participate has value `None`, whereas `(x, x)` is a defined empty capture. The result for a failed start is itself `None`. Pass the pattern body without JavaScript’s slash delimiters. Use `match_all(text)` for global matching.

## Reading the examples in v59

At position 0 on `ab`, compare where each pattern tries its trailing `b`.

| Pattern | Before the final `b` | `Regex(pattern).all_starts('ab')[0]` |
|---|---|---|
| `(a)b` | Read `a`, advance to 1 and record the first group. | `(0, 2, [None, (0, 1)])` |
| `(?:a)b` | Read the same letter without creating a capture for the parentheses. | `(0, 2, [None])` |
| `(?=a)b` | Test for `a` and restore the cursor to 0. The following `b` fails there. | `None` |

A positive lookahead can return to its entrance and still export a longer capture. The allowed final set filters matches before the first result is chosen.

```python
from bitre import Regex

assert Regex(r'(?=(a+))').all_starts('aaaa')[1] == (1, 1, [None, (1, 4)])
rx = Regex(r'a|aa')
assert rx.all_starts('aa')[0][1] == 1
assert rx.all_starts('aa', B={2})[0][1] == 2
```

In the example from Section 2, the body can inspect `aa` without moving, consume and capture one `a`, or consume two letters. At start 0 on `aab` the lazy and greedy versions both end at 3, but their last iterations write different spans.

```python
from bitre import Regex

body = r'(?:(?=(aa))|(a)|aa)'
assert Regex(body + r'+?a?b$').all_starts('aab')[0] == (0, 3, [None, None, (0, 1)])
assert Regex(body + r'+a?b$').all_starts('aab')[0] == (0, 3, [None, None, (1, 2)])
```

The rest of the pattern, `a?b$`, succeeds from 1 or 2. At 0 the first iteration can finish with its lookahead, but the plus must continue. A later iteration replaces the capture written by that lookahead. Run `python3 tests/test_examples.py` to compare the complete rows at every start with V8, including failed starts.

## Repository layout

```
paper/index/          Theorem 1.2: pattern preparation, position layers, word index and reports
paper/bit_walk.mjs    packed Boolean decisions and a single-start walk
regex_syntax.py       Python source parser and primitive character semantics
bitre.py              region sweeps, single-match walk, piecewise batch reporter
bitcolumns.py         packed partial maps, color lookup and stopping forests
families.py           benchmark families: those of RegElk, and lazy variants
run_tests.sh          runs the Python correctness suite
reference/
  semantics.py        reference semantics: the paper's ordered lists, and a transcription
                      of ECMAScript's backtracking matcher
  patterns.py         random pattern generators for the differential tests
tests/
  common.py           shared helpers: import paths, the V8 runner, normalization
  v8_run.js           runs V8 on JSON lines: exec and matchAll, or a sticky exec at a start
  test_reference.py   the offline batch and the single-match walk against both semantics
  test_batch.py       commitment, signed jumps, possessive quantifiers and overlapping starts
  test_columns.py     half-open colors, inverse maps, stopping forests and rank/select
  test_v8.py          bitre against V8 on random patterns
  test_families.py    bitre against V8 on every benchmark family at small sizes
  test_examples.py    bitre against V8 on the paper's examples, at every start
  test_flags.py       bitre against V8 on flags and character classes
bench/
  common.py           timing, least-squares fit and reporting
  bench_batch.py      all anchored answers with overlapping lookaround and atomic jumps
  bench_regelk.py     product-linearity on RegElk's families
  bench_lazy.py       lazy variants, and the clocks-versus-clearing control
  clearing.py         the control matcher: literal capture clearing instead of clocks
  bench_split.py      sweep and walk timed separately, with the number of walk calls
  depth.py            cost of one CPython call against recursion depth
  v8_random.py        random patterns on which V8 backtracks for a long time
  v8_timed.js         runs V8 on JSON lines with a time limit per case
  v8_nested.js        V8 on the nested family G_d
  v8_linear.js        the depth limits and the time per letter of V8's linear engine
  nested.py           the same family counted by a backtracking matcher, and timed in
                      bitre and (if installed) RE2
results/              the outputs reported below (text, and JSON with every timing)
```

## How the implementation follows v59

| Step | Implementation | Manuscript |
|---|---|---|
| Prepare the pattern | `Regex._prepare` cuts at assertions and atomic groups, preserving the local matching direction. `_partition` fixes pieces of size at most `2 ceil(sqrt(m)) - 1` before reading the word. | Sections 4, 7.4 and Appendix C.4 |
| Compute viability | `_sweep` stores the entrance and exit marks, moving success and preferred stationary success in one byte per node and position. Atomic children are solved with all local exits allowed. A stationary commitment is a same-layer edge. A jump reads its chosen destination's already-computed exit mark. | Sections 4–7 and Appendix C.3 |
| Select an endpoint | `_split` chooses full or moving results in a sequence. `Tail` follows the repeated body's first viable advances to the last body before the stop. A nullable mandatory first body supplies the captures when no advancing body supersedes it. | Sections 5–6 and Appendices C.1–C.3 |
| Write captures | `_report` retains piece-root columns. In top-down order it rebuilds each piece and follows only the surviving visits for every selected start. Signed requests are filled in two sweeps, so nested lookbehind can move a capture outside the overall match. | Theorem 7.4 and Appendix C.4 |
| Walk a single match | `_walk` and `_collect` replay a selected path with timestamped capture resets. This remains useful for a single query and the original experiments. | Appendix C.5 |

For a prepared tree of `m` syntax occurrences and `N = len(w)+1`, with constant-cost primitive tests or supplied predicate tables, the batch takes `O(mN)` word-RAM operations. The benchmark constructs the pattern before timing. See the [timing boundaries](REPRODUCING.md#timing). The capture arrays are delivered output. There are `O(sqrt(m))` simultaneously live columns in the piece passes. `bitcolumns.py` uses byte-rounded unsigned arrays for explicit positions. When positions exceed the column's budget, it colors half-open source–target intervals and stores fixed points separately. To look up a color, it stably partitions by digits of radix `O(sqrt(m))`. There are a constant number of digits. Packed bitmaps with prefix counts and select directories route a position through these partitions in constant time. Coded terminal maps traverse parent and inverse links without a word-length recursion stack.

Theorem 7.4 gives `O(mN)` workspace **bits** in the manuscript’s RAM model, excluding input, supplied primitive tests and delivered output. The Python prototype also uses conventional syntax descriptors, objects and byte-rounded buffers. Its process RSS includes the interpreter and allocator. The batch API writes all rows once. `match_at` performs a walk when called later.

## Correctness

Three oracles, none of which shares code with `bitre.py`:

- **The ordered lists of Section 3** (`reference/semantics.py`, `naive_answers`). Each node denotes the list of its results, an end position with capture spans, in the order backtracking would try them. The answer at start x is the first result whose end lies in a given set B of allowed end positions.
- **ECMAScript's backtracking matcher** (`spec_answers`). A transcription of the specification: continuation-passing matchers, RepeatMatcher with its capture clearing and empty check, lookahead and lookbehind. Appendix A relates it to the lists; the tests check the two against each other on every pattern.
- **V8**, through Node.js: `exec`, `matchAll`, and sticky `exec` at a given start, all with the `d` flag, so that every capture span is compared.

The two reference semantics enumerate, so they are exponential in the worst case. They work on their own pattern trees, which are printed as JavaScript source for `bitre.py` and V8 to parse. The tests therefore also cover the parsing path.

The set B comes from Problem 1.1: a match may be required to end in B, and an ordinary `exec` allows every position. The reference test draws B at random, so it also covers restrictions that `exec` never makes.

| Test | Oracle | What is compared | Size | Mismatches |
|---|---|---|---|---|
| `test_reference.py` | both reference semantics | both batch and walk at every start, for a random B | 100,000 random patterns; words over {a, b} of length 0–7; 449,418 starts, 224,349 of them with a match | 0 |
| `test_v8.py` | V8 | `exec` and `matchAll` | 50,000 random patterns; words of length 0–9 | 0 |
| `test_families.py` | V8 | `exec` and `matchAll` | 488 instances of the benchmark families at small sizes | 0 |
| `test_examples.py` | V8 | the match anchored at every start | the paper's examples and related cases: 88 patterns, 263 starts | 0 |
| `test_flags.py` | V8 | `exec` and `matchAll` | 22 cases: flags `i`, `m`, `s`; classes `\d \w \s`; `\b`; case folding | 0 |

The additional `test_batch.py` compares 9,207 anchored rows containing atomic commitments with both reference semantics, tests all three possessive spellings, and checks mixed-direction requests. V8 comparisons use the standard fragment. `test_columns.py` checks 11,824 forward/backward partial maps, 4,276 forest/stop/direction/encoding instances, and the directory spill and shared-boundary cases.

The list semantics and the ECMAScript matcher also agree with each other on all 100,000 patterns. A further 83 generated patterns were skipped because their result lists exceeded the enumeration budget.

Random patterns are built from `a`, `b`, `[ab]`, the empty pattern, failure and the anchors `^ $ \b \B`. These are combined by sequence, choice, capture, the greedy and lazy `?`, `*` and `+`, and positive and negative lookahead and lookbehind. 60% come from a generator biased towards the delicate cases: plus over nullable bodies (often lazy), chains of nested quantifiers, empty captures, and captures inside lookarounds inside repetition. Of the patterns in `test_reference.py`, 53% contain a lookaround, 31% a lookbehind and 39% a lazy plus.

The V8 comparison keeps words short so that V8 finishes. With words of up to 16 letters, three of the same 50,000 random patterns already make V8 run past a two-second limit (see [Where V8 breaks](#where-v8-breaks)).

`results/tests.txt` records the v59 Python suite. The original run under Node.js 25.9.0 is in commit `dee1217`. The RegElk, lazy and V8 measurement files below are the archived single-match experiments from that commit.

## Product-linearity

**All anchored starts.** `bench/bench_batch.py` compares every row of the batch against replay and checks the expected capture spans on `aⁿ`. It varies both the group count and word length for lookahead, lookbehind and a committing lookahead. `moving_cells` counts moving-column entries built (including piece reconstruction and any closed atomic child), and `replay_walk_calls` counts source visits by the single-match walk across all starts. They are separate operation counts, not interchangeable units of time. `results/batch.txt` records a run.

**Original single-match method.** Each instance times `exec`, which builds the bit table for all starts and walks the leftmost match with its captures. RegElk's timer for V8 measures the same operation, `string.match`. Parsing is not timed, and each time is the best of three runs. m is the number of nodes of the parsed pattern and N = |w| + 1. Over each family we fit

  log t = c + a·log m + b·log N

by least squares. Product-linearity predicts a = b = 1, and a constant time per cell, t/(m·N).

**RegElk's families.** The definitions are transcribed from RegElk's `benchmark_vectors.ml` (Barrière and Pit-Claudel, PLDI 2024). RegElk keeps the input of a regex-size family fixed; here both the depth k and the input length vary, with inputs of the same shape. All of these families are greedy.

| Family | Pattern at k = 2 | Input | m | N | Slope in m | Slope in N | ns per cell |
|---|---|---|---|---|---|---|---|
| NNPlus | `(?:(?:a)+)+` | aⁿ | 26–401 | 251–2001 | 0.99 | 0.99 | 629–717 |
| CDN | `(?:(?:a\|(^))+)+` | aⁿ⁻¹b | 29–404 | 251–2001 | 1.02 | 1.00 | 614–717 |
| Clocks | `((a)*)*` | aⁿ | 51–801 | 251–2001 | 1.04 | 1.02 | 484–653 |
| LAreg | `a(?=a(?=(a*)b))` | aⁿ⁻¹b | 80–1205 | 251–2001 | 0.98 | 1.05 | 579–717 |
| LBreg | `a*(?<=a*(?<=ba*))` | baⁿ⁻¹ | 104–1604 | 251–2001 | 1.01 | 1.00 | 657–736 |
| LAstr | `c(?:a(?=a*(?<=c(a*))b))*` (fixed) | caⁿ⁻²b | 17 | 1001–64001 | — | 1.01 | 565–647 |
| LBstr | `b(?:a(?<=ba*))*` (fixed) | baⁿ⁻¹ | 10 | 1001–64001 | — | 1.00 | 623–761 |

Across all families, m·N spans a factor of about 500, while the time per cell stays between 484 and 761 ns.

**Lazy variants.** RegElk's families never use a lazy quantifier, so they do not exercise the paper's treatment of nullable lazy plus. `families.py` adds lazy versions of three families, with a final `$` so that the leftmost match runs through the whole input and the walk does real work. In CDN? the body `a|(^)` is nullable, so a translation that copies the body of a lazy plus would double the pattern at every level.

| Family | Pattern at k = 2 | Input | m | N | Slope in m | Slope in N | ns per cell |
|---|---|---|---|---|---|---|---|
| NNPlus? | `(?:(?:a)+?)+?$` | aⁿ | 28–403 | 251–2001 | 1.07 | 1.01 | 867–1120 |
| CDN? | `(?:(?:a\|(^))+?)+?$` | aⁿ | 31–406 | 251–2001 | 1.09 | 1.00 | 869–1118 |
| Clocks? | `((a)*?)*?$` | aⁿ | 53–803 | 251–2001 | 1.10 | 1.01 | 857–1138 |

**Where the slightly larger slope comes from.** `bench/bench_split.py` times the two phases separately.

- **The sweep.** Building the bit table alone has slopes 1.01–1.04 in m on these families.
- **The walk.** It makes 0.84–1.00 calls per cell, so the number of calls stays below the number of cells. It takes up to 43% of the time here, against at most 4% on RegElk's families.
- **The cost of each call.** Each walk call gets slower as m grows. The walk recurses through every nesting level for every character, and CPython calls get slower with depth: `bench/depth.py` measures the same trivial recursive call at about 44 ns up to depth 200, 70 ns at 400, 96 ns at 800 and 115 ns at 3200.

The excess is thus a constant-factor effect of the interpreter, not extra work.

**Control: clocks against literal clearing.** JavaScript resets the captures of a quantifier's body at every iteration. Clearing them literally costs the number of groups in the body for every iteration. `bitre.py` instead uses timestamps (clocks), as Barrière and Pit-Claudel do, so that each iteration costs O(1). `bench/clearing.py` swaps in literal clearing. It gives the same answers (checked on 2,000 random patterns) and differs only in cost. Nanoseconds per cell at N = 1001:

| | m = 43 | 83 | 163 | 323 | 643 |
|---|---|---|---|---|---|
| Clocks?, clocks (`bitre.py`) | 851 | 864 | 931 | 1042 | 1081 |
| Clocks?, literal clearing | 1031 | 1185 | 1511 | 2032 | 3154 |

- **With clocks.** As m grows fifteenfold, the time per cell rises by 27%.
- **With literal clearing.** It triples and grows linearly in m, so the total grows as m²N. In Clocks? every character re-enters all k levels, and clearing costs 1 + 2 + … + k slot writes per character.
- **RegElk's greedy Clocks.** The two hardly differ: 569–609 against 563–611 ns per cell over m = 41 to 641. The walk follows a single path, and the innermost loop reads the whole input in one entry.

RegElk's own comment on that family is that clocks have a better complexity than dynamic clearing of registers. This holds for engines like RegElk that advance all threads together, because they re-enter every level at every position.

**Machine.** Intel Xeon @ 2.10 GHz, 2 vCPUs, Linux, CPython 3.13.18. Every run is single-threaded. `results/` holds the printed summaries and, in JSON, every (m, N, time) triple.

## Where V8 breaks

V8 matches by backtracking. On some patterns of the fragment it needs exponential time, even as a pure recognizer with neither captures nor lookaround. All measurements below use Node.js 25.9.0 (V8 14.1) on the machine above.

**Found by random testing.** `bench/v8_random.py` regenerates the 50,000 random patterns of `tests/test_v8.py`, but with words of up to 16 letters, and runs each in V8 with a two-second limit. Three cases reach the limit:

| Case | Pattern | Word |
|---|---|---|
| #10189 | `(?:b\|((?:a\|b)(?:(?:))+?)\|(?:[ab]+)??(?:(?:)\|((?:))\|(?:)[ab]))*((?<=(?<!((((?:)))))))` | `ababbbbabbbababb` |
| #34224 | `(?:[ab]\|((?:b??)+?))+?(?<=((?!(b[ab]\|(((?:)))))))` | `bbbbbbabbbbbabab` |
| #39426 | `(?:(?:((?:)(?!(a)))\|(?:(?:[ab]+?)??)*?)*?)+?(?:(?<!([ab]?)))+?(?:)` | `bbaaaaaabbaabaab` |

All three have the same shape: nested quantifiers over bodies that can match the empty string, followed by an assertion that can never succeed. For example, `(?!(b[ab]|()))` always fails because `()` always matches. V8 does not notice this, so it tries every way of matching the quantifiers before it gives up. `bitre.py` answers each of them, `exec` and `matchAll` together, in 0.3–0.4 ms.

**A family that isolates the cause.** Let `G_0 = a?` and `G_d = (?:G_{d−1})+`, and append `b`. On the word aⁿ there is no match.

Write `D_d(k)` for the number of ways in which `G_d` matches aᵏ. In JavaScript the first iteration of a plus may be empty, and every later one must advance. So, as generating functions,

    D_d(x) = D_{d−1}(x) · 1/(1 − (D_{d−1}(x) − 1)) = D_{d−1}(x) / (2 − D_{d−1}(x)).

From `D_0(x) = 1 + x`, induction gives `D_d(x) = (1 + x) / (1 − (2^d − 1)·x)`. That is, `D_d(0) = 1` and `D_d(k) = 2^d · (2^d − 1)^(k−1)` for k ≥ 1.

In the literal backtracking semantics every attempt at the suffix fails. An unanchored search therefore tries `b` exactly `Σ_{k=0..n} D_d(k) · (n − k + 1)` times. For positive lengths the exact-length count grows by a factor of 2^d − 1 per extra letter. The V8 column below gives elapsed times. The suffix counts are calculated from the semantics.

`bench/nested.py` checks this with a matcher that follows ECMAScript's RepeatMatcher, including the empty check. For every d ≤ 5 and n ≤ 6, its count of tests of `b` equals the formula. Its calls grow per letter by 3, 7, 15, 31, 63 for d = 2…6. For the same nesting over a body that cannot be empty (`a`), and for nested stars, the growth is only d. The cause is the empty first iteration of plus, which nearly doubles the number of choices at every level.

**V8.** `bench/v8_nested.js full` times `RegExp.prototype.test` on `G_d b`, after warming up the regex:

| d | Pattern | Length | Word | V8 | Tests of `b` (formula) | Linear engine |
|---|---|---|---|---|---|---|
| 2 | `(?:(?:a?)+)+b` | 13 | a²⁰ | 168 s | 1.05×10¹⁰ | accepts |
| 3 | `(?:(?:(?:a?)+)+)+b` | 18 | a¹¹ | 89 s | 3.08×10⁹ | accepts |
| 5 | `G_5 b` | 28 | a⁶ | 56 s | 9.78×10⁸ | rejects |
| 6 | `G_6 b` | 33 | a⁵ | 86 s | 1.04×10⁹ | rejects |
| 7 | `G_7 b` | 38 | a⁴ | 28 s | 2.66×10⁸ | rejects |
| 8 | `G_8 b` | 43 | a⁴ | 684 s (11.4 min) | 4.28×10⁹ | rejects |
| 9 | `G_9 b` | 48 | a³ | 28 s | 1.34×10⁸ | rejects |

The times follow the predicted growth. At d = 2 the short run (`results/v8_nested_quick.txt`) takes 2.1 s on a¹⁶, and 2.1 s × 3⁴ ≈ 170 s against 168 s on a²⁰. At d = 8 it takes 2.6 s on a³, and 2.6 s × 255 ≈ 663 s against 684 s on a⁴.

**Captured and lazy variants.** The failing searches below have the same number of semantic suffix trials. At d = 3 on a¹⁰ the archived V8 times were:

- 13.1 s without captures
- 16.5 s with captures, `(((a?)+)+)+b`
- 12.4 s with lazy plus
- 36.3 s with captures, lazy plus and the lookbehind `(?<=b)` in place of `b`

Spelled with capturing groups, the d = 2 pattern is `((a?)+)+b`, nine characters.

**V8's linear engine.** V8 also has an experimental linear-time engine, which Node.js enables only with `--enable-experimental-regexp-engine` and the `l` flag. `bench/v8_linear.js` shows that it accepts `G_d` only up to d = 4, and rejects deeper nestings as "Cannot be executed in linear time".

- **The same limit everywhere.** It holds with captures and with lazy plus, and Node.js 22.23.4 (V8 12.4) has the same limits.
- **Only plus over an empty-capable body.** Plus over `a`, and stars over `a` or `a?`, are accepted at every depth tested (up to 40).
- **Copying.** Below the limit, its time per letter doubles with each level: about 115, 250, 470 and 960 ns for d = 1 to 4. This is consistent with copying the body at every level.

**Other matchers.** `bitre.py` answers every row of the table in 30–60 µs, and handles d = 30 on 10,000 letters in about 0.1 s (`results/nested.txt`). RE2, an automata-based engine, answers in microseconds, so recognizing this language is easy in itself. But RE2 rejects lookahead and lookbehind, and its captures follow different rules from JavaScript's: on `ab`, `(?:(a)|b)*` gives group 1 = `a` in RE2 and `undefined` in JavaScript.

## Scope and limitations

- **Syntax.**
  - Supported:
    - characters, classes and `.`
    - `\d \w \s` and their negations
    - the anchors `^ $ \b \B`
    - capturing and non-capturing groups
    - choice
    - the greedy and lazy `?`, `*` and `+`
    - lookahead and lookbehind, of any width
    - the proposed atomic group `(?>...)` and possessive `?+`, `*+` and `++`
    - the flags `i`, `m` and `s`
  - Not supported:
    - backreferences
    - general counted repeats `{n,m}` (the parser identifies bounds spelled equivalently to optional, star or plus)
    - named groups
    - syntax that only JavaScript has: `\cX`, `\u{…}`, `\p{…}` and the `v` flag

  Unsupported flag letters, general counted repeats and backreferences raise `NotImplementedError` or a parser error. The Python parser accepts a different syntax from ECMAScript outside the documented fragment.
- **Parser.** The front end relies on `re._parser`, an internal module of CPython that may change between versions. For example, its parser rejects JavaScript’s empty classes `[]` and `[^]`. It also merges single-letter alternatives into a class and factors common prefixes out of alternatives. Both rewrites preserve JavaScript's answers, and m counts nodes after them.
- **Positions.** Positions are code points. On words without characters outside the Basic Multilingual Plane, they coincide with JavaScript's default mode, whose case folding `bitre.py` implements.
- **Timing.** Pure Python costs roughly 0.5 to 1 µs per cell. Short runs (`quick`) give noisier slopes, because fixed costs weigh more at small sizes.

## Reproducing

Times are for the machine above.

```sh
sh run_tests.sh                    # correctness, including all-start reporting
python3 bench/bench_batch.py       # all-start work counts and timings
python3 bench/bench_regelk.py     # RegElk's families: about 1.5 minutes
python3 bench/bench_lazy.py       # lazy variants and the control: about 1 minute
python3 bench/bench_split.py      # sweep and walk separately: about 2 minutes
python3 bench/depth.py            # CPython call cost against depth: a few seconds
python3 bench/v8_random.py        # random patterns that stall V8: about 20 seconds
python3 bench/nested.py           # the counting check, bitre and RE2: about 2 minutes
node --enable-experimental-regexp-engine bench/v8_nested.js        # V8, short sizes: about 20 seconds
node --enable-experimental-regexp-engine bench/v8_nested.js full   # V8, the sizes reported above: about 20 minutes
node --enable-experimental-regexp-engine bench/v8_linear.js       # V8's linear engine: a few seconds
```

`bench_regelk.py`, `bench_lazy.py` and `bench_split.py` accept `quick` for a short run that writes nothing. A full run overwrites its JSON file in `results/`. The text files in `results/` are the printed output of the runs reported here.
