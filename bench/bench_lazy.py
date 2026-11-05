"""Lazy variants of NNPlus, CDN and Clocks (not in RegElk), and the control experiment.
1. the control matcher (clearing.py) gives the same answers as bitre on random patterns;
2. product-linearity of the lazy families;
3. Clocks and Clocks? timed with clocks (bitre) and with literal clearing (control).
Usage: python3 bench/bench_lazy.py [quick]; the full run writes results/bench_lazy.json."""
import random, sys
from common import timed, report, save
import semantics as S
from patterns import random_pattern
from bitre import Regex, run
from clearing import ClearingRegex
from families import LAZY, REGEX_SIZE


def answers(rx, w):
    return [rx.exec(w), rx.match_all(w)]


def agree(count):
    rng = random.Random(11); bad = 0
    for _ in range(count):
        src = S.to_js(random_pattern(rng))
        w = ''.join(rng.choice('ab') for _ in range(rng.randint(0, 8)))
        bad += answers(Regex(src), w) != answers(ClearingRegex(src), w)
    print('control: %d random patterns, %d disagreements with bitre' % (count, bad), flush=True)


def main(quick):
    agree(300 if quick else 2000)
    results = {}
    ks, ns = ([10, 20, 40], [100, 200, 400]) if quick else ([25, 50, 100, 200, 400], [250, 500, 1000, 2000])
    for name, (fam, gen) in LAZY.items():
        results[name] = rows = [timed(Regex, fam(k), gen(n), 3) for k in ks for n in ns]
        report(name, rows)
    ks, ns = ([10, 20, 40], [100, 200]) if quick else ([20, 40, 80, 160, 320], [250, 500, 1000])
    for name, fam, gen in [('Clocks', REGEX_SIZE['Clocks'][0], REGEX_SIZE['Clocks'][2]),
                           ('Clocks?', LAZY['Clocks?'][0], LAZY['Clocks?'][1])]:
        for cls, how in [(Regex, 'clocks'), (ClearingRegex, 'clearing')]:
            results['%s with %s' % (name, how)] = rows = [timed(cls, fam(k), gen(n), 2) for k in ks for n in ns]
            report('%s with %s' % (name, how), rows)
    if not quick:
        save('bench_lazy.json', results)


if __name__ == '__main__':
    run(main, len(sys.argv) > 1 and sys.argv[1] == 'quick')
