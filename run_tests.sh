#!/bin/sh
# All correctness tests.  Needs python3 (3.11 or later) and node; set NODE to choose the binary.
set -e
cd "$(dirname "$0")"
python3 tests/test_reference.py 1 100000 7
python3 tests/test_v8.py 2 50000 9
python3 tests/test_families.py
python3 tests/test_examples.py
python3 tests/test_flags.py
python3 tests/test_columns.py
python3 tests/test_batch.py
