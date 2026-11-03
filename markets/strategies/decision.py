"""markets/strategies/decision.py - the standardized, serializable strategy decision (M5).

A StrategyDecision is a research record. It is not an order, a position, a short sale, a risk approval or a size.

Serialization and reproducibility rules:
  - to_json() uses sorted keys, no whitespace, ASCII, and refuses NaN and infinity.
  - every float is rounded to contract.DECIMALS places (negative zero becomes zero) before it is stored.
  - the config fingerprint is the SHA-256 of the canonical JSON of {strategy_id, strategy_version, config}, so two
    decisions with the same fingerprint were produced by the same strategy version under the same configuration.
  - a decision holds no clock reading. Its evaluation time is the explicit reference time of the data report.
"""
import hashlib
import json
from dataclasses import dataclass, field

from markets.strategies import contract as C

SCHEMA = "strategy-decision-m5-v1"
NO_TRADING = ("Research decision only. Not an order, not a position, not a short sale, not a risk approval and not an "
              "instruction to trade.")


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def config_fingerprint(strategy_id, strategy_version, config):
    payload = {"strategy_id": strategy_id, "strategy_version": strategy_version, "config": config}
    return hashlib.sha256(canonical_json(payload).encode("ascii")).hexdigest()


def _round_mapping(mapping):
    return {k: C.round_value(v) for k, v in sorted(mapping.items())}


@dataclass(frozen=True)
class StrategyDecision:
    strategy_id: str
    strategy_version: str
    listing: str                        # canonical listing identity
    timeframe_s: int
    evaluation_now_s: int               # explicit reference time, from the data report
    reference_open_s: object            # basis candle open time; None when there is no basis candle
    reference_close_s: object
    decision: str                       # one of contract.DECISIONS
    reason_codes: tuple
    reasons: tuple
    indicators: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    config_fingerprint: str = ""

    def __post_init__(self):
        if self.decision not in C.DECISIONS:
            raise C.StrategyError(f"unknown decision {self.decision!r}")
        if not all(isinstance(c, str) for c in self.reason_codes):
            raise C.StrategyError("reason codes must be strings")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "reasons", tuple(str(r) for r in self.reasons))
        object.__setattr__(self, "indicators", _round_mapping(self.indicators))
        object.__setattr__(self, "config", _round_mapping(self.config))

    def to_dict(self):
        return {
            "schema": SCHEMA,
            "strategy": {"id": self.strategy_id, "version": self.strategy_version},
            "listing": self.listing,
            "timeframe_s": self.timeframe_s,
            "evaluation_now_s": self.evaluation_now_s,
            "reference_candle": {"open_s": self.reference_open_s, "close_s": self.reference_close_s},
            "decision": self.decision,
            "reason_codes": list(self.reason_codes),
            "reasons": list(self.reasons),
            "indicators": dict(self.indicators),
            "provenance": json.loads(canonical_json(self.provenance)),
            "config": dict(self.config),
            "config_fingerprint": self.config_fingerprint,
            "no_trading": NO_TRADING,
        }

    def to_json(self):
        return canonical_json(self.to_dict())
