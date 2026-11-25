# External Audit Checkpoint — Security Design Proposal

**Status:** Proposal only. Not implemented. Requires independent security review before implementation or operational use.
**Scope:** Offline/PAPER-only synthetic settlement ledger.
**Motivation:** The SQLite audit chain detects internal inconsistency, but an unkeyed hash chain stored in the same writable database is not an independent trust anchor. A privileged writer who can rewrite the database and recompute the chain may erase evidence unless an independently held checkpoint exists.

## 1. Security objective

Detect rollback, truncation, replacement, and coordinated rewrite of the local SQLite audit history relative to a checkpoint held outside that database.

The design must not claim to prevent a privileged host administrator from tampering with both the database and every external trust anchor. It aims to make silent database-only rewriting detectable.

## 2. Non-goals and hard boundaries

- No exchange account access, API credentials, wallet access, transfers, or real orders.
- No network transport, cloud dependency, or third-party service is introduced by this proposal.
- No modification of protected ledger/risk modules is authorized by this design document.
- PAPER remains disabled until the wider release gates pass; LIVE remains disabled.
- The checkpoint is evidence, not a risk approval or execution authorization.
- No signing key, seed, password, or private material may be stored in the repository or SQLite database.

## 3. Checkpoint record

A canonical, versioned checkpoint payload should contain at minimum:

- format and canonicalization version;
- stable database/ledger identifier;
- account identifier and quote currency (never private account credentials);
- schema/migration version;
- monotonically increasing audit sequence;
- audit-chain head digest at that sequence;
- previous checkpoint digest (or explicit genesis marker);
- UTC creation timestamp;
- signer key identifier and algorithm identifier.

The signed bytes must be canonical and unambiguous. Reject duplicate JSON keys, non-canonical encodings, unsupported versions, invalid UTF-8, unknown algorithms, malformed digests, and timestamps without an explicit UTC offset.

## 4. Signing and storage trust boundaries

- Signing occurs through a narrow signer interface backed by a key held outside the database and outside the repository (for example, an OS keystore or dedicated hardware signer, subject to platform review).
- The database process receives only a signature result and public verification material; it must never read/export the private key.
- The external checkpoint copy must be stored independently from the SQLite file, with append-only/versioned semantics. A second file in the same writable directory is not independent protection.
- Public keys and key-rotation records must be versioned and independently recoverable.
- Key rotation requires a signed transition from the old trusted key to the new key, or a separately approved recovery ceremony. Unknown keys fail closed.
- Never silently replace an existing checkpoint with an older sequence or a different ledger identity.

## 5. Commit and acknowledgement protocol

SQLite cannot atomically commit with an independent external store. Use a durable outbox protocol rather than pretending there is a cross-system transaction:

1. A local transaction commits the ledger mutation and a pending checkpoint request containing the exact ledger ID, sequence, and audit head.
2. The checkpoint worker reads the pending request and asks the external signer to sign only that exact payload.
3. The signed checkpoint is written to the independent append-only destination.
4. The worker verifies the stored checkpoint by reading it back and checking its signature, identity, sequence, previous-checkpoint link, and audit head.
5. Only after read-back verification does the local database mark the request acknowledged.
6. If the process crashes at any step, recovery retries idempotently. Duplicate submission of the same exact checkpoint is safe; conflicting content for the same sequence is a hard error.
7. While a checkpoint is pending or verification is unavailable, state-mutating settlement/strategy actions must remain blocked. Read-only diagnostics may continue.
8. On startup, compare the local ledger identity, audit head, and acknowledged sequence with the independently held latest checkpoint. Any rollback, truncation, fork, missing anchor, or signature failure blocks operation pending review.

A policy decision is still required on whether every fill batch needs a checkpoint or whether a bounded checkpoint interval is acceptable. For any interval greater than one batch, the maximum unanchored-loss window must be explicit and approved.

## 6. Failure behavior

Fail closed on:
- missing or unreadable external checkpoint;
- signer unavailable or key identifier unknown;
- invalid signature or malformed canonical payload;
- ledger identity mismatch;
- sequence rollback, skipped sequence, or conflicting checkpoint fork;
- audit-head mismatch at an anchored sequence;
- inability to read back and verify the newly written checkpoint;
- checkpoint outbox inconsistency or duplicate/conflicting request.

Do not auto-repair, truncate, reinitialize, regenerate keys, or overwrite evidence. Preserve the database and checkpoint files for forensic review.

## 7. Recovery and backup

- Back up the SQLite database and external checkpoint independently.
- Recovery must verify the external latest checkpoint before accepting a restored database.
- A database older than the latest anchor is not silently rolled forward; it is rejected pending a documented recovery procedure.
- A missing external checkpoint is not equivalent to an empty ledger.
- Recovery of a lost signing key requires a separately approved, auditable process; no automatic key regeneration.

## 8. Required tests before implementation acceptance

