"""Owner-authorized exposure enforcement wrapped around the account risk gateway.

Only this facade is intended for strategy proposal access. Trusted inventory,
marks, policy and authorizers are injected by the composition root, never by an
agent. This remains an in-process interface, not an OS/process security boundary.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Protocol

from .exposure_policy import (
    ExposureMark, ExposurePolicy, ExposurePolicyError, authorize_exposure,
)
from .risk_gateway import (
    AuditAnchor, InventoryLedger, ResetAuthorizer, RiskGateway, RiskGatewayError,
    RiskStateStore, SessionPolicyAuthorizer,
)


class ExposureMarkProvider(Protocol):
    def snapshot_marks(
        self, account_id: str, market_ids: tuple[str, ...], timestamp: int
    ) -> Mapping[str, ExposureMark]:
        """Return fresh trusted marks and executable buy liquidity for every market."""


class ExposurePolicyAuthorizer(Protocol):
    def verify_exposure_policy(
        self, account_id: str, policy: Mapping[str, object]
    ) -> bool:
        """Verify owner-approved policy, including version and downgrade constraints."""


def _policy_record(policy: ExposurePolicy) -> dict[str, object]:
    return {key: value for key, value in asdict(policy).items()}


class PolicyEnforcedRiskGateway:
    """Proposal-only facade enforcing exposure policy before session-loss controls."""

    def __init__(
        self, *, gateway: RiskGateway, account_id: str, ledger: InventoryLedger,
        mark_provider: ExposureMarkProvider, policy: ExposurePolicy,
        policy_authorizer: ExposurePolicyAuthorizer,
    ) -> None:
        self.__gateway = gateway
        self.__account_id = account_id
        self.__ledger = ledger
        self.__mark_provider = mark_provider
        self.__policy = policy
        self.__policy_authorizer = policy_authorizer

    @classmethod
    def create_new(
        cls, *, account_id: str, guard: object, ledger: InventoryLedger,
        store: RiskStateStore, anchor: AuditAnchor, reset_authorizer: ResetAuthorizer,
        session_policy_authorizer: SessionPolicyAuthorizer,
        mark_provider: ExposureMarkProvider, exposure_policy: ExposurePolicy,
        exposure_policy_authorizer: ExposurePolicyAuthorizer,
    ) -> "PolicyEnforcedRiskGateway":
        if exposure_policy_authorizer.verify_exposure_policy(
            account_id, _policy_record(exposure_policy)
        ) is not True:
            raise RiskGatewayError("owner approval of exposure policy was not verified")
        gateway = RiskGateway.create_new(
            account_id=account_id, guard=guard, ledger=ledger, store=store,
            anchor=anchor, reset_authorizer=reset_authorizer,
            session_policy_authorizer=session_policy_authorizer,
        )
        return cls(
            gateway=gateway, account_id=account_id, ledger=ledger,
            mark_provider=mark_provider, policy=exposure_policy,
            policy_authorizer=exposure_policy_authorizer,
        )

    @classmethod
    def restore(
        cls, *, account_id: str, ledger: InventoryLedger, store: RiskStateStore,
        anchor: AuditAnchor, reset_authorizer: ResetAuthorizer,
        session_policy_authorizer: SessionPolicyAuthorizer,
        mark_provider: ExposureMarkProvider, exposure_policy: ExposurePolicy,
        exposure_policy_authorizer: ExposurePolicyAuthorizer,
    ) -> "PolicyEnforcedRiskGateway":
        if exposure_policy_authorizer.verify_exposure_policy(
            account_id, _policy_record(exposure_policy)
        ) is not True:
            raise RiskGatewayError("owner approval of restored exposure policy was not verified")
        gateway = RiskGateway.restore(
            account_id=account_id, ledger=ledger, store=store, anchor=anchor,
            reset_authorizer=reset_authorizer,
            session_policy_authorizer=session_policy_authorizer,
        )
        return cls(
            gateway=gateway, account_id=account_id, ledger=ledger,
            mark_provider=mark_provider, policy=exposure_policy,
            policy_authorizer=exposure_policy_authorizer,
        )

    def propose(self, *, proposals: Mapping[str, object], timestamp: int) -> dict[str, object]:
        if not isinstance(proposals, Mapping) or not proposals:
            raise RiskGatewayError("non-empty market proposals are required")
        try:
            equity = self.__ledger.snapshot_equity(self.__account_id)
            holdings = self.__ledger.snapshot_holdings(self.__account_id)
            if not isinstance(holdings, Mapping) or not holdings:
                raise RiskGatewayError("authoritative inventory is unavailable")
            if not set(proposals).issubset(holdings):
                raise RiskGatewayError("proposal references a market absent from authoritative inventory")
            market_ids = tuple(sorted(holdings))
            marks = self.__mark_provider.snapshot_marks(
                self.__account_id, market_ids, timestamp
            )
            if not isinstance(marks, Mapping) or set(marks) != set(market_ids):
                raise RiskGatewayError("trusted marks must exactly cover authoritative inventory")
            normalized_proposals = {
                market_id: proposals.get(market_id, "0") for market_id in market_ids
            }
            permitted = authorize_exposure(
                account_equity=equity, holdings=holdings,
                proposals=normalized_proposals, marks=marks,
                timestamp=timestamp, policy=self.__policy,
            )
            # The underlying gateway independently reads equity and holdings,
            # then applies the session-loss latch, sell reservations, persistence
            # and external anchoring. Agents never receive its raw object.
            result = self.__gateway.propose(
                proposals={market_id: permitted[market_id] for market_id in proposals},
                timestamp=timestamp,
            )
            return {
                **result,
                "exposure_policy_enforced": True,
                "exposure_policy": _policy_record(self.__policy),
            }
        except (ExposurePolicyError, KeyError, TypeError, ValueError) as exc:
            raise RiskGatewayError("exposure policy rejected proposal; no authorization issued") from exc

    @property
    def is_halted(self) -> bool:
        return self.__gateway.is_halted
