"""markets/strategies/contract.py - the provider-neutral, market-neutral strategy contract (M5).

A strategy is a deterministic function from validated canonical candles to a research decision. It:
  - has a stable id and an explicit version;
  - declares the listings, intervals and history it needs (compatibility rules);
  - declares a configuration schema, validated before use;
  - explains its decision through reason codes, reasons and indicator values;
  - never touches a provider, the network, an order, a broker, an account or a credential.

Strategies return only BUY, SELL or HOLD. NO_DATA and INVALID are produced by the engine (markets/strategies/engine.py),
never by a strategy. A BUY, SELL or HOLD is a research decision about a basis candle. It is not an order, not a position,
not a short sale and not an instruction to trade.

Nothing in this module names an exchange, a provider, an asset or a model.
"""
import abc
import math
import re
from dataclasses import dataclass

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"
NO_DATA = "NO_DATA"
INVALID = "INVALID"
DECISIONS = (BUY, SELL, HOLD, NO_DATA, INVALID)
STRATEGY_DECISIONS = (BUY, SELL, HOLD)

# Reason codes the ENGINE may attach. Each strategy declares its own codes in Strategy.reason_codes.
ENGINE_REASON_CODES = (
    "UNSUPPORTED_LISTING",     # the strategy does not declare this listing
    "UNSUPPORTED_INTERVAL",    # the strategy does not declare this interval
    "LISTING_MISMATCH",        # the listing passed in is not the listing the data report describes
    "DATA_REFUSED",            # the data pipeline refused the data (any refusal other than missing slots)
    "DATA_INCOMPLETE",         # the data pipeline reported PARTIAL: some expected slots are missing
    "DATA_UNAVAILABLE",        # the data pipeline reported UNAVAILABLE: no usable candles for the window
    "INSUFFICIENT_HISTORY",    # complete data, but fewer candles than the strategy requires
    "INPUT_MISSING",           # a COMPLETE report without canonical candles: a contract violation, refused
)

STRATEGY_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STRATEGY_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]{0,31}")
MAX_ID_LENGTH = 64

DECIMALS = 8   # every float in a decision is rounded to this many decimal places before serialization


class StrategyError(Exception):
    """Base class for strategy-layer refusals."""


class StrategyConfigError(StrategyError):
    """A configuration does not match the strategy's schema. Nothing is defaulted silently for an unknown key."""


class RegistryError(StrategyError):
    """Base class for registry refusals."""


class DuplicateStrategyError(RegistryError):
    """The same strategy id and version is registered twice."""


class UnknownStrategyError(RegistryError):
    """No strategy has this id. There is no fallback to another strategy."""


class VersionConflictError(RegistryError):
    """The id is registered at a different version, or a lookup asked for a version that is not registered."""


@dataclass(frozen=True)
class ParamSpec:
    """One configuration parameter. kind is 'int' or 'float'. Bounds are inclusive when given."""
    kind: str
    default: object
    minimum: object = None
    maximum: object = None


