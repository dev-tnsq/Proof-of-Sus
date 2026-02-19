# Web3 Build Execution Guide (Strict, One Part at a Time)

This project follows a strict delivery policy:

- No mock behavior in production paths.
- No hidden fallbacks that bypass verification/security.
- Complete one part fully before starting the next part.

## Part 1: Contract Core (Soroban)

Goal: canonical game logic/state machine on-chain.

Checklist:

1. Phase state machine is enforced (`lobby` → `playing` → `meeting` → `playing`).
2. Every action checks phase and player state.
3. Vote/task/kill are proof-gated and nullifier protected.
4. Verifier contract address is required and invoked.
5. Contract tests pass for positive and negative paths.

Exit criteria:

- `cargo test -p game` is green.
- No placeholder verification path remains in core action methods.

## Part 2: Noir Circuits

Goal: real proof circuits for vote/task/kill/role privacy.

Checklist:

1. Circuit constraints represent real game rules.
2. Public inputs and nullifier format are stable.
3. Proof generation scripts are deterministic and reproducible.
4. Outputs match contract verifier input schema.

Exit criteria:

- `nargo check` passes for all circuits.
- Proof artifacts can be consumed by verifier flow.

## Part 3: Wallet Connect (Localhost Browser Signer)

Goal: non-custodial signing from browser wallet with Pygame trigger.

Checklist:

1. Pygame creates signing request via local bridge.
2. Browser signer page connects Freighter and signs XDR.
3. Signed XDR is persisted and retrievable by Python.
4. Session data persists locally.

Exit criteria:

- End-to-end request lifecycle validated (`pending` → `signed`/`rejected`).

## Part 4: Interconnect

Goal: contract + Noir + wallet are wired together.

Checklist:

1. Pygame calls contract actions through signed transactions.
2. Proof outputs are attached to corresponding actions.
3. On-chain events are consumed to update game state.

Exit criteria:

- Full match loop (join, move, meeting, vote, kill/task updates) runs in Web3 mode.

## Part 5: Testing and Hardening

Goal: reliability and anti-cheat confidence.

Checklist:

1. Contract unit/integration tests.
2. Bridge and client flow tests.
3. Replay and nullifier abuse tests.
4. Failure path handling with explicit errors.

Exit criteria:

- Test suite passes.
- No silent bypass of signing or proof checks.
