"""Offline synthetic tests for safe dataset publication and manifest validation."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fetcher import Candle  # noqa: E402
from research import dataset  # noqa: E402


MARKET = {
    "provider": "synthetic-provider",
    "symbol": "BTCUSDT",
    "base_asset": "BTC",
    "quote_asset": "USDT",
    "timeframe": "1d",
    "market_type": "spot",
}


def candles():
    return [
        Candle(1_700_000_000, 100.0, 105.0, 95.0, 102.0, 10.0),
        Candle(1_700_086_400, 102.0, 108.0, 99.0, 106.0, 12.0),
    ]


class DatasetPublicationTests(unittest.TestCase):
    def test_successful_publication_round_trips(self):
        with tempfile.TemporaryDirectory() as root:
            csv_path, manifest_path = dataset.write_version(
                root, MARKET, candles(), 1_700_200_000
            )
            manifest, loaded = dataset.load_verified(manifest_path)
            self.assertEqual(loaded, candles())
            self.assertEqual(manifest["csv_file"], os.path.basename(csv_path))
            self.assertEqual(sorted(os.listdir(os.path.dirname(csv_path))),
                             sorted([os.path.basename(csv_path),
                                     os.path.basename(manifest_path)]))

    def test_partial_manifest_write_failure_removes_only_this_attempts_files(self):
        def partial_dump(obj, stream, **kwargs):
            stream.write('{"partial":')
            raise OSError("synthetic partial manifest write failure")

        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(dataset.json, "dump", side_effect=partial_dump):
                with self.assertRaises(OSError):
                    dataset.write_version(root, MARKET, candles(), 1_700_200_000)
            folder = os.path.join(root, dataset.dataset_name(MARKET))
            self.assertEqual(os.listdir(folder), [])

    def test_existing_version_is_never_overwritten_or_removed(self):
        with tempfile.TemporaryDirectory() as root:
            csv_path, manifest_path = dataset.write_version(
                root, MARKET, candles(), 1_700_200_000
            )
            with open(csv_path, "rb") as f:
                original_csv = f.read()
            with open(manifest_path, "rb") as f:
                original_manifest = f.read()
            with self.assertRaises(dataset.DatasetError):
                dataset.write_version(root, MARKET, candles(), 1_700_200_000)
            with open(csv_path, "rb") as f:
                self.assertEqual(f.read(), original_csv)
            with open(manifest_path, "rb") as f:
                self.assertEqual(f.read(), original_manifest)

    def test_writer_rejects_market_identifiers_that_escape_dataset_folder(self):
        with tempfile.TemporaryDirectory() as root:
            bad_market = dict(MARKET)
            bad_market["provider"] = "../outside"
            with self.assertRaises(dataset.DatasetError):
                dataset.write_version(root, bad_market, candles(), 1_700_200_000)
            self.assertEqual(os.listdir(root), [])

    def test_manifest_market_identity_requires_nonempty_strings(self):
        with tempfile.TemporaryDirectory() as root:
            _, manifest_path = dataset.write_version(
                root, MARKET, candles(), 1_700_200_000
            )
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["market"]["provider"] = True
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f)
            with self.assertRaises(dataset.DatasetError):
                dataset.load_verified(manifest_path)

    def test_manifest_timestamps_reject_bool_and_inconsistent_range(self):
        for bad_value in (True, -1):
            with self.subTest(value=bad_value), tempfile.TemporaryDirectory() as root:
                _, manifest_path = dataset.write_version(
                    root, MARKET, candles(), 1_700_200_000
                )
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
                manifest["first_open_unix"] = bad_value
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f)
                with self.assertRaises(dataset.DatasetError):
                    dataset.load_verified(manifest_path)


if __name__ == "__main__":
    unittest.main()
