from web3_client.wallet_bridge import WalletBridgeClient


class Web3GameplayBridge:
    def __init__(self, player_id, display_name, bridge_url="http://127.0.0.1:8789"):
        self.player_id = player_id
        self.display_name = display_name
        self.wallet = WalletBridgeClient(bridge_url)

    def ensure_wallet_connected(self):
        account = self.wallet.get_account_for_player(self.player_id)
        if account.get("connected"):
            return account
        self.wallet.connect_player(self.player_id, self.display_name, open_browser=True)
        return self.wallet.get_account_for_player(self.player_id)

    def sign_action_xdr(self, action, xdr, network_passphrase, metadata=None, timeout_seconds=120):
        req = self.wallet.create_sign_request(
            player_id=self.player_id,
            action=action,
            xdr=xdr,
            network_passphrase=network_passphrase,
            metadata=metadata or {},
            open_browser=True,
        )
        request_id = req.get("requestId")
        if not request_id:
            return {"ok": False, "error": "failed_to_create_sign_request", "raw": req}

        result = self.wallet.wait_for_signed_request(request_id, timeout_seconds=timeout_seconds)
        if not result.get("ok"):
            return result

        request_obj = result.get("request", {})
        if request_obj.get("status") != "signed":
            return {"ok": False, "error": request_obj.get("error", "not_signed"), "request": request_obj}

        return {
            "ok": True,
            "signedXdr": request_obj.get("signedXdr"),
            "walletAddress": request_obj.get("walletAddress"),
            "request": request_obj,
        }

    def save_local_progress(self, snapshot):
        return self.wallet.save_snapshot(self.player_id, snapshot)

    def load_local_progress(self):
        return self.wallet.load_snapshot(self.player_id)
