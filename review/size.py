"""Physical source lines in the complete, runnable Theorem 1.2 implementation."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'paper' / 'index'
IMPORT = re.compile(r"""\bfrom\s+['"]([^'"]+)['"]""")


def index_modules():
    """Follow every relative module import/re-export from the documented entry point."""
    files = set()
    pending = [INDEX / 'word_index.mjs']
    while pending:
        file = pending.pop()
        if file in files:
            continue
        files.add(file)
        for specifier in IMPORT.findall(file.read_text()):
            if not specifier.startswith('.'):
                raise ValueError(f'Additional dependency of {file.name}: {specifier}')
            pending.append((file.parent / specifier).resolve())
    if files != set(INDEX.glob('*.mjs')):
        raise ValueError('The directory and the dependencies of the index disagree')
    return sorted(files)


def counts(file):
    lines = file.read_text().splitlines()
    comment = '//' if file.suffix == '.mjs' else '#'
    code = sum(bool(line.strip()) and not line.lstrip().startswith(comment) for line in lines)
    return len(lines), code


def show(files):
    physical = code = 0
    for file in files:
        size, used = counts(file)
        physical += size
        code += used
        print(f'{str(file.relative_to(ROOT)):30} {size:>8} {used:>8}')
    return physical, code


if __name__ == '__main__':
    print('file                           physical     code')
    physical, code = show(index_modules())
    print(f'{"Theorem 1.2, full dependency set":30} {physical:>8} {code:>8}')
    print()
    print('Other components (each whole file, shown separately)')
    show([ROOT / 'paper/bit_walk.mjs', ROOT / 'regex_syntax.py', ROOT / 'bitre.py', ROOT / 'bitcolumns.py'])
