"""bitre against both reference semantics (reference/semantics.py), at every start of the
word and for a random set B of allowed final positions.
Usage: python3 tests/test_reference.py SEED COUNT MAXLEN"""
import random, sys
import common
import semantics as S
from patterns import random_pattern
from bitre import Regex, run


def main(seed, count, maxlen):
    rng = random.Random(seed)
    done = skipped = bad_bitre = bad_batch = bad_spec = starts = matches = 0
    look = behind = lazy = 0
    while done < count:
        t = random_pattern(rng); src = S.to_js(t); G = S.finalize(t)
        n = rng.randint(0, maxlen); w = ''.join(rng.choice('ab') for _ in range(n)); I = range(n + 1)
        r = rng.random()
        B = set(I) if r < 0.4 else ({n} if r < 0.55 else {i for i in I if rng.random() < 0.5})
        try:
            naive = [None if a is None else (a[0], S.caps_from_set(a[1], G)) for a in S.naive_answers(t, w, B)]
        except S.TooBig:                       # too many paths to enumerate: skip the pattern
            skipped += 1; continue
        spec = S.spec_answers(t, w, B, G)
        rx = Regex(src)
        batch = [None if m is None else (m[1], tuple(m[2])) for m in rx.all_starts(w, B)]
        if batch != naive:
            bad_batch += 1
            if bad_batch <= 3:
                print('BATCH MISMATCH', src, repr(w), sorted(B), naive, batch)
        got = [None if m is None else (m[1], tuple(m[2])) for m in map(rx.match_at, I)]
        done += 1; starts += n + 1; matches += sum(a is not None for a in naive)
        look += '(?=' in src or '(?!' in src or '(?<' in src
        behind += '(?<' in src
        lazy += '+?' in src
        if spec != naive:
            bad_spec += 1
        if got != naive:
            bad_bitre += 1
            if bad_bitre <= 3:
                print('MISMATCH', src, repr(w), sorted(B), '\n  reference', naive, '\n  bitre    ', got)
    print('reference: %d patterns (%d skipped as too large to enumerate), %d starts, %d matches;'
          ' lookaround in %.0f%%, lookbehind in %.0f%%, lazy plus in %.0f%%'
          % (done, skipped, starts, matches, 100 * look / done, 100 * behind / done, 100 * lazy / done))
    print('reference: list semantics vs ECMAScript matcher: %d mismatches; bitre vs list semantics: %d mismatches'
          % (bad_spec, bad_bitre))
    print("reference: offline all-start reporter vs list semantics: %d mismatches" % bad_batch)
    return bad_spec + bad_bitre + bad_batch


if __name__ == '__main__':
    sys.exit(1 if run(main, int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])) else 0)
