"""The examples of the paper, anchored at every start, against V8 (sticky exec).
Examples with a backreference or a counted repeat are left out (unsupported).
Edit EXAMPLES when the paper's examples change."""
import sys
import common
from bitre import Regex, run

EXAMPLES = [
    (r'(?=(a+))a', 'aaaa'),
    (r'(?:()|a)+?', 'a'), (r'(?:()|a)+?$', 'a'),
    (r'(?:(a)?)+', 'aa'), (r'(?:(a)?)+?', 'aa'), (r'(a)*?', 'aa'),
    (r'(a)(b)', 'ab'), (r'((ab))', 'ab'), (r'(((a)a)a)', 'aaaaaa'),
    (r'(?:(a)|b)*b$', 'ab'), (r'(?:(a)|b)*$', 'ab'), (r'(?:(?:|a)(?:(?:|a))?)?', 'aa'),
    (r'(?=(a|aa))aa', 'aa'), (r'(?=(aa|a))aa', 'aa'), (r'(?<=(a+)(a+))b', 'aaab'),
    (r'a*a', 'a'),
    (r'(?:|a)+?', 'a'), (r'(?:|a)+', 'a'), (r'(?:a|)+?', 'a'), (r'(?:a|)+', 'a'),
]
# the nine optional/lazy/greedy combinations, alone and followed by four tests
FORMS = ['a', 'a+?', 'a+', 'a??', '(?:a+?)??', '(?:a+)??', 'a?', '(?:a+?)?', '(?:a+)?']
EXAMPLES += [('^' + f + s, 'aa') for f in FORMS for s in ['', '^', '$', '(?<=a)', '(?=a)']]


def main():
    jobs = [{'pat': p, 'word': w, 'sticky': x} for p, w in EXAMPLES for x in range(len(w) + 1)]
    ours = [m for p, w in EXAMPLES for m in common.anchored(Regex(p), w)]
    bad = [(j, o, t) for j, o, t in zip(jobs, ours, common.v8(jobs)) if o != t]
    for j, o, t in bad[:3]:
        print('MISMATCH', j, '\n  bitre', o, '\n  V8   ', t)
    print('examples: %d patterns, %d starts, anchored matches: %d mismatches with V8' % (len(EXAMPLES), len(jobs), len(bad)))
    return len(bad)


if __name__ == '__main__':
    sys.exit(1 if run(main) else 0)
