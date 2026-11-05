"""Finite differential checks for cut-width columns and stopping forests."""
from bisect import bisect_left
from itertools import product
from random import Random
import common  # repository import paths
from bitcolumns import Colored, Encoding, Tail, _Colors, _Select, positions


def cut_width(row):
    return max((len({y for x, y in enumerate(row)
                     if y is not None and (x <= cut) != (y <= cut)})
                for cut in range(len(row) - 1)), default=0)


def check_maps():
    n_cases = 0
    for n in range(1, 7):
        encoding = Encoding(n)
        for forward in product(*[[None, *range(x, n)] for x in range(n)]):
            reverse = [None if y is None else n-1-y for y in reversed(forward)]
            for direction, row in [(True, forward), (False, reverse)]:
                column = Colored(encoding, n, direction)
                for i in range(n):
                    x = column.order(i)
                    column.release(x)
                    if row[x] is not None:
                        column.put(x, row[x])
                column.finish()
                assert column.palette == cut_width(row)
                for y in range(n):
                    assert column.get(y) == row[y]
                    kids = []
                    child = column.child_after(y, None)
                    while child is not None:
                        kids.append(child)
                        child = column.child_after(y, child)
                    expected = [x for x in range(n) if x != y and row[x] == y]
                    assert kids == (expected if direction else expected[::-1])
                n_cases += 1
    # Simultaneous intervals require more than a byte of color ids. Check
    # the last source at a fixed/strict target as well as the backward code.
    d = 519
    encoding = Encoding(2*d)
    for direction in (True, False):
        def entry(x):
            i = x if direction else 2*d-1-x
            y = i+d if i < d else i
            return y if direction else 2*d-1-y
        col = positions(encoding, 32, direction, entry)
        assert isinstance(col, Colored) and col.palette == d
        for x in range(2*d):
            assert col.get(x) == entry(x)
            if entry(x) != x:
                assert col.child_after(entry(x), None) == x
                assert col.child_after(entry(x), x) is None
    return n_cases


def check_forests():
    cases = 0
    for n in range(1, 6):
        encoding = Encoding(n)
        for forward in product(*[[None, *range(x+1, n)] for x in range(n)]):
            reverse = [None if y is None else n-1-y for y in reversed(forward)]
            for direction, row in [(True, forward), (False, reverse)]:
                nonroots = [x for x in range(n) if row[x] is not None]
                for size in (n, encoding.width**2):
                    parent = positions(encoding, size, direction, row.__getitem__)
                    for mask in range(1 << len(nonroots)):
                        stops = [y is None for y in row]
                        for j, x in enumerate(nonroots):
                            stops[x] = bool(mask & (1 << j))
                        tail = Tail(parent, stops, encoding, size, direction)
                        for x in nonroots:
                            u = x
                            while not stops[row[u]]:
                                u = row[u]
                            assert tail.last(x) == u
                        cases += 1
    return cases


def check_color_text():
    rng = Random(37)
    for n, palette, size in [(1, 0, 1), (38, 3, 4), (239, 27, 9), (5003, 85, 25)]:
        encoding = Encoding(n)
        row = [rng.randrange(palette+1) for _ in range(n)]
        index = _Colors(row, palette, size, encoding)
        for color in range(1, palette+2):
            occurrences = [i for i, c in enumerate(row) if c == color]
            for i in range(0, n+1, max(1, n//270)):
                j = bisect_left(occurrences, i)
                assert index.neighbor(color, i) == (occurrences[j] if j < len(occurrences) else None)
                assert index.neighbor(color, i, True) == (occurrences[j-1] if j else None)

    # Exercise both levels of select spills, partial final groups and word boundaries.
    n = 200_000
    encoding = Encoding(n)
    w = encoding.width
    for step in [1, w+1, 2*w*w]:
        bits = _Select(n, encoding)
        ones = list(range(w-1, n, step))
        for x in ones:
            bits.set(x)
        bits.index(encoding)
        for j, x in enumerate(ones):
            assert bits.select(j) == x
            assert bits.rank(x) == j and bits.rank(x+1) == j+1
        if step == w+1:
            assert bits.spill.prefix[-1] > 0
        if step == 2*w*w:
            assert len(bits.absolute) > 0


if __name__ == '__main__':
    check_color_text()
    print('columns: %d maps and %d forest/stop/encoding cases; all comparisons passed'
          % (check_maps(), check_forests()))
