# Python front end and packed reporter

The first reviewer entry point is [the graph demo](../README.md#generate-the-comparison-graphs).
This document describes the separate Python API and its concrete syntax. Run commands from the repository root.

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

## Reading the pattern examples

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

## How the packed reporter follows the paper

| Step | Implementation | Manuscript |
|---|---|---|
| Prepare the pattern | `Regex._prepare` cuts at assertions and atomic groups, preserving the local matching direction. `_partition` fixes pieces of size at most `2 ceil(sqrt(m)) - 1` before reading the word. | Sections 4, 8.1 and Appendix C.4 |
| Compute viability | `_sweep` stores the entrance and exit marks, moving success and preferred stationary success in one byte per node and position. Atomic children are solved with all local exits allowed. A stationary commitment is a same-layer edge. A jump reads its chosen destination's already-computed exit mark. | Sections 4–7 and Appendix C.3 |
| Select an endpoint | `_split` chooses full or moving results in a sequence. `Tail` follows the repeated body's first viable advances to the last body before the stop. A nullable mandatory first body supplies the captures when no advancing body supersedes it. | Sections 5–6 and Appendices C.1–C.3 |
| Write captures | `_report` retains piece-root columns. In top-down order it rebuilds each piece and follows only the surviving visits for every selected start. Signed requests are filled in two sweeps, so nested lookbehind can move a capture outside the overall match. | Theorem 8.1 and Appendix C.4 |
| Walk a single match | `_walk` and `_collect` replay a selected path with timestamped capture resets. This remains useful for a single query and the original experiments. | Appendix B.4 |

For a prepared tree of `m` syntax occurrences and `N = len(w)+1`, with constant-cost primitive tests or supplied predicate tables, the batch takes `O(mN)` word-RAM operations. The benchmark constructs the pattern before timing. See the [timing boundaries](../REPRODUCING.md#timing). The capture arrays are delivered output. There are `O(sqrt(m))` simultaneously live columns in the piece passes. `bitcolumns.py` uses byte-rounded unsigned arrays for explicit positions. When positions exceed the column's budget, it colors half-open source–target intervals and stores fixed points separately. To look up a color, it stably partitions by digits of radix `O(sqrt(m))`. There are a constant number of digits. Packed bitmaps with prefix counts and select directories route a position through these partitions in constant time. Coded terminal maps traverse parent and inverse links without a word-length recursion stack.

Theorem 8.1 gives `O(mN)` workspace **bits** in the manuscript’s RAM model, excluding input, supplied primitive tests and delivered output. The Python prototype also uses conventional syntax descriptors, objects and byte-rounded buffers. Its process RSS includes the interpreter and allocator. The batch API writes all rows once. `match_at` performs a walk when called later.

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
- **Timing.** Parsing and tree construction precede the timers. The general CPython parser is not covered by the product-time matching theorem; it may take superlinear time and has a recursion limit. Historical timings are in [HISTORICAL.md](HISTORICAL.md).
