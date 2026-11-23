# Solana DEX sample research note

**Source:** [pumpdatafun/pump-fun-trades-sample](https://huggingface.co/datasets/pumpdatafun/pump-fun-trades-sample)  
**Attribution:** pumpdata.fun  
**Declared license:** CC BY 4.0  
**Reviewed dataset revision:** `60ab4739e4a0d4f99e1aae7486e9b6320602c50b`  
**Coverage:** 15 October 2026 UTC only.

## What was actually retrieved

A bounded 100-row preview was retrieved from Hugging Face on 23 November 2026. The preview contained both `curve` and `pumpswap` venues, landed and failed attempts, token-quoted trades, migration-pool trades, and a multi-hop leg. Basic schema checks passed for those 100 rows. The paginated rows endpoint returned HTTP 503; the Parquet archive was not downloaded.

The dataset card reports 42,230,410 trade rows for the day. The four trade Parquet shards total 1,489,189,804 bytes. The seven signature shards add about 2.77 GB; they are not required for the first parser stage and were not retrieved. The dataset page reports 4.27 GB total across all tables.

## Parser boundaries

`tmm_core.dex_ingest` is an offline row normalizer only:

- Exact schema checking catches source-column drift.
- It validates timestamps, execution ordering, venue/side values, integer ranges, failed-vs-landed row semantics and optional reserve fields.
- It preserves raw integer token/quote units and does not infer token decimals or calculate a supposedly executable price.
- It keeps failed attempts separate from fills.
- It counts transaction fees/tips once per `(slot, idx)`, not once per trade leg.
- A missing mint on a multi-hop row remains unresolved; it is never guessed from a ticker or wallet.
- Wallet addresses are validated as input text but are not retained in normalized records.
- Large float64 reserve values are flagged because values above 2^53 may have lost integer precision.

The archive was generated after the 15 October 2026 event day. It is therefore not point-in-time evidence that this parsed information was available to a strategy at the event time. This fixture may be used for parser and execution/microstructure mechanics testing only. It cannot establish historical signal availability, strategy profitability, current liquidity, or future tradability.

No raw dataset rows are committed to this repository. The parser has no network, RPC, wallet, exchange or order functionality. It does not authorize paper or live execution.

## Separate Binance restriction

The approved Binance Vision archive is limited to personal, non-production historical research under its current CC BY-NC-SA 4.0 terms. The terms expressly prohibit commercial order generation and integration into commercial trading-bot products. Any such research must remain isolated from Twin Money Maker's product, model-training, validation and trading pipeline unless a separate written commercial license is obtained.
