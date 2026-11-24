# PR114 independent static security review — findings

Review target:
- PR: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/114
- Reviewed head: f8e4c30a073bf525bd8483ab246b8929c804d5a0
- Reviewed file: crypto_engine/tmm_core/sqlite_settlement_store.py
- Method: source-level review of the exact GitHub file content. No runtime tests, database experiments, CI, or independent human review are claimed.

Status: NOT ACCEPTED. Keep PR #114 draft and unmerged until the findings below are resolved and verified.

## Critical — caller-supplied replay hash is not bound to the request payload

Evidence:
- apply_batch accepts request_hash as an argument and checks only that it is 64 hexadecimal characters.
- It normalizes fills and SELL settlement messages separately.
- It looks up an existing batch by batch_id and compares only the supplied request_hash.
- If the supplied hash matches, it returns the stored result without comparing the newly supplied fills, sell_settlements, or timestamp to the committed request.

Impact:
A caller can accidentally or maliciously reuse a batch ID and hash with changed settlement instructions. The store will report the prior result and will not prove that the new request is identical. This undermines the advertised payload-bound replay guarantee.

Required remediation:
1. Define one canonical, versioned request envelope containing account identity, batch ID, timestamp, normalized fills, and normalized outbox items.
2. Compute SHA-256 inside the trusted store from canonical serialization; do not accept a caller-controlled digest as the authoritative identity.
3. Persist the canonical envelope or enough immutable canonical bytes to compare exact replay.
4. Reject same batch ID with any changed canonical request.
5. Add regression tests changing one field at a time: fill ID, side, quantity, price, fee, market, timestamp, outbox key, authorized quantity and filled quantity.
6. Verify concurrent duplicate claims across separate processes.

## High — outbox messages are not proven to correspond to SELL fills

Evidence:
- sell_settlements are normalized independently of fills.
- The implementation checks that outbox markets are registered and that filled_quantity does not exceed authorized_quantity.
- It does not reconcile outbox authorized/filled quantities against actual SELL fills in the same batch.

Impact:
The database can persist a reservation settlement message that is not demonstrably derived from the batch's SELL fills. This weakens accounting consistency at the boundary where reservation state is updated.

Required remediation:
Specify the reservation contract and exact semantics for partial fills, zero fills, multiple SELL fills, and multiple reservations per market. Enforce the resulting invariant transactionally and test mismatches and omissions.

## Medium — replay result can be stale after outbox acknowledgement

Evidence:
- acknowledge_outbox changes the batches.status column to COMPLETE after the final acknowledgement.
- It does not update batches.result_json.
- apply_batch replay returns result_json for both COMPLETE and COMMITTED_PENDING_OUTBOX states.

Impact:
After successful acknowledgement, an identical replay may return a persisted result whose status still says COMMITTED_PENDING_OUTBOX even though the authoritative batch row says COMPLETE. Callers can observe contradictory state.

Required remediation:
Make replay responses derive status from the authoritative row and update/verify the canonical result atomically when the state transition occurs. Add a replay-after-acknowledgement test.

## Medium — startup validation does not explicitly run SQLite integrity_check

Evidence:
- Startup verifies account identity and the local audit hash chain.
- No PRAGMA integrity_check or quick_check is executed before the store is accepted.

Impact:
The application has no explicit startup gate for SQLite structural integrity. Audit-chain verification alone is not a substitute for SQLite database integrity validation.

Required remediation:
Run a bounded integrity check during trusted startup and fail closed on any result other than the exact success response. Add corrupt/truncated database fixtures.

## Medium — audit chain does not cover outbox state transitions

Evidence:
- Synthetic fill events are appended to the hash chain.
- Outbox acknowledgement updates status and receiver_receipt without appending a corresponding audit event.

Impact:
The local audit chain does not provide a chronological record of the transition from pending to acknowledged, or bind the receiver receipt to the batch and idempotency key.

Required remediation:
Append an outbox acknowledgement event in the same transaction as the acknowledgement and batch state update. Include the idempotency key, batch ID, receipt digest (not secret receipt content if sensitive), and previous hash. Verify on reopen.

## Scope and verification boundary

This is a static source review, not an execution test or independent third-party certification. No protected paths were accessed. No exchange/provider calls, network data requests, PAPER execution, LIVE execution, account access, or real-money activity occurred.

The PR114 module remains an offline synthetic accounting primitive. It is not integrated into OfflineSettlementController, does not include an outbox worker or idempotent receiver, and does not establish profitability or win rate.

Acceptance requires remediation, exact-head tests on the supported Python matrix including Python 3.11, crash and multi-process concurrency tests, integration tests, and a separate independent security review. Keep PAPER on hold and LIVE disabled.
