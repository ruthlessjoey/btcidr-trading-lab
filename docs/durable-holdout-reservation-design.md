# Durable holdout reservation design

Status: design proposal only. No holdout calculation or workflow behavior is changed by this document.

## Goal

A TEST-window calculation must not begin until a reservation for its exact frozen evaluation has been committed to the persistent `research-data` branch. If a runner is cancelled, lost, or force-stopped after that point, the reservation remains in the branch and blocks an automatic retry.

## Existing gap

The current workflow loads `test_evaluations/` from `research-data`, runs the backtest, and only afterward publishes `out/test_evaluations/`. The Python reservation is initially created in the ephemeral Actions workspace. A hard cancellation before the publisher successfully pushes can therefore erase the only pending marker. The workflow's `if: always()` does not guarantee that the publisher will run after every force-cancellation.

## Proposed two-phase lifecycle

1. **Prepare (no TEST calculation).** Load and verify the pinned dataset, compute TRAIN/VALIDATION selection, freeze the choice, and write a reservation-intent record under `out/test_evaluations/<key>.pending`. The record binds the dataset SHA-256, frozen hash, registry key, GitHub run ID, and a `reserved` status. This phase must not call the TEST evaluator or compute TEST metrics.
2. **Persist reservation.** In a separate workflow step, clone the current `research-data` branch, verify that neither the matching completed record nor pending marker already exists, copy the exact prepared marker, commit it, and push with a normal non-force push. The workflow must stop if the push fails or if the branch changed unexpectedly. No TEST calculation may run unless this push succeeds.
3. **Reload authoritative state.** Copy the just-committed marker from the successful branch clone into the workspace's prior-results registry. Do not trust only the earlier checkout or the local prepared file.
4. **Evaluate (adopt, do not create).** The TEST evaluator must require an existing regular, non-symlink reservation whose key, frozen hash, run ID, and status exactly match the current run. It must refuse missing, malformed, mismatched, or duplicate reservations before generating a TEST signal or metric.
5. **Publish completion atomically.** After a successful calculation, publish the completed record and remove the corresponding persistent `.pending` marker in the same Git commit to `research-data`. The publisher must verify the completed record matches the reservation before removing it. Use a normal non-force push; a failed push leaves the reservation in place.
6. **Failure/interruption.** If evaluation raises after it starts, or the runner disappears before successful completion publication, retain the persistent pending marker. Never expire or delete it automatically. An operator must inspect the run, artifact, frozen hash, and registry before a deliberate recovery decision.

## Required invariants

- A durable reservation commit must be confirmed before the TEST evaluator can start.
- The prepared frozen hash must be reproduced and verified by the evaluation invocation; the run ID and key must match the committed marker.
- The evaluator must not silently create or adopt a reservation from an arbitrary local file.
- Completed-record publication and pending-marker removal must be one branch commit, so the persistent registry never exposes a gap between them.
- Existing completed records and pending markers are checked with symlink-aware path existence checks. Existing records must be regular, non-symlink files.
- The workflow's `research-data` concurrency group remains enabled. Branch pushes remain append-only and non-force.
- If any stage is uncertain, fail closed. Do not infer that TEST was not evaluated merely because an artifact or local file is missing.

## Workflow structure

For configurations with `evaluate_test: true`, replace the single backtest step with three gated phases:

- prepare reservation (no TEST calculation);
- persist reservation (must succeed);
- execute TEST evaluation (must not run unless persistence succeeded).

The final publisher copies completed records and reports. It removes a pending marker only when the matching completed record is present and validated. If evaluation failed or was interrupted, it preserves the marker. The artifact upload remains useful for investigation but is not the durable lock.

For configurations with `evaluate_test: false`, retain the existing dry-run behavior and do not create a reservation.

## Re-evaluation

A labelled re-evaluation must use a distinct, deterministic reservation identity bound to its explicit run ID and must never overwrite the original completed record. This should be implemented and tested explicitly; do not weaken the original once-only path to accommodate re-evaluation.

## Tests required before implementation is accepted

- Prepare phase writes a reservation intent but never calls the TEST strategy/evaluator.
- Failed or rejected reservation push prevents the TEST step from running (workflow-level review; do not dispatch a workflow as part of code review).
- Evaluator refuses absent, dangling-symlink, malformed, mismatched-key, mismatched-hash, mismatched-run-ID, and wrong-status reservations before TEST signal generation.
- Evaluator accepts only the exact committed reservation and does not create a replacement lock.
- Completed record and pending-marker removal are published together; simulate push failure and prove the marker remains.
- Simulate cancellation after reservation commit but before evaluation, during evaluation, and after local completion but before final publication; persistent registry must remain fail-closed in every incomplete case.
- Dry-run configuration does not create a marker or evaluate TEST.
- Concurrent/repeated workflow invocations remain serialized and cannot reserve the same frozen key twice.
- Re-evaluation has separate reservation and result identities and cannot overwrite the original record.

## Scope and safety

This is research/backtesting infrastructure only. No exchange access, credentials, orders, wallets, or live execution are involved. Do not access `P1/` or `signal/data/`. Do not dispatch or execute workflows during implementation or review. PAPER remains unavailable until its separate portfolio/risk safeguards are complete; LIVE remains reserved and unavailable.

## Acceptance gate

This document is not evidence that the design has been implemented. Do not claim hard-cancellation durability until the workflow, pipeline, registry code, and regression tests all implement and demonstrate the invariants above.