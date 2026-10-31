# Reachability lab (read-only)

| Class | Endpoint | Result | Bytes | Seconds | Start of answer |
|---|---|---|---|---|---|
| crypto | kraken time | HTTP 200 | 87 | 0.2 | {"error":[],"result":{"unixtime":1793419355,"rfc1123":"Sat, 31 Oct 26 04:02:35 +0000"}} |
| crypto | kraken ohlc | HTTP 200 | 59440 | 0.24 | {"error":[],"result":{"XXBTZUSD":[[1790827200,"83698.0","84146.5","83657.2","84051.2","83899.5","74.33403641", |
| crypto | coinbase time | HTTP 200 | 57 | 0.15 | {"iso":"2026-10-31T04:02:35.473Z","epoch":1793419355.473} |
| crypto | coinbase candles | HTTP 200 | 21159 | 0.05 | [[1793415600,76969.01,77296.64,77287.6,76991.06,115.25697546],[1793412000,77162.11,77353.43,77241.32,77287.59, |
| crypto | bitstamp ohlc | HTTP 200 | 708 | 0.33 | {"data": {"pair": "BTC/USD", "ohlc": [{"timestamp": "1793404800", "open": "77173.17", "high": "77392.31", "low |
| crypto | okx time | HTTP 200 | 53 | 0.24 | {"code":"0","data":[{"ts":"1793419356071"}],"msg":""} |
| crypto | okx candles | HTTP 200 | 618 | 0.18 | {"code":"0","data":[["1793419200000","77118.9","77212.3","77112.6","77188.3","11.93759353","921147.207636067", |
| crypto | bybit time | HTTP 403 | 96 | 0.19 | { error:The Amazon CloudFront distribution is configured to block access from your country } |
| crypto | bybit kline | HTTP 403 | 96 | 0.08 | { error:The Amazon CloudFront distribution is configured to block access from your country } |
| crypto | binance time | HTTP 451 | 224 | 0.17 | { "code": 0, "msg": "Service unavailable from a restricted location according to 'b. Eligibility' in https://w |
| crypto | binance klines | HTTP 451 | 224 | 0.08 | { "code": 0, "msg": "Service unavailable from a restricted location according to 'b. Eligibility' in https://w |
| crypto | binance vision klines | HTTP 200 | 884 | 0.51 | [[1793404800000,"77368.76000000","77569.86000000","77271.20000000","77568.81000000","469.27903000",17934083999 |
| crypto | gemini candles | HTTP 200 | 90565 | 0.29 | [[1793415600000,77305.53,77319.76,77000.71,77032.15,1.90901785],[1793412000000,77257.87,77383.92,77192.83,7730 |
| forex | frankfurter latest | HTTP 200 | 96 | 0.41 | {"amount":1.0,"base":"USD","date":"2026-10-30","rates":{"EUR":0.89509,"IDR":18148,"JPY":157.25}} |
| forex | frankfurter series | HTTP 200 | 753 | 0.35 | {"amount":1.0,"base":"USD","start_date":"2026-09-18","end_date":"2026-10-20","rates":{"2026-09-18":{"EUR":0.87 |
| forex | ecb sdmx | HTTP 200 | 3642 | 0.87 | {"header":{"id":"879fc6e2-9654-46a0-bc20-f47e0b937776","test":false,"prepared":"2026-10-31T05:02:39.220+01:00" |
| stocks | stooq spy daily | HTTP 200 | 796 | 0.52 | <!DOCTYPE html><html><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"></head><body>< |
| stocks | yahoo chart spy (unofficial) | HTTP 200 | 3659 | 0.29 | {"chart":{"result":[{"meta":{"currency":"USD","symbol":"SPY","exchangeName":"PCX","fullExchangeName":"NYSEArca |
| shape | kraken assetpairs | HTTP 200 | 680652 | 0.26 | {"error":[],"result":{"0GEUR":{"altname":"0GEUR","wsname":"0G/EUR","aclass_base":"currency","base":"0G","aclas |
| shape | kraken ticker all | HTTP 200 | 417805 | 0.61 | {"error":[],"result":{"0GEUR":{"a":["0.1540000","2675","2675.000"],"b":["0.1530000","26489","26489.000"],"c":[ |
| shape | coinbase products | HTTP 200 | 356323 | 0.09 | [{"id":"RBN-USD","base_currency":"RBN","quote_currency":"USD","quote_increment":"0.00001","base_increment":"0. |
| shape | binance vision exchangeInfo | HTTP 200 | 5349 | 0.52 | {"timezone":"UTC","serverTime":1793419361505,"rateLimits":[{"rateLimitType":"REQUEST_WEIGHT","interval":"MINUT |
| shape | binance vision klines 1d | HTTP 200 | 556 | 0.52 | [[1793232000000,"81343.51000000","81971.00000000","77910.00000000","77991.89000000","23832.18298000",179331839 |
| shape | frankfurter v2 rates | HTTP 200 | 189 | 0.4 | [{"date":"2026-10-31","base":"USD","quote":"EUR","rate":0.89504},{"date":"2026-10-30","base":"USD","quote":"ID |
| shape | frankfurter v2 series | HTTP 200 | 385 | 0.43 | [{"date":"2026-10-15","base":"USD","quote":"EUR","rate":0.89278},{"date":"2026-10-16","base":"USD","quote":"EU |
| shape | frankfurter v2 currencies | HTTP 200 | 21876 | 0.06 | [{"iso_code":"AED","iso_numeric":"784","name":"United Arab Emirates Dirham","symbol":"د.إ","start_date":"1996- |
| shape | frankfurter v1 series (old) | HTTP 200 | 203 | 0.36 | {"amount":1.0,"base":"USD","start_date":"2026-10-15","end_date":"2026-10-20","rates":{"2026-10-15":{"EUR":0.89 |
