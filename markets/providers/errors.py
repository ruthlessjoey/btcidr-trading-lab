"""markets/providers/errors.py - structured provider errors. No imports from this package, so every module can use it."""

KINDS = ("unsupported_listing", "unsupported_interval", "rate_limited", "timeout", "unavailable",
         "bad_payload", "empty", "conflicting_duplicate", "history_unavailable")
RETRIABLE_KINDS = frozenset({"rate_limited", "timeout", "unavailable"})


class ProviderError(Exception):
    """A structured provider failure. The kind is one of KINDS. Retriable kinds are informational only:
    the pipeline never retries automatically."""

    def __init__(self, kind, provider, detail, http_status=None):
        if kind not in KINDS:
            raise ValueError(f"unknown provider error kind {kind!r}")
        self.kind = kind
        self.provider = provider
        self.detail = detail
        self.http_status = http_status
        super().__init__(f"{provider}: {kind}: {detail}")

    @property
    def retriable(self):
        return self.kind in RETRIABLE_KINDS

    def to_dict(self):
        return {"kind": self.kind, "provider": self.provider, "detail": self.detail,
                "http_status": self.http_status, "retriable": self.retriable}
