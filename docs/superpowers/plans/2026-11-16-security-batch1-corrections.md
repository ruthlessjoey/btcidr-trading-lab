# Security Batch 1 Corrections Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete the authorized provider-response sanitization corrections on a fresh branch without merging.

**Architecture:** Start from the approved baseline and apply narrowly scoped fixes at provider and reporting boundaries. Preserve Coinbase and Bitstamp cross-check behavior; use synthetic offline tests to prove untrusted markers do not reach output sinks.

**Tech Stack:** Python 3.11, unittest, GitHub repository APIs.

**Spec:** Approved Workstream A design in the conversation, based on Issue #3 (Security review: provider-response sanitization).

## Global Constraints

- Base SHA: `cd451972e3a641ad6fa78e64abf3968655a4b82a`.
- Branch: `security/batch1-corrections-v2`.
- No access to `P1/`, `signal/data/`, or any copy of `signal/`.
- No credentials, private exchange endpoints, account access, orders, or live trading.
- All tests use synthetic fixtures; no exchange network requests.
- No dependencies, unrelated architecture changes, host allowlisting, or response-size limits.
- No merge. Workflow dispatch requires separate explicit authorization.

## Review Focus

- Persisted dataset row values embedded in `DatasetError` must not leak through history reports.
- Kraken server-time and candle timestamps must be seconds-only; milliseconds must be rejected, not normalized.
- Bitstamp cross-check errors and values must remain sanitized without removing existing cross-check behavior.
- HTTPError bodies must not be read, and responses must be closed.
- Marker strings must be absent from JSON, Markdown, stdout, and GitHub step summaries.

---

### Task 1: Sanitize previous-dataset errors

**Files:**
- Modify: `research/history.py`
- Test: `tests/test_research_sanitization.py`

- [ ] Add a synthetic prior-dataset fixture whose DatasetError contains a unique marker.
- [ ] Verify the test fails because the marker appears in at least one output sink.
- [ ] Replace raw exception interpolation at the history reporting boundary with a fixed safe diagnostic.
- [ ] Verify JSON, Markdown, stdout, and GitHub step summary contain no marker and retain a useful safe failure state.

### Task 2: Enforce Kraken seconds-only timestamps

**Files:**
- Modify: `providers.py`
- Test: `tests/test_live_check.py`

- [ ] Add server-time and candle tests for valid seconds and invalid millisecond values.
- [ ] Verify the millisecond tests fail against the current implementation.
- [ ] Add a Kraken-specific seconds validator; do not change the generic Binance-style seconds/milliseconds parser.
- [ ] Run the focused provider tests.

### Task 3: Restore sanitized Bitstamp cross-check behavior

**Files:**
- Modify: `research/crosscheck.py`, `research/backtest_report.py`
- Test: `tests/test_research_sanitization.py` and applicable existing research tests.

- [ ] Restore Bitstamp BTC/USD window fetching, comparison results, and safe error reporting as present at the approved baseline.
- [ ] Sanitize Bitstamp response shape, row, and network errors without echoing provider-controlled values.
- [ ] Add synthetic marker tests for Bitstamp errors and preserve Coinbase behavior.
- [ ] Verify the report retains the existing Coinbase and Bitstamp fields/schema.

### Task 4: Prove HTTPError body is not read

**Files:**
- Modify: `tests/test_fetcher.py` only unless a failing test proves implementation correction is needed.
- [ ] Add a response double that records read attempts and closure.
- [ ] Verify the test fails if the body is read and passes only when the response is closed unread.
- [ ] Run focused fetcher tests.

### Task 5: Complete output-sink regression coverage

**Files:**
- Modify: `tests/test_research_sanitization.py`, with production changes only in the authorized files above.
- [ ] Exercise synthetic marker rejection across JSON, Markdown, stdout, and GitHub step summary for prior-dataset errors and provider errors.
- [ ] Confirm valid HTTP 403/451 status evidence remains visible while response-controlled body text remains absent.
- [ ] Run all authorized offline tests: `python -m unittest discover -s tests -p 'test_fetcher.py' -v`, `python -m unittest discover -s tests -p 'test_live_check.py' -v`, and `python -m unittest discover -s tests -p 'test_research_sanitization.py' -v`.

## Completion Gate

- Reconcile the final diff against the seven authorized paths and approved scope.
- Verify exact branch head and changed-file list.
- Obtain fresh passing test evidence on the final head; do not reuse stale run results.
- Perform a separate whole-branch code review and resolve Critical/Important findings.
- Open a draft PR only after the final diff and evidence are reviewable. Do not merge.
