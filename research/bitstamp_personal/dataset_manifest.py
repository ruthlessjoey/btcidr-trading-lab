"""Strict validation of the frozen Bitstamp V2 dataset manifest."""
from __future__ import annotations
import hashlib, json, re
from collections.abc import Mapping

START=1704067200
END=1793491200
COUNT=24840
STEP=3600
MARKETS={"btcusd","ethusd","xrpusd","solusd","dogeusd","shibusd","pepeusd"}
CANDLE_KEYS={"open_timestamp","timestamp","open","high","low","close","volume"}

class DatasetManifestError(ValueError):
    """Dataset manifest or normalized candle sequence is incomplete."""


def verify_dataset_manifest(dataset: Mapping[str,object]) -> dict:
    if not isinstance(dataset,Mapping):
        raise DatasetManifestError("dataset manifest must be an object")
    symbol=dataset.get("market_symbol")
    if not isinstance(symbol,str) or symbol.casefold() not in MARKETS:
        raise DatasetManifestError("market symbol is outside frozen V2 universe")
    symbol=symbol.casefold()
    pair=dataset.get("pair")
    if not isinstance(pair,str) or re.sub(r"[^a-z0-9]","",pair.casefold())!=symbol:
        raise DatasetManifestError("returned pair does not match requested market")
    if dataset.get("step_seconds")!=STEP:
        raise DatasetManifestError("interval is not the frozen 1-hour interval")
    if dataset.get("coverage_status")!="CONTIGUOUS" or dataset.get("gap_count")!=0 or dataset.get("gaps")!=[]:
        raise DatasetManifestError("coverage is incomplete or contains gaps")
    if dataset.get("row_count")!=COUNT or dataset.get("first_open_timestamp")!=START or dataset.get("last_close_timestamp")!=END:
        raise DatasetManifestError("dataset range or row count does not match frozen V2 boundaries")
    raw_hash=dataset.get("raw_page_sha256")
    if not isinstance(raw_hash,str) or re.fullmatch(r"[0-9a-f]{64}",raw_hash) is None:
        raise DatasetManifestError("raw_page_sha256 must be lowercase SHA-256")
    pages=dataset.get("page_count")
    if isinstance(pages,bool) or not isinstance(pages,int) or pages<1:
        raise DatasetManifestError("page_count must be a positive integer")
    candles=dataset.get("candles")
    if not isinstance(candles,list) or len(candles)!=COUNT:
        raise DatasetManifestError("candles do not match frozen V2 row count")
    for i,row in enumerate(candles):
        if not isinstance(row,Mapping) or set(row)!=CANDLE_KEYS:
            raise DatasetManifestError(f"candle[{i}] schema is invalid")
        expected=START+i*STEP
        opened,closed=row["open_timestamp"],row["timestamp"]
        if isinstance(opened,bool) or not isinstance(opened,int) or isinstance(closed,bool) or not isinstance(closed,int) or opened!=expected or closed!=expected+STEP:
            raise DatasetManifestError(f"candle[{i}] is misaligned, unordered or missing")
    try:
        row_bytes=json.dumps(candles,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
    except (TypeError,ValueError,RecursionError) as exc:
        raise DatasetManifestError("candles are not canonical JSON") from exc
    rows_hash=hashlib.sha256(row_bytes).hexdigest()
    if dataset.get("dataset_sha256")!=rows_hash:
        raise DatasetManifestError("adapter dataset SHA-256 does not match normalized candle rows")
    return {
        "market_symbol":symbol,
        "candles":candles,
        "raw_page_sha256":raw_hash,
        "rows_sha256":rows_hash,
        "manifest_sha256":hashlib.sha256(json.dumps({
            "market_symbol":symbol,"pair":pair,"step_seconds":STEP,
            "first_open_timestamp":START,"last_close_timestamp":END,
            "row_count":COUNT,"rows_sha256":rows_hash,
            "raw_page_sha256":raw_hash,"page_count":pages,
        },sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest(),
    }
