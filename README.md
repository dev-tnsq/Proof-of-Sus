# AmongUs (Python Game + Stellar Web3 + ZK Privacy)

This repository contains two connected tracks:

1. **Classic desktop game** (Python + Pygame), already playable.
2. **Web3 privacy migration** (Stellar Soroban + Noir + non-custodial wallet flow), under active implementation.

---

## Project Goal

Build a privacy-preserving, verifiable social deduction game inspired by Among Us where:

- canonical match state is on-chain (Soroban contract),
- players sign all game-impacting actions non-custodially,
- sensitive logic (role/vote/task/kill validity) is protected with ZK proofs.

---

## Current Status

### Classic Game

- Singleplayer and LAN multiplayer are available.
- Main client launches with `python3 main.py`.

### Web3 Contract Layer (Part 1)

- Core Soroban game contract implemented in [amongus_contract/contracts/game/src/lib.rs](amongus_contract/contracts/game/src/lib.rs).
- Contract tests pass (`cargo test -p game`) for current test suite.
- Implemented lifecycle/actions include:
  - init/config/start game,
  - join/move,
  - meeting start + finalize,
  - vote submission with proof/nullifier checks,
  - task/kill proof submission,
  - winner transitions.

### Wallet + Signing Layer (Part 3 foundation)

- Localhost browser signer architecture implemented:
  - bridge API + persistence in [wallet_bridge/server.js](wallet_bridge/server.js),
  - signer UI in [wallet_bridge/public/signer.html](wallet_bridge/public/signer.html),
  - signer logic in [wallet_bridge/public/signer.js](wallet_bridge/public/signer.js),
  - Python client bridge wrappers in [web3_client/wallet_bridge.py](web3_client/wallet_bridge.py).

### Noir Circuits (Part 2 in progress)

- Circuit packages present in [noir_circuits](noir_circuits).
- IO/privacy schemas documented.
- End-to-end local `nargo` validation still depends on tool setup consistency in this environment.

---

## Repository Layout

- [main.py](main.py): game entry point.
- [game.py](game.py): core runtime loop and gameplay logic.
- [server.py](server.py): legacy LAN multiplayer server.
- [amongus_contract](amongus_contract): Soroban workspace.
- [noir_circuits](noir_circuits): Noir ZK circuit packages.
- [wallet_bridge](wallet_bridge): localhost signing bridge + browser signer app.
- [web3_client](web3_client): Python integration modules for wallet/signing flow.
- [docs/web3](docs/web3): architecture, roadmap, privacy model, action specs, phase tracker.

---

## Prerequisites

### For Classic Game

- Python 3.10+
- `pygame`
- `pytmx`

### For Soroban Contract Work

- Rust toolchain
- Soroban CLI

### For Wallet Bridge

- Node.js 18+
- npm

### For Noir Circuit Work

- Noir `nargo` CLI (recommended via official installer)

---

## Quick Start (Classic Game)

From project root:

```bash
python3 main.py
```

Menu flow:

- `Freeplay` for singleplayer.
- `Local` for LAN multiplayer.

For LAN multiplayer:

1. Start server:

```bash
python3 server.py
```

2. Start client on each player machine:

```bash
python3 main.py
```

3. Enter server IP in menu (use `127.0.0.1` on same machine).

---

## Quick Start (Web3 Localhost Non-Custodial Flow)

### 1) Start wallet bridge

```bash
./scripts/run_wallet_bridge.sh
```

### 2) Open signer page in browser

- http://127.0.0.1:8787/signer.html?mode=connect&playerId=default-player

Connect Freighter from this page.

### 3) Run Python signing demo

```bash
python3 -m web3_client.demo_sign_flow
```

This validates:

- request creation,
- browser-side sign/reject,
- signed payload polling from Python,
- local session/snapshot persistence.

---

## Contract Build and Test

From [amongus_contract](amongus_contract):

```bash
cargo test -p game
```

Soroban build:

```bash
soroban contract build
```

If shell session issues interrupt foreground builds, re-run from the same directory.

---

## Noir Circuits

Packages:

- [noir_circuits/role_proof](noir_circuits/role_proof)
- [noir_circuits/task_proof](noir_circuits/task_proof)
- [noir_circuits/vote_proof](noir_circuits/vote_proof)
- [noir_circuits/kill_proof](noir_circuits/kill_proof)

When `nargo` is available:

```bash
cd noir_circuits/role_proof && nargo check
cd ../task_proof && nargo check
cd ../vote_proof && nargo check
cd ../kill_proof && nargo check
```

---

## Privacy Model (What is private vs public)

See [docs/web3/PRIVACY_MODEL.md](docs/web3/PRIVACY_MODEL.md).

High-level:

- **Private witness:** role secrets, vote/task/kill witnesses.
- **Public on-chain:** nullifiers, commitments/hashes, phase transitions, aggregate counters.

---

## Contract Action Spec

See [docs/web3/CONTRACT_ACTIONS.md](docs/web3/CONTRACT_ACTIONS.md) for full list.

---

## One-Part-at-a-Time Delivery Plan

Strict phased execution is documented in:

- [docs/web3/PARTS_EXECUTION_GUIDE.md](docs/web3/PARTS_EXECUTION_GUIDE.md)
- [docs/web3/IMPLEMENTATION_ROADMAP.md](docs/web3/IMPLEMENTATION_ROADMAP.md)
- [docs/web3/PHASE_STATUS.md](docs/web3/PHASE_STATUS.md)

Policy:

- no mock behavior in production path,
- no hidden fallback bypassing auth/proof checks,
- complete each part with validation before next part.

---

## Controls (Classic Game)

### Menu

- `Arrow Keys` / `WASD`: navigate
- `Enter`: select
- `Esc`: back

### In-game

- `Arrow Keys` / `WASD`: move
- `Space`: interact / perform actions
- `Left Click`: tasks, voting UI interactions
- `Tab`: map
- `Alt`: cycle vent
- `Enter`: kill (when applicable)
- `Ctrl`: sabotage/fix lights flow
- `Shift`: sabotage/fix reactor flow

---

## Troubleshooting

### `ModuleNotFoundError: pygame`

Install with your Python environment tooling. On restricted macOS Python setups, use either virtualenv or explicit break-system-packages if required by your environment policy.

### Asset path issues on macOS/Linux

The project expects forward-slash paths under `Assets/...`.

### Bridge reachable but no signing

Ensure:

- signer page is opened in browser,
- Freighter extension is installed and unlocked,
- request URL contains `requestId` for signing mode.

