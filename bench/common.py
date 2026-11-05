"""Shared helpers for the benchmarks: import paths, timing, the log-log fit and reporting."""
import json, math, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'reference')]
RESULTS = os.path.join(ROOT, 'results')


def timed(cls, pattern, w, reps):
    """(m, N, t): m = nodes of the parsed pattern, N = |w| + 1, t = best time of exec over reps runs.
    exec builds the bit table for all starts and walks the leftmost match; parsing is not timed."""
    rx = cls(pattern); best = float('inf')
    for _ in range(reps):
        t0 = time.perf_counter(); rx.exec(w); best = min(best, time.perf_counter() - t0)
    return len(rx.kind), len(w) + 1, best


def fit(rows, two_d=True):
    """least squares of log t on (1, log m, log N), or on (1, log N); returns the slopes"""
    X = [[1.0, math.log(m), math.log(N)] if two_d else [1.0, math.log(N)] for m, N, t in rows]
    y = [math.log(t) for m, N, t in rows]
    k = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) for j in range(k)] for i in range(k)]
    b = [sum(r[i] * v for r, v in zip(X, y)) for i in range(k)]
    for i in range(k):
        for j in range(i + 1, k):
            f = A[j][i] / A[i][i]
            A[j] = [a - f * c for a, c in zip(A[j], A[i])]; b[j] -= f * b[i]
    sol = [0.0] * k
    for i in reversed(range(k)):
        sol[i] = (b[i] - sum(A[i][j] * sol[j] for j in range(i + 1, k))) / A[i][i]
    return sol[1:]


def report(label, rows, two_d=True):
    per = [t / (m * N) * 1e9 for m, N, t in rows]
    ms, Ns = sorted({m for m, N, t in rows}), sorted({N for m, N, t in rows})
    if two_d:
        a, b = fit(rows)
        print('%-22s m %4d-%5d  N %5d-%5d  slope in m %.2f, in N %.2f   ns/cell %.0f-%.0f'
              % (label, ms[0], ms[-1], Ns[0], Ns[-1], a, b, min(per), max(per)), flush=True)
    else:
        (b,) = fit(rows, False)
        print('%-22s m %4d        N %5d-%5d  slope in N %.2f                ns/cell %.0f-%.0f'
              % (label, ms[0], Ns[0], Ns[-1], b, min(per), max(per)), flush=True)


def save(name, results):
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, name), 'w') as f:
        json.dump(results, f)
