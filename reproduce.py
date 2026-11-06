"""Generate reviewer plots or check the paper's results; see REPRODUCING.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
NODE = os.environ.get('NODE', 'node')
ENV = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}


def run(args):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run(args, cwd=ROOT, env=ENV, text=True, stdout=subprocess.PIPE,
                          check=True).stdout


def check_files():
    for line in (ROOT / 'review/paper.sha256').read_text().splitlines():
        digest, name = line.split(None, 1)
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('modular edition source differs: ' + name)


def paper_grid():
    reference = (ROOT / 'paper/scaling-measurements.jsonl').read_text().splitlines()
    expected = [json.loads(row) for row in reference]
    for row in expected:
        del row['medianMs'], row['bitsMedianMs']
    actual = [json.loads(row) for row in run([NODE, 'paper/scaling.mjs']).splitlines()]
    assert len(actual) == 9 and actual == expected, 'archived deterministic grid differs'
    print('Paper grid (depth, m, N, mN, ports, selection slots):')
    for row in actual:
        print(' ', row['k'], row['m'], row['N'], row['m'] * row['N'], row['vertices'], row['cells'])
    print('PASS: all deterministic fields in the nine published rows match.')


def batch_counts(output):
    # Drop the environment/header lines and the final two, machine-dependent timings.
    return [(family, *map(int, fields[:5]))
            for family, *fields in (row.split() for row in output.splitlines()[2:])]


def python_control(full):
    args = [sys.executable, 'bench/bench_batch.py']
    actual = batch_counts(run(args if full else args + ['quick']))
    if full:
        expected = batch_counts((ROOT / 'results/batch.txt').read_text())
        assert len(actual) == 36 and actual == expected, 'archived Python work counts differ'
    else:
        assert len(actual) == 18
    print('Overlap control, one group (N, m, batch column entries, replay source visits):')
    for family, groups, m, N, cells, replay in actual:
        assert 2 * m * N <= cells <= 3 * m * N
        if family == 'ahead' and groups == 1:
            n = N - 1
            assert cells == 2 * m * N and replay == n * (n + 11) // 2
            print(' ', N, m, cells, replay)
    print('PASS: all-start answers agree with replay and the closed-form spans.')


def expect_counts(record, fields):
    for key, value in fields.items():
        if record.get(key) != value:
            raise ValueError(f'{key}: expected {value}, got {record.get(key)}')


def full_checks(version):
    # The executable checks compare actual answers. Pin the denominators separately
    # so that dropping test cases cannot silently reproduce the paper's table.
    result = json.loads(run([NODE, 'paper/reference_semantics.mjs']))
    expect_counts(result, dict(three_way_comparisons=521904, guidedRows=521904,
                               atomic_rows=18864, pattern_cases=664, words=16))
    out = run([NODE, 'paper/batch_reporting.mjs'])
    rows = re.search(r'\brows:\s*(\d+)', out)
    forests = re.search(r'Forest/stop-set instances:\s*(\d+)', out)
    assert rows and forests and (int(rows[1]), int(forests[1])) == (23238, 146599)
    checks = [
        ('examples', dict(native_anchored_examples=117, overview_rows=4)),
        ('table_clients', {'global': 960, 'splits': 1920}),
        ('native_chains', dict(native_chain_comparisons=157380, backreference_suffix_comparisons=14560)),
    ]
    for script, expected in checks:
        actual = json.loads(run([NODE, f'paper/{script}.mjs']))
        expect_counts(actual, expected)
        print(' ', json.dumps(actual))
    print(run([sys.executable, 'paper/ordered_rows.py']).strip())
    print(run([sys.executable, 'paper/quantifier_chains.py']).strip())
    admission = run([NODE, '--enable-experimental-regexp-engine', 'paper/v8_admission.mjs'])
    print(admission.strip())
    if version == 'v24.22.1':
        first, second = map(json.loads, admission.splitlines())
        expect_counts(first, {'base': 'a?', 'accepted': list(range(1, 5)), 'rejected': list(range(5, 11))})
        expect_counts(second, {'base': 'a', 'accepted': list(range(1, 11)), 'rejected': []})
    else:
        print('The historical admission ranges above are pinned only on Node v24.22.1.')
    out = run(['sh', 'run_tests.sh'])
    print(out.strip())
    expected = (ROOT / 'results/tests.txt').read_text()
    # The Node version in two labels may vary with the installed runtime.
    normalize = lambda text: re.sub(r'\(v\d+\.\d+\.\d+\)', '(node)', text)
    assert normalize(out) == normalize(expected), 'archived Python suite counts differ'
    packed = re.search(r'^batch: (\d+) anchored atomic rows', out, re.MULTILINE)
    assert packed and int(packed[1]) == 9207, 'packed reporter row count differs'
    print('Validation: 521904 standard JS rows, 18864 atomic rows, 23238 JS reference batch rows, '
          '9207 Python packed rows, 146599 forest/stop-set pairs.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['demo', 'quick', 'full'], nargs='?', default='quick',
                        help='demo: comparison plots; quick/full: deterministic verification')
    parser.add_argument('--profile', choices=['quick', 'full'], help='demo grid size')
    parser.add_argument('--output', type=Path, help='demo output directory')
    parser.add_argument('--timeout-ms', type=int, help='demo limit for one prepared matching call')
    args = parser.parse_args()
    if sys.flags.optimize or os.environ.get('PYTHONOPTIMIZE'):
        parser.error('Run with Python assertions enabled (no -O or PYTHONOPTIMIZE).')
    if sys.version_info < (3, 11):
        parser.error('Use Python 3.11+ for the public Python front end.')
    if args.mode == 'demo':
        check_files()
        demo = [sys.executable, str(ROOT / 'review/demo.py')]
        for name in ['profile', 'output', 'timeout_ms']:
            if getattr(args, name) is not None:
                demo += ['--' + name.replace('_', '-'), str(getattr(args, name))]
        subprocess.run(demo, cwd=ROOT, env=ENV, check=True)
        return
    if any(getattr(args, name) is not None for name in ['profile', 'output', 'timeout_ms']):
        parser.error('--profile, --output and --timeout-ms apply only to demo.')
    version = run([NODE, '--version']).strip()
    if int(version.removeprefix('v').split('.')[0]) < 24:
        parser.error('Use Node.js 24+ (tested with 24.22.1).')
    print(f'Python {sys.version.split()[0]}, Node {version}')
    check_files()
    print(run([sys.executable, 'review/size.py']).strip())
    paper_grid()
    print(run([NODE, 'review/work.mjs']).strip())
    python_control(args.mode == 'full')
    if args.mode == 'full':
        full_checks(version)
    else:
        print(run([NODE, 'paper/examples.mjs']).strip())
        print(run([sys.executable, 'tests/test_examples.py']).strip())
    print('PASS:', args.mode)


if __name__ == '__main__':
    main()
