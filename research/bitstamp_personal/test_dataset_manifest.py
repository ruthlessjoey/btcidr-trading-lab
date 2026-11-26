import hashlib, json, unittest
from decimal import Decimal
from dataset_manifest import DatasetManifestError, verify_dataset_manifest

def sample_dataset():
    rows=[]
    for i in range(24840):
        opened=1704067200+i*3600
        rows.append({"open_timestamp":opened,"timestamp":opened+3600,
          "open":"100","high":"101","low":"99","close":"100","volume":"10000"})
    raw=json.dumps(rows,sort_keys=True,separators=(",",":")).encode()
    return {"market_symbol":"btcusd","pair":"BTC/USD","step_seconds":3600,
      "row_count":24840,"first_open_timestamp":1704067200,"last_close_timestamp":1793491200,
      "gap_count":0,"gaps":[],"coverage_status":"CONTIGUOUS",
      "dataset_sha256":hashlib.sha256(raw).hexdigest(),"raw_page_sha256":"b"*64,
      "page_count":25,"candles":rows}

class DatasetManifestTests(unittest.TestCase):
    def test_accepts_exact_complete_manifest(self):
        result=verify_dataset_manifest(sample_dataset())
        self.assertEqual(result["market_symbol"],"btcusd")
        self.assertEqual(len(result["candles"]),24840)
        self.assertEqual(len(result["manifest_sha256"]),64)

    def test_rejects_pair_coverage_range_and_row_hash_mismatch(self):
        for key,value in (("pair","ETH/USD"),("gap_count",1),("last_close_timestamp",1793487600),("dataset_sha256","c"*64)):
            data=sample_dataset();data[key]=value
            with self.subTest(key=key),self.assertRaises(DatasetManifestError):
                verify_dataset_manifest(data)

    def test_rejects_reordered_or_missing_candle(self):
        data=sample_dataset()
        data["candles"]=list(data["candles"])
        data["candles"][1]=dict(data["candles"][1],open_timestamp=data["candles"][1]["open_timestamp"]+3600)
        with self.assertRaisesRegex(DatasetManifestError,"misaligned"):
            verify_dataset_manifest(data)
        data=sample_dataset();data["candles"].pop()
        with self.assertRaisesRegex(DatasetManifestError,"row count"):
            verify_dataset_manifest(data)

    def test_rejects_unknown_market_and_bad_raw_page_hash(self):
        data=sample_dataset();data["market_symbol"]="unknown"
        with self.assertRaises(DatasetManifestError): verify_dataset_manifest(data)
        data=sample_dataset();data["raw_page_sha256"]="not-a-hash"
        with self.assertRaises(DatasetManifestError): verify_dataset_manifest(data)

if __name__=="__main__": unittest.main()
