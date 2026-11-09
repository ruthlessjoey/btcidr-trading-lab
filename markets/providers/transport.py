"""markets/providers/transport.py - policy-enforced public market-data GET transport.

No credentials, account access, order APIs, redirects, environment proxies, or retries.
"""
import http.client
import socket
import urllib.error
import urllib.request

import transport_policy

TIMEOUT_SECONDS = 20
USER_AGENT = "btcidr-lab-market-data/0.4 (public read-only, no trading)"


class TransportFailure(Exception):
    """A transport could not return a body. Adapters map this to ProviderError."""

    KINDS = ("rate_limited", "timeout", "unavailable")

    def __init__(self, kind, detail, status=None):
        if kind not in self.KINDS:
            raise ValueError(f"unknown transport failure kind {kind!r}")
        self.kind = kind
        self.detail = detail
        self.status = status
        super().__init__(f"{kind}: {detail}")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def live_transport(url):
    """One exact-policy public GET. Response bytes are capped and deadline-bounded."""
    try:
        limit = transport_policy.validate_request(url, "GET", tier="operational")
    except transport_policy.PolicyError:
        raise TransportFailure("unavailable", "request rejected by transport policy")
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, method="GET")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirectHandler())
    try:
        with opener.open(req, timeout=TIMEOUT_SECONDS) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                raise TransportFailure("unavailable", "unexpected HTTP status", status)
            return transport_policy.read_bounded(resp, limit, TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        status = exc.code if type(exc.code) is int and 100 <= exc.code <= 599 else None
        try:
            exc.close()
        except Exception:
            pass
        if status == 429:
            raise TransportFailure("rate_limited", "HTTP 429", 429)
        raise TransportFailure("unavailable", "HTTP request rejected", status)
    except (socket.timeout, TimeoutError):
        raise TransportFailure("timeout", "request deadline exceeded")
    except transport_policy.PolicyError:
        raise TransportFailure("unavailable", "response rejected by transport policy")
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            raise TransportFailure("timeout", "request deadline exceeded")
        raise TransportFailure("unavailable", "network request failed")
    except (OSError, http.client.HTTPException):
        raise TransportFailure("unavailable", "connection failed")
