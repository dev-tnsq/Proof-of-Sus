fn main(
    dx: Field,
    dy: Field,
    cooldown_ok: Field,
    role_flag: Field,
    player_secret: Field,
    round_id: pub Field,
    kill_commitment: pub Field,
    action_nullifier: pub Field,
) {
    let distance_metric = dx * dx + dy * dy;
    assert(distance_metric < 40000);
    assert(cooldown_ok == 1);
    assert(role_flag == 1);

    let out = distance_metric * 11 + cooldown_ok + role_flag * 97 + player_secret * 5;
    assert(out == kill_commitment);

    let computed_nullifier = player_secret * 67 + round_id * 17;
    assert(computed_nullifier == action_nullifier);
}
