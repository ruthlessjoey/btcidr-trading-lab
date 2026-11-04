"""markets/risk - the independent, deterministic risk decision engine (M6).

Public API:
    evaluate_risk(request, config) -> RiskDecision     the only decision entry point (engine.py)
    build_risk_config(mapping) -> RiskConfig            strict, explicit configuration (config.py)
    RiskConfig, RiskConfigError                         configuration and its refusal
    RiskRequest, AccountSnapshot, PositionState, PendingProposal, PriceObservation   inputs (model.py)
    RiskDecision, RuleResult, REASON_CODES, ELIGIBLE, REJECTED, NO_TRADE            outputs (model.py)

Responsibilities. The strategy engine (M5) proposes BUY, SELL or HOLD. This package decides whether a proposal is
eligible for PAPER trading and the permitted size, under explicit limits. It does not fetch data, read a clock, call a
provider, hold credentials, place orders, or keep state. A portfolio engine and an execution engine are separate, future
milestones that require their own approval.

Approval means only that the supplied proposal passed the configured checks on the supplied state. It is not a guarantee
against market loss, and it is not a claim of profitability.

Stated assumptions, each of which a caller must supply explicitly:
  - the stop price for a BUY (M5 decisions carry no stop, and max risk per trade cannot be defined without one);
  - the current price, its time and its source;
  - the account state: equity, cash, remaining risk budget, positions with marks, and pending proposals.
Nothing here defaults or estimates any of them.
"""
from markets.risk.config import RiskConfig, RiskConfigError, build_risk_config  # noqa: F401
from markets.risk.engine import evaluate_risk  # noqa: F401
from markets.risk.model import (ELIGIBLE, NO_TRADE, REASON_CODES, REJECTED, AccountSnapshot,  # noqa: F401
                                PendingProposal, PositionState, PriceObservation, RiskDecision, RiskRequest,
                                RuleResult)
