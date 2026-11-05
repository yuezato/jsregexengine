"""The nested family G_d b outside V8, where G_0 = a? and G_d = (?:G_{d-1})+.
1. A backtracking matcher that follows ECMAScript's RepeatMatcher (empty check included)
   counts how often it tests the suffix b on a^n, from every start.  The count is compared
   with the closed form  sum_k D_d(k) (n - k + 1),  D_d(0) = 1,  D_d(k) = 2^d (2^d - 1)^(k-1).
2. The same matcher counts its calls for other nestings, whose growth per letter is far smaller.
3. bitre is timed on the same patterns, and RE2 too if the google-re2 package is installed.
Usage: python3 bench/nested.py"""
import sys, time
from common import ROOT  # noqa: F401  (sets the import path)
from bitre import Regex, run

INF = float('inf')
A, B = ('chr', 'a'), ('chr', 'b')


def opt(s): return ('q', 0, 1, s)
def plus(s): return ('q', 1, INF, s)
def star(s): return ('q', 0, INF, s)


def nested(d, wrap, base):
    p = base
    for _ in range(d):
        p = wrap(p)
    return ('seq', p, B)


def backtrack(tree, w):
    """greedy backtracking over every start of w; returns (calls, tests of b, matched?)"""
    n = len(w); calls = [0, 0]

    def M(v, x, k):
        calls[0] += 1
        t = v[0]
        if t == 'chr':
            calls[1] += v[1] == 'b'
            return k(x + 1) if x < n and w[x] == v[1] else None
        if t == 'seq':
            return M(v[1], x, lambda y: M(v[2], y, k))
        if t == 'alt':
            r = M(v[1], x, k)
            return r if r is not None else M(v[2], x, k)
        _, mn, mx, body = v

        def RM(mn, mx, x):
            calls[0] += 1
            if mx == 0:
                return k(x)

            def cont(y):
                if mn == 0 and y == x:            # the empty check of RepeatMatcher
                    return None
                return RM(max(mn - 1, 0), mx - 1, y)
            r = M(body, x, cont)
            return r if r is not None or mn > 0 else k(x)
        return RM(mn, mx, x)

    for x in range(n + 1):
        if M(tree, x, lambda y: y) is not None:
            return calls[0], calls[1], True
    return calls[0], calls[1], False


def D(d, k):
    return 1 if k == 0 else 2 ** d * (2 ** d - 1) ** (k - 1)


def main():
    print('1. tests of b by backtracking against the closed form, G_d b on a^n')
    bad = 0
    for d in range(1, 6):
        row = []
        for n in range(0, 7):
            if (2 ** d - 1) ** n > 2_000_000:
                break
            _, tests, matched = backtrack(nested(d, plus, opt(A)), 'a' * n)
            want = sum(D(d, k) * (n - k + 1) for k in range(n + 1))
            bad += tests != want or matched
            row.append('%d%s' % (tests, '' if tests == want else '(formula %d)' % want))
        print('  d=%d  n=0..%d: %s' % (d, len(row) - 1, ' '.join(row)))
    print('  all counts equal the closed form' if not bad else '  %d DIFFERENCES' % bad)

    print('2. growth of all matcher calls per extra letter (the last ratio before a budget)')
    for label, wrap, base in [('(?:P)+ over a?', plus, opt(A)), ('(?:P)+ over a ', plus, A), ('(?:P)* over a ', star, A)]:
        ratios = []
        for d in range(1, 7):
            counts = []
            for n in range(1, 40):
                counts.append(backtrack(nested(d, wrap, base), 'a' * n)[0])
                if counts[-1] > 300_000:
                    break
            ratios.append('%.1f' % (counts[-1] / counts[-2]))
        print('  %s  d=1..6: %s' % (label, ' '.join(ratios)))
    print('  (2^d - 1 for plus over a nullable body; about d otherwise)')

    print('3. bitre (exec) on the same patterns')
    for d, n in [(2, 20), (3, 11), (5, 6), (6, 5), (7, 4), (8, 4), (9, 3), (2, 10_000), (8, 10_000), (30, 10_000)]:
        src = '(?:' * d + 'a?' + ')+' * d + 'b'; rx = Regex(src); w = 'a' * n
        best = min(_time(lambda: rx.exec(w)) for _ in range(3 if n < 1000 else 1))
        print('  d=%2d n=%5d  %s' % (d, n, ('%.0f us' % (best * 1e6)) if best < 1e-3 else ('%.3f s' % best)))

    try:
        import re2
    except ImportError:
        print('4. RE2: not installed (pip install google-re2)'); return
    print('4. RE2 (search) on the same patterns')
    for d, n in [(2, 20), (8, 4), (8, 100_000), (30, 100_000)]:
        r = re2.compile('(?:' * d + 'a?' + ')+' * d + 'b'); w = 'a' * n
        best = min(_time(lambda: r.search(w)) for _ in range(3))
        print('  d=%2d n=%6d  %.0f us' % (d, n, best * 1e6))
    quiet = re2.Options(); quiet.log_errors = False
    for src in ['a(?=b)', '(?<=a)b']:
        try:
            re2.compile(src, quiet); print('  RE2 accepts %s' % src)
        except Exception:
            print('  RE2 rejects %s' % src)
    print('  RE2: (?:(a)|b)* on ab gives group 1 = %r (JavaScript: undefined)' % re2.search('(?:(a)|b)*', 'ab').group(1))


def _time(f):
    t0 = time.perf_counter(); f(); return time.perf_counter() - t0


if __name__ == '__main__':
    sys.setrecursionlimit(1_000_000)
    run(main)
