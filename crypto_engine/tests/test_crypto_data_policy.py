import hashlib
import json
import unittest

from tmm_core.ingest import IngestionError, validate_approved_kline_payload
from tmm_core.provider_policy import (
    ProviderPolicyError, build_kline_provenance, validate_approved_kline_request,
)
from tmm_core.tokocrypto_klines import KlinePayloadError, normalize_tokocrypto_klines


class TokocryptoNextMePolicyTests(unittest.TestCase):
    URL = "https://www.tokocrypto.site/api/v3/klines?symbol=BTCIDR&interval=1m&limit=100"
    OPEN_MS = 1_700_000_000_000
    CLOSE_MS = OPEN_MS + 59_999
    DECISION_MS = CLOSE_MS + 1_000

    def payload(self, open_ms=None, close_ms=None):
        open_ms = self.OPEN_MS if open_ms is None else open_ms
        close_ms = self.CLOSE_MS if close_ms is None else close_ms
        return {"code": 0, "data": [[open_ms, "10", "12", "9", "11", "5",
                                      close_ms, "55", "7", "2", "1", "0"]]}

    def raw(self, payload=None):
        return json.dumps(self.payload() if payload is None else payload,
                          separators=(",", ":")).encode()

    def test_exact_approved_nextme_request_is_validated_without_io(self):
        result = validate_approved_kline_request(method="GET", url=self.URL)
        self.assertEqual(result["host"], "www.tokocrypto.site")
        self.assertEqual(result["path"], "/api/v3/klines")
        self.assertEqual(result["parameters"]["symbol"], "BTCIDR")
        self.assertEqual(result["authentication"], "NONE")
        self.assertFalse(result["network_action_performed"])

    def test_legacy_and_unapproved_hosts_methods_and_paths_are_rejected(self):
        bad = (
            self.URL.replace("www.tokocrypto.site", "cloudme-toko.2meta.app"),
            self.URL.replace("www.tokocrypto.site", "www.tokocrypto.com"),
            self.URL.replace("www.tokocrypto.site", "example.com"),
            self.URL.replace("/api/v3/klines", "/api/v3/depth"),
            self.URL.replace("/api/v3/klines", "/api/v1/klines"),
            self.URL.replace("https://", "http://"),
            self.URL.replace("www.tokocrypto.site", "www.tokocrypto.site:443"),
            self.URL.replace("www.tokocrypto.site", "user@www.tokocrypto.site"),
        )
        for url in bad:
            with self.subTest(url=url), self.assertRaises(ProviderPolicyError):
                validate_approved_kline_request(method="GET", url=url)
        with self.assertRaises(ProviderPolicyError):
            validate_approved_kline_request(method="POST", url=self.URL)
        with self.assertRaises(ProviderPolicyError):
            validate_approved_kline_request(method="GET", url=self.URL,
                                            headers={"Authorization": "Bearer forbidden"})

    def test_request_url_normalization_and_resource_bounds_fail_closed(self):
        bad_urls = (
            self.URL + "#",
            self.URL + "\n",
            self.URL.replace("interval=1m", "interval=1m\t"),
            self.URL.replace("interval=1m", "interval=١m"),
            self.URL + "&x1=1&x2=2&x3=3",
            self.URL + "&startTime=10000000000000000000",
            self.URL + "&startTime=9999999999999999999",
            self.URL + "&limit=0000000000000000001",
            "https://www.tokocrypto.site/api/v3/klines?" + "x" * 2100,
        )
        for url in bad_urls:
            with self.subTest(url=url[:100]), self.assertRaises(ProviderPolicyError):
                validate_approved_kline_request(method="GET", url=url)

    def test_other_symbols_credentials_and_duplicate_parameters_are_rejected(self):
        for url in (self.URL.replace("BTCIDR", "BTCUSDT"),
                    self.URL + "&apiKey=x", self.URL + "&signature=x",
                    self.URL + "&symbol=BTCIDR", self.URL.replace("1m", "1s")):
            with self.subTest(url=url), self.assertRaises(ProviderPolicyError):
                validate_approved_kline_request(method="GET", url=url)

    def test_provenance_hash_binds_exact_raw_response(self):
        raw = self.raw()
        result = build_kline_provenance(method="GET", url=self.URL,
                                        raw_payload=raw, retrieved_at_ms=1_800_000_000_000)
        self.assertEqual(result["payload_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["payload_bytes"], len(raw))
        self.assertIn("SOURCE_TRUTH_NOT_INDEPENDENTLY_VERIFIED", result["provenance_status"])

    def test_ingestion_accepts_only_closed_btcidr_candles_and_binds_provenance(self):
        raw = self.raw()
        result = validate_approved_kline_payload(
            method="GET", url=self.URL, raw_response=raw,
            retrieved_at_ms=1_800_000_000_000, decision_time_ms=self.DECISION_MS,
            expected_symbol="BTCIDR", expected_interval="1m",
        )
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["coverage_status"], "CONTIGUOUS")
        self.assertEqual(result["candles"][0]["timestamp"], self.CLOSE_MS // 1000)
        self.assertEqual(result["candles"][0]["open_timestamp"], self.OPEN_MS // 1000)
        self.assertEqual(result["provenance"]["payload_sha256"], hashlib.sha256(raw).hexdigest())

    def test_ingestion_rejects_symbol_interval_mismatch_and_oversized_response(self):
        args = dict(method="GET", url=self.URL, raw_response=self.raw(),
                    retrieved_at_ms=1_800_000_000_000, decision_time_ms=self.DECISION_MS,
                    expected_symbol="BTCUSDT", expected_interval="1m")
        with self.assertRaises(IngestionError):
            validate_approved_kline_payload(**args)
        args["expected_symbol"] = "BTCIDR"
        args["expected_interval"] = "5m"
        with self.assertRaises(IngestionError):
            validate_approved_kline_payload(**args)
        args["expected_interval"] = "1m"
        args["raw_response"] = b"x" * (4 * 1024 * 1024 + 1)
        with self.assertRaises(IngestionError):
            validate_approved_kline_payload(**args)

    def test_ingestion_rejects_duplicate_json_keys_invalid_utf8_and_nonstandard_numbers(self):
        base = dict(method="GET", url=self.URL, retrieved_at_ms=1_800_000_000_000,
                    decision_time_ms=self.DECISION_MS, expected_symbol="BTCIDR",
                    expected_interval="1m")
        for raw in (b'{"code":0,"code":0,"data":[]}', b"\xff", b'{"code":NaN,"data":[]}'):
            with self.subTest(raw=raw), self.assertRaises(IngestionError):
                validate_approved_kline_payload(raw_response=raw, **base)

    def test_parser_rejects_still_open_and_malformed_candles(self):
        with self.assertRaises(KlinePayloadError):
            normalize_tokocrypto_klines(self.payload(), decision_time_ms=self.CLOSE_MS)
        bad = self.payload()
        bad["data"][0][2] = "8"
        with self.assertRaises(KlinePayloadError):
            normalize_tokocrypto_klines(bad, decision_time_ms=self.DECISION_MS)


if __name__ == "__main__":
    unittest.main()
