"""Safe regression tests for provider-controlled errors and report sinks.

This module imports only fetcher, providers, and research.crosscheck. It does not
import live_check, validator, report, dataset, or any protected module.
"""
import io
import json
import os
import tempfile
import unittest
import urllib.error

import fetcher
import providers
from research import crosscheck

MARKER = "UNTRUSTED_PROVIDER_MARKER_7f3a9c"
CANDLE_URL = ("https://www.tokocrypto.site/api/v3/klines?"
              "symbol=BTCUSDT&interval=1h&startTime=1700000000000&endTime=1700003599999&limit=500")
NO_SLEEP = lambda seconds: None


def scripted(*answers):
    calls = []

    def opener(url, timeout):
        calls.append((url, timeout))
        answer = answers[min(len(calls) - 1, len(answers) - 1)]
        if isinstance(answer, Exception):
            raise answer
        return answer

    opener.calls = calls
    return opener


class UntrustedInt(int):
    def __str__(self):
        return MARKER


class TrackedHTTPError(urllib.error.HTTPError):
    def __init__(self, code=404):
        super().__init__(CANDLE_URL, code, "Not Found", {}, io.BytesIO(MARKER.encode()))
        self.closed_by_test = False
        self.read_called = False

    def read(self, *args, **kwargs):
        self.read_called = True
        raise AssertionError("HTTP error body must never be read")

    def close(self):
        self.closed_by_test = True
        super().close()


class FetcherSanitizationTests(unittest.TestCase):
    def test_transport_errors_never_echo_provider_text_or_url(self):
        cases = (
            (scripted((451, MARKER.encode())), 1),
            (scripted((500, MARKER.encode()), (500, MARKER.encode())), 2),
            (scripted(urllib.error.URLError(MARKER)), 2),
            (scripted(RuntimeError(MARKER)), 1),
        )
        for opener, retries in cases:
            with self.subTest(retries=retries), self.assertRaises(fetcher.ApiError) as ctx:
                fetcher.http_get_json(CANDLE_URL, 5, retries, opener, NO_SLEEP)
            self.assertNotIn(MARKER, str(ctx.exception))
            self.assertNotIn(CANDLE_URL, str(ctx.exception))

    def test_http_error_is_closed_without_reading_provider_body(self):
        error = TrackedHTTPError(404)
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted(error), NO_SLEEP)
        self.assertEqual(str(ctx.exception), "HTTP 404 (not retried)")
        self.assertTrue(error.closed_by_test)
        self.assertFalse(error.read_called)
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_invalid_http_status_types_and_ranges_are_rejected(self):
        for status in (True, 99, 600, 200.0, UntrustedInt(451)):
            with self.subTest(status_type=type(status).__name__), self.assertRaises(fetcher.ApiError) as ctx:
                fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((status, b"{}")), NO_SLEEP)
            self.assertEqual(str(ctx.exception), "transport returned an invalid HTTP status")
            self.assertNotIn(MARKER, str(ctx.exception))

    def test_missing_status_and_non_bytes_body_are_rejected(self):
        with self.assertRaisesRegex(fetcher.ApiError, "no HTTP status"):
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((None, b"{}")), NO_SLEEP)
        with self.assertRaisesRegex(fetcher.ApiError, "invalid response body"):
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((200, MARKER)), NO_SLEEP)

    def test_oversized_body_is_rejected_without_echoing_body(self):
        body = MARKER.encode() + b"x" * fetcher.MAX_RESPONSE_BYTES
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((200, body)), NO_SLEEP)
        self.assertEqual(str(ctx.exception), "response exceeded the 1 MiB public-data limit")
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_nonstandard_json_constants_are_rejected(self):
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((200, b'{"price":NaN}')), NO_SLEEP)
        self.assertEqual(str(ctx.exception), "HTTP 200 response was not valid JSON")

    def test_parser_errors_never_echo_provider_values(self):
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.unwrap({"code": -1, "msg": MARKER})
        self.assertNotIn(MARKER, str(ctx.exception))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.parse_klines([[1_700_000_000_000, MARKER, "2", "1", "1", "1"]])
        self.assertNotIn(MARKER, str(ctx.exception))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.parse_klines({"message": MARKER})
        self.assertNotIn(MARKER, str(ctx.exception))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.extract_server_time(MARKER)
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_timestamp_and_response_code_booleans_are_not_accepted(self):
        for value in (True, False, 1.0, "not-a-timestamp", "-1"):
            with self.subTest(value=repr(value)), self.assertRaises((TypeError, ValueError)):
                fetcher.to_seconds(value)
        with self.assertRaises(fetcher.ApiError):
            fetcher.unwrap({"code": False, "data": [1]})
        self.assertEqual(fetcher.to_seconds("1700000000000"), 1_700_000_000)

    def test_nonfinite_and_boolean_candle_values_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), True):
            row = [1_700_000_000_000, value, "2", "1", "1", "1"]
            with self.subTest(value=repr(value)), self.assertRaises(fetcher.ApiError):
                fetcher.parse_klines([row])


