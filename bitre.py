"""All-start JavaScript regex matching with captures, in the bit-table form of the paper.

Front end: Python's own regex parser (re._parser), whose syntax agrees with JavaScript
on the fragment used here.  Back end: one reverse sweep per region stores four bits per
occurrence and position (A entrance mark, C exit mark, D moving success, Z stationary
preferred result); a walk over these bits reconstructs one match, and timestamps decide
which captures survive (the clocks of Barrière and Pit-Claudel).  Positions are code
points.  Atomic groups, backreferences and counted repeats raise NotImplementedError.
"""
import sys
import re._parser as sre
from re import _constants as K

CHAR, EPS, FAIL, ANCHOR, CAP, ALT, SEQ, QUANT, LOOK = range(9)
OPT, STAR, PLUS = range(3)
ABIT, CBIT, DBIT, ZBIT = 1, 2, 4, 8
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


class Regex:
    def __init__(self, source, flags=''):
        self.kind, self.kids, self.arg = [], [], []
        tree = sre.parse(source, 0)
        self.ngroups = tree.state.groups - 1
        self.root = self._seq(list(tree), frozenset(flags))
        self._prepare()

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
        if op in (K.MAX_REPEAT, K.MIN_REPEAT):
            lo, hi, p = av
            kind = {(0, 1): OPT, (0, K.MAXREPEAT): STAR, (1, K.MAXREPEAT): PLUS}.get((lo, hi))
            if kind is None:
                raise NotImplementedError('counted repeat {%d,%s}' % (lo, hi))
            return self._new(QUANT, (self._seq(list(p), fl),), (kind, op is K.MAX_REPEAT))
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
        cands = {c} | ({canon(c)} | {x for x in (c.lower(), c.upper()) if len(x) == 1} if ic else set())
        hit = any((op is K.LITERAL and ord(d) == a) or (op is K.RANGE and a[0] <= ord(d) <= a[1])
                  or (op is K.CATEGORY and CATS[a](d)) for op, a in items for d in cands)
        return hit != neg

    # ---------------------------------------------------------------- regions and static graph
    def _prepare(self):
        n = len(self.kind)
        self.fwd, self.regions = [True] * n, []

        def collect(v, R, fwd):
            self.fwd[v] = fwd
            if self.kind[v] == LOOK:
                make_region(self.kids[v][0], self.arg[v][0])
            else:
                for k in self.kids[v]:
                    collect(k, R, fwd)
            R['nodes'].append(v)

        def make_region(root, fwd):
            R = {'root': root, 'fwd': fwd, 'nodes': []}
            collect(root, R, fwd)
            self.regions.append(R)                 # child regions precede their parents
            return R

        self.top = make_region(self.root, True)
        for R in self.regions:
            self._static_graph(R)
        exports = [False] * n                      # children have smaller ids than their parents
        for v in range(n):
            k = self.kind[v]
            exports[v] = k == CAP or (k == LOOK and self.arg[v][1] and exports[self.kids[v][0]]) \
                or (k not in (CAP, LOOK) and any(exports[c] for c in self.kids[v]))
        self.has_caps = [self.kind[v] == LOOK and exports[v] for v in range(n)]   # positive, capturing

    def _static_graph(self, R):
        nodes = R['nodes']; li = R['li'] = {v: i for i, v in enumerate(nodes)}
        rev = R['rev'] = [[] for _ in range(2 * len(nodes))]
        R['cond'], R['chars'] = {}, []
        for v in nodes:
            a = 2 * li[v]; b = a + 1; k = self.kind[v]
            ks = [] if k == LOOK else [2 * li[c] for c in self.kids[v]]
            if k == EPS:
                rev[b].append(a)
            elif k in (ANCHOR, LOOK):
                R['cond'][b] = v                   # a -> b when the test holds at the current position
            elif k == CHAR:
                R['chars'].append(v)
            elif k in (CAP, ALT):
                for s in ks:
                    rev[s].append(a); rev[b].append(s + 1)
            elif k == SEQ:
                p, q = ks if R['fwd'] else ks[::-1]
                rev[p].append(a); rev[q].append(p + 1); rev[b].append(q + 1)
            elif k == QUANT:
                s = ks[0]; qk = self.arg[v][0]
                rev[s].append(a); rev[b].append(s + 1)
                if qk != PLUS: rev[b].append(a)
                if qk != OPT: rev[s].append(s + 1)

    # ---------------------------------------------------------------- the sweep
    def index(self, w, B=None):
        """Build the bit index for all starts of w; B is the set of allowed final positions."""
        self.w, n = w, len(w)
        self.N = n + 1
        cache = {}
        for v, k in enumerate(self.kind):
            if k == CHAR and self.arg[v] not in cache:
                table = {c: self._member(self.arg[v], c) for c in set(w)}
                cache[self.arg[v]] = bytes(table[c] for c in w)
        self.ok = {v: cache[self.arg[v]] for v, k in enumerate(self.kind) if k == CHAR}
        self.tab = [None] * len(self.kind)         # per node: (bytearray of its region, base offset)
        for R in self.regions:
            self._sweep(R, B if R is self.top else None, n)
        return self

    def _test(self, v, x):
        if self.kind[v] == LOOK:
            t, base = self.tab[self.kids[v][0]]
            return bool(t[base + x] & ABIT) == self.arg[v][1]
        code, multi = self.arg[v]; w, n = self.w, len(self.w)
        if code is K.AT_BEGINNING:
            return x == 0 or (multi and w[x - 1] in LT)
        if code is K.AT_END:
            return x == n or (multi and w[x] in LT)
        boundary = (x > 0 and isword(w[x - 1])) != (x < n and isword(w[x]))
        return boundary if code is K.AT_BOUNDARY else not boundary

    def _sweep(self, R, T, n):
        nodes, li, rev, cond, N = R['nodes'], R['li'], R['rev'], R['cond'], self.N
        m = len(nodes); tab = bytearray(m * N); fwd = R['fwd']; step = 1 if fwd else -1
        for v in nodes:
            self.tab[v] = (tab, li[v] * N)
        chars = [(2 * li[v], self.ok[v], li[v] * N) for v in R['chars']]
        info = []                                  # per node: kind, child indices in execution order, arg
        for v in nodes:
            ks = [] if self.kind[v] == LOOK else [li[c] for c in self.kids[v]]
            if self.kind[v] == SEQ and not fwd: ks.reverse()
            info.append((self.kind[v], ks, self.arg[v]))
        rootb = 2 * li[R['root']] + 1
        D, Z = bytearray(m), bytearray(m)
        for x in (range(n, -1, -1) if fwd else range(0, n + 1)):
            mark = bytearray(2 * m); stack = []
            if T is None or x in T:
                mark[rootb] = 1; stack.append(rootb)
            y = x + step
            if 0 <= y <= n:                        # seeds: consuming edges into the solved layer y
                i = x if fwd else x - 1
                for a, ok, base in chars:
                    if ok[i] and tab[base + y] & CBIT:
                        mark[a] = 1; stack.append(a)
            while stack:                           # reverse reachability inside layer x
                u = stack.pop()
                for p in rev[u]:
                    if not mark[p]:
                        mark[p] = 1; stack.append(p)
                v = cond.get(u)
                if v is not None and not mark[u - 1] and self._test(v, x):
                    mark[u - 1] = 1; stack.append(u - 1)
            for i, (k, ks, a) in enumerate(info):  # the bit rules, children first
                A, C = mark[2 * i], mark[2 * i + 1]
                if k == CHAR: d, z = A, 0
                elif k in (EPS, ANCHOR, LOOK): d, z = 0, A
                elif k == FAIL: d = z = 0
                elif k == CAP: d, z = D[ks[0]], Z[ks[0]]
                elif k == ALT: d, z = D[ks[0]] | D[ks[1]], Z[ks[0]] if mark[2 * ks[0]] else Z[ks[1]]
                elif k == SEQ: d, z = D[ks[0]] | (mark[2 * ks[0]] & D[ks[1]]), Z[ks[0]] & Z[ks[1]]
                else:
                    s = ks[0]; d = D[s]; t = int(C and (not a[1] or not d))
                    z = t if a[0] != PLUS else t & Z[s]
                D[i], Z[i] = d, z
                tab[i * N + x] = A | C << 1 | d << 2 | z << 3

    # ---------------------------------------------------------------- the walk over the bits
    def _bit(self, v, x, mask):
        t, base = self.tab[v]
        return t[base + x] & mask

    def _tick(self):
        self.clock += 1
        return self.clock

    def _walk(self, v, x, full):
        k = self.kind[v]
        if k == CHAR:
            return x + 1 if self.fwd[v] else x - 1
        if k in (EPS, ANCHOR):
            return x
        if k == LOOK:
            if self.has_caps[v]:
                self.look_at[v] = (x, self._tick())
            return x
        ks = self.kids[v]
        if k == CAP:
            y = self._walk(ks[0], x, full)
            self.written[self.arg[v]] = ((min(x, y), max(x, y)), self._tick())
            return y
        if k == ALT:
            take_left = self._bit(ks[0], x, ABIT if full else DBIT)
            return self._walk(ks[0] if take_left else ks[1], x, full)
        if k == SEQ:
            p, q = ks if self.fwd[v] else ks[::-1]
            if full:
                return self._walk(q, self._walk(p, x, True), True)
            y = self._walk(p, x, bool(self._bit(q, x, DBIT)))
            return self._walk(q, y, y != x)
        qk, greedy = self.arg[v]; s = ks[0]                         # quantifier
        self.entered[v] = self._tick()
        if full and self._bit(v, x, ZBIT):
            if qk == PLUS:
                self._walk(s, x, True)
            return x
        y = self._walk(s, x, False)
        while qk != OPT and not (self._bit(v, y, CBIT) and (not greedy or not self._bit(s, y, DBIT))):
            self.entered[v] = self._tick()
            y = self._walk(s, y, False)
        return y

    def _collect(self, root, slots):
        """Keep a write only if no enclosing repetition restarted after it; replay lookarounds."""
        stack = [(root, 0)]
        while stack:
            v, S = stack.pop()
            k = self.kind[v]
            if k == QUANT:
                S = max(S, self.entered.get(v, 0))
            elif k == CAP:
                span, t = self.written.get(self.arg[v], (None, 0))
                slots[self.arg[v]] = span if t > S else None
            elif k == LOOK:
                x, t = self.look_at.get(v, (None, 0))
                if t > S:                          # the surviving request: replay its child once
                    self._walk(self.kids[v][0], x, True)
                    stack.append((self.kids[v][0], 0))
                continue
            stack.extend((c, S) for c in self.kids[v])

    def match_at(self, x):
        """Anchored match at x after index(): None or (start, end, [None, span1, span2, ...])."""
        if not self._bit(self.root, x, ABIT):
            return None
        self.clock, self.entered, self.written, self.look_at = 0, {}, {}, {}
        y = self._walk(self.root, x, True)
        slots = [None] * (self.ngroups + 1)
        self._collect(self.root, slots)
        return (x, y, slots)

    def exec(self, w, start=0):
        """Leftmost match from start, like RegExp.prototype.exec without the sticky flag."""
        self.index(w)
        x = next((x for x in range(start, len(w) + 1) if self._bit(self.root, x, ABIT)), None)
        return None if x is None else self.match_at(x)

    def match_all(self, w):
        self.index(w); out, cur = [], 0
        while cur <= len(w):
            x = next((x for x in range(cur, len(w) + 1) if self._bit(self.root, x, ABIT)), None)
            if x is None:
                break
            m = self.match_at(x); out.append(m)
            cur = m[1] + 1 if m[1] == x else m[1]
        return out


def run(f, *a):
    """Run f in a thread with a large stack so that deeply nested patterns do not overflow."""
    import threading
    sys.setrecursionlimit(1_000_000); threading.stack_size(512 * 1024 * 1024)
    res = []
    t = threading.Thread(target=lambda: res.append(f(*a))); t.start(); t.join()
    return res[0]
