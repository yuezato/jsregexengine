"""Reference semantics, written independently of bitre.py.

  naive_answers(root, w, B)   the paper's ordered-list semantics: every occurrence denotes the list
                              of (end, captures) pairs in the order backtracking would try them;
                              the answer at start x is the first pair whose end lies in B.
  spec_answers(root, w, B, G) a direct transcription of ECMAScript's backtracking matcher
                              (continuation-passing matchers, RepeatMatcher with capture clearing
                              and the empty check, lookaround).

Both enumerate, so they are exponential in the worst case; naive_rows raises TooBig beyond a budget.
Patterns are trees built from the constructors below; to_js prints them as JavaScript source.
  fail | eps | chr(set) | pos(kind) | seq(l, r) | alt(l, r) | cap(s) | quant(kind, greedy, s)
  | look(dir, positive, s) | atomic(s)
"""
import itertools, random, sys
sys.setrecursionlimit(100000)

INF = float('inf')

class Node:
    __slots__ = ('kind', 'kids', 'arg', 'id', 'g', 'groups')
    def __init__(self, kind, kids=(), arg=None):
        self.kind = kind; self.kids = list(kids); self.arg = arg
        self.id = None; self.g = None; self.groups = None
    def __repr__(self):
        return to_js(self)

def fail(): return Node('fail')
def eps(): return Node('eps')
def chr_(s): return Node('chr', arg=frozenset(s))
def pos(k): return Node('pos', arg=k)          # '^', '$', 'b' (\b), 'B' (\B)
def seq(l, r): return Node('seq', [l, r])
def alt(l, r): return Node('alt', [l, r])
def cap(s): return Node('cap', [s])
def quant(kind, greedy, s): return Node('quant', [s], (kind, greedy))   # kind in opt/star/plus
def look(d, positive, s): return Node('look', [s], (d, positive))       # d in 'f','b'
def atomic(s): return Node('atomic', [s])

def finalize(root):
    """number occurrences (preorder) and capture groups (source order of '(')"""
    cnt = itertools.count(); gcnt = itertools.count(1)
    def go(v):
        v.id = next(cnt)
        if v.kind == 'cap':
            v.g = next(gcnt)
        for k in v.kids:
            go(k)
        gs = set()
        if v.kind == 'cap': gs.add(v.g)
        for k in v.kids: gs |= k.groups
        v.groups = frozenset(gs)
    go(root)
    return next(gcnt) - 1   # number of groups



# ---------------------------------------------------------------- printing
def to_js(v, atomic_ok=True):
    k = v.kind
    if k == 'fail': return '(?!)'
    if k == 'eps': return '(?:)'
    if k == 'chr':
        s = sorted(v.arg)
        return s[0] if len(s) == 1 else '[' + ''.join(s) + ']'
    if k == 'pos': return {'^': '^', '$': '$', 'b': r'\b', 'B': r'\B'}[v.arg]
    if k == 'seq': return _term(v.kids[0]) + _term(v.kids[1])
    if k == 'alt': return to_js(v.kids[0]) + '|' + to_js(v.kids[1])
    if k == 'cap': return '(' + to_js(v.kids[0]) + ')'
    if k == 'look':
        d, p = v.arg
        return '(?' + ('' if d == 'f' else '<') + ('=' if p else '!') + to_js(v.kids[0]) + ')'
    if k == 'atomic': return '(?>' + to_js(v.kids[0]) + ')'
    if k == 'quant':
        kind, gr = v.arg
        op = {'opt': '?', 'star': '*', 'plus': '+'}[kind] + ('' if gr else '?')
        return _atom(v.kids[0]) + op
    raise ValueError(k)

def _term(v):
    return '(?:' + to_js(v) + ')' if v.kind == 'alt' else to_js(v)

def _atom(v):
    if v.kind in ('chr', 'cap'):
        return to_js(v)
    return '(?:' + to_js(v) + ')'

# ---------------------------------------------------------------- word context
class Word:
    def __init__(self, w):
        self.w = w; self.n = len(w)
    def isword(self, i):
        return 0 <= i < self.n and (self.w[i].isalnum() or self.w[i] == '_')
    def postest(self, kind, x):
        n = self.n
        if kind == '^': return x == 0
        if kind == '$': return x == n
        a = self.isword(x - 1); b = self.isword(x)
        if kind == 'b': return a != b
        if kind == 'B': return a == b
        raise ValueError(kind)
    def step(self, cs, d, x):
        """character test in direction d from x: return y or None"""
        if d == 'f':
            if x < self.n and self.w[x] in cs: return x + 1
        else:
            if x > 0 and self.w[x - 1] in cs: return x - 1
        return None

# ---------------------------------------------------------------- the ordered-list semantics
class TooBig(Exception):
    pass

