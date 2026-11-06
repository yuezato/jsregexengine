"""Generate measured comparison plots, raw samples, and actual work counts."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
NODE = os.environ.get('NODE', 'node')
ENV = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
# Keep the default-V8 baseline independent of an inherited fallback setting.
ENV.pop('NODE_OPTIONS', None)
FLAGS = ['--expose-gc', '--enable-experimental-regexp-engine']
PROFILES = {
    'quick': dict(depths=[4, 8, 16], lengths=[512, 1024, 2048, 4096, 8192],
                  global_lengths=[500, 1000, 2000, 4000], backtracking_lengths=list(range(4, 11)),
                  repeats=5, warmups=5),
    'full': dict(depths=[2, 4, 8, 16, 32], lengths=[1024, 2048, 4096, 8192, 16384, 32768],
                 global_lengths=[500, 1000, 2000, 4000, 8000, 16000], backtracking_lengths=list(range(4, 13)),
                 repeats=11, warmups=5),
}


def command(args, **kwargs):
    result = subprocess.run(args, cwd=ROOT, env=ENV, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, args)) + '\n' + result.stderr + result.stdout)
    return result.stdout


def node_job(job, flags):
    limit = (job.get('warmups', 0) + job.get('repeats', 1)) * job.get('timeout_ms', 1500) / 1000 + 20
    try:
        output = command([NODE, *flags, str(ROOT / 'review/measure.mjs')],
                         input=json.dumps(job), timeout=limit)
    except subprocess.TimeoutExpired as error:
        # A preparation/process failure is not a measured matching timeout.
        raise RuntimeError('Worker did not return a measurement; no timing is recorded.') from error
    return json.loads(output)


def write_csv(path, rows, fields):
    with path.open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def measure(profile, output, timeout_ms):
    version = command([NODE, '--version']).strip()
    if int(version.lstrip('v').split('.')[0]) < 24:
        raise RuntimeError('Use Node.js 24 or later (NODE may name another executable).')
    flags = FLAGS
    probe = subprocess.run([NODE, *flags, '-e', 'new RegExp("a", "l")'],
                           cwd=ROOT, env=ENV, text=True, capture_output=True, timeout=20)
    linear_available = probe.returncode == 0
    if not linear_available:
        flags = ['--expose-gc']
    environment = node_job({'op': 'environment'}, flags)
    environment.update(python=platform.python_version(), system=platform.platform(),
                       cpu=platform.processor(), linear_engine_available=linear_available,
                       linear_probe_error=probe.stderr.strip() if not linear_available else None)
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.exists():
        environment['cpu'] = next((x.split(':', 1)[1].strip() for x in cpuinfo.read_text().splitlines()
                                   if x.startswith('model name')), environment['cpu'])
    try:
        environment['base_commit'] = command(['git', 'rev-parse', 'HEAD']).strip()
        environment['working_tree_modified'] = bool(command(['git', 'status', '--porcelain']).strip())
    except (RuntimeError, FileNotFoundError):
        environment['base_commit'] = None
    names = ['paper/index/pattern.mjs', 'paper/index/layers.mjs', 'paper/index/word_index.mjs',
             'review/demo.py', 'review/measure.mjs', 'review/plots.py', 'review/work.mjs']
    environment['source_sha256'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}
    config = {**PROFILES[profile], 'timeout_ms': timeout_ms, 'profile': profile}
    data = dict(schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(),
                environment=environment, config=config, measurements=[], work=[], admission=[])
    raw = output / 'data.json'

    def checkpoint():
        raw.write_text(json.dumps(data, indent=2) + '\n')

    def run(suite, engine, n, depth=3):
        job = dict(suite=suite, engine=engine, n=n, depth=depth,
                   repeats=config['repeats'], warmups=config['warmups'], timeout_ms=timeout_ms)
        row = node_job(job, flags)
        data['measurements'].append(row)
        checkpoint()
        value = f"{row['median_ms']:.3f} ms" if row['status'] == 'ok' else row['status']
        print(f"  {suite:12} {engine:10} depth={depth:2} n={n:6}: {value}", flush=True)
        return row

    print('1/4  Vary pattern size and text length independently (word index).', flush=True)
    for depth in config['depths']:
        stopped = None
        for n in config['lengths']:
            if stopped:
                data['measurements'].append(dict(suite='product', engine='index', n=n, N=n+1,
                    depth=depth, status='not-run', reason=stopped, samples_ms=[], median_ms=None))
            else:
                row = run('product', 'index', n, depth)
                if row['status'] != 'ok':
                    stopped = f"after {row['status']} at n={n}, depth={depth}"
    for stage, suite, sizes in [(2, 'global', config['global_lengths']),
                                (3, 'backtracking', config['backtracking_lengths'])]:
        print(f'{stage}/4  {suite}: index, V8 default, V8 experimental linear engine.', flush=True)
        stopped = {}
        for n in sizes:
            for engine in ['index', 'v8', 'v8-linear']:
                if engine == 'v8-linear' and not linear_available:
                    stopped[engine] = 'linear engine unavailable in this Node build'
                if engine in stopped:
                    data['measurements'].append(dict(suite=suite, engine=engine, n=n, N=n+1,
                        depth=3 if suite != 'global' else None, status='not-run',
                        reason=stopped[engine], samples_ms=[], median_ms=None))
                    continue
                row = run(suite, engine, n)
                if row['status'] != 'ok':
                    stopped[engine] = f"after {row['status']} at n={n}"
        checkpoint()
    print('4/4  Count executed operations and probe nullable-plus admission.', flush=True)
    text = command([NODE, 'review/work.mjs', '--rows'], timeout=180)
    (output / 'work.txt').write_text(text)
    data['work'] = [json.loads(line) for line in text.splitlines() if line.startswith('{')]
    if len(data['work']) != 63 or 'PASS: 63 ' not in text:
        raise RuntimeError('Incomplete work-count check.')
    for depth in range(1, 11):
        if linear_available:
            data['admission'].append(node_job(dict(suite='admission', engine='v8-linear', depth=depth), flags))
        else:
            data['admission'].append(dict(depth=depth, status='unavailable'))
    data['complete'] = True
    checkpoint()
    write_csv(output / 'measurements.csv', data['measurements'],
              ['suite', 'engine', 'depth', 'm', 'n', 'N', 'mN', 'status', 'median_ms', 'timeout_ms', 'phase', 'reason'])
    write_csv(output / 'work.csv', data['work'],
              ['family', 'depth', 'm', 'N', 'mN', 'selectCalls', 'pops', 'predecessors', 'emitted', 'traceVisits'])
    write_csv(output / 'admission.csv', data['admission'], ['depth', 'm', 'status', 'reason'])
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, default='quick')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/reviewer-demo')
    parser.add_argument('--timeout-ms', type=int, default=1500, help='cap for one prepared matching call')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error('Use Python 3.11 or later.')
    if args.timeout_ms < 1:
        parser.error('--timeout-ms must be positive.')
    try:
        import matplotlib
    except ImportError:
        parser.error('Install the plotting dependency: python3 -m pip install -r review/requirements.txt')
    from plots import render
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    data = measure(args.profile, output, args.timeout_ms)
    data['environment']['matplotlib'] = matplotlib.__version__
    data['elapsed_seconds'] = time.perf_counter() - start
    (output / 'data.json').write_text(json.dumps(data, indent=2) + '\n')
    render(data, output)
    print(f"PASS: every completed measurement checked; 63 work-count instances passed.\n"
          f"Open {output / 'index.html'}\nRaw samples: {output / 'data.json'}", flush=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, FileNotFoundError) as error:
        raise SystemExit(str(error))
