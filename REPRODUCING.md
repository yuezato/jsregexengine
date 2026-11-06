# Reproducing the v59 results

From the repository root, with CPython 3.11+, Node.js 24+ and a POSIX shell, run

```sh
python3 reproduce.py quick
python3 reproduce.py full
```

The first command prints a table of work counts and a control that rereads overlapping suffixes. It ends with `PASS: quick`. The second also runs all §9 checks and the public Python suite, pins all five denominators in Table 4, and ends with `PASS: full`. A failed assertion or command exits with a nonzero status. Both commands run offline. This release was tested with CPython 3.12.14 and Node.js 24.22.1 (V8 13.6.233.17-node.58). Set `NODE` to select a different binary. A stock Node build supplies the inspector used to measure function calls.

## Implementation size

`paper/index/word_index.mjs` exports the complete Theorem 1.2 API: `compile`, `prepareMatches`, and `matchAllStarts`. It takes a pattern tree as input. Run `python3 review/size.py` to count that module and its transitive module dependencies. All the index sources, including validation, work counters, sparse reporting and the dense-output wrapper, are counted.

| File | Role | Physical lines | Code lines |
|---|---|---:|---:|
| `paper/index/pattern.mjs` | Number captures, set directions, cut regions, build graph templates and interpret primitive tests | 114 | 105 |
| `paper/index/layers.mjs` | Visit positions in matching order, mark viable ports and consult solved layers | 70 | 61 |
| `paper/index/word_index.mjs` | Select full and moving results, keep the last repeated body, read endpoints and captures | 139 | 130 |
| **Complete word index** | **Theorem 1.2** | **323** | **296** |

A code line is a physical line containing code: imports, declarations and brace-only lines count. We skip blank lines and lines beginning with a comment after whitespace. The three modules use only line comments and have no external dependencies. Pattern preparation, primitive handling and the annotations shared with the appendix walk are included. The number describes the word-space implementation. The packed Python data structures for Theorem 7.4 implement an additional guarantee.

## Timing

```sh
node paper/scaling.mjs --time
```

The expression tree, input word and any supplied exit set are inputs. Constructing them is outside every paper timer. Each measurement below times a fresh invocation of the stated task; separately measured medians need not add up.

| JSON field | First operation in the timer | Last operation in the timer |
|---|---|---|
| `fromAstMedianMs` | `compile(E)` on the supplied tree | After building the text index, write the dense output at every start |
| `indexMedianMs` | `prepareMatches(P,w)` on the prepared pattern | Return the queryable word index |
| `medianMs` | `matchAllStarts(P,w)` on the prepared pattern | Write every dense output row (original v59 field) |
| `bitsMedianMs` | `viableStarts(P,w)` on the prepared pattern | Return packed viability and moving bits (original v59 field) |

The `O(m)` preparation prepares the graph and is part of the from-AST benchmark. All timers that report matching with a prepared pattern still include text-dependent indexing. The time to run the `quick` or `full` verifier includes tests and process startup and is reported separately from matcher measurements. Python batch and single-match timers start after `Regex(source)`. Evaluating primitive tests on the word is inside the Python indexing time.

## Which result is being checked?

| Paper claim | Entry point | What to check |
|---|---|---|
| Theorem 1.2, build an index for every start | `paper/index/word_index.mjs`, `compile` then `prepareMatches` | Linear preparation of the input occurrence tree. The sum of region sizes is exactly m. All regions together have 2mN port positions and 2mN full/moving slots. |
| Theorem 1.2, query a previously unchosen start | `index.endpoint(x)`, `index.report(x, emit)` | One indexed endpoint lookup. At k defined captures, at most max(0, 2k−1) records visited, emitted in declaration order. The check reads the prebuilt index in reverse order. |
| Theorem 7.4, write dense answers at every start | `bitre.py`, `Regex.all_starts` | Python piecewise reporter, plus `paper/batch_reporting.mjs` checked against the word index on 23,238 rows. The latter is a functional reference and uses scanning color strings. The RAM workspace proof is in Appendix C. |
| Section 9, semantics | `paper/reference_semantics.mjs`, `paper/batch_reporting.mjs`, `tests/test_batch.py` | 521,904 standard rows, 18,864 atomic rows, 23,238 reference batch rows, 9,207 Python packed rows, 146,599 forest/stop-set pairs. Native V8 is used for the standard fragment. Atomic syntax uses the literal list evaluator as oracle. |
| Section 9, nested repetitions | `paper/scaling.mjs` | Reproduce all deterministic fields at all nine original sizes. Millisecond columns depend on the host. The experimental V8 admission probe is separate. |
| Public Python benchmarks | `bench/bench_batch.py`, `bench/bench_regelk.py` | The first runs all anchored starts; the second times a leftmost `exec`. Python `index(w).match_at(x)` replays the chosen match. |

## Where the product bound comes from

Let m be the number of occurrence-tree nodes and N the number of text positions, including the end. This is the input model of Problem 1.1. Primitive character or position tests cost one word-RAM operation or read an already prepared truth table. Captures are pairs of coordinates. The following four steps account for the work in the word index.

