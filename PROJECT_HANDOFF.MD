TRADING BOT PROJECT — MASTER HANDOFF & CONTINUATION BRIEF

You are continuing an existing AI-assisted trading system project. This is NOT a new project. Do not restart, recreate files, redesign the architecture, or repeat completed work.

Your first responsibility is to recover the existing project state, understand the safeguards, and continue the unfinished code review.

The user works entirely from an iPhone and uses GitHub’s mobile website. They are a beginner and need clear, exact instructions. The project must remain free/open-source-first, with a starting budget of Rp0.

⸻

1. PROJECT GOAL

Build a serious, modular, AI-assisted multi-market trading research and signal system.

The long-term ambition is to scan and evaluate opportunities across:

* Cryptocurrencies, including established coins, meme coins, newly listed tokens and DEX pairs.
* Stocks and ETFs.
* Forex.
* Indices.
* Commodities.
* Other supported financial instruments.

The system should eventually identify and rank the strongest opportunities across markets, generate BUY/SELL signals, manage risk, and potentially support up to 10 simultaneous positions.

The user wants a system that can eventually become a real trading product, not merely a basic BTC indicator.

However, the current implementation is much earlier in development.

Current operating mode: research-only.

There is:

* No live trading.
* No automatic order execution.
* No deposit or withdrawal system.
* No connected exchange account.
* No API trading credentials.
* No live portfolio management.
* No authorization to risk real funds.

The user must explicitly authorize any future transition toward live trading.

Do not confuse the long-term vision with what is currently implemented.

⸻

2. REPOSITORY AND GITHUB STATE

Repository:

ruthlessjoey/btcidr-trading-lab

Important branches:

* main: contains the previously merged market-data milestone.
* milestone-3-data: current Milestone 3 working branch.
* research-data: contains the frozen historical research dataset.
* audit-m3: separate audit branch containing discrepancy-audit work.

Known commits:

* Main market-data merge: 733abeb
* Current Milestone 3 branch head previously reported: 14ed76c

Pull requests:

* PR #1: merged into main.
* PR #2: Milestone 3 research-only backtest implementation. Previously reported OPEN and NOT MERGED.

Do not assume any of these states remain unchanged. Verify the current GitHub state before making recommendations.

Important: The user has not authorized committing, pushing, merging, migrating, or running the backtest workflow for the pending safety fixes.

⸻

3. MARKET DATA MILESTONE

The previously merged market-data workflow collected:

* Kraken BTC/USD.
* Coinbase BTC/USD.
* Binance BTC/USDT.
* Tokocrypto market-data endpoint was blocked from GitHub Actions with HTTP 451 (not-support).

The last reported successful main workflow run was 40483744642.

Another successful market-data workflow run was reported as 40630155992.

Historical data collection:

* 1-hour candles.
* 14-day window.
* 335 candles per source.
* Oldest-first ordering.
* Schema: time_unix,time_utc,open,high,low,close,volume.
* No duplicate timestamps.
* Closed candles.

These are historical reported results, not a guarantee that the current workflows still work.

Do not bypass Tokocrypto’s HTTP 451 restriction. Investigate legitimate API access and deployment options only.

⸻

4. MILESTONE 3 — HISTORICAL BACKTEST

The research dataset:

* Binance BTC/USDT daily candles.
* 3,358 candles.
* Date range: 2017-08-17 through 2026-10-26.
* SHA-256:

c11776a0bbdcec4c1dbc0d0c556e2d8f9ec691968b31d61e2e2376d950dbad54

Dataset is preserved in research-data.

Do not modify, regenerate, overwrite, or silently replace this frozen dataset.

It is a Binance BTC/USDT proxy for Tokocrypto, NOT actual Tokocrypto execution prices or fills.

Strategy tested:

* Long BTC when daily close is above an N-day simple moving average.
* Otherwise hold cash.
* Candidate N values: 50, 100, 150, 200.
* Selected parameter: 150 days.
* Chronological train/validation/test split:

