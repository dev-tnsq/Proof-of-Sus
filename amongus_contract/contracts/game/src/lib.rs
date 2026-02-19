#![no_std]

use soroban_sdk::{
    contract, contractimpl, contracttype, symbol_short, vec, Address, BytesN, Env, IntoVal, Map,
    Symbol, Val, Vec,
};

#[contract]
pub struct AmongUsContract;

#[contracttype]
#[derive(Clone, Eq, PartialEq)]
pub enum DataKey {
    Admin,
    Verifier,
    Config,
    GameState,
    Players,
    UsedNullifier(BytesN<32>),
}

#[contracttype]
#[derive(Clone, Eq, PartialEq)]
pub struct Player {
    pub x: u32,
    pub y: u32,
    pub alive: bool,
    pub tasks_done: u32,
    pub player_hash: BytesN<32>,
    pub role_hash: BytesN<32>,
    pub voted_for_hash: BytesN<32>,
    pub color: Symbol,
    pub name: Symbol,
}

#[contracttype]
#[derive(Clone, Eq, PartialEq)]
pub struct GameConfig {
    pub max_players: u32,
    pub tasks_to_win: u32,
}

#[contracttype]
#[derive(Clone, Eq, PartialEq)]
pub struct GameState {
    pub phase: Symbol,
    pub round: u32,
    pub meeting_active: bool,
    pub impostor_count: u32,
    pub sabotage_active: bool,
    pub winner: Symbol,
}

#[contracttype]
#[derive(Clone, Eq, PartialEq)]
pub struct VoteInput {
    pub target_hash: BytesN<32>,
    pub proof_hash: BytesN<32>,
    pub nullifier: BytesN<32>,
}

#[contracttype]
#[derive(Clone, Eq, PartialEq)]
pub struct ProofInput {
    pub proof_hash: BytesN<32>,
    pub nullifier: BytesN<32>,
    pub public_inputs: Vec<BytesN<32>>,
}

impl AmongUsContract {
    fn ensure_not_ended(env: &Env) {
        let state = Self::read_state(env);
        if state.phase == symbol_short!("ended") {
            panic!("game already ended");
        }
    }

    fn require_admin(env: &Env, caller: &Address) {
        caller.require_auth();
        let admin: Address = env
            .storage()
            .instance()
            .get(&DataKey::Admin)
            .unwrap_or_else(|| panic!("admin not set"));
        if admin != *caller {
            panic!("not admin");
        }
    }

    fn read_players(env: &Env) -> Map<Address, Player> {
        env.storage()
            .instance()
            .get(&DataKey::Players)
            .unwrap_or(Map::new(env))
    }

    fn write_players(env: &Env, players: &Map<Address, Player>) {
        env.storage().instance().set(&DataKey::Players, players);
    }

    fn read_config(env: &Env) -> GameConfig {
        env.storage().instance().get(&DataKey::Config).unwrap_or(GameConfig {
            max_players: 15,
            tasks_to_win: 40,
        })
    }

    fn write_config(env: &Env, config: &GameConfig) {
        env.storage().instance().set(&DataKey::Config, config);
    }

    fn read_state(env: &Env) -> GameState {
        env.storage().instance().get(&DataKey::GameState).unwrap_or(GameState {
            phase: symbol_short!("lobby"),
            round: 0,
            meeting_active: false,
            impostor_count: 1,
            sabotage_active: false,
            winner: symbol_short!("none"),
        })
    }

    fn write_state(env: &Env, state: &GameState) {
        env.storage().instance().set(&DataKey::GameState, state);
    }

    fn count_alive(players: &Map<Address, Player>) -> u32 {
        let mut alive = 0u32;
        for (_, p) in players.iter() {
            if p.alive {
                alive += 1;
            }
        }
        alive
    }

    fn total_tasks(players: &Map<Address, Player>) -> u32 {
        let mut total = 0u32;
        for (_, p) in players.iter() {
            total += p.tasks_done;
        }
        total
    }

    fn set_winner(env: &Env, winner: Symbol) {
        let mut state = Self::read_state(env);
        state.winner = winner;
        state.phase = symbol_short!("ended");
        state.meeting_active = false;
        Self::write_state(env, &state);
    }
}

