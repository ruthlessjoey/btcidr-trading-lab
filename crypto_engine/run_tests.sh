#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
PYTHONPATH=. python -m unittest discover -s tests -v
