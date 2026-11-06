# Matching at every start: anonymous implementation and checks

From this directory run the following with Python 3.8+ and Node.js 24+.
The examples use Unicode string properties and scoped pattern modifiers.
The other JavaScript checks need only Node.js 18+. No external Python or JavaScript packages,
network access, or datasets are required.

    python3 ordered_rows.py
    python3 quantifier_chains.py
    node reference_semantics.mjs
    node batch_reporting.mjs
    node table_clients.mjs
    node scaling.mjs
    node examples.mjs
    node native_chains.mjs

Each script exits with a nonzero status on a mismatch and prints counts
on success. The scripts cover different claims:

- ordered_rows.py compares ordered substitution and its two queries
  with the literal product. It checks observable row summaries on
  three-vertex graphs, including the exact number of endpoint-observation classes. For repetition it compares both DFS orders,
  their whole discovery paths, the pruned first-child path for each allowed set,
  and the full and advancing choices of star
  and plus with enumerated paths. It independently recovers the ordinary
  tail endpoint and final edge from one nearest-marked-ancestor computation that marks the children of stops. It tests every terminal set on all
  10,400 ranked forward body tables on four positions. The differing entrances for optional, star and plus, and the criteria for erasing priority, are checked against
  the literal greedy and lazy choices for all 166,400 four-position body/domain
  pairs. A further 273 labelled tables on three positions admit repeated offers
  and give another 2,184 such pairs.
- quantifier_chains.py checks all 1,554 direct chains of depths 1–4 on
  273 three-position bodies (424,242 comparisons). It checks the 81 products
  of the nine normal forms and both star expansions on these bodies and all
  10,400 ranked four-position bodies (885,859 comparisons). The comparison
  keeps the first occurrence of each distinct endpoint–value pair. The script
  also checks the nine endpoint orders on a two-letter word and the minimum
  number of fixed exit-set tests that separate them. It separately checks all
  14 instantiated local laws by unfolding raw lists before removing duplicates.
- index/word_index.mjs, index/pattern.mjs and index/layers.mjs implement Theorem 1.2.
  The all_starts.mjs entry point also exports the separate bit-space walk for the paper checks.
  Together the modules support region graphs,
  the first and advancing tables, sparse repetition and direct capture readout.
  Each region is swept one position at a time; only one layer of stationary
  graph edges is closed per position. viableStarts(program, units, allowed)
  returns two packed bit vectors for success and advancing success in the
  fragment with no atomic groups, including nested assertions. hasBit(bits, x)
  reads a vector entry. prepareWalk(program, units, allowed) constructs a packed
  index for every pattern without atomic groups. Its read(x) returns null or a
  row and a source-visit count. Capturing lookarounds are replayed once at each
  surviving request. program.localCaptures indicates that no capture inside
  an assertion can reach the output.
  read(x) also bounds source visits per region by charging once for every
  occurrence, plus max(width-1, 0) more for each occurrence strictly inside
  a star or plus in that region.
  compile(pattern) prepares an occurrence tree independently of the word.
  prepareMatches(program, units, allowed) builds the word-space index.
  endpoint(x) returns the selected end or null. report(x, emit) returns the
  same value and calls emit(slot, lo, hi) only for defined captures, in
  opening-parenthesis order. The implementation's slot indices start at zero.
  For k>0 reported spans and h defined groups with no defined descendant,
  the increment in stats.traceVisits is exactly k+h-1. It is zero when k=0.
  matchAllStarts(program, units, allowed) returns one row per start and counters.
  A successful row is [end, spans], with null for an undefined capture.
  The optional allowed argument is a boolean or 0/1 vector by position.
  units may be a UTF-16 string, an array of matching units, or a length/unitAt view. As in the paper,
  character and position tests are pure, supplied predicates.
- reference_semantics.mjs independently evaluates the ordered lists on small
  pattern trees. Its deterministic cases consist
  of 12 seeds, 360 quantifier/context cases, 288 pair cases, and four examples.
  There are 144 cases containing lookbehind and 98 containing a lazy plus
  whose body has a stationary success somewhere on the test words in its
  assigned direction. These overlapping counts are taken per pattern and
  printed by the script. The 16 words are all binary words of lengths 0–3
  and aaab. Across these 664 cases, 16 words, every subset of exits
  and every start, the prototype, list evaluator and sticky native engine
  agree on 521,904 complete rows. The two packed viability bits are independently
  compared with list membership on those rows (1,043,808 bit tests). The
  packed walk also agrees on all 521,904 rows. Source visits obey the single-
  match bound and, where applicable, the stronger width bound (332,478 rows).
  Sparse reports are checked against the selected rows in both the standard
  and atomic tests, together with group order and the exact trace-visit count.
  The nested-prefix example checks the exact number of distinct spans.
  The full matcher checks internal marks against item presence. Seven
  whole success lists are compared, including duplicate
  offers with equal endpoints. Six separate cases exercise atomic choice,
  inherited direction and the three possessive quantifiers. Another 18,864
  rows compare the prototype with the list evaluator on nested atomic cases.
  Additional checks exercise jumps of varying length and tag invocations in
  literal winning derivations for both size examples. The tests exercise
  deferred reconstruction in the nested lookahead family and count visits
  for overlapping captured suffixes in (?=(a+))a. Repeat-free lookahead
  bodies with 4, 16 and 64 explicit letters test overlapping widths against
  the stronger per-region bound.
