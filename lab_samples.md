# Raw samples (first 1500 characters)

## kraken assetpairs
`https://api.kraken.com/0/public/AssetPairs` -> HTTP 200, 682808 bytes
```
{"error":[],"result":{"0GEUR":{"altname":"0GEUR","wsname":"0G/EUR","aclass_base":"currency","base":"0G","aclass_quote":"currency","quote":"ZEUR","lot":"unit5","cost_decimals":5,"pair_decimals":3,"lot_decimals":5,"lot_multiplier":1,"leverage_buy":[],"leverage_sell":[],"fees":[],"fees_maker":[],"fee_volume_currency":"ZUSD","margin_call":80,"margin_stop":40,"ordermin":"30","costmin":"0.45","tick_size":"0.001","status":"online","execution_venue":"international"},"0GUSD":{"altname":"0GUSD","wsname":"0G/USD","aclass_base":"currency","base":"0G","aclass_quote":"currency","quote":"ZUSD","lot":"unit5","cost_decimals":5,"pair_decimals":3,"lot_decimals":5,"lot_multiplier":1,"leverage_buy":[2,3],"leverage_sell":[],"fees":[],"fees_maker":[],"fee_volume_currency":"ZUSD","margin_call":80,"margin_stop":40,"ordermin":"30","costmin":"0.5","tick_size":"0.001","status":"online","execution_venue":"international","long_position_limit":40000,"short_position_limit":0},"1INCHEUR":{"altname":"1INCHEUR","wsname":"1INCH/EUR","aclass_base":"currency","base":"1INCH","aclass_quote":"currency","quote":"ZEUR","lot":"unit","cost_decimals":5,"pair_decimals":4,"lot_decimals":8,"lot_multiplier":1,"leverage_buy":[],"leverage_sell":[],"fees":[],"fees_maker":[],"fee_volume_currency":"ZUSD","margin_call":80,"margin_stop":40,"ordermin":"60","costmin":"0.45","tick_size":"0.0001","status":"online","execution_venue":"international"},"1INCHUSD":{"altname":"1INCHUSD","wsname":"1INCH/USD","aclass_base":"currency","base":"1
```

## kraken ticker all
`https://api.kraken.com/0/public/Ticker` -> HTTP 200, 419050 bytes
```
{"error":[],"result":{"0GEUR":{"a":["0.1340000","24968","24968.000"],"b":["0.1320000","31414","31414.000"],"c":["0.1350000","1000.00000"],"v":["1000.00000","8006.82225"],"p":["0.1350000","0.1362467"],"t":[1,11],"l":["0.1350000","0.1340000"],"h":["0.1350000","0.1380000"],"o":"0.1350000"},"0GUSD":{"a":["0.1490000","32414","32414.000"],"b":["0.1480000","769","769.000"],"c":["0.1490000","60.00000"],"v":["14581.02011","71366.97257"],"p":["0.1499187","0.1518973"],"t":[16,74],"l":["0.1490000","0.1470000"],"h":["0.1520000","0.1550000"],"o":"0.1520000"},"1INCHEUR":{"a":["0.07180","4593","4593.000"],"b":["0.07170","177","177.000"],"c":["0.07170","594.51967110"],"v":["29997.75256720","101963.94679638"],"p":["0.07076","0.07052"],"t":[9,35],"l":["0.06990","0.06990"],"h":["0.07170","0.07170"],"o":"0.07030"},"1INCHUSD":{"a":["0.07990","5780","5780.000"],"b":["0.07970","12929","12929.000"],"c":["0.07980","270.73299000"],"v":["57493.43062259","142499.79866346"],"p":["0.07860","0.07850"],"t":[31,70],"l":["0.07790","0.07790"],"h":["0.07980","0.07980"],"o":"0.07790"},"2ZEUR":{"a":["0.019210000","7667","7667.000"],"b":["0.019130000","7492","7492.000"],"c":["0.019260000","260.65226"],"v":["485116.91548","1411124.64761"],"p":["0.019671066","0.019562765"],"t":[116,299],"l":["0.019260000","0.019190000"],"h":["0.020050000","0.020050000"],"o":"0.019280000"},"2ZUSD":{"a":["0.021330000","990","990.000"],"b":["0.021310000","7361","7361.000"],"c":["0.021320000","200.00000"],"v":["3380614.23204","4758745.90
```

