"""All anchored rows on overlapping assertions. Usage: python3 bench/bench_batch.py [quick]"""
import sys
from time import perf_counter
import common  # sets the repository import path
from bitre import Regex


class CountedRegex(Regex):
    walk_calls = 0
    moving_cells = 0

    def _walk(self, v, x, full):
        self.walk_calls += 1
        return super()._walk(v, x, full)

    def _column(self, v, moving, size):
        self.moving_cells += self.N
        return super()._column(v, moving, size)


def compare(family, groups, n):
    body = '(' * groups + 'a+' + ')' * groups
    if family == 'behind':
        pattern = '(?<=' + body + ')'
    else:
        if family == 'atomic':
            body = '(?>' + body + ')'
        pattern = '(?=' + body + ')a'
    word = 'a' * n
    rx = CountedRegex(pattern)
    t0 = perf_counter()
    batch = rx.all_starts(word)
    elapsed_batch = perf_counter() - t0
    cells = rx.moving_cells
    assert rx.walk_calls == 0
    t0 = perf_counter()
    rx.index(word)
    replay = [rx.match_at(x) for x in range(n+1)]
    elapsed_walk = perf_counter() - t0
    assert batch == replay
    for x, row in enumerate(batch):
        if family == 'behind':
            expected = (x, x, [None] + [(0, x)] * groups) if x else None
        else:
            expected = (x, x+1, [None] + [(x, n)] * groups) if x < n else None
        assert row == expected
    return len(rx.kind), cells, rx.walk_calls, elapsed_batch, elapsed_walk


def main(quick):
    depths = [1, 9] if quick else [1, 8, 24]
    sizes = [32, 64, 128] if quick else [64, 128, 256, 512]
    print('Python', sys.version.split()[0], '(timings in ms; both start after pattern preparation and include text indexing)')
    print('family groups m N moving_cells replay_walk_calls batch_ms replay_ms')
    for family in ('ahead', 'behind', 'atomic'):
        for g in depths:
            for n in sizes:
                m, cells, calls, batch, replay = compare(family, g, n)
                print(f'{family} {g} {m} {n+1} {cells} {calls} {1000*batch:.2f} {1000*replay:.2f}')


if __name__ == '__main__':
    main(sys.argv[1:] == ['quick'])
