"""Control matcher: bitre with the ECMAScript specification's capture reset instead of clocks.
RepeatMatcher clears every group of the body at each iteration; doing that literally costs the
number of groups in the body per iteration.  The answers are identical; only the cost differs."""
from bitre import Regex, QUANT, CAP, PLUS, OPT, CBIT, DBIT, ZBIT


class ClearingRegex(Regex):
    def _prepare(self):
        super()._prepare()
        self.body_groups = {}
        for v, k in enumerate(self.kind):
            if k == QUANT:
                gs, stack = [], [self.kids[v][0]]
                while stack:
                    u = stack.pop()
                    if self.kind[u] == CAP:
                        gs.append(self.arg[u])
                    stack.extend(self.kids[u])
                self.body_groups[v] = gs

    def _enter(self, v):
        self.entered[v] = self._tick()
        for g in self.body_groups[v]:
            self.written.pop(g, None)

    def _walk(self, v, x, full):
        if self.kind[v] != QUANT:
            return super()._walk(v, x, full)
        qk, greedy = self.arg[v]; s = self.kids[v][0]
        self._enter(v)
        if full and self._bit(v, x, ZBIT):
            if qk == PLUS:
                self._walk(s, x, True)
            return x
        y = self._walk(s, x, False)
        while qk != OPT and not (self._bit(v, y, CBIT) and (not greedy or not self._bit(s, y, DBIT))):
            self._enter(v)
            y = self._walk(s, y, False)
        return y
