# Raw samples (first 1500 characters)

## kraken assetpairs
`https://api.kraken.com/0/public/AssetPairs` -> HTTP 200, 680652 bytes
```
{"error":[],"result":{"0GEUR":{"altname":"0GEUR","wsname":"0G/EUR","aclass_base":"currency","base":"0G","aclass_quote":"currency","quote":"ZEUR","lot":"unit5","cost_decimals":5,"pair_decimals":3,"lot_decimals":5,"lot_multiplier":1,"leverage_buy":[],"leverage_sell":[],"fees":[],"fees_maker":[],"fee_volume_currency":"ZUSD","margin_call":80,"margin_stop":40,"ordermin":"17","costmin":"0.45","tick_size":"0.001","status":"online","execution_venue":"international"},"0GUSD":{"altname":"0GUSD","wsname":"0G/USD","aclass_base":"currency","base":"0G","aclass_quote":"currency","quote":"ZUSD","lot":"unit5","cost_decimals":5,"pair_decimals":3,"lot_decimals":5,"lot_multiplier":1,"leverage_buy":[2,3],"leverage_sell":[],"fees":[],"fees_maker":[],"fee_volume_currency":"ZUSD","margin_call":80,"margin_stop":40,"ordermin":"17","costmin":"0.5","tick_size":"0.001","status":"online","execution_venue":"international","long_position_limit":40000,"short_position_limit":0},"1INCHEUR":{"altname":"1INCHEUR","wsname":"1INCH/EUR","aclass_base":"currency","base":"1INCH","aclass_quote":"currency","quote":"ZEUR","lot":"unit","cost_decimals":5,"pair_decimals":4,"lot_decimals":8,"lot_multiplier":1,"leverage_buy":[],"leverage_sell":[],"fees":[],"fees_maker":[],"fee_volume_currency":"ZUSD","margin_call":80,"margin_stop":40,"ordermin":"50","costmin":"0.45","tick_size":"0.0001","status":"online","execution_venue":"international"},"1INCHUSD":{"altname":"1INCHUSD","wsname":"1INCH/USD","aclass_base":"currency","base":"1
```

## kraken ticker all
`https://api.kraken.com/0/public/Ticker` -> HTTP 200, 417847 bytes
```
{"error":[],"result":{"0GEUR":{"a":["0.1540000","2675","2675.000"],"b":["0.1530000","26489","26489.000"],"c":["0.1540000","60.08632"],"v":["8731.13994","57472.90217"],"p":["0.1528157","0.1518290"],"t":[17,96],"l":["0.1520000","0.1470000"],"h":["0.1540000","0.1570000"],"o":"0.1520000"},"0GUSD":{"a":["0.1720000","40936","40936.000"],"b":["0.1710000","27971","27971.000"],"c":["0.1720000","1162.79069"],"v":["50352.36298","228948.38455"],"p":["0.1714319","0.1704765"],"t":[51,266],"l":["0.1690000","0.1640000"],"h":["0.1720000","0.1760000"],"o":"0.1700000"},"1INCHEUR":{"a":["0.07130","6181","6181.000"],"b":["0.07120","5103","5103.000"],"c":["0.07160","5166.81944590"],"v":["29956.71289095","452440.60903556"],"p":["0.07182","0.07059"],"t":[9,131],"l":["0.07150","0.06820"],"h":["0.07220","0.07220"],"o":"0.07210"},"1INCHUSD":{"a":["0.07950","7460","7460.000"],"b":["0.07930","10888","10888.000"],"c":["0.07960","6397.86340530"],"v":["49778.46405443","383007.74375274"],"p":["0.08000","0.07907"],"t":[16,174],"l":["0.07940","0.07740"],"h":["0.08050","0.08050"],"o":"0.08000"},"2ZEUR":{"a":["0.023970000","4721","4721.000"],"b":["0.023940000","6158","6158.000"],"c":["0.023950000","4732.47313"],"v":["60679.50190","2198605.06151"],"p":["0.024294333","0.023891659"],"t":[29,665],"l":["0.023900000","0.023320000"],"h":["0.024490000","0.024490000"],"o":"0.024430000"},"2ZUSD":{"a":["0.026720000","80","80.000"],"b":["0.026700000","6442","6442.000"],"c":["0.026710000","5411.72975"],"v":["287506.93220","4
```