class ProviderSanitizationTests(unittest.TestCase):
    def test_provider_http_log_rejects_untrusted_status_subclasses(self):
        http = providers.Http(5, 1, lambda url, timeout: (UntrustedInt(451), b""), NO_SLEEP)
        with self.assertRaises(fetcher.ApiError):
            http.get(CANDLE_URL)
        self.assertEqual(http.log, [("/api/v3/klines", "invalid HTTP status")])
        self.assertNotIn(MARKER, repr(http.log))

    def test_provider_http_log_sanitizes_http_error_code(self):
        error = TrackedHTTPError(MARKER)
        http = providers.Http(5, 1, lambda url, timeout: (_ for _ in ()).throw(error), NO_SLEEP)
        with self.assertRaises(fetcher.ApiError):
            http.get(CANDLE_URL)
        self.assertEqual(http.log, [("/api/v3/klines", "invalid HTTP status")])
        self.assertTrue(error.closed_by_test)
        self.assertFalse(error.read_called)
        self.assertNotIn(MARKER, repr(http.log))

    def test_legacy_venue_adapters_cannot_be_constructed(self):
        for adapter, label in (
            (providers.Kraken, "Kraken"),
            (providers.Coinbase, "Coinbase"),
        ):
            with self.subTest(adapter=label), self.assertRaisesRegex(
                    fetcher.DisallowedRequestError,
                    f"{label} provider adapter is not authorized"):
                adapter()

    def test_legacy_adapter_errors_are_fixed_safe_messages(self):
        with self.assertRaises(fetcher.ApiError) as ctx:
            providers.Kraken._result({"result": {}, "error": [MARKER]})
        self.assertEqual(str(ctx.exception), "Kraken returned an error response")

        class FakeHttp:
            def __init__(self, response):
                self.response = response

            def get(self, url):
                return self.response

        # TEST-ONLY BYPASS: parser-error fixtures use uninitialized objects.
        # Normal constructor refusal is asserted by test_legacy_venue_adapters_cannot_be_constructed.
        legacy_coinbase = object.__new__(providers.Coinbase)
        legacy_kraken = object.__new__(providers.Kraken)

        with self.assertRaises(fetcher.ApiError) as ctx:
            legacy_coinbase.server_time(FakeHttp({"epoch": MARKER}))
        self.assertEqual(str(ctx.exception), "Coinbase server-time response is invalid")

        with self.assertRaises(fetcher.ApiError) as ctx:
            legacy_kraken.server_time(FakeHttp({"error": [], "result": {"unixtime": MARKER}}))
        self.assertEqual(str(ctx.exception), "Kraken server-time response is invalid")

        with self.assertRaises(fetcher.ApiError) as ctx:
            legacy_coinbase.candles("1h", 1, 3600, FakeHttp([[MARKER, "1", "2", "1", "1", "1"]]))
        self.assertNotIn(MARKER, str(ctx.exception))


