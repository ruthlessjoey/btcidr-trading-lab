"""markets/strategies - the provider-neutral, market-neutral strategy engine (M5).

Public API:
    Strategy, ParamSpec              the strategy contract (contract.py)
    StrategyDecision                 the standardized, serializable decision (decision.py)
    StrategyRegistry, default_registry  explicit registration and lookup (registry.py)
    evaluate_report                  one strategy, one data report -> one decision (engine.py)
    BUY, SELL, HOLD, NO_DATA, INVALID, and the error classes

Status semantics: see the table in engine.py. A strategy may return only BUY, SELL or HOLD.

Risk separation (documented, not implemented): a strategy proposes BUY, SELL or HOLD and nothing else. It has no field
for exposure, size, leverage, account or order. A future independent risk engine would take a StrategyDecision together
with its own limits and return an approval or a refusal. That engine is not in M5 and must be a separate, reviewed
milestone. Until then no decision here reaches any execution path.

Extension point (not implemented): the next strategy is a new module that subclasses Strategy, declares its identity and
compatibility, and is registered in default_registry() or by the caller. No strategy may import a provider, the network
or an execution module. Independent example strategies are deferred until their assumptions are specified.

Equity and FX listings are refused by every strategy here, because their calendars and validation paths are not
implemented (see markets/calendars.py).
"""
from markets.strategies.contract import (  # noqa: F401
    BUY, DECISIONS, ENGINE_REASON_CODES, HOLD, INVALID, NO_DATA, SELL, STRATEGY_DECISIONS,
    DuplicateStrategyError, ParamSpec, RegistryError, Strategy, StrategyConfigError, StrategyError,
    UnknownStrategyError, VersionConflictError,
)
from markets.strategies.decision import StrategyDecision, canonical_json, config_fingerprint  # noqa: F401
from markets.strategies.engine import evaluate_report  # noqa: F401
from markets.strategies.registry import StrategyRegistry, default_registry  # noqa: F401
