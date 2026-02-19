#![cfg(test)]

use super::*;
use soroban_sdk::{
    contract, contractimpl, symbol_short, testutils::Address as _, Address, BytesN, Env, Vec,
};

#[contract]
pub struct MockVerifier;

#[contractimpl]
impl MockVerifier {
    pub fn verify(_env: Env, proof_hash: BytesN<32>, _public_inputs: Vec<BytesN<32>>) -> bool {
        proof_hash != BytesN::from_array(&_env, &[0; 32])
    }
}

fn join_four_players(env: &Env, client: &AmongUsContractClient<'_>) -> Vec<Address> {
    let p1 = Address::generate(env);
    let p2 = Address::generate(env);
    let p3 = Address::generate(env);
    let p4 = Address::generate(env);

    client.join_game(
        &p1,
        &symbol_short!("Red"),
        &symbol_short!("P1"),
        &BytesN::from_array(env, &[11; 32]),
        &BytesN::from_array(env, &[1; 32]),
    );
    client.join_game(
        &p2,
        &symbol_short!("Blu"),
        &symbol_short!("P2"),
        &BytesN::from_array(env, &[22; 32]),
        &BytesN::from_array(env, &[2; 32]),
    );
    client.join_game(
        &p3,
        &symbol_short!("Gre"),
        &symbol_short!("P3"),
        &BytesN::from_array(env, &[33; 32]),
        &BytesN::from_array(env, &[3; 32]),
    );
    client.join_game(
        &p4,
        &symbol_short!("Yel"),
        &symbol_short!("P4"),
        &BytesN::from_array(env, &[44; 32]),
        &BytesN::from_array(env, &[4; 32]),
    );

    let mut out = Vec::new(env);
    out.push_back(p1);
    out.push_back(p2);
    out.push_back(p3);
    out.push_back(p4);
    out
}

#[test]
fn join_and_move_player() {
    let env = Env::default();
    env.mock_all_auths();
    let contract_id = env.register_contract(None, AmongUsContract);
    let client = AmongUsContractClient::new(&env, &contract_id);

    let admin = Address::generate(&env);

    client.init(&admin, &1);
    let players = join_four_players(&env, &client);
    client.start_game(&admin);

    let player = players.get(0).unwrap();
    client.submit_move(&player, &42, &84);

    let all_players = client.get_players();
    let stored = all_players.get(player).unwrap();

    assert_eq!(stored.x, 42);
    assert_eq!(stored.y, 84);
    assert_eq!(stored.alive, true);
}

#[test]
fn submit_vote_with_verifier() {
    let env = Env::default();
    env.mock_all_auths();

    let verifier_id = env.register_contract(None, MockVerifier);
    let contract_id = env.register_contract(None, AmongUsContract);
    let client = AmongUsContractClient::new(&env, &contract_id);

    let admin = Address::generate(&env);
    client.init(&admin, &1);
    client.set_verifier(&admin, &verifier_id);
    let players = join_four_players(&env, &client);
    client.start_game(&admin);

    let voter = players.get(0).unwrap();

    client.start_meeting(&voter);

    let vote = VoteInput {
        target_hash: BytesN::from_array(&env, &[4; 32]),
        proof_hash: BytesN::from_array(&env, &[8; 32]),
        nullifier: BytesN::from_array(&env, &[5; 32]),
    };
    client.submit_vote(&voter, &vote);

    let players = client.get_players();
    let stored = players.get(voter).unwrap();
    assert_eq!(stored.voted_for_hash, BytesN::from_array(&env, &[4; 32]));
}

#[test]
fn finalize_meeting_ejects_majority_target() {
    let env = Env::default();
    env.mock_all_auths();

    let verifier_id = env.register_contract(None, MockVerifier);
    let contract_id = env.register_contract(None, AmongUsContract);
    let client = AmongUsContractClient::new(&env, &contract_id);

    let admin = Address::generate(&env);
    client.init(&admin, &1);
    client.set_verifier(&admin, &verifier_id);
    let players = join_four_players(&env, &client);
    client.start_game(&admin);

    let p1 = players.get(0).unwrap();
    let p2 = players.get(1).unwrap();
    let p3 = players.get(2).unwrap();
    let p4 = players.get(3).unwrap();

    client.start_meeting(&p1);

    let target_hash = BytesN::from_array(&env, &[22; 32]);

    client.submit_vote(
        &p1,
        &VoteInput {
            target_hash: target_hash.clone(),
            proof_hash: BytesN::from_array(&env, &[8; 32]),
            nullifier: BytesN::from_array(&env, &[51; 32]),
        },
    );
    client.submit_vote(
        &p3,
        &VoteInput {
            target_hash: target_hash.clone(),
            proof_hash: BytesN::from_array(&env, &[9; 32]),
            nullifier: BytesN::from_array(&env, &[52; 32]),
        },
    );
    client.submit_vote(
        &p4,
        &VoteInput {
            target_hash: target_hash.clone(),
            proof_hash: BytesN::from_array(&env, &[10; 32]),
            nullifier: BytesN::from_array(&env, &[53; 32]),
        },
    );

    client.finalize_meeting(&admin, &target_hash);

    let all_players = client.get_players();
    let ejected = all_players.get(p2).unwrap();
    assert_eq!(ejected.alive, false);
}

