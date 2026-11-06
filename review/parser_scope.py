"""Optional diagnostic for CPython's raw-source front end (outside the paper's input model)."""
from pathlib import Path
import re._parser as parser
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitre import Regex


def measure(length):
    # In CPython 3.12.14 SubPattern.__delitem__ performs del self.data[index].
    # Count the list entries following each removed first item.
    counts = [0, 0]
    delete_code = parser.SubPattern.__delitem__.__code__

    def profile(frame, event, arg):
        if event == 'call' and frame.f_code is delete_code and frame.f_locals['index'] == 0:
            counts[0] += 1
            counts[1] += len(frame.f_locals['self'].data) - 1

    source = 'a' * length + 'b|' + 'a' * length + 'c'
    original = sys.getprofile()
    try:
        sys.setprofile(profile)
        regex = Regex(source)
    finally:
        sys.setprofile(original)
    assert regex.all_starts('') == [None]
    return (len(regex.kind), *counts)


if __name__ == '__main__':
    print(sys.version.split()[0], 'common-prefix length, parsed nodes, deletions, trailing entries')
    for length in [32, 64, 128, 256, 512]:
        print(length, *measure(length))