def naive_rows(root, w, limit=200000):
    """returns function den(v, d, x) -> list of (y, caps) where caps is a frozenset of (g,i,j)"""
    W = Word(w); n = W.n
    memo = {}
    budget = [limit]
    def den(v, d, x):
        key = (v.id, d, x)
        r = memo.get(key)
        if r is not None:
            return r
        r = _den(v, d, x)
        budget[0] -= len(r) + 1
        if budget[0] < 0:
            raise TooBig()
        memo[key] = r
        return r
    E = frozenset()
    def _den(v, d, x):
        k = v.kind
        if k == 'fail': return []
        if k == 'eps': return [(x, E)]
        if k == 'pos': return [(x, E)] if W.postest(v.arg, x) else []
        if k == 'chr':
            y = W.step(v.arg, d, x)
            return [] if y is None else [(y, E)]
        if k == 'alt':
            return den(v.kids[0], d, x) + den(v.kids[1], d, x)
        if k == 'seq':
            u, t = (v.kids[0], v.kids[1]) if d == 'f' else (v.kids[1], v.kids[0])
            out = []
            for (i, h) in den(u, d, x):
                for (z, kk) in den(t, d, i):
                    out.append((z, h | kk))
            return out
        if k == 'cap':
            g = v.g
            return [(z, h | {(g, min(x, z), max(x, z))}) for (z, h) in den(v.kids[0], d, x)]
        if k == 'atomic':
            r = den(v.kids[0], d, x)
            return r[:1]
        if k == 'look':
            dd, positive = v.arg
            r = den(v.kids[0], dd, x)
            if positive:
                return [(x, r[0][1])] if r else []
            return [] if r else [(x, E)]
        if k == 'quant':
            kind, greedy = v.arg
            s = v.kids[0]
            P = den(s, d, x)
            if kind == 'opt':
                D = [(y, kk) for (y, kk) in P if y != x]
                return D + [(x, E)] if greedy else [(x, E)] + D
            if kind == 'star':
                return T(v, d, x, E)
            if kind == 'plus':
                out = []
                for (y, kk) in P:
                    out += T(v, d, y, kk)
                return out
        raise ValueError(k)
    tmemo = {}
    def tailrest(v, d, x):
        key = (v.id, d, x)
        r = tmemo.get(key)
        if r is not None:
            return r
        s = v.kids[0]
        out = []
        for (y, kk) in den(s, d, x):
            if y != x:
                out += T(v, d, y, kk)
        budget[0] -= len(out) + 1
        if budget[0] < 0:
            raise TooBig()
        tmemo[key] = out
        return out
    def T(v, d, x, h):
        greedy = v.arg[1]
        rest = tailrest(v, d, x)
        return rest + [(x, h)] if greedy else [(x, h)] + rest
    return den

def naive_answers(root, w, B):
    den = naive_rows(root, w)
    out = []
    for x in range(len(w) + 1):
        ans = None
        for (y, h) in den(root, 'f', x):
            if y in B:
                ans = (y, h); break
        out.append(ans)
    return out

# ---------------------------------------------------------------- the ECMAScript continuation matcher
def spec_answers(root, w, B, G):
    W = Word(w); n = W.n
    def clear(caps, groups):
        if not groups: return caps
        c = list(caps)
        for g in groups: c[g] = None
        return tuple(c)
    def setc(caps, g, val):
        c = list(caps); c[g] = val; return tuple(c)
    def M(v, d, x, caps, c):
        k = v.kind
        if k == 'fail': return None
        if k == 'eps': return c(x, caps)
        if k == 'pos': return c(x, caps) if W.postest(v.arg, x) else None
        if k == 'chr':
            y = W.step(v.arg, d, x)
            return None if y is None else c(y, caps)
        if k == 'alt':
            r = M(v.kids[0], d, x, caps, c)
            return r if r is not None else M(v.kids[1], d, x, caps, c)
        if k == 'seq':
            u, t = (v.kids[0], v.kids[1]) if d == 'f' else (v.kids[1], v.kids[0])
            return M(u, d, x, caps, lambda i, tau: M(t, d, i, tau, c))
        if k == 'cap':
            g = v.g
            return M(v.kids[0], d, x, caps, lambda y, tau: c(y, setc(tau, g, (min(x, y), max(x, y)))))
        if k == 'look':
            dd, positive = v.arg
            r = M(v.kids[0], dd, x, caps, lambda y, tau: (y, tau))
            if positive:
                return None if r is None else c(x, r[1])
            return None if r is not None else c(x, caps)
        if k == 'atomic':
            r = M(v.kids[0], d, x, caps, lambda y, tau: (y, tau))
            return None if r is None else c(r[0], r[1])
        if k == 'quant':
            kind, greedy = v.arg
            mn, mx = {'opt': (0, 1), 'star': (0, INF), 'plus': (1, INF)}[kind]
            s = v.kids[0]; groups = s.groups
            def RM(mn, mx, x, caps):
                if mx == 0: return c(x, caps)
                def dcont(y, tau):
                    if mn == 0 and y == x: return None
                    mn2 = 0 if mn == 0 else mn - 1
                    mx2 = INF if mx == INF else mx - 1
                    return RM(mn2, mx2, y, tau)
                xr = clear(caps, groups)
                if mn != 0: return M(s, d, x, xr, dcont)
                if not greedy:
                    z = c(x, caps)
                    if z is not None: return z
                    return M(s, d, x, xr, dcont)
                z = M(s, d, x, xr, dcont)
                if z is not None: return z
                return c(x, caps)
            return RM(mn, mx, x, caps)
        raise ValueError(k)
    out = []
    init = tuple([None] * (G + 1))
    for x in range(n + 1):
        r = M(root, 'f', x, init, lambda y, tau: (y, tau) if y in B else None)
        out.append(r)
    return out


def caps_from_set(h, G):
    c = [None] * (G + 1)
    for (g, i, j) in h: c[g] = (i, j)
    return tuple(c)
