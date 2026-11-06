"""Parse Python-compatible regex source into the occurrence tree used by bitre."""
import sys
import re._parser as sre
from re import _constants as K
from functools import lru_cache

CHAR, EPS, FAIL, ANCHOR, CAP, ALT, SEQ, QUANT, LOOK, ATOMIC = range(10)
OPT, STAR, PLUS = range(3)
LT = '\n\r\u2028\u2029'
WS = '\t\v\f \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000\ufeff' + LT
FLAGBITS = (('i', 2), ('m', 8), ('s', 16))
ANCHORS = (K.AT_BEGINNING, K.AT_END, K.AT_BOUNDARY, K.AT_NON_BOUNDARY)
isword = lambda c: c.isascii() and (c.isalnum() or c == '_')
CATS = {K.CATEGORY_DIGIT: lambda c: '0' <= c <= '9', K.CATEGORY_WORD: isword, K.CATEGORY_SPACE: lambda c: c in WS}
CATS.update({K.CATEGORY_NOT_DIGIT: lambda c: not ('0' <= c <= '9'),
             K.CATEGORY_NOT_WORD: lambda c: not isword(c), K.CATEGORY_NOT_SPACE: lambda c: c not in WS})


def canon(c):  # Canonicalize of ECMAScript without u/v
    u = c.upper()
    return c if len(u) != 1 or (ord(c) >= 128 and ord(u) < 128) else u


@lru_cache(maxsize=1)
def _nontrivial_case_classes():
    # Inverse images of legacy Canonicalize. Several letters (e.g. both
    # lowercase sigmas) can have the same uppercase representative.
    groups = {}
    for code in range(128, sys.maxunicode + 1):
        c = chr(code)
        key = canon(c)
        if c != key:
            groups.setdefault(key, []).append(c)
    for key, group in groups.items():
        if canon(key) == key:
            group.append(key)
    return groups


def case_class(c):
    if c.isascii():  # legacy mode never folds a non-ASCII letter to ASCII
        return (c.upper(), c.lower()) if c.isalpha() else (c,)
    return _nontrivial_case_classes().get(canon(c), (c,))


class ParsedPattern:
    def __init__(self, source, flags=''):
        self.kind, self.kids, self.arg = [], [], []
        flags = frozenset(flags)
        unsupported = flags - {'i', 'm', 's'}
        if unsupported:
            raise NotImplementedError('unsupported regex flags: ' + ''.join(sorted(unsupported)))
        tree = sre.parse(source, 0)
        self.ngroups = tree.state.groups - 1
        self.root = self._seq(list(tree), flags)

    # ---------------------------------------------------------------- syntax tree
    def _new(self, kind, kids=(), arg=None):
        self.kind.append(kind); self.kids.append(list(kids)); self.arg.append(arg)
        return len(self.kind) - 1

    def _seq(self, items, fl):
        nodes = [self._item(op, av, fl) for op, av in items]
        r = nodes.pop() if nodes else self._new(EPS)
        for v in reversed(nodes):
            r = self._new(SEQ, (v, r))
        return r

    def _item(self, op, av, fl):
        if op in (K.LITERAL, K.NOT_LITERAL, K.ANY, K.IN):
            return self._new(CHAR, (), self._charset(op, av, fl))
        if op is K.AT and av in ANCHORS:
            return self._new(ANCHOR, (), (av, 'm' in fl))
        if op is K.FAILURE:
            return self._new(FAIL)
        if op is K.SUBPATTERN:
            g, add, rem, p = av
            fl = (fl | {f for f, b in FLAGBITS if add & b}) - {f for f, b in FLAGBITS if rem & b}
            s = self._seq(list(p), fl)
            return s if g is None else self._new(CAP, (s,), g)
        if op is K.BRANCH:
            alts = [self._seq(list(a), fl) for a in av[1]]
            r = alts.pop()
            for a in reversed(alts):
                r = self._new(ALT, (a, r))
            return r
        if op is K.ATOMIC_GROUP:
            return self._new(ATOMIC, (self._seq(list(av), fl),))
        if op in (K.MAX_REPEAT, K.MIN_REPEAT, K.POSSESSIVE_REPEAT):
            lo, hi, p = av
            kind = {(0, 1): OPT, (0, K.MAXREPEAT): STAR, (1, K.MAXREPEAT): PLUS}.get((lo, hi))
            if kind is None:
                raise NotImplementedError('counted repeat {%d,%s}' % (lo, hi))
            q = self._new(QUANT, (self._seq(list(p), fl),), (kind, op is not K.MIN_REPEAT))
            return self._new(ATOMIC, (q,)) if op is K.POSSESSIVE_REPEAT else q
        if op in (K.ASSERT, K.ASSERT_NOT):
            d, p = av
            return self._new(LOOK, (self._seq(list(p), fl),), (d == 1, op is K.ASSERT))
        raise NotImplementedError(str(op))

    def _charset(self, op, av, fl):
        if op is K.ANY:
            return ('any', 's' in fl)
        if op in (K.LITERAL, K.NOT_LITERAL):
            items, neg = ((K.LITERAL, av),), op is K.NOT_LITERAL
        else:
            neg = bool(av) and av[0][0] is K.NEGATE
            items = tuple(av[1:] if neg else av)
        return ('set', items, neg, 'i' in fl)

    @staticmethod
    def _member(spec, c):
        if spec[0] == 'any':
            return spec[1] or c not in LT
        _, items, neg, ic = spec
        cands = case_class(c) if ic else (c,)
        hit = any((op is K.LITERAL and ord(d) == a) or (op is K.RANGE and a[0] <= ord(d) <= a[1])
                  or (op is K.CATEGORY and CATS[a](d)) for op, a in items for d in cands)
        return hit != neg
