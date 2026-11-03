"""markets/providers/transport.py - the only module that can reach the network.

The live transport exists so the path can be reviewed, but no test and no fixture run calls it. Tests inject
deterministic transports. The pipeline uses this transport only when a caller explicitly declares
data_source='live' and passes no transport.

Public, read-only GET requests only: no keys, no login, no retries, no sleeping.
"""

TIMEOUT_SECONDS = 20
USER_AGENT = "btcidr-lab-market-data/0.4 (public read-only, no trading)"


class TransportFailure(Exception):
    """A transport could not return a body. Adapters map this to ProviderError with the same kind."""

    KINDS = ("rate_limited", "timeout", "unavailable")

    def __init__(self, kind, detail, status=None):
        if kind not in self.KINDS:
            raise ValueError(f"unknown transport failure kind {kind!r}")
        self.kind = kind
        self.detail = detail
        self.status = status
        super().__init__(f"{kind}: {detail}")


def live_transport(url):
    """One public GET. Returns the response body bytes. Maps every failure to TransportFailure."""
    import http.client
    import socket
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                                 method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise TransportFailure("rate_limited", "HTTP 429", 429)
        raise TransportFailure("unavailable", f"HTTP {e.code}", e.code)
    except (socket.timeout, TimeoutError) as e:
        raise TransportFailure("timeout", f"timed out: {e}")
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise TransportFailure("timeout", f"timed out: {e.reason}")
        raise TransportFailure("unavailable", f"network error: {type(e.reason).__name__}")
    except (OSError, http.client.HTTPException) as e:
        # Connection resets, dropped sockets, TLS errors, truncated bodies. Reported, never allowed to escape.
        raise TransportFailure("unavailable", f"connection failed: {type(e).__name__}")
    if status != 200:
        raise TransportFailure("unavailable", f"HTTP {status}", status)
    return body
