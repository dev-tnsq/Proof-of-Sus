# Noir Circuits for AmongUs ZK Privacy

This directory contains separate Noir packages for game privacy primitives.

- `role_proof`: prove role authorization without revealing role.
- `task_proof`: prove valid task completion witness.
- `vote_proof`: prove valid vote + nullifier uniqueness input.
- `kill_proof`: prove kill constraints (distance/cooldown/authorization).

## Local workflow

1. Install Noir toolchain (`nargo`, `noirup`).
2. For each package:
   - `cd <package>`
   - `nargo check`
   - `nargo compile`
   - `nargo prove`
3. Export verification artifacts for Soroban integration flow.