#[contractimpl]
impl AmongUsContract {
    pub fn init(env: Env, admin: Address, impostor_count: u32) {
        if env.storage().instance().has(&DataKey::GameState) {
            panic!("already initialized");
        }
        admin.require_auth();

        let state = GameState {
            phase: symbol_short!("lobby"),
            round: 0,
            meeting_active: false,
            impostor_count,
            sabotage_active: false,
            winner: symbol_short!("none"),
        };

        Self::write_state(&env, &state);
        Self::write_config(
            &env,
            &GameConfig {
                max_players: 15,
                tasks_to_win: 40,
            },
        );
        env.storage().instance().set(&DataKey::Admin, &admin);
        Self::write_players(&env, &Map::new(&env));
    }

    pub fn configure_game(env: Env, caller: Address, max_players: u32, tasks_to_win: u32) {
        Self::require_admin(&env, &caller);
        if max_players < 4 {
            panic!("max_players must be >= 4");
        }
        if tasks_to_win == 0 {
            panic!("tasks_to_win must be > 0");
        }
        Self::write_config(
            &env,
            &GameConfig {
                max_players,
                tasks_to_win,
            },
        );
    }

    pub fn set_verifier(env: Env, caller: Address, verifier: Address) {
        Self::require_admin(&env, &caller);
        env.storage().instance().set(&DataKey::Verifier, &verifier);
    }

    pub fn set_phase(env: Env, caller: Address, phase: Symbol) {
        Self::require_admin(&env, &caller);
        let mut state = Self::read_state(&env);
        state.phase = phase;
        Self::write_state(&env, &state);
    }

    pub fn start_game(env: Env, caller: Address) {
        Self::require_admin(&env, &caller);
        let mut state = Self::read_state(&env);
        if state.phase != symbol_short!("lobby") {
            panic!("game already started");
        }
        let players = Self::read_players(&env);
        if players.len() < 4 {
            panic!("need at least 4 players");
        }
        state.phase = symbol_short!("playing");
        state.round = 1;
        state.meeting_active = false;
        state.winner = symbol_short!("none");
        Self::write_state(&env, &state);
        env.events().publish((symbol_short!("started"), caller), state.round);
    }

    pub fn join_game(
        env: Env,
        player: Address,
        color: Symbol,
        name: Symbol,
        player_hash: BytesN<32>,
        role_hash: BytesN<32>,
    ) {
        player.require_auth();
        Self::ensure_not_ended(&env);

        let state = Self::read_state(&env);
        if state.phase != symbol_short!("lobby") {
            panic!("joining only allowed in lobby");
        }

        let config = Self::read_config(&env);
        let mut players = Self::read_players(&env);
        if players.len() >= config.max_players {
            panic!("lobby is full");
        }
        if players.get(player.clone()).is_some() {
            panic!("player already joined");
        }

        for (_, p) in players.iter() {
            if p.player_hash == player_hash {
                panic!("duplicate player hash");
            }
        }

        let entry = Player {
            x: 0,
            y: 0,
            alive: true,
            tasks_done: 0,
            player_hash,
            role_hash,
            voted_for_hash: BytesN::from_array(&env, &[0; 32]),
            color,
            name,
        };

        players.set(player.clone(), entry);
        Self::write_players(&env, &players);
        env.events().publish((symbol_short!("joined"), player), ());
    }

    pub fn submit_move(env: Env, player: Address, x: u32, y: u32) {
        player.require_auth();
        Self::ensure_not_ended(&env);
        let state = Self::read_state(&env);
        if state.phase != symbol_short!("playing") {
            panic!("movement not allowed in current phase");
        }

        let mut players = Self::read_players(&env);
        let mut entry = players.get(player.clone()).unwrap_or_else(|| panic!("player not found"));
        if !entry.alive {
            panic!("dead player cannot move");
        }

        entry.x = x;
        entry.y = y;

        players.set(player.clone(), entry);
        Self::write_players(&env, &players);
        env.events().publish((symbol_short!("moved"), player), (x, y));
    }

    pub fn start_meeting(env: Env, caller: Address) {
        caller.require_auth();
        Self::ensure_not_ended(&env);

        let players_for_caller = Self::read_players(&env);
        let caller_entry = players_for_caller
            .get(caller.clone())
            .unwrap_or_else(|| panic!("caller not found"));
        if !caller_entry.alive {
            panic!("dead player cannot start meeting");
        }

        let mut state = Self::read_state(&env);
        if state.phase != symbol_short!("playing") {
            panic!("meeting can only be started while playing");
        }
        state.phase = symbol_short!("meeting");
        state.meeting_active = true;
        state.round += 1;

        let mut players = Self::read_players(&env);
        for (addr, mut p) in players.clone().iter() {
            if p.alive {
                p.voted_for_hash = BytesN::from_array(&env, &[0; 32]);
                players.set(addr, p);
            }
        }
        Self::write_players(&env, &players);

        Self::write_state(&env, &state);
        env.events().publish((symbol_short!("meeting"), caller), state.round);
    }

