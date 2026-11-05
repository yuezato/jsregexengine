"""Random patterns for differential testing, built with the constructors of semantics.py.

general(rng, depth)   trees over a, b, [ab], the empty pattern, failure and the four anchors,
                      combined by sequence, choice, capture, the six quantifiers and the four
                      lookarounds.
targeted(rng, depth)  biased towards the delicate cases: plus (often lazy) over nullable bodies,
                      chains of nested quantifiers, empty captures, and captures inside
                      lookarounds inside repetition.
random_pattern(rng)   one of the two, as all tests use it.
Neither produces atomic groups, which bitre.py does not support.
"""
from semantics import chr_, eps, fail, pos, seq, alt, cap, quant, look

LETTERS = [set('a'), set('b'), set('ab')]
ANCHORS = ['^', '$', 'b', 'B']


def general(rng, depth):
    def leaf():
        r = rng.random()
        if r < 0.55: return chr_(rng.choice(LETTERS))
        if r < 0.70: return eps()
        if r < 0.75: return fail()
        return pos(rng.choice(ANCHORS))

    def go(dp):
        if dp <= 0 or rng.random() < 0.18:
            return leaf()
        r = rng.random()
        if r < 0.24: return seq(go(dp - 1), go(dp - 1))
        if r < 0.40: return alt(go(dp - 1), go(dp - 1))
        if r < 0.52: return cap(go(dp - 1))
        if r < 0.82: return quant(rng.choice(['opt', 'star', 'plus', 'plus', 'star']), rng.random() < 0.5, go(dp - 1))
        if r < 0.94: return look(rng.choice('fb'), rng.random() < 0.6, go(dp - 1))
        return cap(go(dp - 1))
    return go(depth)


def targeted(rng, depth):
    if depth <= 0 or rng.random() < 0.12:
        r = rng.random()
        if r < 0.5: return chr_(rng.choice(LETTERS))
        if r < 0.7: return eps()
        if r < 0.8: return cap(eps())
        return pos(rng.choice(ANCHORS))
    r = rng.random()
    if r < 0.35:
        kind = rng.choice(['plus', 'plus', 'plus', 'star', 'opt'])
        return quant(kind, rng.random() < 0.4, targeted(rng, depth - 1))
    if r < 0.50: return alt(targeted(rng, depth - 1), targeted(rng, depth - 1))
    if r < 0.62: return seq(targeted(rng, depth - 1), targeted(rng, depth - 1))
    if r < 0.76: return cap(targeted(rng, depth - 1))
    if r < 0.92:
        body = cap(targeted(rng, depth - 1)) if rng.random() < 0.6 else targeted(rng, depth - 1)
        return look(rng.choice('fb'), rng.random() < 0.7, body)
    return cap(targeted(rng, depth - 1))


def random_pattern(rng):
    return targeted(rng, rng.randint(3, 7)) if rng.random() < 0.6 else general(rng, 5)