TRAIN:
2018-03-05 to 2023-02-20

VALIDATION:
2023-02-21 to 2024-12-22

TEST:
2024-12-23 to 2026-10-26

Previously reported results:

Metric	Result
Test strategy return	-11.0%
Test buy-and-hold return	-16.2%
Cash benchmark	0%
Closed trades	10
Open trades	1
Win rate	10%
Profit factor	0.36
Exposure	49%

Training return: +603.9%, maximum drawdown 46.3%.

Validation return: +171.4%, maximum drawdown 26.6%.

These are historical backtest results, NOT evidence of future profitability.

Important limitations:

* Daily-close drawdown understates intraday risk.
* Strategy is long-only.
* No leverage.
* Fractional BTC.
* Hypothetical starting balance: 1,000 USDT.
* Cost assumptions have not been verified against actual Tokocrypto fees.
* Previously tested fee assumptions: 0.40% or 0.10% per side.
* Slippage assumptions: 0.05% or 0.20% per fill.
* Minimum order assumption: 10 USDT.
* Quantity step assumption: 0.00001 BTC.
* These trading constraints are not verified Tokocrypto rules.

Never describe this strategy as profitable or ready for live deployment.

⸻

5. CROSS-EXCHANGE DATA DISCREPANCY AUDIT

The separate audit-m3 branch contains:

tools/audit_discrepancy.py

and its associated workflow.

The audit compared Binance BTC/USDT with Coinbase BTC/USD.

Previously reported findings:

* Daily UTC boundaries matched.
* Many 2017–2019 daily closes differed by more than 1%.
* Maximum reported difference: 11.8% on 2017-12-23.
* Binance had thinner early historical volume.
* Test-period differences were much smaller: maximum 0.24%, with none above 1%.
* Coinbase 150-day signal comparison showed zero differences in training, one in validation, and zero in test.
* The audit did not fully separate quote-currency effects from exchange/venue effects.
* Bitstamp supporting documentation had not been fully examined.

Do not dismiss this issue. Historical cross-venue discrepancies matter when interpreting the training results.

The audit branch is separate from PR #2 and has NOT been merged as far as the last report indicated.

⸻

6. CRITICAL MILESTONE 3 SAFETY PROBLEM

An independent review identified serious flaws in the original test-window evaluation guard.

Original problems:

1. Registry identity included the Git commit hash. A new commit could potentially bypass the once-only test guard.
2. A refused evaluation could still write test-window rows into equity, trades, and orders outputs.
3. Missing registry files could silently pass.
4. Frozen evaluation records were not sufficiently bound to the dataset and exact split boundaries.
5. Open-position valuation omitted exit costs.
6. Running-sum drift could theoretically affect exact-tie signals, although no differences were found on the 3,358 real dataset rows.
7. Report headings and flagged-candle information were partly hardcoded.

The most serious issue is the once-only evaluation guard. The system must not permit repeated testing of the same holdout period through trivial changes to commits or configuration.

The original review concluded:

PR #2 was not safe to merge as-is.

⸻

7. PENDING SAFETY FIXES — IMPORTANT

The user authorized Claude to PREPARE fixes, but NOT to commit or push them.

Previously reported local, uncommitted, unpushed changes on milestone-3-data:

backtest_config.json

* evaluate_test set to false by default.

New research/registry.py

Registry v2 uses stable identity based on:

* Full dataset SHA-256.
* Selected parameter.
* Exact test-window boundaries.
* Start and end indices.
* First and last open timestamps.

It does not use commit hashes or frozen-record hashes as identity.

Reported protections:

* Missing/unreadable registry fails closed.
* Unknown registry format fails closed.
* Unknown/unlisted legacy records fail closed.
* Tampered legacy bytes fail closed.
* Duplicate identities fail closed.
* Entries inconsistent with their keys fail closed.
* Overlapping test-window evaluations on the same dataset are blocked even when the parameter changes.

