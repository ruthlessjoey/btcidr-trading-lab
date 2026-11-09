"""Synthetic offline tests for market identifier path-safety validation."""
import json
import os
import tempfile
import unittest

from fetcher import Candle
from research import dataset


MARKET = {
    "provider": "synthetic-provider",
    "symbol": "BTCUSDT",
    "base_asset": "BTC",
    "quote_asset": "USDT",
    "timeframe": "1d",
    "market_type": "spot",
}
CANDLES = [
    Candle(1_700_000_000, 100.0, 105.0, 95.0, 102.0, 10.0),
    Candle(1_700_086_400, 102.0, 108.0, 99.0, 106.0, 12.0),
]


class IdentifierEscapeTests(unittest.TestCase):
    def test_writer_rejects_single_backslash_and_nul_identifiers(self):
        for bad in ("bad\\provider", "bad\x00provider"):
            with self.subTest(value=repr(bad)), tempfile.TemporaryDirectory() as root:
                market = dict(MARKET)
                market["provider"] = bad
                with self.assertRaisesRegex(dataset.DatasetError, "safe, non-empty identifier"):
                    dataset.write_version(root, market, CANDLES, 1_700_200_000)
                self.assertEqual(os.listdir(root), [])

    def test_loader_rejects_backslash_and_nul_market_identifiers(self):
        for bad in ("bad\\symbol", "bad\x00symbol"):
            with self.subTest(value=repr(bad)), tempfile.TemporaryDirectory() as root:
                _, manifest_path = dataset.write_version(
                    root, MARKET, CANDLES, 1_700_200_000
                )
                with open(manifest_path, encoding="utf-8") as stream:
                    manifest = json.load(stream)
                manifest["market"]["symbol"] = bad
                with open(manifest_path, "w", encoding="utf-8") as stream:
                    json.dump(manifest, stream)
                with self.assertRaisesRegex(dataset.DatasetError, "safe, non-empty identifier"):
                    dataset.load_verified(manifest_path)


if __name__ == "__main__":
    unittest.main()
