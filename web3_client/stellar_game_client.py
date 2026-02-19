from dataclasses import dataclass


@dataclass
class StellarConfig:
    rpc_url: str
    network_passphrase: str
    contract_id: str


class StellarGameClient:
    def __init__(self, config: StellarConfig):
        self.config = config

    def build_join_tx(self, player_address, color, name, role_hash_hex):
        return {
            "method": "join_game",
            "args": [player_address, color, name, role_hash_hex],
        }

    def build_move_tx(self, player_address, x, y):
        return {
            "method": "submit_move",
            "args": [player_address, x, y],
        }

    def build_vote_tx(self, player_address, target_address, proof_hash_hex):
        return {
            "method": "submit_vote",
            "args": [player_address, target_address, proof_hash_hex],
        }

    def build_task_tx(self, player_address):
        return {
            "method": "increment_tasks",
            "args": [player_address],
        }

    def submit_signed_xdr(self, signed_xdr):
        return {
            "submitted": True,
            "signed_xdr": signed_xdr,
            "rpc_url": self.config.rpc_url,
        }
