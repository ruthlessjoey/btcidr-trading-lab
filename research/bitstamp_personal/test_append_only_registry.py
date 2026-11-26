import json
import unittest

from verify_append_only_registry import (
    GENESIS_GIT_BLOB_SHA1,
    AppendOnlyRegistryError,
    git_blob_sha1,
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
        json.dumps(row, separators=(",", ":")).encode("utf-8") + b"\n"
        for row in rows
    )


def complete_registry():
    return raw_registry([
        event(market, strategy)
        for market in MARKETS
        for strategy in STRATEGIES
    ])


GENESIS = complete_registry()


def verify(base, head, *, genesis=GENESIS):
    return verify_append_only_registry(genesis, base, head)


class AppendOnlyRegistryTests(unittest.TestCase):
    def test_committed_genesis_snapshot_matches_pinned_git_blob(self):
        self.assertEqual(git_blob_sha1(GENESIS), GENESIS_GIT_BLOB_SHA1)

    def test_unchanged_complete_ledger_is_accepted(self):
        result = verify(GENESIS, GENESIS)
        self.assertEqual(result["status"], "APPEND_ONLY_VERIFIED")
        self.assertEqual(result["registered_trial_count"], 14)
        self.assertEqual(result["appended_events"], 0)
        self.assertEqual(result["base_sha256"], result["head_sha256"])

    def test_previous_two_argument_verifier_api_remains_supported(self):
        result = verify_append_only_registry(GENESIS, GENESIS)
        self.assertEqual(result["status"], "APPEND_ONLY_VERIFIED")
        self.assertEqual(result["registered_trial_count"], 14)

    def test_deeply_nested_appended_json_fails_closed_without_traceback(self):
        deeply_nested = b"[" * 10000 + b"0" + b"]" * 10000 + b"\\n"
        with self.assertRaisesRegex(AppendOnlyRegistryError, "semantic validation failed"):
            verify_append_only_registry(GENESIS, GENESIS + deeply_nested)

    def test_complete_new_event_may_be_appended(self):
        appended = raw_registry([
            event("btcusd", "SMA20_50_LONG_ONLY", "FAILED"),
        ])
        result = verify(GENESIS, GENESIS + appended)
        self.assertEqual(result["appended_events"], 1)
        self.assertEqual(result["event_count"], 15)

    def test_rewrite_of_existing_registration_is_rejected(self):
        changed = GENESIS.replace(b"2026-11-27", b"2026-11-26", 1)
        with self.assertRaisesRegex(AppendOnlyRegistryError, "rewrote|rewritten|pinned genesis"):
            verify(GENESIS, changed)

    def test_deletion_or_reordering_of_old_events_is_rejected(self):
        lines = GENESIS.splitlines(keepends=True)
        deleted = b"".join(lines[:-1])
        reordered = b"".join(reversed(lines))
        with self.assertRaisesRegex(AppendOnlyRegistryError, "genesis prefix|truncated"):
            verify(GENESIS, deleted)
        with self.assertRaisesRegex(AppendOnlyRegistryError, "genesis prefix|reordered"):
            verify(GENESIS, reordered)

    def test_partial_or_blank_appended_event_is_rejected(self):
        with self.assertRaisesRegex(AppendOnlyRegistryError, "complete LF-delimited"):
            verify(GENESIS, GENESIS + b'{"trial_id":"partial"}')
        with self.assertRaisesRegex(AppendOnlyRegistryError, "empty event"):
            verify(GENESIS, GENESIS + b"\n")

    def test_invalid_appended_event_is_rejected_by_semantic_parser(self):
        appended = raw_registry([
            event("btcusd", "SMA20_50_LONG_ONLY", "COMPLETED"),
            event("btcusd", "SMA20_50_LONG_ONLY", "FAILED"),
        ])
        with self.assertRaisesRegex(AppendOnlyRegistryError, "terminal trial"):
            verify(GENESIS, GENESIS + appended)

    def test_empty_base_allows_only_the_pinned_complete_genesis_ledger(self):
        result = verify(b"", GENESIS)
        self.assertEqual(result["status"], "APPEND_ONLY_VERIFIED")
        self.assertEqual(result["appended_events"], 14)
        incomplete = raw_registry([event("btcusd", "SMA20_50_LONG_ONLY")])
        with self.assertRaisesRegex(AppendOnlyRegistryError, "genesis prefix"):
            verify(b"", incomplete)

    def test_tampered_genesis_snapshot_fails_even_with_matching_base_and_head(self):
        tampered = GENESIS.replace(b"2026-11-27", b"2026-11-26", 1)
        with self.assertRaisesRegex(AppendOnlyRegistryError, "pinned Git blob SHA-1"):
            verify(tampered, tampered, genesis=tampered)

    def test_base_cannot_omit_or_rewrite_the_pinned_genesis(self):
        base = GENESIS.splitlines(keepends=True)[0]
        head = GENESIS + raw_registry([
            event("btcusd", "SMA20_50_LONG_ONLY", "FAILED"),
        ])
        with self.assertRaisesRegex(AppendOnlyRegistryError, "base registry does not preserve"):
            verify(base, head)

    def test_size_and_line_ending_bounds(self):
        with self.assertRaisesRegex(AppendOnlyRegistryError, "1 MiB"):
            verify(GENESIS, GENESIS, genesis=b"x" * (1024 * 1024 + 1))
        with self.assertRaisesRegex(AppendOnlyRegistryError, "LF-only"):
            verify(GENESIS, GENESIS + b"\r\n")


if __name__ == "__main__":
    unittest.main()