    pub fn end_meeting(env: Env, caller: Address) {
        Self::require_admin(&env, &caller);
        let mut state = Self::read_state(&env);
        if state.phase != symbol_short!("meeting") {
            panic!("meeting not active");
        }
        state.phase = symbol_short!("playing");
        state.meeting_active = false;
        Self::write_state(&env, &state);
        env.events().publish((symbol_short!("resume"), caller), state.round);
    }

    pub fn finalize_meeting(env: Env, caller: Address, ejected_player_hash: BytesN<32>) {
        Self::require_admin(&env, &caller);
        let mut state = Self::read_state(&env);
        if state.phase != symbol_short!("meeting") {
            panic!("meeting not active");
        }

        let mut players = Self::read_players(&env);
        let mut alive_voters = 0u32;
        let mut votes_for_target = 0u32;
        for (_, p) in players.iter() {
            if p.alive {
                alive_voters += 1;
                if p.voted_for_hash == ejected_player_hash {
                    votes_for_target += 1;
                }
            }
        }

        if alive_voters == 0 {
            panic!("no alive voters");
        }

        let mut ejected = false;
        if votes_for_target * 2 > alive_voters {
            for (addr, mut p) in players.clone().iter() {
                if p.alive && p.player_hash == ejected_player_hash {
                    p.alive = false;
                    players.set(addr, p);
                    ejected = true;
                    break;
                }
            }
        }

        if ejected {
            env.events()
                .publish((symbol_short!("ejected"), caller.clone()), ejected_player_hash);
        } else {
            env.events()
                .publish((symbol_short!("skipped"), caller.clone()), ejected_player_hash);
        }

        Self::write_players(&env, &players);
        state.phase = symbol_short!("playing");
        state.meeting_active = false;
        Self::write_state(&env, &state);
    }

    pub fn submit_vote(env: Env, voter: Address, vote: VoteInput) {
        voter.require_auth();
        Self::ensure_not_ended(&env);
        let state = Self::read_state(&env);
        if state.phase != symbol_short!("meeting") {
            panic!("voting not allowed in current phase");
        }

        if env.storage().instance().has(&DataKey::UsedNullifier(vote.nullifier.clone())) {
            panic!("nullifier already used");
        }

        let mut players = Self::read_players(&env);
        let mut entry = players.get(voter.clone()).unwrap_or_else(|| panic!("player not found"));
        if !entry.alive {
            panic!("dead player cannot vote");
        }
        if entry.voted_for_hash != BytesN::from_array(&env, &[0; 32]) {
            panic!("player already voted");
        }

        if !Self::verify_zk_proof(
            env.clone(),
            vote.proof_hash,
            vec![&env, vote.nullifier.clone()],
        ) {
            panic!("invalid vote proof");
        }

        entry.voted_for_hash = vote.target_hash.clone();
        players.set(voter.clone(), entry);
        Self::write_players(&env, &players);
        env.storage()
            .instance()
            .set(&DataKey::UsedNullifier(vote.nullifier), &true);
        env.events().publish((symbol_short!("voted"), voter), vote.target_hash);
    }

    pub fn submit_task_proof(env: Env, player: Address, proof: ProofInput) {
        player.require_auth();
        Self::ensure_not_ended(&env);
        let state = Self::read_state(&env);
        if state.phase != symbol_short!("playing") {
            panic!("task submission not allowed in current phase");
        }

        if env
            .storage()
            .instance()
            .has(&DataKey::UsedNullifier(proof.nullifier.clone()))
        {
            panic!("task nullifier already used");
        }

        let mut players = Self::read_players(&env);
        let mut entry = players.get(player.clone()).unwrap_or_else(|| panic!("player not found"));
        if !entry.alive {
            panic!("dead player cannot submit tasks");
        }

        let mut public_inputs = proof.public_inputs.clone();
        public_inputs.push_back(proof.nullifier.clone());
        if !Self::verify_zk_proof(env.clone(), proof.proof_hash, public_inputs) {
            panic!("invalid task proof");
        }

        entry.tasks_done += 1;
        players.set(player.clone(), entry);
        Self::write_players(&env, &players);
        env.storage()
            .instance()
            .set(&DataKey::UsedNullifier(proof.nullifier), &true);

        let cfg = Self::read_config(&env);
        let total_tasks = Self::total_tasks(&players);
        if total_tasks >= cfg.tasks_to_win {
            Self::set_winner(&env, symbol_short!("crew"));
            env.events().publish((symbol_short!("winner"), player), symbol_short!("crew"));
        }
    }