1. `compile` scans the tree once. Cutting at assertions and atomic groups assigns each node to one region. Each node contributes two ports and at most four fixed edges in `makeLayout`.
2. In `markLayer`, one position of one region is active. An atom tests its outgoing edge once. `mark` pushes a port upon its first visit only. Each popped port scans its predecessor list once. Summing over every region and position gives at most 2mN pops and 4mN fixed predecessor inspections. This implements Theorem 4.2.
3. The word index calls `selectCell` once per node and position. For a sequence with right factor `r`, the previously computed entry `r.moving[x]` already tells whether `r` can advance from `x`. A separate Boolean pass is needed by the packed walk; in the word matcher that independent check runs only when verification is requested. In `selectCell`, a sequence reads the selected entries of its children. A repeated body reads the already available tail at its strict successor and keeps only the final body. A mandatory stationary first body uses the tail computed at the current position. Each case reads or constructs a bounded number of records (Lemma 5.2, Theorems 6.1 and 7.3). The tables occupy O(mN) words.
4. Each capture record in `report` emits one defined group. Each branch record joins two nonempty capture subtrees. Lemma 7.1 bounds each declaration to one surviving visit. Corollary 7.2 gives O(1+k) visits/time per query, including failure and k=0. Initializing the dense output at every start costs at most N times the number of groups, at most mN.

The term “port positions” describes available table entries. The paper's original `stats.vertices` and `stats.cells` accumulate table dimensions. Independent execution counts are recorded by `review/work.mjs`: Node's precise-coverage API counts actual calls to `selectCell` in the word index, while wrapping the predecessor lists counts actual pops and edge inspections. All seven families vary the nesting depth (4, 8, 16) and N (129, 257, 513) independently. Every endpoint and emitted span is checked against a formula for that family. The atomic case permits only the final text position; the sparse choice also has a successful start with no defined captures; the sibling-capture case attains exactly 2k−1 visits when k>0.

```sh
node review/work.mjs --rows       # every individual work count
node paper/scaling.mjs --time    # published grid plus host-dependent median milliseconds
```

For the nested nullable lazy-plus family of §9 the paper grid includes the following rows. The driver prints and compares all nine archived rows. Each AST has m=2+2d nodes.

| Depth d | m | N | mN | Port positions | Full/moving slots |
|---:|---:|---:|---:|---:|---:|
| 4 | 10 | 129 | 1,290 | 2,580 | 2,580 |
| 8 | 18 | 257 | 4,626 | 9,252 | 9,252 |
| 16 | 34 | 513 | 17,442 | 34,884 | 34,884 |

The operation counts exercise the explanation in Steps 1–4. Finite measurements cover the listed inputs. The bound for every pattern and input follows from the bounds on the loops and the cited proofs.

## Why all-start sharing matters

On n copies of `a`, the pattern `(?=(a+))a` captures the suffix [x,n) at each x<n and consumes just its first letter. For this family the Python batch fills two moving columns per node (m=6), for exactly 2mN entries. Calling the single-start walk at every position instead makes n(n+11)/2 source visits. These counts use different units; the growth of each count is what matters. Both methods return identical rows.

| N | Batch column entries | Replay source visits |
|---:|---:|---:|
| 65 | 780 | 2,400 |
| 129 | 1,548 | 8,896 |
| 257 | 3,084 | 34,176 |
| 513 | 6,156 | 133,888 |

The full run checks the archived structural columns of all 36 Python batch instances (ahead, behind, atomic). For a single expression occurrence the atomic-region pass can construct at most one column, and each of the two piece passes can construct at most one more. Thus at most 3mN moving-column entries are built. This counter covers one phase. The proof also charges two at-most-linear visits through each piece per start, all outgoing piece boundaries once per sweep, and linear-time construction of each encoded column and stopping forest. See Theorem 7.4 and Appendix C. Implementation RSS includes interpreter objects, syntax metadata, input and delivered output; it does not measure the workspace in that theorem.

## Input and reproduction boundaries

* The paper starts with an occurrence tree and matching units; `paper/all_starts.mjs` is the matching core for that input. The public Python examples start from a CPython-compatible regex source string. Python uses code-point positions. The public README lists flags and concrete syntax accepted by its front end. In particular, the JavaScript source spellings `[]` and `[^]` are rejected by this parser. Very deep sources may also hit CPython's recursion limit.
* `paper/bit_columns.mjs` uses scans to make color lookups easy to inspect. Its tests establish agreement of results. `bitcolumns.py` implements packed lookup and explicit/coded maps. Appendix C supplies the asymptotic bit-space argument. The quick counters and timings do not measure peak packed workspace.
* Node's optional `l` flag is engine-specific. `full` checks the historical admission ranges on Node 24.22.1. On other supported versions it prints the observed ranges. The optional Unicode-fold conformance probe and historical long-running V8 stress tests have their own commands in the corresponding READMEs; they are outside the Table 4 and work-count checks.

## Provenance

The public Python baseline is Git tree `45ea3600af76cc7ee76a33781e9246029f1b4bb3`, commit `aaa49bbffd731722e7ab4ef82f77acfb15ac5edd`. Its 42 tracked files have the same contents and executable attributes as the preceding upload ZIP (SHA-256 `ddc40ee29ca0cd9ea36c275121cca22063f6e05974ccdf9fd6836837099f20cc`). The original paper reproduction ZIP (SHA-256 `35d5cdcf8f4ce5c5a9450e5bed4c4b7dab57a5f7d0d467b3696dd7575375c110`) contains the unchanged v59 `checks/`. This edition reorganizes the JavaScript sources, uses stored moving entries directly in the word index, and isolates the Python source parser. The revised paper’s anonymous supplement distributes the same JavaScript index and Python engine under index/ and packed/, respectively. The literal semantics, expected rows, archived work counts and all timing data under `results/` are the original ones. The per-file fingerprints under `review/paper.sha256` describe this modular edition. The optional `bench/v8_timed.js` random-timeout probe now constructs and warms its V8 expressions before timing. Historical measurements used the earlier probe.