def round_value(value):
    """Deterministic rounding and normalization for one serialized value.
    Floats must be finite and are rounded to DECIMALS places; negative zero becomes zero. Ints, bools, strings and
    None pass through. Anything else is refused, so a decision can always be serialized."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StrategyError(f"non-finite number {value!r} cannot be serialized deterministically")
        rounded = round(value, DECIMALS)
        return 0.0 if rounded == 0 else rounded
    raise StrategyError(f"value of type {type(value).__name__} is not serializable as a decision value")


def normalize_config(schema, supplied):
    """Validates a configuration against a schema and fills defaults. Unknown keys, wrong types, booleans given as
    numbers, non-finite floats and out-of-range values are refused. Returns a new dict with sorted keys."""
    if supplied is None:
        supplied = {}
    if not isinstance(supplied, dict):
        raise StrategyConfigError("configuration must be a mapping")
    unknown = sorted(set(supplied) - set(schema))
    if unknown:
        raise StrategyConfigError(f"unknown configuration key(s): {', '.join(unknown)}")
    out = {}
    for name in sorted(schema):
        spec = schema[name]
        value = supplied.get(name, spec.default)
        if spec.kind == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise StrategyConfigError(f"{name} must be an integer")
        elif spec.kind == "float":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise StrategyConfigError(f"{name} must be a number")
            if not math.isfinite(float(value)):
                raise StrategyConfigError(f"{name} must be finite")
            value = round_value(float(value))
        else:
            raise StrategyConfigError(f"schema for {name} has an unknown kind {spec.kind!r}")
        if spec.minimum is not None and value < spec.minimum:
            raise StrategyConfigError(f"{name} must be at least {spec.minimum}")
        if spec.maximum is not None and value > spec.maximum:
            raise StrategyConfigError(f"{name} must be at most {spec.maximum}")
        out[name] = value
    return out


class Strategy(abc.ABC):
    """Base class for strategies. Subclasses set the identity and compatibility attributes and implement two methods.

    Attributes:
      strategy_id      stable lowercase id, e.g. "s1-btc-daily-trend"
      version          explicit version text, e.g. "btc-rules-v1"; a change of version is a change of behaviour
      description      one line, for the registry listing
      asset_classes    accepted asset classes; () means refuse everything (a strategy must declare at least one)
      market_types     accepted market types; () means any
      base_assets      accepted base assets; () means any
      quote_assets     accepted quote assets; () means any
      intervals_s      accepted candle intervals in seconds
      CONFIG_SCHEMA    {name: ParamSpec}; () means no tunable parameters
      reason_codes     every reason code this strategy may attach to a decision

    Methods:
      required_history(config) -> int        candles needed, counting the basis candle
      evaluate(config, candles) -> dict      pure: {decision, reason_codes, reasons, indicators}; reads only `candles`
    """

    strategy_id = ""
    version = ""
    description = ""
    asset_classes = ()
    market_types = ()
    base_assets = ()
    quote_assets = ()
    intervals_s = ()
    canonical_listings = ()     # () = no exact-listing restriction; otherwise the only canonical listings accepted
    CONFIG_SCHEMA = {}
    reason_codes = ()

    def normalize_config(self, supplied):
        return normalize_config(self.CONFIG_SCHEMA, supplied)

    def compatibility_problems(self, listing, timeframe_s):
        """Returns (engine_reason_code, text) for each reason the listing or interval is not supported."""
        problems = []
        inst = listing.instrument
        if self.canonical_listings and listing.canonical not in self.canonical_listings:
            problems.append(("UNSUPPORTED_LISTING", f"listing {listing.canonical!r} is not one of the exact listings "
                                                    f"supported by {self.strategy_id}: "
                                                    f"{', '.join(self.canonical_listings)}"))
        if inst.asset_class not in self.asset_classes:
            problems.append(("UNSUPPORTED_LISTING", f"asset class {inst.asset_class!r} is not supported by "
                                                    f"{self.strategy_id}"))
        if self.market_types and listing.market_type not in self.market_types:
            problems.append(("UNSUPPORTED_LISTING", f"market type {listing.market_type!r} is not supported by "
                                                    f"{self.strategy_id}"))
        if self.base_assets and inst.base not in self.base_assets:
            problems.append(("UNSUPPORTED_LISTING", f"base asset {inst.base!r} is not supported by "
                                                    f"{self.strategy_id}"))
        if self.quote_assets and inst.quote not in self.quote_assets:
            problems.append(("UNSUPPORTED_LISTING", f"quote asset {inst.quote!r} is not supported by "
                                                    f"{self.strategy_id}"))
        if timeframe_s not in self.intervals_s:
            problems.append(("UNSUPPORTED_INTERVAL", f"interval {timeframe_s}s is not supported by "
                                                     f"{self.strategy_id}"))
        return problems

    @abc.abstractmethod
    def required_history(self, config):
        """Number of completed candles the evaluation needs, including the basis candle."""

    @abc.abstractmethod
    def evaluate(self, config, candles):
        """Pure evaluation of validated, complete candles, oldest first. The basis candle is candles[-1].

        Must return a dict with:
          decision       one of STRATEGY_DECISIONS
          reason_codes   list of codes, each in self.reason_codes
          reasons        list of human-readable strings
          indicators     dict of name -> number or None
        Must not read the clock, the network, the filesystem, a provider or any state outside its arguments."""

    def describe(self):
        """Inspectable metadata for the registry listing. Plain data only."""
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "description": self.description,
            "asset_classes": list(self.asset_classes),
            "market_types": list(self.market_types),
            "base_assets": list(self.base_assets),
            "quote_assets": list(self.quote_assets),
            "intervals_s": list(self.intervals_s),
            "canonical_listings": list(self.canonical_listings),
            "config_schema": {k: {"kind": v.kind, "default": v.default, "minimum": v.minimum, "maximum": v.maximum}
                              for k, v in sorted(self.CONFIG_SCHEMA.items())},
            "reason_codes": list(self.reason_codes),
        }


def validate_identity(strategy):
    """Refuses a strategy whose identity or declared vocabulary is malformed. Called at registration."""
    if not isinstance(strategy, Strategy):
        raise StrategyError("only Strategy instances can be registered")
    sid = strategy.strategy_id
    if not isinstance(sid, str) or not sid or len(sid) > MAX_ID_LENGTH or not STRATEGY_ID.fullmatch(sid):
        raise StrategyError(f"invalid strategy_id {sid!r}: lowercase letters, digits and single hyphens only")
    ver = strategy.version
    if not isinstance(ver, str) or not STRATEGY_VERSION.fullmatch(ver):
        raise StrategyError(f"invalid version {ver!r} for {sid}")
    if not strategy.asset_classes:
        raise StrategyError(f"{sid} must declare at least one asset class")
    if not strategy.intervals_s:
        raise StrategyError(f"{sid} must declare at least one interval")
    if not strategy.reason_codes:
        raise StrategyError(f"{sid} must declare its reason codes")
    for code in strategy.reason_codes:
        if not isinstance(code, str) or not code or code in ENGINE_REASON_CODES:
            raise StrategyError(f"{sid} declares an invalid or engine-owned reason code {code!r}")
