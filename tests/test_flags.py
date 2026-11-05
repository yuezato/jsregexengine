"""JavaScript-specific primitives against V8: the i, m and s flags, \\d \\w \\s \\b, case folding.
A case that this Node.js rejects (for example the (?i:...) modifier before Node 23) is skipped."""
import sys
import common
from bitre import Regex, run

CASES = [(r'^\w+$', 'm', 'ab\ncd'), (r'^(\w)', 'm', 'x\ny\nz'), (r'a.c', '', 'a\nc abc'), (r'a.c', 's', 'a\nc'),
         (r'[A-Z]+', 'i', 'xAbCy'), (r'(?i:a)b', '', 'AB Ab ab'), (r'\d+(\s)\D', '', 'x12 y'), (r'\bfoo\B', '', 'foo fool'),
         (r'[^\d\s]+', '', '12 ab3'), (r'(\w+)\s(?=(\w+))', '', 'hello big world'), (r'(?<!\d)(\d)', '', 'a1 22'),
         (r'k', 'i', 'K'), (r'[à-ÿ]+', 'i', 'xÀÉy'), (r'(a|b)*?c', '', 'ababc')]


def main():
    jobs = [{'pat': p, 'word': w, 'flags': f} for p, f, w in CASES]
    bad = skipped = 0
    for (p, f, w), theirs in zip(CASES, common.v8(jobs)):
        if isinstance(theirs, dict):
            skipped += 1; print('SKIP', p, f, '--', theirs['error']); continue
        ours = common.answers(Regex(p, f), w)
        if ours != theirs:
            bad += 1; print('MISMATCH', p, f, repr(w), '\n  bitre', ours, '\n  V8   ', theirs)
    print('flags and classes (%s): %d cases, %d skipped, %d mismatches with V8'
          % (common.node_version(), len(CASES), skipped, bad))
    return bad


if __name__ == '__main__':
    sys.exit(1 if run(main) else 0)
