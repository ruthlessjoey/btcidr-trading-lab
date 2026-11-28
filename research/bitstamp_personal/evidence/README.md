# Official-source evidence captures

These files are small, structured research extracts of specific official Bitstamp pages, not raw HTML, complete page copies, market data, or legal opinions.

Each JSON capture records:
- official source URL and the page publication date where known;
- research capture date;
- the claim used in the point-in-time manifest;
- one short supporting excerpt;
- explicit limitations and what the source does not establish.

The manifest stores a relative `snapshot_path` and SHA-256 for each capture. The offline verifier reads the file beneath this directory, rejects path traversal and symbolic links, enforces a 64 KiB size bound, and recomputes the SHA-256 before accepting the source reference.

**Integrity scope:** the hash proves the committed evidence-extract bytes match the manifest. It does not cryptographically authenticate the original website, freeze the live website, establish that the excerpt is complete, or replace independent review. Reviewers must follow each official URL and check the cited claim against the source. No raw OHLC or order data is included.

The captures do not resolve the missing continuous historical market-status ledgers, exact market-order enablement timestamps, or the data-retention rights question. Those gates remain closed.