## coinbase products
`https://api.exchange.coinbase.com/products` -> HTTP 200, 356744 bytes
```
[{"id":"ORN-USD","base_currency":"ORN","quote_currency":"USD","quote_increment":"0.001","base_increment":"0.01","display_name":"ORN-USD","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only":false,"status":"delisted","status_message":"","trading_disabled":true,"fx_stablecoin":false,"max_slippage_percentage":"0.03000000","auction_mode":false,"high_bid_limit_percentage":""},{"id":"OPN-USD","base_currency":"OPN","quote_currency":"USD","quote_increment":"0.0001","base_increment":"0.01","display_name":"OPN/USD","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only":false,"status":"online","status_message":"","trading_disabled":false,"fx_stablecoin":false,"max_slippage_percentage":"0.03000000","auction_mode":false,"high_bid_limit_percentage":""},{"id":"ZETA-USD","base_currency":"ZETA","quote_currency":"USD","quote_increment":"0.000001","base_increment":"0.1","display_name":"ZETA-USD","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only":false,"status":"online","status_message":"","trading_disabled":false,"fx_stablecoin":false,"max_slippage_percentage":"0.03000000","auction_mode":false,"high_bid_limit_percentage":""},{"id":"BTC-INR","base_currency":"BTC","quote_currency":"INR","quote_increment":"1","base_increment":"0.00000001","display_name":"BTC/INR","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":true,"cancel_only":false,"sta
```

## binance vision exchangeInfo
`https://data-api.binance.vision/api/v3/exchangeInfo?symbol=BTCUSDT` -> HTTP 200, 5349 bytes
```
{"timezone":"UTC","serverTime":1794047171985,"rateLimits":[{"rateLimitType":"REQUEST_WEIGHT","interval":"MINUTE","intervalNum":1,"limit":6000},{"rateLimitType":"ORDERS","interval":"SECOND","intervalNum":10,"limit":100},{"rateLimitType":"ORDERS","interval":"DAY","intervalNum":1,"limit":200000},{"rateLimitType":"RAW_REQUESTS","interval":"MINUTE","intervalNum":5,"limit":300000}],"exchangeFilters":[],"symbols":[{"symbol":"BTCUSDT","status":"TRADING","baseAsset":"BTC","baseAssetPrecision":8,"quoteAsset":"USDT","quotePrecision":8,"quoteAssetPrecision":8,"baseCommissionPrecision":8,"quoteCommissionPrecision":8,"orderTypes":["LIMIT","LIMIT_MAKER","MARKET","STOP_LOSS","STOP_LOSS_LIMIT","TAKE_PROFIT","TAKE_PROFIT_LIMIT"],"icebergAllowed":true,"ocoAllowed":true,"otoAllowed":true,"opoAllowed":true,"quoteOrderQtyMarketAllowed":true,"allowTrailingStop":true,"cancelReplaceAllowed":true,"amendAllowed":true,"pegInstructionsAllowed":true,"isSpotTradingAllowed":true,"isMarginTradingAllowed":true,"filters":[{"filterType":"PRICE_FILTER","minPrice":"0.01000000","maxPrice":"1000000.00000000","tickSize":"0.01000000"},{"filterType":"LOT_SIZE","minQty":"0.00001000","maxQty":"9000.00000000","stepSize":"0.00001000"},{"filterType":"ICEBERG_PARTS","limit":100},{"filterType":"MARKET_LOT_SIZE","minQty":"0.00000000","maxQty":"115.24131476","stepSize":"0.00000000"},{"filterType":"TRAILING_DELTA","minTrailingAboveDelta":10,"maxTrailingAboveDelta":2000,"minTrailingBelowDelta":10,"maxTrailingBelowDelta":2000},{"
```

## binance vision klines 1d
`https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=3` -> HTTP 200, 557 bytes
```
[[1793836800000,"80504.01000000","80918.01000000","75208.42000000","76088.01000000","26059.74254000",1793923199999,"2025460886.89644500",4929786,"11649.36680000","904097623.22911000","0"],[1793923200000,"76088.01000000","76416.24000000","74888.00000000","75844.00000000","17207.67786000",1794009599999,"1304297511.90781530",3623348,"9114.41434000","691050346.25323710","0"],[1794009600000,"75844.00000000","76249.99000000","75790.00000000","76026.00000000","2760.17683000",1794095999999,"209757532.76122880",304442,"1456.05198000","110649725.34751670","0"]]
```

## frankfurter v2 rates
`https://api.frankfurter.dev/v2/rates?base=USD&quotes=EUR,JPY,IDR` -> HTTP 200, 190 bytes
```
[{"date":"2026-11-08","base":"USD","quote":"EUR","rate":0.89162},{"date":"2026-11-08","base":"USD","quote":"IDR","rate":18097},{"date":"2026-11-08","base":"USD","quote":"JPY","rate":158.18}]
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
