import copy
import json
import unittest

from point_in_time_universe import (
    PointInTimeUniverseError,
    evidence_payload_sha256,
    verify_point_in_time_universe_evidence,
)

SYMBOLS = ("btcusd", "ethusd", "xrpusd", "dogeusd", "shibusd", "pepeusd", "solusd")
START = 1704067200
END = 1793491200
STEP = 3600


def valid_manifest():
    sources = [
        {"source_id": "listing", "evidence_type": "LISTING_NOTICE",
         "url": "https://blog.bitstamp.net/test-listing", "published_date": "2024-01-01",
         "claim": "Synthetic verified listing snapshot for unit tests.",
         "snapshot_sha256": "a" * 64},
        {"source_id": "status", "evidence_type": "MARKET_STATUS_LEDGER",
         "url": "https://www.bitstamp.net/test-status", "published_date": "2026-11-01",
         "claim": "Synthetic verified historical status ledger for unit tests.",
         "snapshot_sha256": "b" * 64},
        {"source_id": "rights", "evidence_type": "DATA_RIGHTS",
         "url": "https://www.bitstamp.net/test-rights", "published_date": "2026-11-01",
         "claim": "Synthetic accepted personal research rights record for unit tests.",
         "snapshot_sha256": "c" * 64},
    ]
    markets = []
    for symbol in SYMBOLS:
        listing = START - 100 * STEP
        matching = START - 90 * STEP
        market_orders = START - 80 * STEP
        pair = symbol[:-3].upper() + "/" + symbol[-3:].upper()
        markets.append({
            "market_symbol": symbol, "pair": pair,
            "market_type": "SPOT", "global_scope": "GLOBAL_PUBLIC_MARKET",
            "listing_announcement_date": "2023-01-01",
            "first_listing_timestamp": listing,
            "first_matching_enabled_timestamp": matching,
            "first_market_orders_enabled_timestamp": market_orders,
            "eligible_start_timestamp": START,
            "limit_only_matching_from_timestamp": None,
            "jurisdictional_notes": [],
            "source_ids": ["listing", "status"],
            "status_intervals": [{
                "start_timestamp": START, "end_timestamp": END,
                "market_type": "SPOT", "trading": "Enabled",
                "matching": "Enabled", "instant_and_market_orders": "Enabled",
                "source_ids": ["status"],
            }],
        })
    manifest = {
        "schema_version": 1,
        "preregistration_id": "BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V2",
        "candidate_symbols": list(SYMBOLS),
        "requested_window": {
            "start_timestamp": START, "end_timestamp": END,
            "interval_seconds": STEP,
        },
        "date_policy": {
            "status": "APPROVED", "mode": "COMMON_START",
            "decision_note": "Synthetic test fixture only.",
        },
        "data_rights": {
            "status": "APPROVED_PERSONAL_NONCOMMERCIAL",
            "scope": "PERSONAL_NONCOMMERCIAL_SPOT_RESEARCH",
            "source_ids": ["rights"],
        },
        "independent_review": {"status": "NOT_YET_SET", "reviewers": []},
        "source_evidence": sources, "markets": markets,
    }
    digest = evidence_payload_sha256(manifest)
    manifest["independent_review"] = {
        "status": "ACCEPTED",
        "reviewers": [
            {"reviewer_id": "reviewer-a", "status": "ACCEPTED",
             "reviewed_evidence_sha256": digest, "reviewed_market_status": True,
             "reviewed_data_rights": True},
            {"reviewer_id": "reviewer-b", "status": "ACCEPTED",
             "reviewed_evidence_sha256": digest, "reviewed_market_status": True,
             "reviewed_data_rights": True},
        ],
    }
    return manifest


def verify_fixture(manifest):
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode()
    return verify_point_in_time_universe_evidence(
        raw, expected_sha256=evidence_payload_sha256(manifest),
    )


