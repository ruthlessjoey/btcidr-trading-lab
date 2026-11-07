# Raw samples (first 1500 characters)

## kraken assetpairs
`https://api.kraken.com/0/public/AssetPairs` -> HTTP 200, 682809 bytes
```
{"error":[],"result":{"0GEUR":{"altname":"0GEUR","wsname":"0G/EUR","aclass_base":"currency","base":"0G","aclass_quote":"currency","quote":"ZEUR","lot":"unit5","cost_decimals":5,"pair_decimals":3,"lot_decimals":5,"lot_multiplier":1,"leverage_buy":[],"leverage_sell":[],"fees":[],"fees_maker":[],"fee_volume_currency":"ZUSD","margin_call":80,"margin_stop":40,"ordermin":"30","costmin":"0.45","tick_size":"0.001","status":"online","execution_venue":"international"},"0GUSD":{"altname":"0GUSD","wsname":"0G/USD","aclass_base":"currency","base":"0G","aclass_quote":"currency","quote":"ZUSD","lot":"unit5","cost_decimals":5,"pair_decimals":3,"lot_decimals":5,"lot_multiplier":1,"leverage_buy":[2,3],"leverage_sell":[],"fees":[],"fees_maker":[],"fee_volume_currency":"ZUSD","margin_call":80,"margin_stop":40,"ordermin":"30","costmin":"0.5","tick_size":"0.001","status":"online","execution_venue":"international","long_position_limit":40000,"short_position_limit":0},"1INCHEUR":{"altname":"1INCHEUR","wsname":"1INCH/EUR","aclass_base":"currency","base":"1INCH","aclass_quote":"currency","quote":"ZEUR","lot":"unit","cost_decimals":5,"pair_decimals":4,"lot_decimals":8,"lot_multiplier":1,"leverage_buy":[],"leverage_sell":[],"fees":[],"fees_maker":[],"fee_volume_currency":"ZUSD","margin_call":80,"margin_stop":40,"ordermin":"60","costmin":"0.45","tick_size":"0.0001","status":"online","execution_venue":"international"},"1INCHUSD":{"altname":"1INCHUSD","wsname":"1INCH/USD","aclass_base":"currency","base":"1
```

## kraken ticker all
`https://api.kraken.com/0/public/Ticker` -> HTTP 200, 419537 bytes
```
{"error":[],"result":{"0GEUR":{"a":["0.1330000","973","973.000"],"b":["0.1320000","34669","34669.000"],"c":["0.1350000","1000.00000"],"v":["1000.00000","8006.82225"],"p":["0.1350000","0.1362467"],"t":[1,11],"l":["0.1350000","0.1340000"],"h":["0.1350000","0.1380000"],"o":"0.1350000"},"0GUSD":{"a":["0.1490000","35832","35832.000"],"b":["0.1470000","81485","81485.000"],"c":["0.1480000","9860.45878"],"v":["47001.52117","83705.87009"],"p":["0.1484642","0.1507930"],"t":[54,92],"l":["0.1470000","0.1470000"],"h":["0.1520000","0.1550000"],"o":"0.1520000"},"1INCHEUR":{"a":["0.07160","8845","8845.000"],"b":["0.07150","17204","17204.000"],"c":["0.07130","6012.21772842"],"v":["92091.81308127","144077.86420042"],"p":["0.07096","0.07072"],"t":[28,44],"l":["0.06990","0.06990"],"h":["0.07180","0.07180"],"o":"0.07030"},"1INCHUSD":{"a":["0.07980","5758","5758.000"],"b":["0.07960","5541","5541.000"],"c":["0.07970","3247.87157350"],"v":["157826.54273676","208051.35495961"],"p":["0.07904","0.07884"],"t":[66,85],"l":["0.07790","0.07790"],"h":["0.08000","0.08000"],"o":"0.07790"},"2ZEUR":{"a":["0.018850000","5894","5894.000"],"b":["0.018830000","8207","8207.000"],"c":["0.018830000","5935.74532"],"v":["548256.88317","822577.70981"],"p":["0.019586330","0.019518638"],"t":[124,165],"l":["0.018830000","0.018830000"],"h":["0.020050000","0.020050000"],"o":"0.019280000"},"2ZUSD":{"a":["0.020990000","850","850.000"],"b":["0.020970000","28180","28180.000"],"c":["0.020970000","7511.41431"],"v":["3658208.01850",
```

