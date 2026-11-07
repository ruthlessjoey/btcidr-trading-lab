# Reachability lab (read-only)

| Class | Endpoint | Result | Bytes | Seconds | Start of answer |
|---|---|---|---|---|---|
| crypto | kraken time | HTTP 200 | 87 | 0.13 | {"error":[],"result":{"unixtime":1794077745,"rfc1123":"Sat, 07 Nov 26 18:55:45 +0000"}} |
| crypto | kraken ohlc | HTTP 200 | 59436 | 0.03 | {"error":[],"result":{"XXBTZUSD":[[1791482400,"80672.3","81500.0","80474.7","81444.0","81206.3","240.52780396" |
| crypto | coinbase time | HTTP 200 | 57 | 0.08 | {"iso":"2026-11-07T18:55:45.544Z","epoch":1794077745.544} |
| crypto | coinbase candles | HTTP 200 | 21139 | 0.02 | [[1794074400,75683.89,75789.4,75735.08,75709.87,86.94644969],[1794070800,75640.66,75773.89,75640.66,75735.07,1 |
| crypto | bitstamp ohlc | HTTP 200 | 708 | 0.22 | {"data": {"pair": "BTC/USD", "ohlc": [{"timestamp": "1794060000", "open": "75838.14", "high": "75883.86", "low |
| crypto | okx time | HTTP 200 | 53 | 0.21 | {"code":"0","data":[{"ts":"1794077745944"}],"msg":""} |
| crypto | okx candles | HTTP 200 | 610 | 0.21 | {"code":"0","data":[["1794074400000","75842.6","75898.4","75803.9","75833.9","34.15496135","2590446.229713385" |
| crypto | bybit time | HTTP 403 | 96 | 0.09 | { error:The Amazon CloudFront distribution is configured to block access from your country } |
| crypto | bybit kline | HTTP 403 | 96 | 0.08 | { error:The Amazon CloudFront distribution is configured to block access from your country } |
| crypto | binance time | HTTP 451 | 224 | 0.27 | { "code": 0, "msg": "Service unavailable from a restricted location according to 'b. Eligibility' in https://w |
| crypto | binance klines | HTTP 451 | 224 | 0.04 | { "code": 0, "msg": "Service unavailable from a restricted location according to 'b. Eligibility' in https://w |
| crypto | binance vision klines | HTTP 200 | 878 | 0.76 | [[1794060000000,"75936.01000000","75980.92000000","75930.77000000","75948.54000000","149.55753000",17940635999 |
| crypto | gemini candles | HTTP 200 | 90470 | 0.1 | [[1794070800000,75651.42,75783.45,75651.42,75750.64,1.15504032],[1794067200000,75673.42,75719.51,75613.33,7565 |
| forex | frankfurter latest | HTTP 200 | 96 | 0.27 | {"amount":1.0,"base":"USD","date":"2026-11-06","rates":{"EUR":0.89566,"IDR":18100,"JPY":158.33}} |
| forex | frankfurter series | HTTP 200 | 753 | 0.26 | {"amount":1.0,"base":"USD","start_date":"2026-09-18","end_date":"2026-10-20","rates":{"2026-09-18":{"EUR":0.87 |
| forex | ecb sdmx | HTTP 200 | 3644 | 1.21 | {"header":{"id":"2e21cc0e-6e84-404d-9560-61ddccf10b56","test":false,"prepared":"2026-11-07T19:55:49.258+01:00" |
| stocks | stooq spy daily | HTTP 200 | 796 | 0.48 | <!DOCTYPE html><html><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"></head><body>< |
| stocks | yahoo chart spy (unofficial) | HTTP 200 | 3630 | 0.08 | {"chart":{"result":[{"meta":{"currency":"USD","symbol":"SPY","exchangeName":"PCX","fullExchangeName":"NYSEArca |
| shape | kraken assetpairs | HTTP 200 | 682809 | 0.14 | {"error":[],"result":{"0GEUR":{"altname":"0GEUR","wsname":"0G/EUR","aclass_base":"currency","base":"0G","aclas |
| shape | kraken ticker all | HTTP 200 | 419535 | 0.03 | {"error":[],"result":{"0GEUR":{"a":["0.1330000","973","973.000"],"b":["0.1320000","33916","33916.000"],"c":["0 |
| shape | coinbase products | HTTP 200 | 356744 | 0.02 | [{"id":"EURC-EUR","base_currency":"EURC","quote_currency":"EUR","quote_increment":"0.001","base_increment":"0. |
| shape | binance vision exchangeInfo | HTTP 200 | 5349 | 0.64 | {"timezone":"UTC","serverTime":1794077750628,"rateLimits":[{"rateLimitType":"REQUEST_WEIGHT","interval":"MINUT |
| shape | binance vision klines 1d | HTTP 200 | 557 | 0.7 | [[1793836800000,"80504.01000000","80918.01000000","75208.42000000","76088.01000000","26059.74254000",179392319 |
| shape | frankfurter v2 rates | HTTP 200 | 190 | 0.32 | [{"date":"2026-11-08","base":"USD","quote":"EUR","rate":0.89168},{"date":"2026-11-08","base":"USD","quote":"ID |
| shape | frankfurter v2 series | HTTP 200 | 385 | 0.3 | [{"date":"2026-10-15","base":"USD","quote":"EUR","rate":0.89278},{"date":"2026-10-16","base":"USD","quote":"EU |
| shape | frankfurter v2 currencies | HTTP 200 | 29041 | 0.02 | [{"iso_code":"AAVE","iso_numeric":null,"name":"Aave","symbol":"AAVE","type":"crypto","start_date":"2020-10-10" |
| shape | frankfurter v1 series (old) | HTTP 200 | 203 | 0.26 | {"amount":1.0,"base":"USD","start_date":"2026-10-15","end_date":"2026-10-20","rates":{"2026-10-15":{"EUR":0.89 |
