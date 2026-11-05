"""exec split into the sweep (building the bit table) and the walk (the leftmost match),
with the number of walk calls, for every regex-size family.
Usage: python3 bench/bench_split.py [quick]; the full run writes results/bench_split.json."""
import sys, time
from common import fit, save
from bitre import Regex, run, ABIT
from families import REGEX_SIZE, LAZY


class Counting(Regex):
    calls = 0

    def _walk(self, v, x, full):
        self.calls += 1
        return super()._walk(v, x, full)


def first(rx, w):
    return next((x for x in range(len(w) + 1) if rx._bit(rx.root, x, ABIT)), None)


def measure(pattern, w, reps):
    rx = Regex(pattern); ts = tw = float('inf')
    for _ in range(reps):
        t0 = time.perf_counter(); rx.index(w); t1 = time.perf_counter()
        x = first(rx, w)
        t2 = time.perf_counter()
        if x is not None:
            rx.match_at(x)
        t3 = time.perf_counter()
        ts, tw = min(ts, t1 - t0), min(tw, t3 - t2)
    cx = Counting(pattern).index(w); x = first(cx, w)
    if x is not None:
        cx.match_at(x)
    return len(rx.kind), len(w) + 1, ts, tw, cx.calls


def main(quick):
    ks, ns = ([10, 20, 40], [100, 200, 400]) if quick else ([25, 50, 100, 200, 400], [250, 500, 1000, 2000])
    fams = [(name, fam, gen) for name, (fam, _, gen) in REGEX_SIZE.items()] + \
           [(name, fam, gen) for name, (fam, gen) in LAZY.items()]
    results = {}
    for name, fam, gen in fams:
        results[name] = rows = [measure(fam(k), gen(n), 2) for k in ks for n in ns]
        a, b = fit([(m, N, ts) for m, N, ts, tw, c in rows])
        cell = [ts / (m * N) * 1e9 for m, N, ts, tw, c in rows]
        cpc = [c / (m * N) for m, N, ts, tw, c in rows]
        npc = [tw / c * 1e9 for m, N, ts, tw, c in rows if c > 1000]
        share = max(tw / (ts + tw) for m, N, ts, tw, c in rows)
        print('%-8s sweep: slope m %.2f N %.2f, %3.0f-%3.0f ns/cell | walk: %.3f-%.3f calls/cell, %s ns/call, at most %2.0f%% of exec'
              % (name, a, b, min(cell), max(cell), min(cpc), max(cpc),
                 '%.0f-%.0f' % (min(npc), max(npc)) if npc else '  -  ', 100 * share), flush=True)
    if not quick:
        save('bench_split.json', results)


if __name__ == '__main__':
    run(main, len(sys.argv) > 1 and sys.argv[1] == 'quick')
