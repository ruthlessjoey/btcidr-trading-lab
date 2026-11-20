---
name: verification-before-completion
description: Use before claiming a change is fixed, complete, safe, or passing, and before creating a commit or pull request.
---

# Verification Before Completion

Never make a success claim based on confidence, a prior run, partial output, or another agent's report. Fresh verification must support the exact claim.

## Gate
1. Name the exact command or independent check that proves the claim.
2. Run the complete relevant command in the stated environment.
3. Inspect the full output, exit status, warning count, failure count, and test count.
4. Verify the output actually proves the claim; a unit test does not prove integration, security, performance, or live exchange behavior.
5. Check the final diff and ensure no unrelated or protected files changed.
6. Record interpreter/runtime version, commit, command, result, and limitations.
7. If a required environment or check is unavailable, say so explicitly and leave the gate open.

## Claim precision
- Say “compiled” only after compilation.
- Say “tests passed” only for the exact suite and interpreter that ran.
- Say “independently reviewed” only when a genuinely separate reviewer inspected the artifact.
- Say “installed” only after configuration and files are present and verified.
- Never infer deployment, PAPER authorization, or LIVE readiness from passing tests.

## Final checklist
- [ ] Fresh full relevant verification run
- [ ] Full output and exit code inspected
- [ ] Regression test demonstrates the original defect
- [ ] Final diff reviewed
- [ ] Security and protected-path scope checked
- [ ] Documentation and milestone gates consistent
- [ ] Unverified items and limitations explicitly listed
