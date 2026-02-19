"""
stellar_game_client.py
Builds Soroban contract invocation XDRs and submits signed transactions.

Prerequisites
-------------
- stellar-sdk >= 13.0  (pip install stellar-sdk)
- SOROBAN_CONTRACT_ID  env var must be set to the deployed contract address.
- SOROBAN_RPC_URL      defaults to https://soroban-testnet.stellar.org
- SOROBAN_NET_PHRASE   defaults to Testnet passphrase.

Flow
----
  1. Call build_<action>_xdr(wallet_address, ...) → simulates on RPC, returns
     unsigned transaction XDR.
  2. Pass XDR to WalletBridgeClient for Freighter signing.
  3. Call submit_signed_xdr(signed_xdr) → broadcasts on-chain.
"""

import os
from dataclasses import dataclass, field

from stellar_sdk import Network, SorobanServer, TransactionEnvelope, scval
from stellar_sdk.contract import ContractClient


# ── configuration ────────────────────────────────────────────────────────────

@dataclass
class StellarConfig:
    rpc_url: str
    network_passphrase: str
    contract_id: str

    @classmethod
    def from_env(cls) -> "StellarConfig":
        contract_id = os.environ.get("SOROBAN_CONTRACT_ID", "").strip()
        if not contract_id:
            raise EnvironmentError(
                "SOROBAN_CONTRACT_ID is not set.\n"
                "Deploy the contract first:\n"
                "  cd amongus_contract && cargo build --target wasm32-unknown-unknown --release\n"
                "  soroban contract deploy ...\n"
                "Then export SOROBAN_CONTRACT_ID=<deployed_address>"
            )
        rpc_url = os.environ.get(
            "SOROBAN_RPC_URL", "https://soroban-testnet.stellar.org"
        )
        passphrase = os.environ.get(
            "SOROBAN_NET_PHRASE", Network.TESTNET_NETWORK_PASSPHRASE
        )
        return cls(rpc_url=rpc_url, network_passphrase=passphrase, contract_id=contract_id)


# ── client ───────────────────────────────────────────────────────────────────

class StellarGameClient:
    """
    Builds Soroban contract-invocation XDRs by simulating transactions
    against the Soroban RPC and returns unsigned XDRs for wallet signing.
    """

    def __init__(self, config: StellarConfig):
        self.config = config
        self._contract = ContractClient(
            contract_id=config.contract_id,
            rpc_url=config.rpc_url,
            network_passphrase=config.network_passphrase,
        )

    # ── internal ─────────────────────────────────────────────────────────────

    def _build_xdr(self, function_name: str, params: list, source: str) -> str:
        """
        Simulate `function_name` with `params` from `source` account,
        assemble the footprint, and return the unsigned transaction XDR.
        """
        assembled = self._contract.invoke(
            function_name=function_name,
            parameters=params,
            source=source,
            signer=None,    # no signing here — wallet bridge signs
            simulate=True,
        )
        return assembled.to_xdr()

    @staticmethod
    def _proof_struct(proof_hash_hex: str, nullifier_hex: str, public_inputs_hex: list) -> object:
        """Encode a ProofInput { proof_hash, nullifier, public_inputs } struct."""
        return scval.to_struct({
            "proof_hash": scval.to_bytes(bytes.fromhex(proof_hash_hex)),
            "nullifier":  scval.to_bytes(bytes.fromhex(nullifier_hex)),
            "public_inputs": scval.to_vec(
                [scval.to_bytes(bytes.fromhex(h)) for h in public_inputs_hex]
            ),
        })

    # ── public builders ──────────────────────────────────────────────────────

    def build_join_xdr(
        self,
        player_address: str,
        color: str,
        name: str,
        player_hash_hex: str,
        role_hash_hex: str,
    ) -> str:
        """
        Build a join_game transaction XDR.

        player_hash_hex / role_hash_hex must be 64-char hex strings (32 bytes).
        """
        params = [
            scval.to_address(player_address),
            scval.to_symbol(color),
            scval.to_symbol(name[:10]),          # contract Symbol max 10 chars
            scval.to_bytes(bytes.fromhex(player_hash_hex)),
            scval.to_bytes(bytes.fromhex(role_hash_hex)),
        ]
        return self._build_xdr("join_game", params, player_address)

    def build_move_xdr(self, player_address: str, x: int, y: int) -> str:
        """Build a submit_move transaction XDR."""
        params = [
            scval.to_address(player_address),
            scval.to_uint32(x),
            scval.to_uint32(y),
        ]
        return self._build_xdr("submit_move", params, player_address)

    def build_task_xdr(
        self,
        player_address: str,
        proof_hash_hex: str,
        nullifier_hex: str,
        public_inputs_hex: list,
    ) -> str:
        """
        Build a submit_task_proof transaction XDR.
        Proof values come from nargo prove on noir_circuits/task_proof.
        """
        params = [
            scval.to_address(player_address),
            self._proof_struct(proof_hash_hex, nullifier_hex, public_inputs_hex),
        ]
        return self._build_xdr("submit_task_proof", params, player_address)

    def build_vote_xdr(
        self,
        voter_address: str,
        target_hash_hex: str,
        proof_hash_hex: str,
        nullifier_hex: str,
    ) -> str:
        """
        Build a submit_vote transaction XDR.
        Vote proof values come from nargo prove on noir_circuits/vote_proof.
        """
        vote_struct = scval.to_struct({
            "target_hash": scval.to_bytes(bytes.fromhex(target_hash_hex)),
            "proof_hash":  scval.to_bytes(bytes.fromhex(proof_hash_hex)),
            "nullifier":   scval.to_bytes(bytes.fromhex(nullifier_hex)),
        })
        params = [scval.to_address(voter_address), vote_struct]
        return self._build_xdr("submit_vote", params, voter_address)

    def build_kill_xdr(
        self,
        killer_address: str,
        victim_address: str,
        proof_hash_hex: str,
        nullifier_hex: str,
        public_inputs_hex: list,
    ) -> str:
        """
        Build a submit_kill_proof transaction XDR.
        Kill proof values come from nargo prove on noir_circuits/kill_proof.
        """
        params = [
            scval.to_address(killer_address),
            scval.to_address(victim_address),
            self._proof_struct(proof_hash_hex, nullifier_hex, public_inputs_hex),
        ]
        return self._build_xdr("submit_kill_proof", params, killer_address)

    def build_meeting_xdr(self, caller_address: str) -> str:
        """Build a start_meeting transaction XDR."""
        params = [scval.to_address(caller_address)]
        return self._build_xdr("start_meeting", params, caller_address)

    # ── submission ───────────────────────────────────────────────────────────

    def submit_signed_xdr(self, signed_xdr: str) -> dict:
        """
        Broadcast a wallet-signed transaction XDR to the Stellar network.
        Returns {"hash": ..., "status": ...} on success.
        """
        server = SorobanServer(self.config.rpc_url)
        tx = TransactionEnvelope.from_xdr(
            signed_xdr,
            network_passphrase=self.config.network_passphrase,
        )
        response = server.send_transaction(tx)
        status = (
            response.status.value
            if hasattr(response.status, "value")
            else str(response.status)
        )
        return {"hash": response.hash, "status": status}

    def get_game_state(self) -> dict:
        """Fetch current on-chain game state via get_game_state() read call."""
        assembled = self._contract.invoke(
            function_name="get_game_state",
            parameters=[],
            source="GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF",
            signer=None,
            simulate=True,
        )
        raw = assembled.result
        if raw is None:
            return {}
        return scval.to_native(raw)

