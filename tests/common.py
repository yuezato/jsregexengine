"""Shared helpers for the tests: import paths, the V8 runner and result normalization.
Set the environment variable NODE to choose the Node.js binary (default: node)."""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'reference')]
NODE = os.environ.get('NODE', 'node')


def norm(m):
    """bitre's (start, end, slots) as v8_run.js prints a match"""
    return None if m is None else [m[0], m[1]] + [list(s) if s else None for s in m[2][1:]]


def answers(rx, w):
    """exec and matchAll, as v8_run.js prints them"""
    return [norm(rx.exec(w)), [norm(m) for m in rx.match_all(w)]]


def anchored(rx, w):
    """the match anchored at every start, as v8_run.js prints sticky matches"""
    rx.index(w)
    return [norm(rx.match_at(x)) for x in range(len(w) + 1)]


def v8(jobs):
    """jobs: dicts {pat, word, flags?, sticky?}; returns V8's answer for each"""
    inp = ''.join(json.dumps(j) + '\n' for j in jobs)
    out = subprocess.run([NODE, os.path.join(ROOT, 'tests', 'v8_run.js')], input=inp,
                         capture_output=True, text=True, check=True).stdout.split('\n')
    return [json.loads(line) for line in out[:len(jobs)]]


def node_version():
    return subprocess.run([NODE, '--version'], capture_output=True, text=True).stdout.strip()