## coinbase products
`https://api.exchange.coinbase.com/products` -> HTTP 200, 356744 bytes
```
[{"id":"EURC-EUR","base_currency":"EURC","quote_currency":"EUR","quote_increment":"0.001","base_increment":"0.01","display_name":"EURC/EUR","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only":false,"status":"delisted","status_message":"","trading_disabled":true,"fx_stablecoin":true,"max_slippage_percentage":"0.01000000","auction_mode":false,"high_bid_limit_percentage":"0.03000000"},{"id":"APT-USD","base_currency":"APT","quote_currency":"USD","quote_increment":"0.0001","base_increment":"0.001","display_name":"APT-USD","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only":false,"status":"online","status_message":"","trading_disabled":false,"fx_stablecoin":false,"max_slippage_percentage":"0.03000000","auction_mode":false,"high_bid_limit_percentage":""},{"id":"ADA-ETH","base_currency":"ADA","quote_currency":"ETH","quote_increment":"0.000001","base_increment":"0.01","display_name":"ADA-ETH","min_market_funds":"0.00022","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only":false,"status":"online","status_message":"","trading_disabled":false,"fx_stablecoin":false,"max_slippage_percentage":"0.03000000","auction_mode":false,"high_bid_limit_percentage":""},{"id":"XRP-USDT","base_currency":"XRP","quote_currency":"USDT","quote_increment":"0.0001","base_increment":"0.000001","display_name":"XRP-USDT","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,
```

## binance vision exchangeInfo
`https://data-api.binance.vision/api/v3/exchangeInfo?symbol=BTCUSDT` -> HTTP 200, 5349 bytes
```
{"timezone":"UTC","serverTime":1794077753441,"rateLimits":[{"rateLimitType":"REQUEST_WEIGHT","interval":"MINUTE","intervalNum":1,"limit":6000},{"rateLimitType":"ORDERS","interval":"SECOND","intervalNum":10,"limit":100},{"rateLimitType":"ORDERS","interval":"DAY","intervalNum":1,"limit":200000},{"rateLimitType":"RAW_REQUESTS","interval":"MINUTE","intervalNum":5,"limit":300000}],"exchangeFilters":[],"symbols":[{"symbol":"BTCUSDT","status":"TRADING","baseAsset":"BTC","baseAssetPrecision":8,"quoteAsset":"USDT","quotePrecision":8,"quoteAssetPrecision":8,"baseCommissionPrecision":8,"quoteCommissionPrecision":8,"orderTypes":["LIMIT","LIMIT_MAKER","MARKET","STOP_LOSS","STOP_LOSS_LIMIT","TAKE_PROFIT","TAKE_PROFIT_LIMIT"],"icebergAllowed":true,"ocoAllowed":true,"otoAllowed":true,"opoAllowed":true,"quoteOrderQtyMarketAllowed":true,"allowTrailingStop":true,"cancelReplaceAllowed":true,"amendAllowed":true,"pegInstructionsAllowed":true,"isSpotTradingAllowed":true,"isMarginTradingAllowed":true,"filters":[{"filterType":"PRICE_FILTER","minPrice":"0.01000000","maxPrice":"1000000.00000000","tickSize":"0.01000000"},{"filterType":"LOT_SIZE","minQty":"0.00001000","maxQty":"9000.00000000","stepSize":"0.00001000"},{"filterType":"ICEBERG_PARTS","limit":100},{"filterType":"MARKET_LOT_SIZE","minQty":"0.00000000","maxQty":"118.53020320","stepSize":"0.00000000"},{"filterType":"TRAILING_DELTA","minTrailingAboveDelta":10,"maxTrailingAboveDelta":2000,"minTrailingBelowDelta":10,"maxTrailingBelowDelta":2000},{"
```

