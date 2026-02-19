"""
Bridge integration test — run with: python3 scripts/test_bridge.py
Requires the wallet bridge to be running on localhost:8789.
"""
import sys, threading, time, urllib.request, json

sys.path.insert(0, __file__.rsplit("/scripts", 1)[0])
from web3_client.wallet_bridge import WalletBridgeClient

c = WalletBridgeClient()

print("=== Bridge Integration Test ===\n")

# 1 — health
h = c.health()
assert h.get("ok"), f"health failed: {h}"
print("✓ /health")

# 2 — connect
conn = c.connect_player("py-test", "PythonTest", open_browser=False)
assert conn.get("ok") and conn.get("connectUrl"), f"connect failed: {conn}"
print("✓ POST /wallet/connect")

# 3 — account (no wallet linked yet)
acc = c.get_account_for_player("py-test")
assert acc.get("ok"), f"account failed: {acc}"
print("✓ GET /wallet/account")

# 4 — create sign request
req = c.create_sign_request(
    "py-test", "join_game", "AAAADEMOEXDR",
    "Test SDF Network ; September 2015",
    {"phase": "lobby"},
    open_browser=False,
)
assert req.get("ok") and req.get("requestId"), f"tx/request failed: {req}"
rid = req["requestId"]
print(f"✓ POST /tx/request  id={rid}")

# 5 — poll (should be pending)
poll = c.get_sign_request(rid)
assert poll.get("ok") and poll["request"]["status"] == "pending"
print("✓ GET /tx/request/:id  status=pending")

# 6 — simulate browser completing the sign in background after 1.5 s
def _complete():
    time.sleep(1.5)
    body = json.dumps({"signedXdr": "AAAA_SIGNED_XDR", "walletAddress": "GTEST123"}).encode()
    r = urllib.request.Request(
        f"http://127.0.0.1:8789/tx/request/{rid}/complete",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(r)

threading.Thread(target=_complete, daemon=True).start()

# 7 — wait_for_signed_request (poll loop)
result = c.wait_for_signed_request(rid, timeout_seconds=10, poll_seconds=0.5)
assert result.get("ok"), f"wait failed: {result}"
assert result["request"]["status"] == "signed"
assert result["request"]["signedXdr"] == "AAAA_SIGNED_XDR"
print("✓ wait_for_signed_request  status=signed  signedXdr verified")

# 8 — snapshot round-trip
c.save_snapshot("py-test", {"phase": "playing", "tasks": 3})
snap = c.load_snapshot("py-test")
assert snap.get("ok") and snap.get("found")
assert snap["snapshot"]["tasks"] == 3
print("✓ /game/snapshot  save + load")

print("\n=== All tests passed ✓ ===")
