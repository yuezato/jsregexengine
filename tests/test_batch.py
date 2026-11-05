"""All starts with atomic commitments, verified against both semantic oracles."""
from itertools import product
from random import Random
import common
import semantics as S
from patterns import random_pattern
from bitre import Regex, run
from bitcolumns import ceil_sqrt


def check(term, word, exits):
    src = S.to_js(term)
    groups = S.finalize(term)
    reference = [None if r is None else (x, r[0], list(S.caps_from_set(r[1], groups)))
                 for x, r in enumerate(S.naive_answers(term, word, exits))]
    spec = [None if r is None else (x, r[0], list(r[1]))
            for x, r in enumerate(S.spec_answers(term, word, exits, groups))]
    rx = Regex(src)
    got = rx.all_starts(word, exits)
    assert got == reference == spec, (src, word, exits, got, reference, spec)
    assert [rx.match_at(x) for x in range(len(word)+1)] == reference
    if exits == set(range(len(word)+1)):
        cursor = 0
        global_rows = []
        for row in reference:
            if row is not None and row[0] >= cursor:
                global_rows.append(row)
                cursor = row[1] if row[0] != row[1] else row[1] + 1
        assert rx.match_all(word) == global_rows
        assert rx.exec(word) == next((row for row in reference if row is not None), None)
    b = ceil_sqrt(len(rx.kind))
    assert len(rx.pieces) <= 1 + len(rx.kind)//b
    assert all(1 <= len(nodes) <= 2*b-1 for _, nodes, _ in rx.pieces)
    return len(reference)


def random_atomic(rng):
    term = random_pattern(rng)
    inserted = False

    def wrap(v):
        nonlocal inserted
        v.kids = [wrap(c) for c in v.kids]
        if rng.randrange(4) == 0:
            inserted = True
            return S.atomic(v)
        return v

    term = wrap(term)
    return term if inserted else S.atomic(term)


def main():
    a, b = S.chr_({'a'}), S.chr_({'b'})
    captured = S.quant('plus', True, S.cap(a))
    cases = [
        S.seq(S.atomic(S.alt(a, S.seq(a, b))), b),
        S.seq(S.atomic(S.alt(S.seq(a, b), a)), b),
        S.atomic(S.quant('plus', False, S.alt(S.cap(S.eps()), a))),
        S.quant('star', True, S.atomic(S.alt(S.cap(a), b))),
        S.look('b', True, S.cap(S.atomic(captured))),
        S.seq(S.look('f', False, S.atomic(S.cap(a))), b),
        S.seq(S.look('f', True, S.atomic(S.look('b', True, captured))), S.alt(a, S.eps())),
    ]
    rows = 0
    for term in cases:
        for word in ('', 'a', 'aa', 'ab', 'aaa', 'aba', 'aab'):
            for mask in range(1 << (len(word)+1)):
                rows += check(term, word, {x for x in range(len(word)+1) if mask & (1 << x)})

    rng = Random(260)
    done = 0
    while done < 1500:
        term = random_atomic(rng)
        word = ''.join(rng.choice('ab') for _ in range(rng.randrange(9)))
        exits = {x for x in range(len(word)+1) if rng.randrange(3)}
        try:
            rows += check(term, word, exits)
        except S.TooBig:
            continue
        done += 1

    for greedy, possessive in [('?', '?+'), ('*', '*+'), ('+', '++')]:
        rx = Regex('((?:()|a)' + possessive + ')b')
        expanded = Regex('((?>(?:()|a)' + greedy + '))b')
        for n in range(5):
            for letters in product('ab', repeat=n):
                word = ''.join(letters)
                assert rx.all_starts(word) == expanded.all_starts(word)
    assert Regex('a*+a').all_starts('a') == [None, None]
    assert Regex('a*a').all_starts('a')[0][1] == 1

    class WithoutReplay(Regex):
        def _walk(self, *args):
            raise AssertionError('offline reporters must not replay per start')

    rx = WithoutReplay(r'(?=(a+))a')
    for n in [64, 0, 129]:
        word = 'a' * n
        expected = [(x, x+1, [None, (x, n)]) for x in range(n)]
        assert rx.all_starts(word) == expected + [None]
        assert rx.match_all(word) == expected
        assert rx.all_starts(word, []) == [None] * (n+1)
    # The same capture inside a lookbehind can receive a forward jump, an
    # unchanged entrance and a backward jump from different original starts.
    word = 'abb' * 40
    groups = 5
    rx = WithoutReplay('a?(?<=' + '(' * groups + ')' * groups + 'b*)')
    for x, row in enumerate(rx.all_starts(word)):
        end = x + (word[x:x+1] == 'a')
        y = end
        while y and word[y-1] == 'b':
            y -= 1
        assert row == (x, end, [None] + [(y, y)] * groups)
    # Conventional syntax metadata must also handle large m and a tiny N.
    assert WithoutReplay('(a?)' + 'a?' * 1500).all_starts('') == [(0, 0, [None, (0, 0)])]
    # Global empty matches advance once and can include the end of the word.
    assert WithoutReplay('(?:)').match_all('ab') == [(i, i, [None]) for i in range(3)]
    print('batch: %d anchored atomic rows against two oracles; possessive and overlapping cases passed' % rows)


if __name__ == '__main__':
    run(main)
