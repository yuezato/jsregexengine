"""Check the benchmark's task agreement, censoring and error propagation."""
import subprocess
import unittest

from demo import ENV, NODE, ROOT, FLAGS, node_job


class MeasurementTests(unittest.TestCase):
    def job(self, suite, engine, **changes):
        return node_job(dict(suite=suite, engine=engine, n=5, depth=3,
                             repeats=1, warmups=0, timeout_ms=500) | changes, FLAGS)

    def test_global_outputs(self):
        # The worker checks every interval, including the empty input.
        for n in [0, 3, 32]:
            for engine in ['index', 'v8', 'v8-linear']:
                row = node_job(dict(suite='global', engine=engine, n=n, depth=3,
                                    repeats=1, warmups=0, timeout_ms=500), FLAGS)
                self.assertEqual(row['status'], 'ok')
                self.assertTrue(row['verified'])
                self.assertEqual(len(row['samples_ms']), 1)
                self.assertGreater(row['median_ms'], 0)

    def test_product_and_search(self):
        for suite, engine in [('product', 'index'), ('backtracking', 'index'),
                              ('backtracking', 'v8'), ('backtracking', 'v8-linear')]:
            row = self.job(suite, engine)
            self.assertEqual(row['status'], 'ok')
            self.assertEqual(row['mN'], row['m'] * row['N'])
            self.assertTrue(row['verified'])

    def test_matching_timeout_is_censored(self):
        for warmups in [0, 1]:
            row = node_job(dict(suite='backtracking', engine='v8', n=20, depth=3,
                                repeats=1, warmups=warmups, timeout_ms=50), FLAGS)
            self.assertEqual(row['status'], 'timeout')
            self.assertEqual(row['phase'], 'warmup' if warmups else 'measurement')
            self.assertIsNone(row['median_ms'])
            self.assertEqual(row['samples_ms'], [])

    def test_unsupported_is_separate(self):
        # Without the engine flag, rejection must not become a time or a timeout.
        row = node_job(dict(suite='admission', engine='v8-linear', depth=3), ['--expose-gc'])
        self.assertEqual(row['status'], 'unsupported')
        self.assertIsNone(row['median_ms'])
        self.assertIn('reason', row)

    def test_invalid_job_fails(self):
        with self.assertRaises(RuntimeError):
            node_job(dict(suite='product', engine='index', n=-1), FLAGS)

    def test_plot_excludes_censored_runs(self):
        from plots import completed
        rows = [dict(status='ok', N=8, median_ms=2),
                dict(status='timeout', N=16, median_ms=None, timeout_ms=1500),
                dict(status='unsupported', N=32, median_ms=None),
                dict(status='not-run', N=64, median_ms=None)]
        self.assertEqual(completed(rows), rows[:1])


if __name__ == '__main__':
    probe = subprocess.run([NODE, *FLAGS, '-e', 'new RegExp("a", "l")'], cwd=ROOT,
                           env=ENV, text=True, capture_output=True)
    if probe.returncode:
        raise SystemExit('These harness tests require Node with the experimental regexp engine.')
    unittest.main()
