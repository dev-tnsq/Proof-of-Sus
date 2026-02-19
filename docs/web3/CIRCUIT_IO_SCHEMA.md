# Noir Circuit IO Schema

This schema defines how Noir outputs map into Soroban contract calls.

## Common contract input

Contract methods using proof-gated actions consume:

- `proof_hash`: `BytesN<32>`
- `nullifier`: `BytesN<32>`
- `public_inputs`: `Vec<BytesN<32>>`

## Vote proof mapping

- Circuit public:
  - `meeting_round`
  - `vote_commitment`
  - `action_nullifier`
- Contract mapping:
  - `target_hash` ← `vote_commitment`
  - `proof_hash` ← verifier proof artifact hash
  - `nullifier` ← `action_nullifier`

## Task proof mapping

- Circuit public:
  - `round_id`
  - `task_commitment`
  - `action_nullifier`
- Contract mapping:
  - `proof_hash` ← verifier proof artifact hash
  - `nullifier` ← `action_nullifier`
  - `public_inputs` includes `task_commitment` and `round_id`.

## Kill proof mapping

- Circuit public:
  - `round_id`
  - `kill_commitment`
  - `action_nullifier`
- Contract mapping:
  - `proof_hash` ← verifier proof artifact hash
  - `nullifier` ← `action_nullifier`
  - `public_inputs` includes `kill_commitment` and `round_id`.