## binance vision klines 1d
`https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=3` -> HTTP 200, 557 bytes
```
[[1793836800000,"80504.01000000","80918.01000000","75208.42000000","76088.01000000","26059.74254000",1793923199999,"2025460886.89644500",4929786,"11649.36680000","904097623.22911000","0"],[1793923200000,"76088.01000000","76416.24000000","74888.00000000","75844.00000000","17207.67786000",1794009599999,"1304297511.90781530",3623348,"9114.41434000","691050346.25323710","0"],[1794009600000,"75844.00000000","76249.99000000","75600.82000000","75824.73000000","4166.61978000",1794095999999,"316494227.68284230",538869,"2089.45198000","158719520.41220330","0"]]
```

## frankfurter v2 rates
`https://api.frankfurter.dev/v2/rates?base=USD&quotes=EUR,JPY,IDR` -> HTTP 200, 190 bytes
```
[{"date":"2026-11-08","base":"USD","quote":"EUR","rate":0.89168},{"date":"2026-11-08","base":"USD","quote":"IDR","rate":18097},{"date":"2026-11-08","base":"USD","quote":"JPY","rate":158.18}]
```

## frankfurter v2 series
`https://api.frankfurter.dev/v2/rates?from=2026-10-15&to=2026-10-20&base=USD&quotes=EUR` -> HTTP 200, 385 bytes
```
[{"date":"2026-10-15","base":"USD","quote":"EUR","rate":0.89278},{"date":"2026-10-16","base":"USD","quote":"EUR","rate":0.89034},{"date":"2026-10-17","base":"USD","quote":"EUR","rate":0.88994},{"date":"2026-10-18","base":"USD","quote":"EUR","rate":0.88977},{"date":"2026-10-19","base":"USD","quote":"EUR","rate":0.89026},{"date":"2026-10-20","base":"USD","quote":"EUR","rate":0.89065}]
```

## frankfurter v2 currencies
`https://api.frankfurter.dev/v2/currencies` -> HTTP 200, 29041 bytes
```
[{"iso_code":"AAVE","iso_numeric":null,"name":"Aave","symbol":"AAVE","type":"crypto","start_date":"2020-10-10","end_date":"2026-11-06"},{"iso_code":"ADA","iso_numeric":null,"name":"Cardano","symbol":"₳","type":"crypto","start_date":"2017-12-01","end_date":"2026-11-06"},{"iso_code":"AED","iso_numeric":"784","name":"United Arab Emirates Dirham","symbol":"د.إ","type":"currency","start_date":"1996-04-11","end_date":"2026-11-08"},{"iso_code":"AFN","iso_numeric":"971","name":"Afghan Afghani","symbol":"؋","type":"currency","start_date":"2003-01-07","end_date":"2026-11-07"},{"iso_code":"ALGO","iso_numeric":null,"name":"Algorand","symbol":"ALGO","type":"crypto","start_date":"2019-06-22","end_date":"2026-11-06"},{"iso_code":"ALL","iso_numeric":"008","name":"Albanian Lek","symbol":"L","type":"currency","start_date":"1998-07-07","end_date":"2026-11-06"},{"iso_code":"AMD","iso_numeric":"051","name":"Armenian Dram","symbol":"֏","type":"currency","start_date":"1994-03-18","end_date":"2026-11-07"},{"iso_code":"ANG","iso_numeric":"532","name":"Netherlands Antillean Guilder","symbol":"ƒ","type":"currency","start_date":"1971-12-18","end_date":"2026-11-08"},{"iso_code":"AOA","iso_numeric":"973","name":"Angolan Kwanza","symbol":"Kz","type":"currency","start_date":"1999-01-04","end_date":"2026-11-06"},{"iso_code":"APT","iso_numeric":null,"name":"Aptos","symbol":"APT","type":"crypto","start_date":"2022-10-13","end_date":"2026-11-06"},{"iso_code":"ARB","iso_numeric":null,"name":"Arbitrum","symbol":"
```

## frankfurter v1 series (old)
`https://api.frankfurter.dev/v1/2026-10-15..2026-10-20?base=USD&symbols=EUR` -> HTTP 200, 203 bytes
```
{"amount":1.0,"base":"USD","start_date":"2026-10-15","end_date":"2026-10-20","rates":{"2026-10-15":{"EUR":0.89222},"2026-10-16":{"EUR":0.88865},"2026-10-19":{"EUR":0.89087},"2026-10-20":{"EUR":0.89166}}}
```