## coinbase products
`https://api.exchange.coinbase.com/products` -> HTTP 200, 356323 bytes
```
[{"id":"RBN-USD","base_currency":"RBN","quote_currency":"USD","quote_increment":"0.00001","base_increment":"0.01","display_name":"RBN-USD","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only":false,"status":"delisted","status_message":"","trading_disabled":true,"fx_stablecoin":false,"max_slippage_percentage":"0.03000000","auction_mode":false,"high_bid_limit_percentage":""},{"id":"HONEY-USD","base_currency":"HONEY","quote_currency":"USD","quote_increment":"0.000001","base_increment":"0.1","display_name":"HONEY-USD","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only":false,"status":"online","status_message":"","trading_disabled":false,"fx_stablecoin":false,"max_slippage_percentage":"0.03000000","auction_mode":false,"high_bid_limit_percentage":""},{"id":"MANA-USD","base_currency":"MANA","quote_currency":"USD","quote_increment":"0.0001","base_increment":"0.01","display_name":"MANA-USD","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only":false,"status":"online","status_message":"","trading_disabled":false,"fx_stablecoin":false,"max_slippage_percentage":"0.03000000","auction_mode":false,"high_bid_limit_percentage":""},{"id":"XYO-USDT","base_currency":"XYO","quote_currency":"USDT","quote_increment":"0.00001","base_increment":"0.1","display_name":"XYO-USDT","min_market_funds":"1","margin_enabled":false,"post_only":false,"limit_only":false,"cancel_only"
```

## binance vision exchangeInfo
`https://data-api.binance.vision/api/v3/exchangeInfo?symbol=BTCUSDT` -> HTTP 200, 5349 bytes
```
{"timezone":"UTC","serverTime":1793419364231,"rateLimits":[{"rateLimitType":"REQUEST_WEIGHT","interval":"MINUTE","intervalNum":1,"limit":6000},{"rateLimitType":"ORDERS","interval":"SECOND","intervalNum":10,"limit":100},{"rateLimitType":"ORDERS","interval":"DAY","intervalNum":1,"limit":200000},{"rateLimitType":"RAW_REQUESTS","interval":"MINUTE","intervalNum":5,"limit":300000}],"exchangeFilters":[],"symbols":[{"symbol":"BTCUSDT","status":"TRADING","baseAsset":"BTC","baseAssetPrecision":8,"quoteAsset":"USDT","quotePrecision":8,"quoteAssetPrecision":8,"baseCommissionPrecision":8,"quoteCommissionPrecision":8,"orderTypes":["LIMIT","LIMIT_MAKER","MARKET","STOP_LOSS","STOP_LOSS_LIMIT","TAKE_PROFIT","TAKE_PROFIT_LIMIT"],"icebergAllowed":true,"ocoAllowed":true,"otoAllowed":true,"opoAllowed":true,"quoteOrderQtyMarketAllowed":true,"allowTrailingStop":true,"cancelReplaceAllowed":true,"amendAllowed":true,"pegInstructionsAllowed":true,"isSpotTradingAllowed":true,"isMarginTradingAllowed":true,"filters":[{"filterType":"PRICE_FILTER","minPrice":"0.01000000","maxPrice":"1000000.00000000","tickSize":"0.01000000"},{"filterType":"LOT_SIZE","minQty":"0.00001000","maxQty":"9000.00000000","stepSize":"0.00001000"},{"filterType":"ICEBERG_PARTS","limit":100},{"filterType":"MARKET_LOT_SIZE","minQty":"0.00000000","maxQty":"102.39495420","stepSize":"0.00000000"},{"filterType":"TRAILING_DELTA","minTrailingAboveDelta":10,"maxTrailingAboveDelta":2000,"minTrailingBelowDelta":10,"maxTrailingBelowDelta":2000},{"
```