- canonicalization vectors and duplicate-key rejection;
- signature valid/invalid, unknown key, rotation, and revoked-key cases;
- database-only rewrite and recomputed-chain attack detection;
- audit truncation, rollback, database replacement, and ledger-ID substitution;
- checkpoint replay, duplicate delivery, conflicting same-sequence payload, and fork detection;
- crash injection before/after local commit, signing, external write, read-back, and local acknowledgement;
- external-store unavailable, read-only, partial-write, and corruption behavior;
- restore from backup with newer/older/missing checkpoint;
- concurrency and idempotent worker behavior;
- property/fuzz tests for malformed checkpoint payloads;
- proof that pending/unverified checkpoints block state mutation;
- Python-version and filesystem/platform compatibility.

Tests must use synthetic temporary files and generated test keys only. They must not access protected modules or real user data.

## 9. Rollout gates

1. Independent review of this threat model and signer/storage boundary.
2. Approve checkpoint frequency and maximum unanchored window.
3. Approve supported platform/key-store and independent-storage mechanism.
4. Implement the signer interface and canonical record parser in an isolated, unprotected module.
5. Implement durable outbox/recovery with no bypass around the pending gate.
6. Complete adversarial, crash, restore, and compatibility testing.
7. Verify exact-head CI and independent acceptance.
8. Only then consider PAPER enablement under the existing project approvals. LIVE remains disabled.

## 10. Open design decisions

- Which independent storage medium is available to the iPhone-only operator without introducing a network or cloud dependency?
- Is one checkpoint per committed fill batch required, or is a bounded interval acceptable?
- Which signing mechanism is supported on every intended installation platform?
- Who controls recovery and key rotation, and how is that authority separated from the trading process?

Until these decisions are approved, this document is a design proposal and no external-anchor security claim may be made.


## 11. Additional independent-signer validation requirement

A signature over a caller-supplied digest is not sufficient to establish trustworthy ledger progression. A compromised database writer could rewrite the local database and pending checkpoint request before asking a hardware/OS key to sign the new head. A signer that blindly signs the request would anchor the fabricated state rather than detect it.

Before implementation, the trust boundary must distinguish:

- **Key custody:** the private signing key is outside SQLite and the trading process.
- **Anti-rollback state:** the signer/independent verifier retains the last trusted ledger ID, account/currency identity, schema version, audit sequence, audit head, checkpoint digest, key ID and algorithm outside SQLite.
- **Chain-extension verification:** a new checkpoint must extend the last trusted checkpoint. The verifier must independently recompute the event hash chain from the last anchored sequence through the proposed sequence, reject gaps/forks/duplicate sequences, and confirm the resulting head equals the proposed head. It must not trust only the database's pending row or supplied digest.
- **Semantic verification:** before signing, an independent deterministic verifier should validate event schemas and the accounting invariants relevant to the checkpoint (account identity, market registration, fill ordering, cash/holdings reconciliation, reservation allocation/consumption and outbox consistency). If this cannot be done, the system must explicitly limit its claim to anchoring the byte-level audit prefix; it must not imply that the signer has authenticated the truth or authorization of the events.
- **Monotonic commit:** the external store must reject a checkpoint whose ledger identity changes, whose previous-checkpoint digest does not equal the independently retained latest digest, whose sequence rolls back, or whose same-sequence content conflicts. Updating the external checkpoint and monotonic trusted state must itself be atomic or recoverable without accepting a fork.

The verifier may obtain the appended event segment from a read-only SQLite snapshot or from a separately authenticated append-only event stream. In either case it must independently recompute the chain extension from the last trusted head. A signer that only provides a generic "sign bytes" operation is a key-custody component, not a ledger validator.

### Revised assurance statement

A checkpoint can make post-anchor database-only rewriting, truncation, rollback and fork detectable only if the signer/verifier retains independent monotonic state and verifies extension from the previous trusted head. It does not prove the economic truth of market data or fills. If the checkpoint is created after a malicious writer has already replaced the unanchored suffix and the signer blindly signs it, the fabricated suffix becomes anchored. The maximum unanchored window therefore remains a security-critical policy decision, not just an operational setting.

### Additional required tests

- Submit a fabricated but syntactically valid new audit head after altering the unanchored suffix; the independent verifier must reject it unless the suffix extends the last trusted checkpoint and passes semantic reconciliation.
- Submit an old checkpoint with a valid signature after a newer checkpoint has been stored; reject rollback using independently retained monotonic state.
- Submit a validly signed checkpoint with a different ledger ID/account identity; reject substitution.
- Re-submit the same sequence with a different digest; reject fork/conflict.
- Crash between external checkpoint append and monotonic-state update; recovery must deterministically discover whether the append committed and must never accept an alternate branch.
- Restore the SQLite file and checkpoint file together from an older backup while the signer retains a newer trusted head; operation must remain blocked.
- Demonstrate that a generic signing-only key service cannot, by itself, claim semantic verification.

These are design requirements only. They do not authorize a signer, storage platform, network dependency, key management workflow, or operational deployment.