- batch_reporting.mjs checks the all-start bit-space construction. It computes
  each region's Boolean decisions from the child regions, codes moving endpoints
  and last-body entrances, cuts the syntax into square-root-sized pieces, and rebuilds
  one piece at a time. It compares every output cell with the word-space matcher
  on 23,238 rows from 1,890 cases (five fixed patterns at all tested exit sets
  and 1,300 generated instances with a fixed seed). The cases include nested
  assertions in both directions, atomic groups, nullable repeats and failed
  matches. It uses both explicit and coded columns where the proof prescribes
  them and also checks alternate piece sizes. The cuts are computed by a
  larger-child-first postorder. Independently it checks the color code, preimages and terminal map
  on all 146,599 forward-forest/stop-set pairs through seven positions. The
  code is checked on all forward partial maps through six positions, together
  with their backward reflections, including fixed points and touching
  intervals. The two stopping inequalities are checked for arbitrary partial
  maps, stopping sets and cuts through four states, including cycles. The
  reference color strings in bit_columns.mjs use ordinary arrays and scans.
  These are functional checks. The time and bit-space guarantees for the packed
  representations, including rank/select, are proved in Appendix C.
- table_clients.mjs checks both the full root table and the packed walk against
  the built-in nonsticky global match iterator (960 cases) and the built-in regex separator (1,920
  cases). Cases include Unicode boundaries, lone surrogates, captures from
  assertions, empty matches and limits. A packed prefix index converts matcher
  positions to UTF-16 offsets. Global initial cursors are unit-aligned.
- scaling.mjs counts graph vertices, edges, query cells, trace visits and
  emitted slots and the two packed output vectors on the nine nested-capture instances in the paper. Use
  node scaling.mjs --time to add elapsed time. The expression tree is already built.
  fromAstMedianMs includes pattern preparation, text indexing and all dense rows.
  indexMedianMs isolates text indexing after pattern preparation. Each size has five warm-ups
  and 11 timed runs for each timed routine; the script reports their median in milliseconds.
  scaling-measurements.jsonl records a run on the structural family
  (Node.js 24.22.1 on AMD EPYC 9V74). Timings vary by host and process.
- examples.mjs checks 117 anchored cases, including the opening nullable lazy
  plus, capture rollback, both signs of lookbehind and the two lookaheads with
  equal matching intervals and different captures. For the worked example
  it independently checks the body offers, the feasible suffix and tail
  positions, both body choices, all four starting positions at both
  priorities and the effect of removing the suffix. It also checks both moving-product
  examples, the overlapping opening captures, the two output trees, and the mixed-priority example. Four cases contrast native counted
  repetition with literal expansion, for progress and for capture reset. Backreference contexts
  distinguish prefixes that agree on every allowed exit set. Twelve more
  cases check Unicode string classes, the empty-string member, fallback in
  both directions, UTF-16 span offsets and scoped modifiers.
- native_chains.mjs compares the original and normalized expressions
  on a native JavaScript engine in 157,380 cases. It checks both the
  endpoint and the half-open span or undefined value of each capture. A
  further 14,560 comparisons place a suffix that tests group 1 by backreference
  after the original or normalized chain. On the nine normal forms it separately
  checks all 36 native matches with the four concrete suffixes of the paper.

To repeat the V8 admission comparison in the paper, run
`node --enable-experimental-regexp-engine v8_admission.mjs`. This V8-specific
probe tries the capturing lazy-plus family over both a? and a at depths 1–10.
It reports the Node and V8 versions and the depths accepted and rejected by
the experimental flag. With Node.js 24.22.1 the accepted depths were 1–4
and 1–10, respectively.

A separate conformance probe checks the single-code-point string member in
`/[\q{a}]/iv` on `"A"` and fallback to it inside a local modifier. The
standard requires success in both cases. Run `node examples.mjs --unicode-fold`
or `bun examples.mjs --unicode-fold`. Node.js 24.22.1 (V8 13.6.233.17-node.58)
missed the match in both cases. Bun 1.4.4 (JavaScriptCore) agreed with both
specified results. This probe deliberately exits on a disagreement.
[V8 change for one-character class strings](https://chromium.googlesource.com/v8/v8/+/bca5c4eb1db2dc36cffd133eb5c9d2ce8b54f1f6).

The comparisons against Node.js use standardized ECMAScript syntax. The
reference evaluator handles atomic groups directly and represents possessive
quantifiers by their expansion into atomic groups. The fragment-wide prototype operates on prepared syntax and text units. The
reported measurements are on a controlled family and do not compare production
engine throughput. The correspondence and the running-time bound are proved
in the manuscript.
