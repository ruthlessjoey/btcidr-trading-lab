"""markets/risk/config.py - the explicit risk configuration (M6).

Every limit is required. There are no defaults: a missing or unknown key is refused. The configuration is validated
once, when it is built. A risk decision records the configuration's version and fingerprint, so a decision can be
reproduced and audited.

Fields:
  version                      text identifier of this configuration, required
  allowed_asset_classes        tuple of asset classes this configuration permits, e.g. ("crypto",); required, non-empty
  allowed_listings             tuple of canonical listings permitted; () means every listing of an allowed asset class
  max_risk_fraction_per_trade  fraction of account equity that one BUY may put at risk, in (0, 1]
  max_position_notional        largest notional of one BUY, in account currency, > 0
  max_exposure_fraction        largest total exposure after a BUY, as a fraction of equity, in (0, 1]
  quantity_step                quantities must be whole multiples of this, > 0
  money_quantum                reported money is rounded up to a multiple of this, > 0
  max_price_age_s              the price observation may be at most this many seconds old, integer >= 0
  pyramiding                   True to permit a BUY into a listing already held; False refuses it (required)
"""
import hashlib
import json
from dataclasses import dataclass

from markets.risk.amounts import NumberError, parse_fraction_of_one, parse_int, parse_positive, to_text

FIELDS = ("version", "allowed_asset_classes", "allowed_listings", "max_risk_fraction_per_trade",
          "max_position_notional", "max_exposure_fraction", "quantity_step", "money_quantum", "max_price_age_s",
          "pyramiding")


class RiskConfigError(ValueError):
    """The risk configuration is invalid. This is a caller error, raised before any decision is made."""


@dataclass(frozen=True)
class RiskConfig:
    version: str
    allowed_asset_classes: tuple
    allowed_listings: tuple
    max_risk_fraction_per_trade: object      # Decimal
    max_position_notional: object            # Decimal
    max_exposure_fraction: object            # Decimal
    quantity_step: object                    # Decimal
    money_quantum: object                    # Decimal
    max_price_age_s: int
    pyramiding: bool

    def fingerprint(self):
        payload = {
            "version": self.version,
            "allowed_asset_classes": list(self.allowed_asset_classes),
            "allowed_listings": list(self.allowed_listings),
            "max_risk_fraction_per_trade": to_text(self.max_risk_fraction_per_trade),
            "max_position_notional": to_text(self.max_position_notional),
            "max_exposure_fraction": to_text(self.max_exposure_fraction),
            "quantity_step": to_text(self.quantity_step),
            "money_quantum": to_text(self.money_quantum),
            "max_price_age_s": self.max_price_age_s,
            "pyramiding": self.pyramiding,
        }
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(text.encode("ascii")).hexdigest()


def _text_tuple(name, value, allow_empty):
    if not isinstance(value, (tuple, list)) or any(not isinstance(v, str) or not v for v in value):
        raise RiskConfigError(f"{name} must be a sequence of non-empty strings")
    if len(set(value)) != len(value):
        raise RiskConfigError(f"{name} must not repeat an entry")
    if not value and not allow_empty:
        raise RiskConfigError(f"{name} must not be empty")
    return tuple(value)


def build_risk_config(mapping):
    """Validates a mapping with exactly FIELDS and returns a RiskConfig. Raises RiskConfigError on any problem."""
    if not isinstance(mapping, dict):
        raise RiskConfigError("risk configuration must be a mapping")
    missing = [f for f in FIELDS if f not in mapping]
    if missing:
        raise RiskConfigError(f"missing risk configuration key(s): {', '.join(missing)}")
    unknown = sorted(set(mapping) - set(FIELDS))
    if unknown:
        raise RiskConfigError(f"unknown risk configuration key(s): {', '.join(unknown)}")
    try:
        version = mapping["version"]
        if not isinstance(version, str) or not version or len(version) > 64:
            raise RiskConfigError("version must be a non-empty string of at most 64 characters")
        pyramiding = mapping["pyramiding"]
        if not isinstance(pyramiding, bool):
            raise RiskConfigError("pyramiding must be a boolean")
        return RiskConfig(
            version=version,
            allowed_asset_classes=_text_tuple("allowed_asset_classes", mapping["allowed_asset_classes"], False),
            allowed_listings=_text_tuple("allowed_listings", mapping["allowed_listings"], True),
            max_risk_fraction_per_trade=parse_fraction_of_one("max_risk_fraction_per_trade",
                                                              mapping["max_risk_fraction_per_trade"]),
            max_position_notional=parse_positive("max_position_notional", mapping["max_position_notional"]),
            max_exposure_fraction=parse_fraction_of_one("max_exposure_fraction", mapping["max_exposure_fraction"]),
            quantity_step=parse_positive("quantity_step", mapping["quantity_step"]),
            money_quantum=parse_positive("money_quantum", mapping["money_quantum"]),
            max_price_age_s=parse_int("max_price_age_s", mapping["max_price_age_s"], 0),
            pyramiding=pyramiding,
        )
    except NumberError as e:
        raise RiskConfigError(str(e)) from e
