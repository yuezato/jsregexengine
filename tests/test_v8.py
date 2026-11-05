"""bitre's exec and matchAll against V8 on random patterns.
Usage: python3 tests/test_v8.py SEED COUNT MAXLEN"""
import random, sys
import common
import semantics as S
from patterns import random_pattern
from bitre import Regex, run


def main(seed, count, maxlen):
    rng = random.Random(seed); jobs, ours = [], []
    for _ in range(count):
        src = S.to_js(random_pattern(rng))
        w = ''.join(rng.choice('ab') for _ in range(rng.randint(0, maxlen)))
        jobs.append({'pat': src, 'word': w}); ours.append(common.answers(Regex(src), w))
    bad = [(j, o, t) for j, o, t in zip(jobs, ours, common.v8(jobs)) if o != t]
    for j, o, t in bad[:3]:
        print('MISMATCH', j, '\n  bitre', o, '\n  V8   ', t)
    print('V8 (%s): %d random patterns, exec and matchAll: %d mismatches' % (common.node_version(), count, len(bad)))
    return len(bad)


if __name__ == '__main__':
    sys.exit(1 if run(main, int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])) else 0)
