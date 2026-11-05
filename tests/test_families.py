"""Every benchmark family (families.py) at small sizes: exec and matchAll against V8."""
import sys
import common
from bitre import Regex, run
from families import REGEX_SIZE, STRING_SIZE, LAZY


def instances():
    for name, (fam, _, gen) in REGEX_SIZE.items():
        for k in range(1, 6):
            for n in range(1, 11):
                yield fam(k), gen(n)
    for name, (pattern, gen) in STRING_SIZE.items():
        for n in range(2, 16):
            yield pattern, gen(n)
    for name, (fam, gen) in LAZY.items():
        for k in range(1, 6):
            for w in [gen(n) for n in range(0, 10)] + ['b', 'ab', 'ba', 'aab']:
                yield fam(k), w


def main():
    cases = list(instances())
    jobs = [{'pat': p, 'word': w} for p, w in cases]
    ours = [common.answers(Regex(p), w) for p, w in cases]
    bad = [(j, o, t) for j, o, t in zip(jobs, ours, common.v8(jobs)) if o != t]
    for j, o, t in bad[:3]:
        print('MISMATCH', j, '\n  bitre', o, '\n  V8   ', t)
    print('families: %d instances (RegElk families and lazy variants), exec and matchAll: %d mismatches with V8'
          % (len(cases), len(bad)))
    return len(bad)


if __name__ == '__main__':
    sys.exit(1 if run(main) else 0)
