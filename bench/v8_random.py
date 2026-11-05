"""Random patterns on which V8 backtracks for a long time.  Regenerates the cases that
tests/test_v8.py would compare (same generator, same seed), but with longer words, and runs
each in V8 with a time limit; prints every case slower than 20 ms, then times bitre on the
cases that reached the limit.
Usage: python3 bench/v8_random.py [SEED COUNT MAXLEN LIMIT_MS]   (default: 2 50000 16 2000)
Set NODE to choose the Node.js binary."""
import json, os, random, subprocess, sys, time
from common import ROOT
import semantics as S
from patterns import random_pattern
from bitre import Regex, run


def main(seed, count, maxlen, limit):
    rng = random.Random(seed); jobs = []
    for _ in range(count):
        src = S.to_js(random_pattern(rng))
        w = ''.join(rng.choice('ab') for _ in range(rng.randint(0, maxlen)))
        jobs.append({'pat': src, 'word': w})
    node = os.environ.get('NODE', 'node')
    version = subprocess.run([node, '--version'], capture_output=True, text=True).stdout.strip()
    out = subprocess.run([node, os.path.join(ROOT, 'bench', 'v8_timed.js'), str(limit), '20'],
                         input=''.join(json.dumps(j) + '\n' for j in jobs),
                         capture_output=True, text=True, check=True).stdout
    slow = [json.loads(line) for line in out.split('\n') if line]
    print('V8 (%s): %d random patterns (seed %d), words of length 0-%d, limit %d ms' % (version, count, seed, maxlen, limit))
    for c in slow:
        print('  #%-6d %-8s %6s ms  %r  on %r' % (c['i'], c['status'], c['ms'], c['pat'], c['word']))
    stopped = [c for c in slow if c['status'] == 'stopped']
    print('%d cases slower than 20 ms, %d stopped at the limit' % (len(slow), len(stopped)))
    for c in stopped:
        rx = Regex(c['pat']); best = float('inf')
        for _ in range(3):
            t0 = time.perf_counter(); rx.exec(c['word']); rx.match_all(c['word'])
            best = min(best, time.perf_counter() - t0)
        print('  bitre on #%d (exec and match_all): %.2f ms' % (c['i'], best * 1e3))


if __name__ == '__main__':
    args = [int(a) for a in sys.argv[1:5]]
    run(main, *(args + [2, 50000, 16, 2000][len(args):]))
