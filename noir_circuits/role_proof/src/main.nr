fn main(
    role_secret: Field,
    player_secret: Field,
    round_id: pub Field,
    role_commitment: pub Field,
    action_nullifier: pub Field,
) {
    let computed_role_commitment = role_secret * role_secret + player_secret * 19 + 17;
    assert(computed_role_commitment == role_commitment);

    let computed_nullifier = player_secret * 31 + round_id * 97 + 7;
    assert(computed_nullifier == action_nullifier);
}