class PointInTimeUniverseTests(unittest.TestCase):
    def test_accepts_complete_reviewed_evidence(self):
        manifest = valid_manifest()
        result = verify_fixture(manifest)
        self.assertEqual(result["market_count"], 7)
        self.assertTrue(result["rights_verified"])
        self.assertTrue(result["independent_review_accepted"])
        self.assertEqual(set(result["eligible_start_by_symbol"]), set(SYMBOLS))

    def test_unpinned_or_mismatched_digest_fails_closed(self):
        manifest = valid_manifest()
        raw = json.dumps(manifest).encode()
        with self.assertRaisesRegex(PointInTimeUniverseError, "digest is not pinned"):
            verify_point_in_time_universe_evidence(raw, expected_sha256=None)
        with self.assertRaisesRegex(PointInTimeUniverseError, "does not match"):
            verify_point_in_time_universe_evidence(raw, expected_sha256="0" * 64)

    def test_unresolved_date_policy_and_pepe_common_start_conflict_fail(self):
        manifest = valid_manifest()
        manifest["date_policy"]["status"] = "NOT_SELECTED"
        with self.assertRaisesRegex(PointInTimeUniverseError, "date policy decision"):
            verify_fixture(manifest)
        manifest = valid_manifest()
        pepe = next(m for m in manifest["markets"] if m["market_symbol"] == "pepeusd")
        pepe["first_listing_timestamp"] = START + 100 * STEP
        pepe["first_matching_enabled_timestamp"] = START + 101 * STEP
        pepe["first_market_orders_enabled_timestamp"] = START + 102 * STEP
        with self.assertRaisesRegex(PointInTimeUniverseError, "not fully eligible"):
            verify_fixture(manifest)

    def test_per_market_inception_must_follow_full_market_order_time(self):
        manifest = valid_manifest()
        manifest["date_policy"]["mode"] = "PER_MARKET_INCEPTION"
        pepe = next(m for m in manifest["markets"] if m["market_symbol"] == "pepeusd")
        listing = START + 100 * STEP
        matching = listing + 1
        market_orders = listing + 2
        eligible = ((market_orders + STEP - 1) // STEP) * STEP
        pepe["first_listing_timestamp"] = listing
        pepe["first_matching_enabled_timestamp"] = matching
        pepe["first_market_orders_enabled_timestamp"] = market_orders
        pepe["eligible_start_timestamp"] = eligible
        pepe["status_intervals"] = [{
            "start_timestamp": eligible, "end_timestamp": END,
            "market_type": "SPOT", "trading": "Enabled",
            "matching": "Enabled", "instant_and_market_orders": "Enabled",
            "source_ids": ["status"],
        }]
        result = verify_fixture(manifest)
        self.assertEqual(result["eligible_start_by_symbol"]["pepeusd"], eligible)
        pepe["eligible_start_timestamp"] = eligible + STEP
        pepe["status_intervals"][0]["start_timestamp"] = eligible + STEP
        with self.assertRaisesRegex(PointInTimeUniverseError, "does not follow full-order eligibility"):
            verify_fixture(manifest)

    def test_limit_only_does_not_supply_market_order_enable_timestamp(self):
        manifest = valid_manifest()
        shib = next(m for m in manifest["markets"] if m["market_symbol"] == "shibusd")
        shib["first_market_orders_enabled_timestamp"] = None
        with self.assertRaisesRegex(PointInTimeUniverseError, "Unix timestamp"):
            verify_fixture(manifest)

    def test_status_history_must_be_contiguous_enabled_and_reach_end(self):
        mutations = (
            (lambda m: m["markets"][0]["status_intervals"].clear(), "no historical"),
            (lambda m: m["markets"][0]["status_intervals"][0].update(end_timestamp=END-STEP), "does not reach"),
            (lambda m: m["markets"][0]["status_intervals"][0].update(matching="Disabled"), "disabled interval"),
            (lambda m: m["markets"][0]["status_intervals"][0].update(instant_and_market_orders="Disabled"), "disabled interval"),
            (lambda m: m["markets"][0]["status_intervals"][0].update(start_timestamp=START+STEP), "gap, overlap"),
        )
        for mutate, expected in mutations:
            manifest = valid_manifest()
            mutate(manifest)
            with self.subTest(expected=expected), self.assertRaisesRegex(PointInTimeUniverseError, expected):
                verify_fixture(manifest)

    def test_intervals_require_official_status_ledger_snapshots(self):
        manifest = valid_manifest()
        manifest["source_evidence"][1]["evidence_type"] = "API_SEMANTICS"
        with self.assertRaisesRegex(PointInTimeUniverseError, "not MARKET_STATUS_LEDGER"):
            verify_fixture(manifest)
        manifest = valid_manifest()
        manifest["source_evidence"][1]["snapshot_sha256"] = None
        with self.assertRaisesRegex(PointInTimeUniverseError, "no captured"):
            verify_fixture(manifest)

    def test_source_host_snapshot_and_market_identity_are_checked(self):
        manifest = valid_manifest()
        manifest["source_evidence"][0]["url"] = "https://example.com/fake"
        with self.assertRaisesRegex(PointInTimeUniverseError, "not an official"):
            verify_fixture(manifest)
        manifest = valid_manifest()
        manifest["markets"][0]["pair"] = "ETH/USD"
        with self.assertRaisesRegex(PointInTimeUniverseError, "pair does not match"):
            verify_fixture(manifest)

    def test_rights_need_explicit_acceptance(self):
        manifest = valid_manifest()
        manifest["data_rights"]["status"] = "NOT_VERIFIED"
        with self.assertRaisesRegex(PointInTimeUniverseError, "rights are not"):
            verify_fixture(manifest)

    def test_two_distinct_reviewers_must_accept_same_evidence(self):
        manifest = valid_manifest()
        manifest["independent_review"]["reviewers"][1]["reviewer_id"] = "reviewer-a"
        with self.assertRaisesRegex(PointInTimeUniverseError, "distinct"):
            verify_fixture(manifest)
        manifest = valid_manifest()
        manifest["independent_review"]["reviewers"][1]["reviewed_evidence_sha256"] = "0" * 64
        with self.assertRaisesRegex(PointInTimeUniverseError, "different evidence digest"):
            verify_fixture(manifest)

    def test_duplicate_keys_nonstandard_json_and_size_fail(self):
        with self.assertRaisesRegex(PointInTimeUniverseError, "duplicate JSON key"):
            verify_point_in_time_universe_evidence(
                b'{"schema_version":1,"schema_version":2}', expected_sha256="0" * 64,
            )
        with self.assertRaisesRegex(PointInTimeUniverseError, "non-standard JSON"):
            verify_point_in_time_universe_evidence(b'{"x":NaN}', expected_sha256="0" * 64)
        with self.assertRaisesRegex(PointInTimeUniverseError, "512 KiB"):
            verify_point_in_time_universe_evidence(
                b"x" * (512 * 1024 + 1), expected_sha256="0" * 64,
            )

    def test_wrong_universe_and_window_are_rejected(self):
        manifest = valid_manifest()
        manifest["candidate_symbols"].pop()
        with self.assertRaisesRegex(PointInTimeUniverseError, "candidate universe"):
            verify_fixture(manifest)
        manifest = valid_manifest()
        manifest["requested_window"]["start_timestamp"] += STEP
        with self.assertRaisesRegex(PointInTimeUniverseError, "requested window"):
            verify_fixture(manifest)


if __name__ == "__main__":
    unittest.main()
