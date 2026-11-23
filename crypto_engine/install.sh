#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required")
print(f"Python {sys.version.split()[0]} OK")
PY
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip check
python security_check.py
sh run_tests.sh
python -m compileall -q tmm_core tests
echo "Offline crypto spot core verified; no third-party packages installed."
