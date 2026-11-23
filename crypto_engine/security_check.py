"""Small static boundary check; not a full SAST or sandbox."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FORBIDDEN_MODULES = {"requests", "httpx", "aiohttp", "ccxt", "web3", "socket",
                     "subprocess", "urllib", "http", "websockets"}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "system", "popen",
                   "Popen", "run", "spawn", "urlopen", "connect", "create_connection"}
errors = []
modules = sorted((ROOT / "tmm_core").glob("*.py"))
for path in modules:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    errors.append(f"{path.name}: forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] in FORBIDDEN_MODULES:
                errors.append(f"{path.name}: forbidden import {node.module}")
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else "")
            if name in FORBIDDEN_CALLS:
                errors.append(f"{path.name}: forbidden call {name}")

config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
required = {
    "mode": "RESEARCH_ONLY",
    "position_mode": "SPOT_LONG_ONLY",
    "live_trading_enabled": False,
    "private_exchange_api_enabled": False,
    "network_enabled": False,
}
for key, expected in required.items():
    if config.get(key) != expected:
        errors.append(f"config.example.json: {key} must equal {expected!r}")

if errors:
    raise SystemExit("\n".join(errors))
print(f"Static boundary check passed for {len(modules)} modules; no network/process imports or calls; RESEARCH_ONLY/SPOT_LONG_ONLY; LIVE, private API and network disabled.")