research/selection.py

* New bind_frozen validates frozen selection against dataset and split boundaries.
* evaluate_test returns a refusal/already-evaluated result when uncertain.
* Removes old commit-based reevaluation path.

research/pipeline.py

* Test-window rows are written only after a verified evaluation.
* Refusal returns exit code 1.
* Dry run reads the registry only.

research/backtest_report.py

* Removes misleading “first and only” language.
* Test section reports verified status or refusal reason.
* Does not display stored metrics when evaluation is refused.

run_backtest.py

* Removes --allow-reeval.

New tools/migrate_registry.py

* Offline migration.
* Dry-run by default.
* Refuses migration if evidence is missing or inconsistent.

Tests

* New tests/test_registry.py with 34 tests.
* Updates to test_engine.py and test_backtest_pipeline.py.

Claude previously reported:

* 203 offline tests passed.
* Zero skipped tests.
* ResourceWarnings treated as errors.
* Mutation tests detected missing-registry fail-open, exact-match-only overlap and unverified legacy bytes.

These test results have NOT been independently verified by ChatGPT. Review the actual code and test output rather than blindly trusting the report.

⸻

8. REGISTRY MIGRATION STATE

Claude previously tested migration on a scratch copy of research-data.

Reported state:

* Legacy file remained byte-identical:
    test_evaluations/c11776a0bbdc_7c677144b9ce.json
* Legacy file SHA-256 began 527c60c4 and ended 3678.
* New files were added:
    * REGISTRY.json
    * v2_8d9d4c4b9f527e38.json
* Migrated entry:
    * Dataset: c11776a0...
    * Parameter: 150
    * Test window indices: 2685 to 3358
    * Run: 40669485193
    * Source: migrated_legacy

Claude reported that the migration matched the original run’s frozen_choice.json and legacy hashes.

This was a scratch-copy experiment. Do not assume the actual research-data branch was migrated or modified.

The user has NOT authorized a real migration.

⸻

9. GITHUB ACTIONS / CI SAFETY

