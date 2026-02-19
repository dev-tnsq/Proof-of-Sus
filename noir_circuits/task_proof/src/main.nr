fn main(
    task_id: Field,
    task_secret: Field,
    player_secret: Field,
    round_id: pub Field,
    task_commitment: pub Field,
    action_nullifier: pub Field,
) {
    let task_id_u: u32 = task_id as u32;
    assert(task_id_u < 16);

    let computed_task_commitment = task_id * 131 + task_secret * 17 + player_secret * 23;
    assert(computed_task_commitment == task_commitment);

    let computed_nullifier = player_secret * 41 + task_id * 13 + round_id * 101;
    assert(computed_nullifier == action_nullifier);
}
