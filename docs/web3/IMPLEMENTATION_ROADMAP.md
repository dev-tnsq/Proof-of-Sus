# Web3 + ZK Implementation Roadmap

## Phase 0: Baseline Freeze

- Keep current Pygame gameplay functional.
- Add feature flag: `GAME_MODE=web3`.
- Enforce policy: no mock signing/proof flow in production path.
- Enforce policy: no fallback path that bypasses auth/proof checks.

## Phase 1: Soroban Core Game State

- Implement and test:
  - `init`
  - `join_game`
  - `submit_move`
  - `start_meeting`
  - `submit_vote`
  - `increment_tasks`
- Add events for all state changes.
- Add integration script to deploy and invoke on testnet.

## Phase 2: Wallet Bridge + Python Client

- Run local bridge service.
- Add Python wallet service wrapper (`web3_client/wallet_bridge.py`).
- Add Stellar transaction builder (`web3_client/stellar_client.py`).
- Add `Web3` option in menu and switch action handlers to contract calls.

## Phase 3: Noir ZK MVP

- Circuit 1: vote validity + nullifier.
- Circuit 2: task completion witness.
- Produce proof hash / public input model consumed by Soroban.
- Use verifier integration path aligned with contract inputs; no mock verifier in production deployment.

## Phase 4: Noir Verification Integration

- Integrate generated verifier path compatible with Soroban constraints.
- Replace placeholder verifier with actual verification endpoint or precompile-compatible path.
- Enforce proof verification in vote/task/kill endpoints.

## Phase 5: Full Privacy Mechanics

- Hidden role commitment + reveal protocol at game end.
- Anonymous voting outcome tally.
- Kill proof with position witness and cooldown witness.
- Add anti-cheat checks for replay and duplicate nullifiers.

## Phase 6: Production Hardening

- Event reorg / retry handling.
- Deterministic state reconciliation.
- Metrics and telemetry for tx latency and proof generation times.

## Definition of Done

- A complete match can be played in Web3 mode with no centralized authority.
- Every game-impacting action is verifiable on-chain.
- Sensitive role/action details are private using ZK proofs.