    pub fn submit_kill_proof(env: Env, killer: Address, victim: Address, proof: ProofInput) {
        killer.require_auth();
        Self::ensure_not_ended(&env);

        let state = Self::read_state(&env);
        if state.phase != symbol_short!("playing") {
            panic!("kills not allowed in current phase");
        }

        if env
            .storage()
            .instance()
            .has(&DataKey::UsedNullifier(proof.nullifier.clone()))
        {
            panic!("kill nullifier already used");
        }

        let mut players = Self::read_players(&env);
        let killer_entry = players
            .get(killer.clone())
            .unwrap_or_else(|| panic!("killer not found"));
        if !killer_entry.alive {
            panic!("dead player cannot kill");
        }

        let mut victim_entry = players
            .get(victim.clone())
            .unwrap_or_else(|| panic!("victim not found"));
        if !victim_entry.alive {
            panic!("victim already dead");
        }

        let mut public_inputs = proof.public_inputs.clone();
        public_inputs.push_back(proof.nullifier.clone());
        if !Self::verify_zk_proof(env.clone(), proof.proof_hash, public_inputs) {
            panic!("invalid kill proof");
        }

        victim_entry.alive = false;
        players.set(victim.clone(), victim_entry);
        Self::write_players(&env, &players);
        env.storage()
            .instance()
            .set(&DataKey::UsedNullifier(proof.nullifier), &true);

        let alive = Self::count_alive(&players);
        if alive <= state.impostor_count {
            Self::set_winner(&env, symbol_short!("impost"));
            env.events().publish((symbol_short!("winner"), killer.clone()), symbol_short!("impost"));
        }

        env.events().publish((symbol_short!("killed"), killer), victim);
    }

    pub fn submit_impostor_win_proof(env: Env, caller: Address, proof: ProofInput) {
        caller.require_auth();
        Self::ensure_not_ended(&env);

        if env
            .storage()
            .instance()
            .has(&DataKey::UsedNullifier(proof.nullifier.clone()))
        {
            panic!("impostor nullifier already used");
        }

        let mut public_inputs = proof.public_inputs.clone();
        public_inputs.push_back(proof.nullifier.clone());
        if !Self::verify_zk_proof(env.clone(), proof.proof_hash, public_inputs) {
            panic!("invalid impostor win proof");
        }

        env.storage()
            .instance()
            .set(&DataKey::UsedNullifier(proof.nullifier), &true);
        Self::set_winner(&env, symbol_short!("impost"));
        env.events()
            .publish((symbol_short!("winner"), caller), symbol_short!("impost"));
    }

    pub fn end_game_admin(env: Env, caller: Address, winner: Symbol) {
        Self::require_admin(&env, &caller);
        if winner != symbol_short!("crew") && winner != symbol_short!("impost") {
            panic!("invalid winner symbol");
        }
        Self::set_winner(&env, winner);
    }

    pub fn get_players(env: Env) -> Map<Address, Player> {
        Self::read_players(&env)
    }

    pub fn get_config(env: Env) -> GameConfig {
        Self::read_config(&env)
    }

    pub fn get_game_state(env: Env) -> GameState {
        Self::read_state(&env)
    }

    pub fn verify_zk_proof(env: Env, proof_hash: BytesN<32>, public_inputs: Vec<BytesN<32>>) -> bool {
        let verifier: Address = env
            .storage()
            .instance()
            .get(&DataKey::Verifier)
            .unwrap_or_else(|| panic!("verifier not configured"));

        let args: Vec<Val> = vec![
            &env,
            proof_hash.into_val(&env),
            public_inputs.into_val(&env),
        ];

        env.invoke_contract::<bool>(&verifier, &symbol_short!("verify"), args)
    }
}

mod test;
