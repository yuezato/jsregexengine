"""The examples of the paper, anchored at every start, against V8 (sticky exec).
Examples with a backreference or a counted repeat are left out (unsupported).
Edit EXAMPLES when the paper's examples change."""
import sys
import common
from bitre import Regex, run

BODY = r'(?:(?=(aa))|(a)|aa)'  # the three alternatives in Section 2
LAZY = BODY + r'+?a?b$'
GREEDY = BODY + r'+a?b$'

EXAMPLES = [
    # The same input cursor makes grouping, capturing and testing distinguishable.
    (r'(a)b', 'ab'), (r'(?:a)b', 'ab'), (r'(?=a)b', 'ab'),
    (r'(?=(a+))', 'aaaa'), (r'(?=a)', 'a'), (r'(?=a)', ''),
    (r'(?=b)', 'ab'), (r'(?!b)', 'ab'), (r'(?<=a)', 'ab'), (r'(?<!a)', 'ab'),
    (r'(?<=ab)', 'ab'), (r'(?:)', ''), (r'(?!)', ''),
    (r'()?', ''), (r'()+', ''), (r'(?:aa|a)+?', 'aa'),
    (r'a|aa', 'aa'), (r'(?:a|aa)$', 'aa'),
    (LAZY, 'aab'), (GREEDY, 'aab'), (BODY + '+?', 'aab'),
    (r'(?=(a+))a', 'aaaa'), (r'(?:^a+|a)', 'aaaaa'), (r'a?(?<=()b*)', 'abb'),
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


def check_paper_rows():
    # B filters candidate ends before the matcher selects its preferred result.
    rx = Regex(r'a|aa')
    assert rx.all_starts('aa')[0] == (0, 1, [None])
    rows = rx.all_starts('aa', B={2})
    assert rows == [(0, 2, [None]), (1, 2, [None]), None]
    assert [rx.match_at(x) for x in range(3)] == rows
    assert rows == Regex(r'(?:a|aa)$').all_starts('aa')

    # The two priorities select different final bodies but the same match end.
    assert Regex(LAZY).all_starts('aab') == [
        (0, 3, [None, None, (0, 1)]), (1, 3, [None, None, (1, 2)]), None, None]
    assert Regex(GREEDY).all_starts('aab') == [
        (0, 3, [None, None, (1, 2)]), (1, 3, [None, None, (1, 2)]), None, None]
    assert Regex(BODY + '+?').all_starts('aab')[0] == (0, 0, [None, (0, 2), None])


def main():
    check_paper_rows()
    jobs = [{'pat': p, 'word': w, 'sticky': x} for p, w in EXAMPLES for x in range(len(w) + 1)]
    ours = [m for p, w in EXAMPLES for m in common.anchored(Regex(p), w)]
    bad = [(j, o, t) for j, o, t in zip(jobs, ours, common.v8(jobs)) if o != t]
    for j, o, t in bad[:3]:
        print('MISMATCH', j, '\n  bitre', o, '\n  V8   ', t)
    print('examples: %d patterns, %d starts, anchored matches: %d mismatches with V8' % (len(EXAMPLES), len(jobs), len(bad)))
    return len(bad)


if __name__ == '__main__':
    sys.exit(1 if run(main) else 0)
