"""markets/risk/model.py - inputs, rule results and the structured risk decision (M6).

Inputs are frozen dataclasses. They hold raw values exactly as the caller supplied them; the engine validates and parses
them. Nothing here mutates, retains or logs a caller's object. Account identifiers and credentials are not part of any
input, so none can appear in a decision.

Output statuses:
  ELIGIBLE   every applicable rule passed. The proposal may be used for PAPER trading only. This is not a guarantee
             against market loss, and it is not an order.
  REJECTED   at least one rule failed, or an input was invalid. Every failed rule's reason code is listed.
  NO_TRADE   the strategy decision was HOLD, and the inputs were valid. There is no proposal to size.
"""
import json
from dataclasses import dataclass, field

SCHEMA = "risk-decision-m6-v1"
ELIGIBLE = "ELIGIBLE"
REJECTED = "REJECTED"
NO_TRADE = "NO_TRADE"
STATUSES = (ELIGIBLE, REJECTED, NO_TRADE)

PASS = "PASS"
FAIL = "FAIL"
NOT_APPLICABLE = "NOT_APPLICABLE"

NO_RISK_DISCLAIMER = ("Risk approval means only that the supplied proposal passed the configured checks on the supplied "
                      "state. It is not a guarantee against market loss or a claim of profitability. No order is placed.")

# Machine-readable reason codes. Each failed rule or invalid input contributes exactly one of these.
REASON_CODES = (
    "INVALID_LISTING", "LISTING_MISMATCH", "UNSUPPORTED_ASSET_CLASS", "UNSUPPORTED_LISTING",
    "INVALID_STRATEGY_DECISION", "DATA_NOT_COMPLETE", "NOT_ACTIONABLE",
    "INVALID_PRICE", "INVALID_TIME", "FUTURE_PRICE", "STALE_PRICE",
    "MISSING_ACCOUNT_STATE", "INVALID_EQUITY", "INVALID_CASH", "INVALID_RISK_BUDGET", "INVALID_POSITION",
    "INCONSISTENT_ACCOUNT", "INVALID_PENDING_PROPOSAL", "DUPLICATE_PROPOSAL",
    "INVALID_QUANTITY", "QUANTITY_STEP_MISMATCH", "INVALID_STOP",
    "UNSUPPORTED_DIRECTION", "NO_POSITION_TO_SELL", "SELL_EXCEEDS_POSITION", "POSITION_CONFLICT",
    "MAX_RISK_EXCEEDED", "MAX_NOTIONAL_EXCEEDED", "INSUFFICIENT_CAPITAL", "MAX_EXPOSURE_EXCEEDED",
)


@dataclass(frozen=True)
class PriceObservation:
    listing: str
    price: object            # decimal string, int or Decimal
    as_of_s: object          # integer UTC epoch second of the observation
    source: str              # text identifying where the price came from, e.g. a dataset hash; required


@dataclass(frozen=True)
class PositionState:
    listing: str
    quantity: object         # decimal; negative values are refused (no short positions)
    mark_price: object       # decimal, > 0 when quantity > 0


@dataclass(frozen=True)
class PendingProposal:
    listing: str
    side: str                # "BUY" or "SELL" (proposals not yet resolved)


@dataclass(frozen=True)
class AccountSnapshot:
    equity: object           # decimal, > 0
    cash: object             # decimal, >= 0; available buying power (no leverage)
    risk_budget: object      # decimal, > 0; remaining risk this account may take on
    positions: tuple = ()    # tuple of PositionState
    pending: tuple = ()      # tuple of PendingProposal


@dataclass(frozen=True)
class RiskRequest:
    strategy_decision: object    # a markets.strategies.StrategyDecision (M5)
    listing: str                 # canonical listing this proposal is for
    price: PriceObservation      # validated market price to value the proposal
    now_s: object                # explicit reference time, integer UTC epoch second; never the machine clock
    account: object              # AccountSnapshot, or None (refused as MISSING_ACCOUNT_STATE)
    requested_quantity: object = None   # decimal; required for BUY and SELL, must be absent for HOLD
    stop_price: object = None           # decimal; required for BUY (must be below price), absent otherwise


@dataclass(frozen=True)
class RuleResult:
    name: str
    status: str                  # PASS, FAIL or NOT_APPLICABLE
    reason_code: object          # one of REASON_CODES when FAIL, else None
    detail: str


@dataclass(frozen=True)
class RiskDecision:
    status: str
    listing: object
    side: object
    strategy_id: object
    strategy_version: object
    strategy_decision: object
    strategy_reference_open_s: object
    strategy_config_fingerprint: object
    evaluated_at_s: object
    risk_config_version: object
    risk_config_fingerprint: object
    requested_quantity: object = None
    permitted_quantity: object = None
    approved_quantity: object = None    # set only for ELIGIBLE: the quantity approved for PAPER trading
    entry_price: object = None
    stop_price: object = None
    notional: object = None
    max_loss: object = None
    equity: object = None
    cash: object = None
    exposure_before: object = None
    exposure_after: object = None
    caps: dict = field(default_factory=dict)
    rules: tuple = ()
    reason_codes: tuple = ()
    explanations: tuple = ()

    def to_dict(self):
        return {
            "schema": SCHEMA,
            "status": self.status,
            "listing": self.listing,
            "side": self.side,
            "strategy": {"id": self.strategy_id, "version": self.strategy_version,
                         "decision": self.strategy_decision,
                         "reference_open_s": self.strategy_reference_open_s,
                         "config_fingerprint": self.strategy_config_fingerprint},
            "evaluated_at_s": self.evaluated_at_s,
            "risk_config": {"version": self.risk_config_version, "fingerprint": self.risk_config_fingerprint},
            "requested_quantity": self.requested_quantity,
            "permitted_quantity": self.permitted_quantity,
            "approved_quantity": self.approved_quantity,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "notional": self.notional,
            "max_loss": self.max_loss,
            "equity": self.equity,
            "cash": self.cash,
            "exposure_before": self.exposure_before,
            "exposure_after": self.exposure_after,
            "caps": dict(sorted(self.caps.items())),
            "rules": [{"name": r.name, "status": r.status, "reason_code": r.reason_code, "detail": r.detail}
                      for r in self.rules],
            "reason_codes": list(self.reason_codes),
            "explanations": list(self.explanations),
            "disclaimer": NO_RISK_DISCLAIMER,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
