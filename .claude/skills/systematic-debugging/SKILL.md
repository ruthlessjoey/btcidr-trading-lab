---
name: systematic-debugging
description: Use for any bug, failing test, unexpected behavior, performance regression, or integration failure before proposing a fix.
---

# Systematic Debugging

Find and reproduce the root cause before changing code. Do not patch a symptom based on a guess.

## Process
1. Read the complete error, traceback, failing assertion, and relevant logs.
2. Reproduce the failure with the smallest deterministic case. If it cannot be reproduced, gather evidence rather than guessing.
3. Trace the bad value and control flow backward to its origin. Identify the first boundary where valid data becomes invalid or trusted data becomes untrusted.
4. Compare against a working path and list concrete differences.
5. Form one falsifiable hypothesis. Test it with the smallest isolated experiment; change one variable at a time.
6. Once root cause is established, write a regression test that fails for the observed defect.
7. Implement the smallest fix at the source. Add defense-in-depth checks at downstream trust boundaries where justified.
8. Rerun the regression test and full relevant suite. Inspect all output and state changes.
9. If several distinct fixes fail, stop and reassess the architecture with the user instead of layering on another guess.

## Multi-layer systems
For provider → normalization → risk → portfolio → journal flows, record the input and output contract at each boundary using safe test fixtures. Determine exactly where the invariant breaks. Do not add diagnostic logging that exposes secrets or protected data.

## Report
State reproduction steps, root cause, evidence, fix, verification, remaining uncertainty, and unrun checks.
