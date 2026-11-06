"""JavaScript-style matching on code-point positions.

One reverse sweep per region builds a byte of A/C/D/Z decisions per cell.
Single anchored matches can walk that guide. The all-start reporter instead
shares endpoint columns and reconstructs each syntax piece once for all starts.
Atomic groups commit to the locally preferred child endpoint, in either direction.
"""
import sys
from functools import lru_cache, partial
from re import _constants as K

from bitcolumns import Colored, Encoding, Positions, Tail, ceil_sqrt, positions
from regex_syntax import (
    ALT, ANCHOR, ATOMIC, CAP, CHAR, EPS, FAIL, LOOK, OPT, PLUS, QUANT, SEQ, STAR,
    LT, ParsedPattern, isword,
)
# Re-export the named character helpers from the original module.
from regex_syntax import ANCHORS, CATS, FLAGBITS, WS, canon, case_class

ABIT, CBIT, DBIT, ZBIT = 1, 2, 4, 8


class Regex(ParsedPattern):
    def __init__(self, source, flags=''):
        super().__init__(source, flags)
        self._prepare()

    # ---------------------------------------------------------------- regions and static graph
    def _prepare(self):
        n = len(self.kind)
        self.fwd = [True] * n
        self.top = {'root': self.root, 'fwd': True, 'nodes': [], 'atomic_result': False}
        regions = [self.top]
        owner = [None] * n
        owner[self.root] = self.top
        for v in reversed(range(n)):  # a parent always has a larger id
            region = owner[v]
            self.fwd[v] = region['fwd']
            region['nodes'].append(v)
            kind = self.kind[v]
            if kind in (LOOK, ATOMIC):
                child = self.kids[v][0]
                direction = self.arg[v][0] if kind == LOOK else self.fwd[v]
                inner = {'root': child, 'fwd': direction, 'nodes': [], 'atomic_result': kind == ATOMIC}
                regions.append(inner)
                owner[child] = inner
            else:
                for child in self.kids[v]:
                    owner[child] = region
        self.regions = regions[::-1]
        self.local = [0] * n
        for region in self.regions:
            region['nodes'].reverse()
            for i, v in enumerate(region['nodes']):
                self.local[v] = i
            self._static_graph(region)
        self._partition()
        exports = [False] * n                      # children have smaller ids than their parents
        for v in range(n):
            k = self.kind[v]
            exports[v] = k == CAP or (k == LOOK and self.arg[v][1] and exports[self.kids[v][0]]) \
                or (k not in (CAP, LOOK) and any(exports[c] for c in self.kids[v]))
        self.has_caps = [self.kind[v] == LOOK and exports[v] for v in range(n)]   # positive, capturing

    def _partition(self):
        """Piece boundaries depend only on syntax. Visit larger children first."""
        m = len(self.kind)
        threshold = ceil_sqrt(m)
        self.size = [1] * m
        parent = [-1] * m
        for v, children in enumerate(self.kids):
            for c in children:
                parent[c] = v
                self.size[v] += self.size[c]

        cut = bytearray(m)
        residuals = []
        previous, v = -1, self.root
        while v != -1:
            children = self.kids[v]
            first = children[0] if children else -1
            second = children[1] if len(children) == 2 else -1
            if second != -1 and self.size[second] > self.size[first]:
                first, second = second, first
            if previous == parent[v] and first != -1:
                nxt = first
            elif previous == first and second != -1:
                nxt = second
            else:
                size = 1 + sum(residuals.pop() for _ in children)
                cut[v] = size >= threshold or v == self.root
                residuals.append(0 if cut[v] else size)
                nxt = parent[v]
            previous, v = v, nxt

        self.piece = [0] * m
        self.pieces = []  # (root, interior nodes, child-piece roots), parents first
        for v in reversed(range(m)):
            if cut[v]:
                owner = len(self.pieces)
                if v != self.root:
                    self.pieces[self.piece[parent[v]]][2].append(v)
                self.pieces.append((v, [], []))
            else:
                owner = self.piece[parent[v]]
            self.piece[v] = owner
        for v, owner in enumerate(self.piece):
            self.pieces[owner][1].append(v)  # child-before-parent order

    def _static_graph(self, R):
        nodes, li = R['nodes'], self.local
        rev = R['rev'] = [[] for _ in range(2 * len(nodes))]
        R['cond'], R['chars'], R['jumps'] = [None] * len(rev), [], []
        for v in nodes:
            a = 2 * li[v]; b = a + 1; k = self.kind[v]
            ks = [] if k in (LOOK, ATOMIC) else [2 * li[c] for c in self.kids[v]]
            if k == EPS:
                rev[b].append(a)
            elif k == ATOMIC:
                R['jumps'].append(v)
                R['cond'][b] = v
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
        self.encoding = Encoding(self.N)
        allowed = None
        if B is not None:
            allowed = bytearray(self.N)
            for x in B:
                if 0 <= x <= n:
                    allowed[x] = 1
        cache = {}
        for v, k in enumerate(self.kind):
            if k == CHAR and self.arg[v] not in cache:
                spec = self.arg[v]
                member = lru_cache(maxsize=256)(partial(self._member, spec))
                cache[spec] = bytes(member(c) for c in w)
        self.ok = [cache[self.arg[v]] if k == CHAR else None for v, k in enumerate(self.kind)]
        self.tab = [None] * len(self.kind)
        live = [None] * len(self.kind)
        for R in self.regions:
            self._sweep(R, allowed if R is self.top else None, n, live)
            if R['atomic_result']:
                # Keep only the region root for its parent. The live subtree
                # roots are disjoint; node ids address slots directly.
                for v in R['nodes']:
                    live[v], _ = self._column(v, live, self.size[v])
                    if self.kind[v] != LOOK:
                        for c in self.kids[v]:
                            live[c] = None
            else:
                for v in R['jumps']:
                    live[self.kids[v][0]] = None
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

    def _sweep(self, R, T, n, closed):
        nodes, li, rev, cond, N = R['nodes'], self.local, R['rev'], R['cond'], self.N
        m = len(nodes); tab = bytearray(m * N); fwd = R['fwd']; step = 1 if fwd else -1
        for v in nodes:
            self.tab[v] = (tab, li[v] * N)
        chars = [(2 * li[v], self.ok[v], li[v] * N) for v in R['chars']]
        info = []                                  # per node: kind, child indices in execution order, arg
        for v in nodes:
            ks = [] if self.kind[v] in (LOOK, ATOMIC) else [li[c] for c in self.kids[v]]
            if self.kind[v] == SEQ and not fwd: ks.reverse()
            info.append((self.kind[v], ks, self.arg[v]))
        jumps = [(li[v], self.kids[v][0], closed[self.kids[v][0]]) for v in R['jumps']]
        committed = [None] * m if jumps else None
        rootb = 2 * li[R['root']] + 1
        D, Z = bytearray(m), bytearray(m)
        for x in (range(n, -1, -1) if fwd else range(0, n + 1)):
            mark = bytearray(2 * m); stack = []
            if T is None or T[x]:
                mark[rootb] = 1; stack.append(rootb)
            y = x + step
            if 0 <= y <= n:                        # seeds: consuming edges into the solved layer y
                i = x if fwd else x - 1
                for a, ok, base in chars:
                    if ok[i] and tab[base + y] & CBIT:
                        mark[a] = 1; stack.append(a)
            for i, child, column in jumps:
                end = committed[i] = self._end(child, x, True, column)
                if end is not None and end != x and tab[i * N + end] & CBIT:
                    mark[2 * i] = 1
                    stack.append(2 * i)
            while stack:                           # reverse reachability inside layer x
                u = stack.pop()
                for p in rev[u]:
                    if not mark[p]:
                        mark[p] = 1; stack.append(p)
                v = cond[u]
                if v is not None and not mark[u - 1]:
                    enabled = committed[u // 2] == x if self.kind[v] == ATOMIC else self._test(v, x)
                    if enabled:
                        mark[u - 1] = 1; stack.append(u - 1)
            for i, (k, ks, a) in enumerate(info):  # the bit rules, children first
                A, C = mark[2 * i], mark[2 * i + 1]
                if k == CHAR: d, z = A, 0
                elif k in (EPS, ANCHOR, LOOK): d, z = 0, A
                elif k == ATOMIC:
                    end = committed[i]
                    d, z = A and end != x, A and end == x
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
        if k == ATOMIC:
            return self._walk(self.kids[v][0], x, True)
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
        if not 0 <= x < self.N or not self._bit(self.root, x, ABIT):
            return None
        self.clock, self.entered, self.written, self.look_at = 0, {}, {}, {}
        y = self._walk(self.root, x, True)
        slots = [None] * (self.ngroups + 1)
        self._collect(self.root, slots)
        return (x, y, slots)

    def exec(self, w, start=0):
        """Leftmost match from start, like RegExp.prototype.exec without the sticky flag."""
        self.index(w)
        x = next((x for x in range(max(0, start), len(w) + 1) if self._bit(self.root, x, ABIT)), None)
        return None if x is None else self.match_at(x)

    # -------------------------------------------------------- shared endpoint columns
    def _end(self, v, x, full, column):
        if full:
            if not self._bit(v, x, ABIT):
                return None
            if self._bit(v, x, ZBIT):
                return x
        return column.get(x)

    def _split(self, v, x, full, moving):
        p, q = self.kids[v] if self.fwd[v] else reversed(self.kids[v])
        left_full = full or bool(self._bit(q, x, DBIT))
        y = self._end(p, x, left_full, moving[p])
        return p, q, y, left_full, full or y != x

    def _column(self, v, moving, size):
        """Build the moving endpoint; keep a terminal map only while its piece is live."""
        k, children = self.kind[v], self.kids[v]
        tail = None
        if k == QUANT and self.arg[v][0] != OPT:
            parent = moving[children[0]]
            if self.arg[v][1]:  # greedy: stop at roots
                stops = bytearray(parent.get(x) is None for x in range(self.N))
            else:
                stops = bytearray(bool(self._bit(v, x, CBIT)) for x in range(self.N))
            tail = Tail(parent, stops, self.encoding, size, self.fwd[v])

        def entry(x):
            if not self._bit(v, x, DBIT):
                return None
            if k == CHAR:
                return x + (1 if self.fwd[v] else -1)
            if k == ATOMIC:
                return self._end(children[0], x, True, moving[children[0]])
            if k == ALT:
                s, t = children
                return moving[s if self._bit(s, x, DBIT) else t].get(x)
            if k == SEQ:
                _, right, y, _, right_full = self._split(v, x, False, moving)
                return self._end(right, y, right_full, moving[right])
            # A capture or optional inherits its child. A strict repeat uses
            # the parent of the last surviving body entrance.
            return moving[children[0]].get(tail.last(x) if tail else x)

        return positions(self.encoding, size, self.fwd[v], entry), tail

    def _build_piece(self, nodes, moving, tails=None):
        for v in nodes:
            moving[v], tail = self._column(v, moving, len(self.kind))
            if tails is not None:
                tails[v] = tail

    def _visit_piece(self, root, x, full, moving, tails, slots, send):
        work = [(root, x, full)]
        while work:
            v, x, full = work.pop()
            if self.piece[v] != self.piece[root]:
                send(v, x, full)
                continue
            k, children = self.kind[v], self.kids[v]
            if k == CAP:
                if slots is not None:
                    y = self._end(v, x, full, moving[v])
                    slots[self.arg[v]] = (min(x, y), max(x, y))
                work.append((children[0], x, full))
            elif k == ALT:
                s, t = children
                work.append((s if self._bit(s, x, ABIT if full else DBIT) else t, x, full))
            elif k == ATOMIC or (k == LOOK and self.arg[v][1]):
                work.append((children[0], x, True))
            elif k == SEQ:
                p, q, y, left_full, right_full = self._split(v, x, full, moving)
                work.extend(((q, y, right_full), (p, x, left_full)))
            elif k == QUANT:
                q = self.arg[v][0]
                if full and self._bit(v, x, ZBIT):
                    if q == PLUS:
                        work.append((children[0], x, True))
                else:
                    work.append((children[0], x if q == OPT else tails[v].last(x), False))

    def all_starts(self, w, B=None):
        """One anchored result per position, including None for failures (Theorem 8.1)."""
        return self.index(w, B)._report(global_only=False)

    def match_all(self, w):
        """Global nonoverlapping matches; advance one unit after an empty success."""
        return self.index(w)._report(global_only=True)

    def _report(self, global_only):
        # Bottom up: only the moving columns at piece roots survive.
        if not any(self._bit(self.root, x, ABIT) for x in range(self.N)):
            return [] if global_only else [None] * self.N
        size = len(self.kind)
        moving = [None] * size
        for root, nodes, _ in reversed(self.pieces):
            self._build_piece(nodes, moving)
            for v in nodes:
                if v != root:
                    moving[v] = None

        selected = bytearray(self.N)
        rows = [] if global_only else [None] * self.N
        cursor = 0
        for x in range(self.N):
            if global_only and x < cursor:
                continue
            y = self._end(self.root, x, True, moving[self.root])
            if y is None:
                continue
            selected[x] = 1
            row = (x, y, [None] * (self.ngroups + 1))
            if global_only:
                rows.append(row)
                cursor = y if y != x else x + 1
            else:
                rows[x] = row

        if not self.ngroups:
            return rows

        # Top down: rebuild each interior once. Only selected starts have
        # requests. A reverse pass fills backward jumps without staging N
        # word-sized destinations for every outgoing edge.
        pending = [None] * size
        tails = [None] * size
        raw = self.encoding.explicit(size)
        for root, nodes, children in self.pieces:
            incoming, pending[root] = pending[root], None
            self._build_piece(nodes, moving, tails)
            outgoing = []
            for c in children:
                pending[c] = _Requests(self.encoding, size, raw)
                outgoing.append(pending[c])
            for forward in ([True] if raw or not children else [True, False]):
                slot_index = 0
                for x in (range(self.N) if forward else reversed(range(self.N))):
                    if not raw:
                        for request in outgoing:
                            request.release(x, forward)
                    if not selected[x]:
                        continue
                    row_index = slot_index if global_only else x
                    slot_index += 1
                    if incoming is None:
                        y, full = x, True
                    else:
                        y, full = incoming.get(x)
                        if y is None:
                            continue
                    def send(child, pos, mode):
                        pending[child].put(x, pos, mode, forward)
                    slots = rows[row_index][2] if forward else None
                    self._visit_piece(root, y, full, moving, tails, slots, send)
            for request in outgoing:
                request.finish()
            for v in nodes:
                moving[v] = tails[v] = None
        return rows


class _Requests:
    """A tagged map from original starts to entrances of a child piece."""
    def __init__(self, encoding, size, raw):
        self.raw = raw
        self.mode = bytearray(encoding.n)  # 0 absent, 1 moving, 2 full
        if raw:
            self.positions = Positions(encoding.n)
        else:
            self.forward = Colored(encoding, size, True)
            self.backward = Colored(encoding, size, False)

    def release(self, x, forward):
        (self.forward if forward else self.backward).release(x)

    def put(self, x, y, full, forward):
        if forward:
            self.mode[x] = 2 if full else 1
        if self.raw:
            self.positions.put(x, y)
        elif forward and y >= x:
            self.forward.put(x, y)
        elif not forward and y < x:
            self.backward.put(x, y)

    def finish(self):
        if not self.raw:
            self.forward.finish()
            self.backward.finish()

    def get(self, x):
        mode = self.mode[x]
        if not mode:
            return None, False
        if self.raw:
            y = self.positions.get(x)
        else:
            y = self.forward.get(x)
            if y is None:
                y = self.backward.get(x)
        return y, mode == 2


def run(f, *a):
    """Run f in a thread with a large stack so that deeply nested patterns do not overflow."""
    import threading
    sys.setrecursionlimit(1_000_000); threading.stack_size(512 * 1024 * 1024)
    res = []
    t = threading.Thread(target=lambda: res.append(f(*a))); t.start(); t.join()
    return res[0]
