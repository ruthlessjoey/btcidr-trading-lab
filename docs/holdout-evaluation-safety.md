# Holdout evaluation reservation and recovery

The research backtest must not silently calculate the same frozen TEST window more than once.

## Required registry layout

A holdout evaluation requires a persistent prior-results registry. The pipeline refuses
`evaluate_test: true` when `prev_results_root` is missing. The registry is loaded from the
preserved `test_evaluations` directory; each run writes its completed record and a reservation
marker to its output `test_evaluations` directory. The publication workflow copies that output
directory back into the preserved registry.

The repository's research-backtest workflow also serializes runs with its
`research-data` concurrency group. Do not remove that serialization while relying on this
reservation design.

## Reservation lifecycle

For a frozen dataset/choice key, evaluation:

1. Checks the prior registry and this run's output registry for an existing completed record.
2. Creates an exclusive `.pending` reservation in the shared registry and a matching marker
   in the output registry (when the directories differ).
3. Rechecks completed records while holding the reservation.
4. Calculates the TEST window only after the reservation is secured.
5. Writes the completed JSON to a temporary file, flushes it, and publishes it with an
   exclusive hard link. Existing records are never overwritten.
6. Removes reservation markers only after successful publication.

An ordinary validation failure before TEST calculation releases the reservation. If TEST
calculation begins and then raises, or the process is forcibly terminated, the reservation is
left in place. This is intentional fail-closed behavior.

## Interrupted-run recovery

A preserved `.pending` marker means the run may have started looking at the TEST window.
Do not delete it automatically and do not rerun the holdout. An operator must inspect the
workflow logs, output artifacts, preserved registry, frozen hash, and run ID to determine
whether a completed result was published. If that cannot be established, retain the marker
and treat the holdout result as unavailable. Recovery must be an explicit, documented human
decision; there is no automatic stale-lock timeout.

## Re-evaluation

A second look requires the explicit `allow_reeval` option and a unique `run_id`. Its result is
stored under a deterministic, path-safe suffix and cannot overwrite the original record.
Re-evaluation is not a substitute for the original once-only test.

## Limits

This mechanism protects cooperating processes that use the same registry and output paths.
The workflow-level concurrency group serializes repository workflow runs. It does not provide
a distributed lock across unrelated machines that do not share the registry. The hard-link
publication requires a filesystem that supports same-directory hard links. The repository's
append-only publication process and preserved registry remain part of the safety boundary.
