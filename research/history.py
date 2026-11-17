"""research/history.py - fail-closed Step 1 gate.

The only currently approved Tokocrypto public routes are server time and candles.
Those routes do not independently establish market identity, while symbol metadata is
not approved. Therefore this module deliberately performs no network requests and
cannot publish a dataset until the owner approves a verifiable market-identity method.
"""
import json
import os
import time
from datetime import datetime, timezone


def run_step1(cfg, out_dir="out", opener=None, sleep=None, local_now=None, previous_root=None):
    now = time.time() if local_now is None else local_now
    generated = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    provider = cfg.get("provider")
    host = cfg.get("host")
    symbol = cfg.get("symbol")
    base_asset = cfg.get("base_asset")
    quote_asset = cfg.get("quote_asset")
    approved_config = (cfg.get("mode") == "read_only" and
                       provider == "tokocrypto" and
                       host == "https://www.tokocrypto.site" and
                       symbol == "BTCUSDT" and base_asset == "BTC" and quote_asset == "USDT")
    reason = (
        "Market identity is unverified: the currently approved public API scope permits only "
        "server-time and candle routes, not symbol metadata. Configuration alone is insufficient. "
        "No request was made and no dataset was written."
        if approved_config else
        "Research configuration is outside the exact approved read-only Tokocrypto BTC/USDT scope. "
        "No request was made and no dataset was written."
    )
    result = {
        "generated_utc": generated,
        "market": {
            "provider": provider, "host": host, "symbol": symbol,
            "base_asset": base_asset, "quote_asset": quote_asset,
            "pair_label": f"{base_asset}/{quote_asset}" if base_asset and quote_asset else None,
            "timeframe": cfg.get("timeframe"), "market_type": "spot",
        },
        "checks": [{"name": "market_identity", "status": "FAIL", "detail": reason}],
        "pages": [],
        "gate": "FAIL",
        "dataset": None,
        "previous": None,
        "coverage": None,
        "exchange_info": None,
        "stop_reason": reason,
        "top_moves": [],
        "backtest_allowed": False,
        "http_log": [],
        "network_requests": 0,
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "dataset_report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    report = (
        "# Research history gate\n\n"
        f"Generated: {generated}\n\n"
        "**GATE: FAIL**\n\n"
        f"{reason}\n\n"
        "- Network requests: 0\n"
        "- Dataset written: no\n"
        "- Backtest allowed: no\n"
    )
    with open(os.path.join(out_dir, "dataset_report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    return 1


if __name__ == "__main__":
    with open("research_config.json", encoding="utf-8") as f:
        config = json.load(f)
    raise SystemExit(run_step1(config))
