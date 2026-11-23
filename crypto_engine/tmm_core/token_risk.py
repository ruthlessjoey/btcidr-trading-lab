"""Fail-closed, evidence-driven token eligibility gate for crypto/meme research.

The gate consumes caller-supplied evidence only. It does not inspect contracts,
query chains, verify source truth, generate signals, or authorize orders.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .portfolio import PortfolioError, _d

D = Decimal
BOOLEAN_CHECKS = frozenset({
    "contract_verified", "mint_authority_disabled", "freeze_authority_disabled",
    "upgrade_authority_disabled", "honeypot_check_passed", "market_active",
})
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class TokenRiskError(ValueError):
    """Raised when token risk evidence or policy is malformed."""


@dataclass(frozen=True)
class TokenRiskEvidence:
    token_id: str
    source_id: str
    source_sha256: str
    source_timestamp: int
    observed_at: int
    contract_verified: bool | None = None
    mint_authority_disabled: bool | None = None
    freeze_authority_disabled: bool | None = None
    upgrade_authority_disabled: bool | None = None
    honeypot_check_passed: bool | None = None
    market_active: bool | None = None
    liquidity_usd: Decimal | str | float | None = None
    top_holder_share: Decimal | str | float | None = None
    lp_lock_ratio: Decimal | str | float | None = None
    buy_tax_bps: Decimal | str | float | None = None
    sell_tax_bps: Decimal | str | float | None = None
    holder_count: int | None = None


@dataclass(frozen=True)
class TokenRiskPolicy:
    required_checks: tuple[str, ...]
    min_liquidity_usd: Decimal | str | float
    max_top_holder_share: Decimal | str | float
    min_lp_lock_ratio: Decimal | str | float
    max_buy_tax_bps: Decimal | str | float
    max_sell_tax_bps: Decimal | str | float
    min_holder_count: int
    max_evidence_age_seconds: int


def evaluate_token_eligibility(*, evidence: TokenRiskEvidence,
                               policy: TokenRiskPolicy,
                               decision_time: int) -> dict[str, object]:
    """Return BLOCKED or ELIGIBLE_FOR_HUMAN_REVIEW; never authorizes a trade."""
    if not isinstance(evidence, TokenRiskEvidence) or not isinstance(policy, TokenRiskPolicy):
        raise TokenRiskError("typed TokenRiskEvidence and TokenRiskPolicy are required")
    if isinstance(decision_time, bool) or not isinstance(decision_time, int) or decision_time < 0:
        raise TokenRiskError("decision_time must be a nonnegative integer timestamp")
    if (not evidence.token_id or not evidence.token_id.strip()
            or not evidence.source_id or not evidence.source_id.strip()):
        raise TokenRiskError("token_id and source_id are required")
    if not isinstance(evidence.source_sha256, str) or not HASH_RE.fullmatch(evidence.source_sha256):
        raise TokenRiskError("source_sha256 must be a lowercase 64-character SHA-256 hex digest")
    for field, stamp in (("source_timestamp", evidence.source_timestamp),
                         ("observed_at", evidence.observed_at)):
        if isinstance(stamp, bool) or not isinstance(stamp, int) or stamp < 0 or stamp > decision_time:
            raise TokenRiskError(f"{field} must be a valid timestamp no later than decision_time")
    if evidence.source_timestamp > evidence.observed_at:
        raise TokenRiskError("source_timestamp cannot be later than observed_at")
    if (not isinstance(policy.max_evidence_age_seconds, int)
            or isinstance(policy.max_evidence_age_seconds, bool)
            or policy.max_evidence_age_seconds < 0):
        raise TokenRiskError("max_evidence_age_seconds must be a nonnegative integer")
    if (not isinstance(policy.min_holder_count, int) or isinstance(policy.min_holder_count, bool)
            or policy.min_holder_count < 0):
        raise TokenRiskError("min_holder_count must be a nonnegative integer")
    if (not isinstance(policy.required_checks, tuple)
            or any(not isinstance(check, str) for check in policy.required_checks)
            or len(set(policy.required_checks)) != len(policy.required_checks)):
        raise TokenRiskError("required_checks must be a tuple of unique string check names")
    if any(check not in BOOLEAN_CHECKS for check in policy.required_checks):
        raise TokenRiskError("required_checks contains an unsupported boolean evidence field")

    try:
        min_liquidity = _d(policy.min_liquidity_usd, "min_liquidity_usd")
        max_holder_share = _d(policy.max_top_holder_share, "max_top_holder_share")
        min_lp_lock = _d(policy.min_lp_lock_ratio, "min_lp_lock_ratio")
        max_buy_tax = _d(policy.max_buy_tax_bps, "max_buy_tax_bps")
        max_sell_tax = _d(policy.max_sell_tax_bps, "max_sell_tax_bps")
    except PortfolioError as exc:
        raise TokenRiskError(str(exc)) from exc
    if min_liquidity < 0 or not D("0") <= max_holder_share <= 1 or not D("0") <= min_lp_lock <= 1:
        raise TokenRiskError("liquidity and concentration/LP thresholds are invalid")
    if not D("0") <= max_buy_tax <= 10000 or not D("0") <= max_sell_tax <= 10000:
        raise TokenRiskError("tax thresholds must be between 0 and 10000 basis points")

    reasons: list[str] = []
    if decision_time - evidence.source_timestamp > policy.max_evidence_age_seconds:
        reasons.append("STALE_SOURCE_EVIDENCE")
    for check in policy.required_checks:
        value = getattr(evidence, check)
        if value is None:
            reasons.append(f"MISSING_CHECK:{check}")
        elif not isinstance(value, bool):
            raise TokenRiskError(f"{check} must be boolean or None")
        elif value is False:
            reasons.append(f"CHECK_FAILED:{check}")

    numeric_fields = (
        ("liquidity_usd", evidence.liquidity_usd, min_liquidity, "MIN_LIQUIDITY_NOT_MET"),
        ("top_holder_share", evidence.top_holder_share, max_holder_share, "TOP_HOLDER_CONCENTRATION_TOO_HIGH"),
        ("lp_lock_ratio", evidence.lp_lock_ratio, min_lp_lock, "LP_LOCK_RATIO_TOO_LOW"),
        ("buy_tax_bps", evidence.buy_tax_bps, max_buy_tax, "BUY_TAX_TOO_HIGH"),
        ("sell_tax_bps", evidence.sell_tax_bps, max_sell_tax, "SELL_TAX_TOO_HIGH"),
    )
    for field, raw_value, threshold, reason in numeric_fields:
        if raw_value is None:
            reasons.append(f"MISSING_VALUE:{field}")
            continue
        try:
            value = _d(raw_value, field)
        except PortfolioError as exc:
            raise TokenRiskError(str(exc)) from exc
        if value < 0:
            raise TokenRiskError(f"{field} cannot be negative")
        if field in {"top_holder_share", "lp_lock_ratio"} and value > 1:
            raise TokenRiskError(f"{field} must be between 0 and 1")
        if field in {"buy_tax_bps", "sell_tax_bps"} and value > 10000:
            raise TokenRiskError(f"{field} cannot exceed 10000 basis points")
        if field == "liquidity_usd" and value < threshold:
            reasons.append(reason)
        elif field == "top_holder_share" and value > threshold:
            reasons.append(reason)
        elif field == "lp_lock_ratio" and value < threshold:
            reasons.append(reason)
        elif field in {"buy_tax_bps", "sell_tax_bps"} and value > threshold:
            reasons.append(reason)

    if evidence.holder_count is None:
        reasons.append("MISSING_VALUE:holder_count")
    elif (isinstance(evidence.holder_count, bool) or not isinstance(evidence.holder_count, int)
          or evidence.holder_count < 0):
        raise TokenRiskError("holder_count must be a nonnegative integer or None")
    elif evidence.holder_count < policy.min_holder_count:
        reasons.append("HOLDER_COUNT_TOO_LOW")

    return {
        "token_id": evidence.token_id,
        "source_id": evidence.source_id,
        "source_sha256": evidence.source_sha256,
        "source_timestamp": evidence.source_timestamp,
        "observed_at": evidence.observed_at,
        "decision_time": decision_time,
        "status": "BLOCKED" if reasons else "ELIGIBLE_FOR_HUMAN_REVIEW",
        "reasons": sorted(set(reasons)),
        "order_authorized": False,
        "evidence_truth_independently_verified": False,
        "disclaimer": "Eligibility is a preliminary evidence screen, not proof of token safety or authorization to trade.",
    }