## binance vision klines 1d
`https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=3` -> HTTP 200, 556 bytes
```
[[1793232000000,"81343.51000000","81971.00000000","77910.00000000","77991.89000000","23832.18298000",1793318399999,"1905694751.28867070",4200501,"11606.74159000","928951404.35168380","0"],[1793318400000,"77991.89000000","78804.01000000","76325.98000000","77368.77000000","24295.94848000",1793404799999,"1883010706.67806380",4894043,"11423.34439000","885326734.15352940","0"],[1793404800000,"77368.76000000","77654.44000000","77136.20000000","77237.78000000","1337.70407000",1793491199999,"103548709.57295120",302934,"734.36952000","56847797.82086640","0"]]
```

## frankfurter v2 rates
`https://api.frankfurter.dev/v2/rates?base=USD&quotes=EUR,JPY,IDR` -> HTTP 200, 189 bytes
```
[{"date":"2026-10-31","base":"USD","quote":"EUR","rate":0.89504},{"date":"2026-10-30","base":"USD","quote":"IDR","rate":18147},{"date":"2026-10-31","base":"USD","quote":"JPY","rate":157.7}]
```

## frankfurter v2 series
`https://api.frankfurter.dev/v2/rates?from=2026-10-15&to=2026-10-20&base=USD&quotes=EUR` -> HTTP 200, 385 bytes
```
[{"date":"2026-10-15","base":"USD","quote":"EUR","rate":0.89278},{"date":"2026-10-16","base":"USD","quote":"EUR","rate":0.89035},{"date":"2026-10-17","base":"USD","quote":"EUR","rate":0.88994},{"date":"2026-10-18","base":"USD","quote":"EUR","rate":0.88976},{"date":"2026-10-19","base":"USD","quote":"EUR","rate":0.89025},{"date":"2026-10-20","base":"USD","quote":"EUR","rate":0.89066}]
```

## frankfurter v2 currencies
`https://api.frankfurter.dev/v2/currencies` -> HTTP 200, 21876 bytes
```
[{"iso_code":"AED","iso_numeric":"784","name":"United Arab Emirates Dirham","symbol":"د.إ","start_date":"1996-04-11","end_date":"2026-10-31"},{"iso_code":"AFN","iso_numeric":"971","name":"Afghan Afghani","symbol":"؋","start_date":"2003-01-07","end_date":"2026-10-30"},{"iso_code":"ALL","iso_numeric":"008","name":"Albanian Lek","symbol":"L","start_date":"1998-07-07","end_date":"2026-10-30"},{"iso_code":"AMD","iso_numeric":"051","name":"Armenian Dram","symbol":"֏","start_date":"1994-03-18","end_date":"2026-10-30"},{"iso_code":"ANG","iso_numeric":"532","name":"Netherlands Antillean Guilder","symbol":"ƒ","start_date":"1971-12-18","end_date":"2026-10-31"},{"iso_code":"AOA","iso_numeric":"973","name":"Angolan Kwanza","symbol":"Kz","start_date":"1999-01-04","end_date":"2026-10-30"},{"iso_code":"ARS","iso_numeric":"032","name":"Argentine Peso","symbol":"$","start_date":"1998-07-07","end_date":"2026-10-30"},{"iso_code":"AUD","iso_numeric":"036","name":"Australian Dollar","symbol":"$","start_date":"1971-01-04","end_date":"2026-10-31"},{"iso_code":"AWG","iso_numeric":"533","name":"Aruban Florin","symbol":"ƒ","start_date":"1999-01-04","end_date":"2026-10-30"},{"iso_code":"AZN","iso_numeric":"944","name":"Azerbaijani Manat","symbol":"₼","start_date":"2006-01-02","end_date":"2026-10-30"},{"iso_code":"BAM","iso_numeric":"977","name":"Bosnia and Herzegovina Convertible Mark","symbol":"КМ","start_date":"1998-01-06","end_date":"2026-10-31"},{"iso_code":"BBD","iso_numeric":"052","name":"Barbadia
```

## frankfurter v1 series (old)
`https://api.frankfurter.dev/v1/2026-10-15..2026-10-20?base=USD&symbols=EUR` -> HTTP 200, 203 bytes
```
{"amount":1.0,"base":"USD","start_date":"2026-10-15","end_date":"2026-10-20","rates":{"2026-10-15":{"EUR":0.89222},"2026-10-16":{"EUR":0.88865},"2026-10-19":{"EUR":0.89087},"2026-10-20":{"EUR":0.89166}}}
```
