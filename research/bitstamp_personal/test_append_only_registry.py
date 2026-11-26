import json
import unittest

from verify_append_only_registry import (
    AppendOnlyRegistryError,
    verify_append_only_registry,
)

PREREG = "BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V2_5FOLD"
MARKETS = ("btcusd", "ethusd", "xrpusd", "dogeusd", "shibusd", "pepeusd", "solusd")
STRATEGIES = ("SMA20_50_LONG_ONLY", "RSI14_MEAN_REVERSION_LONG_ONLY")


def event(market, strategy, name="REGISTERED"):
    return {
        "trial_id": f"{PREREG}:{market}:{strategy}",
        "market_symbol": market,
        "strategy_id": strategy,
        "preregistration_id": PREREG,
        "event": name,
        "registered_date": "2026-11-27",
    }


def raw_registry(rows):
    return b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for row in rows
    )


def complete_registry():
    return raw_registry([
        event(market, strategy)
        for market in MARKETS
        for strategy in STRATEGIES
    ])


class AppendOnlyRegistryTests(unittest.TestCase):
    def test_unchanged_complete_ledger_is_accepted(self):
        raw = complete_registry()
        result = verify_append_only_registry(raw, raw)
        self.assertEqual(result["status"], "APPEND_ONLY_VERIFIED")
        self.assertEqual(result["registered_trial_count"], 14)
        self.assertEqual(result["appended_events"], 0)
        self.assertEqual(result["base_sha256"], result["head_sha256"])

    def test_complete_new_event_may_be_appended(self):
        base = complete_registry()
        appended = raw_registry([
            event("btcusd", "SMA20_50_LONG_ONLY", "FAILED"),
        ])
        result = verify_append_only_registry(base, base + appended)
        self.assertEqual(result["appended_events"], 1)
        self.assertEqual(result["event_count"], 15)

    def test_rewrite_of_existing_registration_is_rejected(self):
        base = complete_registry()
        changed = base.replace(b"2026-11-27", b"2026-11-26", 1)
        with self.assertRaisesRegex(AppendOnlyRegistryError, "rewritten"):
            verify_append_only_registry(base, changed)

    def test_deletion_or_reordering_of_old_events_is_rejected(self):
        base = complete_registry()
        lines = base.splitlines(keepends=True)
        deleted = b"".join(lines[:-1])
        reordered = b"".join(reversed(lines))
        with self.assertRaisesRegex(AppendOnlyRegistryError, "truncated"):
            verify_append_only_registry(base, deleted)
        with self.assertRaisesRegex(AppendOnlyRegistryError, "reordered"):
            verify_append_only_registry(base, reordered)

    def test_partial_or_blank_appended_event_is_rejected(self):
        base = complete_registry()
        with self.assertRaisesRegex(AppendOnlyRegistryError, "complete LF-delimited"):
            verify_append_only_registry(base, base + b'{"trial_id":"partial"}')
        with self.assertRaisesRegex(AppendOnlyRegistryError, "empty event"):
            verify_append_only_registry(base, base + b"\n")

    def test_invalid_appended_event_is_rejected_by_semantic_parser(self):
        base = complete_registry()
        appended = raw_registry([
            event("btcusd", "SMA20_50_LONG_ONLY", "COMPLETED"),
            event("btcusd", "SMA20_50_LONG_ONLY", "FAILED"),
        ])
        with self.assertRaisesRegex(AppendOnlyRegistryError, "terminal trial"):
            verify_append_only_registry(base, base + appended)

    def test_empty_base_allows_only_a_complete_valid_initial_ledger(self):
        head = complete_registry()
        result = verify_append_only_registry(b"", head)
        self.assertEqual(result["status"], "APPEND_ONLY_VERIFIED")
        self.assertEqual(result["appended_events"], 14)
        incomplete = raw_registry([event("btcusd", "SMA20_50_LONG_ONLY")])
        with self.assertRaisesRegex(AppendOnlyRegistryError, "semantic validation failed"):
            verify_append_only_registry(b"", incomplete)

    def test_size_and_line_ending_bounds(self):
        with self.assertRaisesRegex(AppendOnlyRegistryError, "1 MiB"):
            verify_append_only_registry(b"", b"x" * (1024 * 1024 + 1))
        base = complete_registry()
        with self.assertRaisesRegex(AppendOnlyRegistryError, "LF-only"):
            verify_append_only_registry(base, base + b"\r\n")


    def test_deeply_nested_json_fails_closed_without_traceback(self):
        base = complete_registry()
        deeply_nested = b"[" * 10000 + b"0" + b"]" * 10000 + b"\\n"
        with self.assertRaisesRegex(AppendOnlyRegistryError, "semantic validation failed"):
            verify_append_only_registry(base, base + deeply_nested)


if __name__ == "__main__":
    unittest.main()
