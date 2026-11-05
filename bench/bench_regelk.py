"""Product-linearity on the benchmark families of RegElk (families.py).
For each instance, times exec (bit table for all starts + leftmost match with captures), best of 3,
and fits log t = c + a log m + b log N.  Usage: python3 bench/bench_regelk.py [quick]
The full run writes results/bench_regelk.json; quick runs smaller sizes and writes nothing."""
import sys
from common import timed, report, save
from bitre import Regex, run
from families import REGEX_SIZE, STRING_SIZE


def main(quick):
    ks, ns = ([10, 20, 40], [100, 200, 400]) if quick else ([25, 50, 100, 200, 400], [250, 500, 1000, 2000])
    ns_string = [500, 1000, 2000] if quick else [1000, 2000, 4000, 8000, 16000, 32000, 64000]
    results = {}
    for name, (fam, _, gen) in REGEX_SIZE.items():
        results[name] = rows = [timed(Regex, fam(k), gen(n), 3) for k in ks for n in ns]
        report(name, rows)
    for name, (pattern, gen) in STRING_SIZE.items():
        results[name] = rows = [timed(Regex, pattern, gen(n), 3) for n in ns_string]
        report(name, rows, two_d=False)
    if not quick:
        save('bench_regelk.json', results)


if __name__ == '__main__':
    run(main, len(sys.argv) > 1 and sys.argv[1] == 'quick')