class CrosscheckEvidenceValidationTests(unittest.TestCase):
    @staticmethod
    def _comparison():
        return {
            "open_diff_pct": 0.0,
            "close_diff_pct": 0.0,
            "high_diff_pct": 0.0,
            "low_diff_pct": 0.0,
            "binance_return_pct": 0.0,
            "other_return_pct": 0.0,
            "return_gap_pp": 0.0,
            "agrees": True,
        }

    def _payload(self, providers=None, verdict=None, bitstamp=True):
        return {
            "dataset_version": "synthetic-v1",
            "dataset_sha256": "a" * 64,
            "providers": ["coinbase", "bitstamp"] if providers is None else providers,
            "flagged": [{
                "date": "2020-03-12",
                "verdict": crosscheck.CONFIRMED_VERDICT if verdict is None else verdict,
                "coinbase": self._comparison(),
                **({"bitstamp": self._comparison()} if bitstamp else {}),
            }],
        }

    def _validate(self, payload):
        cfg = {"flagged_dates": ["2020-03-12"]}
        manifest = {"version_id": "synthetic-v1", "csv_sha256": "a" * 64}
        with tempfile.TemporaryDirectory() as out:
            path = os.path.join(out, "crosscheck.json")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(payload, stream)
            return crosscheck.validate_crosscheck_artifact(
                cfg, manifest, path, frozenset({"coinbase", "bitstamp"})
            )

    def test_two_provider_artifact_with_complete_agreement_is_accepted(self):
        result = self._validate(self._payload())
        self.assertEqual(result["providers"], ["coinbase", "bitstamp"])

    def test_single_provider_artifact_is_rejected(self):
        with self.assertRaisesRegex(crosscheck.CrosscheckError, "both distinct"):
            self._validate(self._payload(providers=["coinbase"]))

    def test_missing_bitstamp_evidence_is_rejected(self):
        with self.assertRaisesRegex(crosscheck.CrosscheckError, "both independent providers"):
            self._validate(self._payload(bitstamp=False))

    def test_confirmed_prefix_with_untrusted_suffix_is_rejected(self):
        with self.assertRaisesRegex(crosscheck.CrosscheckError, "both independent providers"):
            self._validate(self._payload(verdict="CONFIRMED_UNTRUSTED"))

    def test_two_provider_authorization_is_required(self):
        cfg = {"flagged_dates": ["2020-03-12"]}
        manifest = {"version_id": "synthetic-v1", "csv_sha256": "a" * 64}
        with tempfile.TemporaryDirectory() as out:
            path = os.path.join(out, "crosscheck.json")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(self._payload(), stream)
            with self.assertRaisesRegex(crosscheck.CrosscheckError, "two independent"):
                crosscheck.validate_crosscheck_artifact(
                    cfg, manifest, path, frozenset({"coinbase"})
                )

    def test_high_and_low_divergence_are_rejected_in_artifact_evidence(self):
        for field in ("high_diff_pct", "low_diff_pct"):
            with self.subTest(field=field):
                payload = self._payload()
                for provider in ("coinbase", "bitstamp"):
                    payload["flagged"][0][provider][field] = 3.01
                with self.assertRaisesRegex(
                    crosscheck.CrosscheckError, "lacks confirmed"
                ):
                    self._validate(payload)

    def test_comparison_requires_high_and_low_to_be_within_tolerance(self):
        previous_btc = fetcher.Candle(
            1_583_884_800, 100.0, 101.0, 99.0, 100.0, 1.0
        )
        previous_other = fetcher.Candle(
            1_583_884_800, 100.0, 101.0, 99.0, 100.0, 1.0
        )
        for field, high, low in (
            ("high_diff_pct", 111.0, 99.0),
            ("low_diff_pct", 101.0, 89.0),
        ):
            with self.subTest(field=field):
                current_btc = fetcher.Candle(
                    1_583_971_200, 100.0, 101.0, 99.0, 100.0, 1.0
                )
                current_other = fetcher.Candle(
                    1_583_971_200, 100.0, high, low, 100.0, 1.0
                )
                btc = {
                    previous_btc.time: previous_btc,
                    current_btc.time: current_btc,
                }
                other = {
                    previous_other.time: previous_other,
                    current_other.time: current_other,
                }
                result = crosscheck.compare(
                    [previous_btc, current_btc], other, other, ["2020-03-12"]
                )
                self.assertEqual(
                    result["flagged"][0]["verdict"], "NOT CONFIRMED"
                )

    def test_comparison_is_unavailable_when_bitstamp_evidence_is_missing(self):
        previous = fetcher.Candle(1_583_884_800, 100.0, 101.0, 99.0, 100.0, 1.0)
        current = fetcher.Candle(1_583_971_200, 100.0, 101.0, 99.0, 100.0, 1.0)
        independent = {previous.time: previous, current.time: current}
        result = crosscheck.compare(
            [previous, current], independent, {}, ["2020-03-12"]
        )
        self.assertEqual(result["flagged"][0]["verdict"], "UNAVAILABLE")

    def test_comparison_confirms_only_when_both_independent_sources_agree(self):
        previous = fetcher.Candle(1_583_884_800, 100.0, 101.0, 99.0, 100.0, 1.0)
        current = fetcher.Candle(1_583_971_200, 100.0, 101.0, 99.0, 100.0, 1.0)
        independent = {previous.time: previous, current.time: current}
        result = crosscheck.compare(
            [previous, current], independent, independent, ["2020-03-12"]
        )
        self.assertEqual(
            result["flagged"][0]["verdict"], crosscheck.CONFIRMED_VERDICT
        )


class CrosscheckSanitizationTests(unittest.TestCase):
    def test_crosscheck_cannot_be_enabled_by_mutating_legacy_authorization_state(self):
        calls = []

        def forbidden_opener(url, timeout):
            calls.append(url)
            raise AssertionError("unapproved provider opener must not be called")

        candle = fetcher.Candle(1_700_000_000, 10.0, 11.0, 9.0, 10.0, 1.0)
        manifest = {"version_id": "synthetic-v1", "csv_sha256": "a" * 64}
        original_authorization = crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS
        self.assertIs(type(original_authorization), frozenset)
        self.assertEqual(original_authorization, frozenset())
        crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS = frozenset({"coinbase", "bitstamp"})
        try:
            with tempfile.TemporaryDirectory() as out:
                with self.assertRaisesRegex(
                        fetcher.ApiError, "independent cross-check providers are not authorized"):
                    crosscheck.run_crosscheck(
                        manifest, [candle], [], out, opener=forbidden_opener,
                        sleep=NO_SLEEP, timeout=1, retries=1)
                self.assertFalse(os.path.exists(os.path.join(out, "crosscheck.json")))
                self.assertFalse(os.path.exists(os.path.join(out, "crosscheck.md")))
        finally:
            crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS = original_authorization

        self.assertEqual(calls, [])

    def test_zero_reference_prices_do_not_crash_comparison(self):
        zero = fetcher.Candle(1_700_000_000, 0.0, 0.0, 0.0, 0.0, 0.0)
        result = crosscheck.compare([zero], {zero.time: zero}, {}, [])
        self.assertIsNone(result["summary"])


if __name__ == "__main__":
    unittest.main()
