# Contract Actions (Part 1 Complete)

This document lists the complete on-chain actions implemented in the Soroban game contract.

## Admin actions

- init(admin, impostor_count)
- configure_game(caller, max_players, tasks_to_win)
- set_verifier(caller, verifier)
- set_phase(caller, phase)
- start_game(caller)
- end_meeting(caller)
- finalize_meeting(caller, ejected_player_hash)
- end_game_admin(caller, winner)

## Player actions

- join_game(player, color, name, player_hash, role_hash)
- submit_move(player, x, y)
- start_meeting(caller)
- submit_vote(voter, vote)
- submit_task_proof(player, proof)
- submit_kill_proof(killer, victim, proof)
- submit_impostor_win_proof(caller, proof)

## Read actions

- get_players()
- get_config()
- get_game_state()

## Security and integrity checks included

- Phase-gated actions (lobby/playing/meeting/ended).
- Verifier contract required for proof-gated actions.
- Nullifier replay protection via UsedNullifier key.
- Duplicate join and duplicate player hash prevention.
- Majority vote check for ejection.
- Crew win from task threshold.
- Impostor win from alive-threshold or verified win proof.
