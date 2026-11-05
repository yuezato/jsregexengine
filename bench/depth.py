"""How the cost of one CPython call grows with recursion depth: the same number of calls
(two million) at each depth, best of three.  Explains the slope slightly above 1 that the
lazy families show in this prototype, whose walk recurses once per nesting level."""
import sys, time, threading


def main():
    def down(d):
        if d == 0:
            return 0
        return down(d - 1) + 1

    for d in [25, 50, 100, 200, 400, 800, 1600, 3200]:
        R = 2_000_000 // d
        best = float('inf')
        for _ in range(3):
            t0 = time.perf_counter()
            for _ in range(R):
                down(d)
            best = min(best, time.perf_counter() - t0)
        print('depth %5d  %.1f ns/call' % (d, best / (R * d) * 1e9), flush=True)


sys.setrecursionlimit(10 ** 6); threading.stack_size(512 * 1024 * 1024)
t = threading.Thread(target=main); t.start(); t.join()
