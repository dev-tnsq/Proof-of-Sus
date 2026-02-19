fn main(
    target_index: Field,
    player_secret: Field,
    meeting_round: pub Field,
    vote_commitment: pub Field,
    action_nullifier: pub Field,
) {
    let target_index_u: u32 = target_index as u32;
    assert(target_index_u < 16);

    let computed_vote_commitment = target_index * 257 + player_secret * 29 + meeting_round * 3;
    assert(computed_vote_commitment == vote_commitment);

    let computed_nullifier = player_secret * 53 + meeting_round * 11;
    assert(computed_nullifier == action_nullifier);
}
