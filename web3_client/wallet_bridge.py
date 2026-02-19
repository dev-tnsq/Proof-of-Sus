import json
import time
import webbrowser
from urllib import request, error


class WalletBridgeClient:
    def __init__(self, base_url="http://127.0.0.1:8787"):
        self.base_url = base_url.rstrip("/")

    def _get(self, path):
        url = f"{self.base_url}{path}"
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path, payload):
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def health(self):
        return self._get("/health")

    def get_account(self):
        return self._get("/wallet/account")

    def get_account_for_player(self, player_id):
        return self._get(f"/wallet/account?playerId={player_id}")

    def connect(self):
        return self._post("/wallet/connect", {})

    def connect_player(self, player_id, display_name=None, open_browser=True):
        payload = {"playerId": player_id, "displayName": display_name}
        response = self._post("/wallet/connect", payload)
        if open_browser and response.get("connectUrl"):
            webbrowser.open(response["connectUrl"])
        return response

    def sign_xdr(self, xdr, network_passphrase):
        return self._post(
            "/wallet/sign",
            {
                "xdr": xdr,
                "networkPassphrase": network_passphrase,
            },
        )

    def create_sign_request(self, player_id, action, xdr, network_passphrase, metadata=None, open_browser=True):
        response = self._post(
            "/tx/request",
            {
                "playerId": player_id,
                "action": action,
                "xdr": xdr,
                "networkPassphrase": network_passphrase,
                "metadata": metadata or {},
            },
        )
        if open_browser and response.get("signerUrl"):
            webbrowser.open(response["signerUrl"])
        return response

    def get_sign_request(self, request_id):
        return self._get(f"/tx/request/{request_id}")

    def wait_for_signed_request(self, request_id, timeout_seconds=120, poll_seconds=1.5):
        started = time.time()
        while time.time() - started <= timeout_seconds:
            payload = self.get_sign_request(request_id)
            if not payload.get("ok"):
                return payload
            status = payload["request"].get("status")
            if status in {"signed", "rejected"}:
                return payload
            time.sleep(poll_seconds)
        return {"ok": False, "error": "sign_request_timeout", "requestId": request_id}

    def save_snapshot(self, player_id, snapshot):
        return self._post(
            "/game/snapshot",
            {
                "playerId": player_id,
                "snapshot": snapshot,
            },
        )

    def load_snapshot(self, player_id):
        return self._get(f"/game/snapshot/{player_id}")

    def sign_and_submit(self, xdr, network_passphrase, rpc_url):
        return self._post(
            "/wallet/sign-and-submit",
            {
                "xdr": xdr,
                "networkPassphrase": network_passphrase,
                "rpcUrl": rpc_url,
            },
        )

    def safe_connect(self):
        try:
            health = self.health()
            if not health.get("ok", False):
                return {"ok": False, "reason": "bridge_not_healthy"}
            return self.connect()
        except error.URLError:
            return {"ok": False, "reason": "bridge_unreachable"}
