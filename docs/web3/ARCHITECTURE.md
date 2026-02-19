# AmongUs Stellar Web3 Architecture

## 1) Target System

The project becomes a hybrid real-time game with verifiable on-chain state:

- **Pygame client** renders world, UI, and interactions.
- **Wallet bridge** handles browser wallet auth/signing and returns signed payloads to Pygame.
- **Soroban contract** is authoritative for identity, phase state, actions, and outcomes.
- **Noir circuits** provide privacy proofs for role-sensitive actions.

This keeps gameplay smooth while preserving on-chain trust and ZK privacy.

## 2) Components

### A. Pygame Client (Python)

- Existing loops stay: `events()`, `update()`, `draw()`.
- Networking path changes:
  - old: sockets to `server.py`
  - new: RPC to Stellar + local wallet bridge HTTP calls.
- Maintains local prediction for movement and UI responsiveness.

### B. Wallet Bridge (Node.js local process)

- Opens localhost API for wallet actions Pygame cannot do directly.
- Responsibilities:
  - connect to Freighter in browser context,
  - request account/public key,
  - sign XDR payloads,
  - return signatures and metadata to Python.

### C. Soroban Contract (Rust)

- Stores all canonical game state:
  - players,
  - phase (`lobby`, `playing`, `meeting`),
  - task counters,
  - vote commitments.
- Emits events for clients to consume.
- Performs stateless validation and phase transitions.

### D. Noir Circuits

- Role proof (authorized kill action without revealing role).
- Task proof (valid task completion without leaking exact secret input).
- Vote proof (ballot validity + anti-double-vote nullifier).
- Kill proof (proximity and cooldown correctness under hidden witness inputs).

## 3) Data Flow

1. Player opens Pygame and chooses `Web3` mode.
2. Pygame asks local wallet bridge for account session.
3. Player joins game by submitting signed transaction to `join_game`.
4. During runtime:
   - movement and public actions: direct signed calls,
   - private actions: Pygame generates Noir proof, submits proof hash + public inputs.
5. Contract emits events.
6. Pygame polls events / state snapshots and updates render.

## 4) Fully On-Chain Scope

For this project, “fully on-chain” means:

- Canonical game state and rule enforcement are on Soroban.
- Every game-impacting action is represented by an on-chain transaction.
- Off-chain processes (render, wallet UX, proof generation) are execution helpers only.

## 5) Security Constraints

- Never store plain role in contract state; store commitment/hash.
- Enforce sender auth for all state-changing calls.
- Add nullifier checks for one-time actions (vote per meeting, single kill per cooldown window).
- Reject malformed proof metadata before expensive verification.

## 6) Performance Model

- Movement batching window: 500ms–1500ms per tx bundle.
- Meeting/vote actions are single-tx and synchronous.
- Event polling interval from client: 1s–2s.

## 7) Migration Strategy

- Keep existing Freeplay and LAN modes intact.
- Add a third mode: `Web3`.
- Move server-side logic incrementally from `server.py` into Soroban calls.
