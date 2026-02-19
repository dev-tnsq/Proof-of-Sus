# Privacy Model for AmongUs on Stellar

## Private by default

These values must remain private witness inputs in circuits:

- Player role secret (`impostor` / `crewmate` witness encoding).
- Vote selection preimage.
- Task witness details (task secret / nonce).
- Kill witness details (exact local geometry, cooldown witness).

## Public on-chain signals

These values are safe to publish as contract inputs:

- Action nullifier hash (anti-replay / anti-double-spend).
- Proof hash / commitment.
- Round index and action type tags.
- Committed vote target hash (not raw target identity).

## Privacy requirements per action

### Voting

- Private: who was selected.
- Public: one vote in current meeting by this account (nullifier uniqueness).

### Task completion

- Private: task witness payload and local randomness.
- Public: proof that a valid task transition occurred once.

### Kill action

- Private: role secret and exact positional witness.
- Public: validity of kill constraints and unique action nullifier.

## Non-goals (not private)

- Transaction sender address (wallet account is public on-chain).
- High-level game phase transitions.
- Aggregate task counters.
