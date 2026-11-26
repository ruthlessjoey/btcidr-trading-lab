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


## 12. Separate integrity, consistency, authenticity, and authorization claims

The checkpoint protocol must not collapse four distinct properties into the word "verified":

1. **Byte integrity:** a stored event prefix is unchanged relative to a trusted checkpoint digest.
2. **Chain continuity:** the candidate prefix extends the previous trusted sequence/head without gaps, rollback, replay or fork.
3. **Semantic consistency:** a deterministic verifier reconstructs account, market, holdings, fill, reservation, allocation and outbox state and confirms the recorded transitions obey the accepted schemas/invariants.
4. **Source authenticity and authorization:** evidence that an input came from an approved source and that the relevant action was authorized by the appropriate trusted boundary.

Properties 1–3 do not establish property 4. Recomputing a valid hash chain and reconciling balances can still validate a fabricated but internally consistent fill. A signature from a local signer does not prove a market price came from an exchange, that an order/fill occurred, or that a strategy was approved. A checkpoint authenticates only the exact bytes and state progression it is designed to attest.

Before any stronger source-authenticity claim, each event class must define its own evidence:
- Market observations: source/venue, instrument identity, retrieval time, event time, interval, pagination/coverage, raw response or immutable content digest, adapter/version and data-quality result. If the source does not sign data, say that provenance is locally recorded rather than cryptographically authenticated.
- Strategy decisions: immutable strategy/config/code digest, point-in-time input references and parameters, decision timestamp and deterministic replay evidence.
- Risk decisions: a reference to the existing independently controlled risk verdict and its exact input/output digests. The checkpoint design must not bypass, recreate, weaken or modify protected risk controls.
- PAPER fills: the approved simulator/version, source observations, fee/spread/slippage/impact model version, fill model inputs and deterministic simulated-fill result. A PAPER fill is a simulation record, not evidence of an exchange execution.
- Administrative/bootstrap events: an owner approval reference, evidence bundle digest, approving authority, scope and timestamp. A hash or signature must not be used to imply approval that was never granted.

The independent verifier may check that evidence references are present, canonical, correctly bound and consistent. It cannot independently prove off-platform facts unless it has a separate trusted source or attestation mechanism. Unsupported source-authenticity assertions must fail closed or be explicitly downgraded to "locally recorded, not independently authenticated."

## 13. Genesis and first-anchor requirements

A checkpoint chain needs an independently trusted genesis. It must not begin by accepting a caller-supplied current database head as the first trusted state.

- For a new ledger, initialize the account and explicit market policy, verify the corresponding initial audit events, then create and externally commit a genesis checkpoint before enabling any state-changing trading/simulation workflow.
- The genesis record binds a newly generated stable ledger ID, account/currency identity, schema version, initial audit sequence/head, key ID/algorithm and an explicit no-previous-checkpoint marker.
- The independent trust boundary records the genesis digest and identity in monotonic state. Repeating genesis with the same identity/digest is idempotent; a different digest or identity is a conflict.
- A pre-marker or historical ledger must not be silently adopted as a new genesis. It remains read-only until a separate, owner-approved bootstrap procedure supplies independently reviewable opening-cash, market-identity and inventory evidence. The bootstrap itself must be recorded as an explicit event and separately anchored before subsequent mutations.
- Never infer opening cash or tradable inventory from an unanchored database snapshot. A schema-only v1→v2 copy does not satisfy genesis or bootstrap evidence.
- If genesis/checkpoint storage is unavailable, no state-changing workflow may become enabled.

## 14. Checkpoint cadence and unanchored suffix bound

The safe default for a paper settlement ledger is one checkpoint per committed state-changing settlement batch:
- Commit the ledger mutation and its exact pending checkpoint request atomically in SQLite.
- Block subsequent state-changing strategy/settlement/reservation mutations while that checkpoint is pending.
- The independent verifier checks chain extension and semantic consistency, commits the signed checkpoint with monotonic anti-rollback state, reads it back, and only then allows local acknowledgement/unblocking.
- A retry must use the same ledger ID, sequence, previous checkpoint digest, audit head and idempotency key. Changed content at the same sequence is a fork/conflict.
- If an implementation proposes batching multiple mutations per checkpoint, it must explicitly quantify the maximum event/time exposure, justify why intermediate mutations remain blocked or otherwise tamper-evident, and obtain independent security review plus owner approval. A time-based interval alone is not an adequate security argument.

This does not solve malicious fabrication before the first trusted genesis, or prove economic truth of market data/fills. Source authenticity and bootstrap requirements above remain independent gates.

## 15. Independent-state placement and recovery authority

A private key in a phone/OS keystore provides key custody only. It does not automatically provide rollback-resistant monotonic ledger state, independent storage, semantic verification, or protection against a compromised operator account.

Before selecting a deployment model, document separately:
- where the private key is held;
- where monotonic ledger/checkpoint state is retained;
- where append-only checkpoint records are stored;
- which actors can rewrite each location;
- whether those locations share the same device, account, administrator or recovery credentials;
- how the system recovers after loss of the phone, signer, storage or network;
- who can approve recovery/key rotation and how that authority is recorded.

Do not call a second file, another directory, or a backup on the same writable device an independent trust anchor. Do not add a cloud/network service or select an iPhone key-storage mechanism without a separate owner-approved architecture decision. If there is no practical independent state boundary for the intended installation, keep external checkpoint protection unimplemented and keep the ledger's assurance limitation explicit.

### Additional required adversarial cases

- A caller presents a correctly hashed but fabricated PAPER fill with internally consistent cash/holdings; confirm that the checkpoint layer claims only semantic consistency unless simulator/input provenance is independently bound.
- A caller tries to establish genesis from a pre-existing pre-marker database with a fabricated opening balance; reject without an approved bootstrap evidence bundle.
- A caller changes only the strategy or simulator digest while retaining the same fill payload; reject or surface the mismatch.
- A locally stored keystore key signs bytes while monotonic state remains on the same rollbackable filesystem; prove this is not accepted as independent anti-rollback protection.
- Attempt a second state mutation while one checkpoint is pending; reject before any balance, reservation, audit, fill or outbox write.
- Lose or restore the operator device while the independent witness retains a newer head; require recovery authority and fail closed.
- Simulate the witness being unavailable before genesis and after a settlement commit; no state-changing progression is permitted.

These are design requirements only. They do not select a signer, device, storage service, network dependency, recovery owner, or operational deployment.
