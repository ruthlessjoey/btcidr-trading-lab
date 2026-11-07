# Reachability lab (read-only)

| Class | Endpoint | Result | Bytes | Seconds | Start of answer |
|---|---|---|---|---|---|
| crypto | kraken time | HTTP 200 | 87 | 0.17 | {"error":[],"result":{"unixtime":1794047163,"rfc1123":"Sat, 07 Nov 26 10:26:03 +0000"}} |
| crypto | kraken ohlc | HTTP 200 | 59446 | 0.15 | {"error":[],"result":{"XXBTZUSD":[[1791453600,"83059.4","83114.7","82538.0","82667.9","82760.2","81.05018535", |
| crypto | coinbase time | HTTP 200 | 57 | 0.07 | {"iso":"2026-11-07T10:26:03.692Z","epoch":1794047163.692} |
| crypto | coinbase candles | HTTP 200 | 21146 | 0.04 | [[1794045600,75922.46,75976.41,75954.3,75933.11,13.31852326],[1794042000,75906.92,76152.43,76097.15,75954.3,85 |
| crypto | bitstamp ohlc | HTTP 200 | 706 | 0.29 | {"data": {"pair": "BTC/USD", "ohlc": [{"timestamp": "1794031200", "open": "75931.53", "high": "75966.49", "low |
| crypto | okx time | HTTP 200 | 53 | 0.24 | {"code":"0","data":[{"ts":"1794047164199"}],"msg":""} |
| crypto | okx candles | HTTP 200 | 603 | 0.21 | {"code":"0","data":[["1794045600000","76056.4","76082.3","76019","76033.5","12.14167455","923311.101844617","9 |
| crypto | bybit time | HTTP 403 | 96 | 0.16 | { error:The Amazon CloudFront distribution is configured to block access from your country } |
| crypto | bybit kline | HTTP 403 | 96 | 0.07 | { error:The Amazon CloudFront distribution is configured to block access from your country } |
| crypto | binance time | HTTP 451 | 224 | 0.09 | { "code": 0, "msg": "Service unavailable from a restricted location according to 'b. Eligibility' in https://w |
| crypto | binance klines | HTTP 451 | 224 | 0.05 | { "code": 0, "msg": "Service unavailable from a restricted location according to 'b. Eligibility' in https://w |
| crypto | binance vision klines | HTTP 200 | 884 | 0.54 | [[1794031200000,"76034.01000000","76070.01000000","76014.00000000","76056.11000000","275.28689000",17940347999 |
| crypto | gemini candles | HTTP 200 | 90481 | 0.26 | [[1794042000000,76101.04,76153.99,75939.73,75949.06,3.62445622],[1794038400000,76023.67,76101.04,76005.99,7610 |
| forex | frankfurter latest | HTTP 200 | 96 | 0.37 | {"amount":1.0,"base":"USD","date":"2026-11-06","rates":{"EUR":0.89566,"IDR":18100,"JPY":158.33}} |
| forex | frankfurter series | HTTP 200 | 753 | 0.34 | {"amount":1.0,"base":"USD","start_date":"2026-09-18","end_date":"2026-10-20","rates":{"2026-09-18":{"EUR":0.87 |
| forex | ecb sdmx | HTTP 200 | 3644 | 0.94 | {"header":{"id":"b8116d10-cef5-4fa1-9817-e6241bca4df6","test":false,"prepared":"2026-11-07T11:26:07.244+01:00" |
| stocks | stooq spy daily | HTTP 200 | 796 | 0.58 | <!DOCTYPE html><html><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"></head><body>< |
| stocks | yahoo chart spy (unofficial) | HTTP 200 | 3630 | 0.22 | {"chart":{"result":[{"meta":{"currency":"USD","symbol":"SPY","exchangeName":"PCX","fullExchangeName":"NYSEArca |
| shape | kraken assetpairs | HTTP 200 | 682808 | 0.19 | {"error":[],"result":{"0GEUR":{"altname":"0GEUR","wsname":"0G/EUR","aclass_base":"currency","base":"0G","aclas |
| shape | kraken ticker all | HTTP 200 | 418672 | 0.18 | {"error":[],"result":{"0GEUR":{"a":["0.1340000","24894","24894.000"],"b":["0.1320000","35085","35085.000"],"c" |
| shape | coinbase products | HTTP 200 | 356744 | 0.08 | [{"id":"ORN-USD","base_currency":"ORN","quote_currency":"USD","quote_increment":"0.001","base_increment":"0.01 |
| shape | binance vision exchangeInfo | HTTP 200 | 5349 | 0.54 | {"timezone":"UTC","serverTime":1794047169036,"rateLimits":[{"rateLimitType":"REQUEST_WEIGHT","interval":"MINUT |
| shape | binance vision klines 1d | HTTP 200 | 557 | 0.54 | [[1793836800000,"80504.01000000","80918.01000000","75208.42000000","76088.01000000","26059.74254000",179392319 |
| shape | frankfurter v2 rates | HTTP 200 | 190 | 0.23 | [{"date":"2026-11-08","base":"USD","quote":"EUR","rate":0.89162},{"date":"2026-11-08","base":"USD","quote":"ID |
| shape | frankfurter v2 series | HTTP 200 | 385 | 0.39 | [{"date":"2026-10-15","base":"USD","quote":"EUR","rate":0.89278},{"date":"2026-10-16","base":"USD","quote":"EU |
| shape | frankfurter v2 currencies | HTTP 200 | 29041 | 0.49 | [{"iso_code":"AAVE","iso_numeric":null,"name":"Aave","symbol":"AAVE","type":"crypto","start_date":"2020-10-10" |
| shape | frankfurter v1 series (old) | HTTP 200 | 203 | 0.33 | {"amount":1.0,"base":"USD","start_date":"2026-10-15","end_date":"2026-10-20","rates":{"2026-10-15":{"EUR":0.89 |