A push to milestone-3-data touching research/** or backtest_config.json may trigger:

research-backtest.yml

The user explicitly prohibited triggering the research backtest workflow, including a dry run.

Previously reported:

* Workflow was not triggered by pull_request.
* There may be a workflow_dispatch trigger.
* Claude was investigating whether a workflow could be manually dispatched after merging.
* [skip ci] was discussed but is NOT verified as a reliable way to suppress this workflow.
* research-data.yml was not believed to be triggered by the pending changes, but this must be checked against actual workflow files.

Inspect actual YAML triggers, path filters, permissions, concurrency rules and dispatch behavior.

Do not rely on assumptions about GitHub Actions skip annotations.

Never push a change if it could trigger the prohibited backtest workflow without first obtaining explicit user authorization.

⸻

10. TOKOCRYPTO — FIRST EXCHANGE CANDIDATE

The user asked which exchange would be best for them.

Our recommendation was:

Tokocrypto is the first Indonesian crypto exchange to evaluate.

Reasons:

* It is included in OJK’s published licensed-provider list.
* It has documented API endpoints.
* Its listed markets include IDR crypto pairs such as BTC, ETH, SOL and DOGE.
* It is a natural first candidate for an Indonesia-based crypto integration.

Official resources:

* Tokocrypto API documentation: https://www.tokocrypto.com/
* OJK official site: https://www.ojk.go.id/

Important limitation:

* The earlier GitHub Actions market-data test returned HTTP 451 from Tokocrypto.
* This has not been solved.
* Do not bypass restrictions.
* Verify current official API documentation and legitimate connectivity before making an integration decision.

Future architecture:

1. Tokocrypto as the first exchange candidate for crypto.
2. Binance public market data may be used for independent research comparison, not as the user’s deposit/execution account.
3. Other brokers/providers will be required for stocks, ETFs, forex, indices and commodities.
4. Read-only API access first.
5. Paper trading before any real execution.
6. Never enable withdrawal permission for a trading bot.

The user has not deposited money or authorized live trading.

⸻

11. WHAT THE USER WANTS NEXT

The immediate task is NOT to build the multi-market scanner yet.

The immediate task is to finish the Milestone 3 safety review.

Claude should:

1. Recover the current repository and branch state.
2. Inspect the exact uncommitted diff on milestone-3-data.
3. Confirm whether the reported safety fixes are actually present.
4. Review research/registry.py line by line.
5. Check stable identity and overlap detection.
6. Check missing, malformed, tampered, duplicated and legacy registry behavior.
7. Check that refused evaluations produce absolutely no test-window outputs.
8. Check frozen-record binding to the dataset and split boundaries.
9. Check the migration tool’s refusal behavior and whether it can overwrite or delete evidence.
10. Inspect every GitHub Actions workflow trigger and permission.
11. Confirm that no pending action can trigger a research backtest.
12. Review tests and identify untested edge cases.
13. Produce a clear final audit report.

The review should explicitly answer:

* Is the once-only test guard genuinely resistant to a new commit bypass?
* Can the same dataset and overlapping test window be evaluated under another parameter?
* Does missing or malformed registry data fail closed?
* Can legacy evidence be tampered with or silently accepted?
* Does a refusal leave any test-window output behind?
* Can migration alter or delete the original legacy evidence?
* Can a push, PR merge or manual dispatch accidentally run a backtest?
* Is PR #2 safe to merge after these fixes?
* What remains before the research milestone is considered complete?

If something is uncertain, say so. Do not invent verification.

⸻

12. ABSOLUTE PERMISSIONS AND PROHIBITIONS

Until the user explicitly changes these instructions:

DO NOT:

* Commit.
* Push.
* Merge PR #2.
* Run the research backtest workflow.
* Manually dispatch the backtest workflow.
* Run a test evaluation.
* Migrate the real registry.
* Modify or regenerate the frozen dataset.
* Add exchange API credentials.
* Enable live orders.
* Enable withdrawals.
* Deposit money.
* Create automatic trading.
* Build the multi-market execution engine yet.

Allowed:

* Read repository files.
* Inspect GitHub workflow YAML.
* Inspect diffs.
* Review code.
* Run safe offline unit tests that do not evaluate the holdout test window or trigger Actions.
* Use scratch copies for migration experiments.
* Produce review documentation.
* Recommend fixes without applying unauthorized changes.

If a test might invoke the research pipeline or touch the holdout evaluation, inspect it before running it.

Do not assume a command is safe because its name includes test, dry-run, or probe.

⸻

13. HOW TO WORK WITH THE USER

The user:

* Uses an iPhone only.
* Uses GitHub mobile website.
* Is not a professional developer.
* Needs exact, practical explanations.
* Wants the system built properly, not rushed.
* Has a zero-budget starting constraint.
* Prefers free/open-source solutions.
* Wants to understand what is genuinely working versus what is only planned.

Use manageable work sections. Do not flood the user with enormous technical dumps when a concise checkpoint is more useful.

For every major action, state:

* What you inspected.
* What changed, if anything.
* Whether it was committed or pushed.
* Whether any workflow ran.
* Whether any real-money risk exists.
* What remains.

Do not ask the user to repeat information already included here.

⸻

14. FIRST RESPONSE IN THIS NEW SESSION

Start by acknowledging that this is a continuation of an existing project.

Then inspect the actual repository state and identify:

* Current branch and commit.
* PR #2 status.
* Whether the pending safety fixes are still uncommitted.
* Whether any workflows have run since the last reported state.

Do not make changes yet.

Your first deliverable should be a concise state-recovery report, followed by the next safe code-review section.

Remember: preserve the project. Do not restart it. Do not commit, push, migrate, merge, or run the backtest.
