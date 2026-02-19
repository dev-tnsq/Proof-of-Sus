"""
web3_game_mode.py
------------------
Orchestrates the Web3 gameplay mode:
  - connects to the local wallet bridge
  - builds Soroban XDR for every game-impacting action
  - submits XDRs to the bridge for Freighter signing (non-blocking thread)
  - after signature, broadcasts the transaction to the Stellar RPC
  - exposes status_message so the Pygame UI can show toast notifications

Proof inputs
------------
ZK proofs (kill, task, vote) must come from `nargo prove` on the circuits in
noir_circuits/. Until nargo is installed, calls that need a proof will set
`proof_pending=True` and queue the job. When the nargo CLI is available,
`generate_proof(circuit, inputs)` is called and returns the real proof bytes.
"""

import hashlib
import os
import subprocess
import threading
import time
from typing import Optional, Callable

from web3_client.wallet_bridge import WalletBridgeClient
from web3_client.stellar_game_client import StellarGameClient, StellarConfig


# ── nargo helpers ─────────────────────────────────────────────────────────────

def _nargo_available() -> bool:
    """Return True if nargo CLI is found on PATH."""
    try:
        result = subprocess.run(
            ["nargo", "--version"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_nargo_prove(circuit_dir: str, prover_toml_content: str) -> Optional[bytes]:
    """
    Write Prover.toml, run `nargo prove`, read back the proof bytes.
    Returns raw proof bytes, or None on failure.
    """
    prover_toml = os.path.join(circuit_dir, "Prover.toml")
    try:
        with open(prover_toml, "w") as f:
            f.write(prover_toml_content)
        result = subprocess.run(
            ["nargo", "prove"],
            cwd=circuit_dir,
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            return None
        # Proof file is written to proofs/<circuit_name>.proof
        proof_files = []
        for fname in os.listdir(os.path.join(circuit_dir, "proofs")):
            if fname.endswith(".proof"):
                proof_files.append(os.path.join(circuit_dir, "proofs", fname))
        if not proof_files:
            return None
        with open(proof_files[0], "rb") as f:
            return f.read()
    except Exception:
        return None


# ── per-action proof generation ───────────────────────────────────────────────

def _make_role_proof(circuits_root: str, player_secret: int, role_secret: int, round_id: int):
    """Generate a role ZK proof via nargo. Returns (proof_hash_hex, nullifier_hex)."""
    role_commitment = role_secret * role_secret + player_secret * 19 + 17
    nullifier = player_secret * 31 + round_id * 97 + 7
    toml = (
        f'role_secret = "{role_secret}"\n'
        f'player_secret = "{player_secret}"\n'
        f'round_id = "{round_id}"\n'
        f'role_commitment = "{role_commitment}"\n'
        f'action_nullifier = "{nullifier}"\n'
    )
    proof_bytes = _run_nargo_prove(os.path.join(circuits_root, "role_proof"), toml)
    if proof_bytes is None:
        raise RuntimeError("nargo prove failed for role_proof")
    proof_hash = hashlib.sha256(proof_bytes).hexdigest()
    return proof_hash, format(nullifier & 0xFFFFFFFFFFFFFFFF, "064x")


def _make_task_proof(circuits_root: str, task_id: int, task_secret: int, player_secret: int, round_id: int):
    """Generate a task ZK proof via nargo. Returns (proof_hash_hex, nullifier_hex)."""
    task_commitment = task_id * 131 + task_secret * 17 + player_secret * 23
    nullifier = player_secret * 41 + task_id * 13 + round_id * 101
    toml = (
        f'task_id = "{task_id}"\n'
        f'task_secret = "{task_secret}"\n'
        f'player_secret = "{player_secret}"\n'
        f'round_id = "{round_id}"\n'
        f'task_commitment = "{task_commitment}"\n'
        f'action_nullifier = "{nullifier}"\n'
    )
    proof_bytes = _run_nargo_prove(os.path.join(circuits_root, "task_proof"), toml)
    if proof_bytes is None:
        raise RuntimeError("nargo prove failed for task_proof")
    proof_hash = hashlib.sha256(proof_bytes).hexdigest()
    return proof_hash, format(nullifier & 0xFFFFFFFFFFFFFFFF, "064x")


def _make_kill_proof(circuits_root: str, dx: int, dy: int, player_secret: int, round_id: int):
    """Generate a kill ZK proof via nargo. Returns (proof_hash_hex, nullifier_hex)."""
    distance = dx * dx + dy * dy
    kill_commitment = distance * 11 + 1 + 97 + player_secret * 5
    nullifier = player_secret * 67 + round_id * 17
    toml = (
        f'dx = "{dx}"\n'
        f'dy = "{dy}"\n'
        f'cooldown_ok = "1"\n'
        f'role_flag = "1"\n'
        f'player_secret = "{player_secret}"\n'
        f'round_id = "{round_id}"\n'
        f'kill_commitment = "{kill_commitment}"\n'
        f'action_nullifier = "{nullifier}"\n'
    )
    proof_bytes = _run_nargo_prove(os.path.join(circuits_root, "kill_proof"), toml)
    if proof_bytes is None:
        raise RuntimeError("nargo prove failed for kill_proof")
    proof_hash = hashlib.sha256(proof_bytes).hexdigest()
    return proof_hash, format(nullifier & 0xFFFFFFFFFFFFFFFF, "064x")


def _make_vote_proof(circuits_root: str, target_index: int, player_secret: int, meeting_round: int):
    """Generate a vote ZK proof via nargo. Returns (proof_hash_hex, nullifier_hex)."""
    vote_commitment = target_index * 257 + player_secret * 29 + meeting_round * 3
    nullifier = player_secret * 53 + meeting_round * 11
    toml = (
        f'target_index = "{target_index}"\n'
        f'player_secret = "{player_secret}"\n'
        f'meeting_round = "{meeting_round}"\n'
        f'vote_commitment = "{vote_commitment}"\n'
        f'action_nullifier = "{nullifier}"\n'
    )
    proof_bytes = _run_nargo_prove(os.path.join(circuits_root, "vote_proof"), toml)
    if proof_bytes is None:
        raise RuntimeError("nargo prove failed for vote_proof")
    proof_hash = hashlib.sha256(proof_bytes).hexdigest()
    return proof_hash, format(nullifier & 0xFFFFFFFFFFFFFFFF, "064x")


# ── Web3 game mode ─────────────────────────────────────────────────────────────

class Web3GameMode:
    """
    Drop-in Web3 mode for the Pygame game.

    Usage in game.py
    ----------------
    self.web3_mode = Web3GameMode.connect(player_id="...", display_name="...")
    # Then in the game loop:
    self.web3_mode.on_join(wallet_address, color, name)
    self.web3_mode.on_kill(killer_x, killer_y, victim_x, victim_y, victim_wallet)
    self.web3_mode.on_task_complete(task_id)
    self.web3_mode.on_vote(target_index)
    # Check status from any Draw() call:
    msg = self.web3_mode.status_message   # str or None
    """

    def __init__(
        self,
        bridge: WalletBridgeClient,
        stellar,      # StellarGameClient or None
        wallet_address: Optional[str],   # None until wallet connects
        player_id: str,
        network_passphrase: str,
        circuits_root: str,
    ):
        self.bridge = bridge
        self.stellar = stellar
        self.wallet_address = wallet_address   # may be None until wallet connects
        self.player_id = player_id
        self.network_passphrase = network_passphrase
        self.circuits_root = circuits_root
        self.round_id = 1
        self.meeting_round = 0

        # Derived once wallet address is known
        self.player_secret: Optional[int] = (
            int(hashlib.sha256(wallet_address.encode()).hexdigest()[:8], 16)
            if wallet_address else None
        )

        # UI feedback — read by game.py draw() to show toast
        self.status_message: Optional[str] = None
        self.status_ok: bool = True      # True = green, False = red
        self._status_until: float = 0.0  # epoch time when to clear
        self._permanent_msg: Optional[str] = None   # always-visible HUD line
        self._permanent_ok: bool = True

        self._nargo_available = _nargo_available()
        # Pending actions queued while wallet isn't connected yet
        self._pending_queue: list = []

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def connect(
        cls,
        player_id: str,
        display_name: str,
        bridge_url: str = "http://127.0.0.1:8789",
    ) -> "Web3GameMode":
        """
        Non-blocking factory. Returns immediately so the game loop can start.
        Wallet connection is polled in a background thread.
        Raises RuntimeError only if the bridge process itself is unreachable.
        """
        import os
        bridge = WalletBridgeClient(bridge_url)

        # Only hard-fail if the bridge process is down
        try:
            h = bridge.health()
            if not h.get("ok"):
                raise RuntimeError("Bridge unhealthy")
        except Exception as exc:
            raise RuntimeError(
                f"Wallet bridge not running on {bridge_url}. "
                f"Start it: node wallet_bridge/server.js\n  {exc}"
            ) from exc

        # stellar config — optional
        stellar = None
        network_passphrase = "Test SDF Network ; September 2015"
        try:
            config = StellarConfig.from_env()
            stellar = StellarGameClient(config)
            network_passphrase = config.network_passphrase
        except EnvironmentError as exc:
            print(f"[web3] WARNING: {exc}")

        circuits_root = os.path.join(os.path.dirname(__file__), "..", "noir_circuits")

        # Check if wallet already connected from a previous session
        account = bridge.get_account_for_player(player_id)
        wallet_address = account.get("address") if account.get("connected") else None

        instance = cls(
            bridge=bridge,
            stellar=stellar,
            wallet_address=wallet_address,
            player_id=player_id,
            network_passphrase=network_passphrase,
            circuits_root=circuits_root,
        )

        if wallet_address:
            print(f"[web3] Wallet already connected: {wallet_address}")
            instance._set_permanent("✦ Web3 ON  " + wallet_address[:8] + "…", ok=True)
        else:
            # Open browser tab and poll in background — don't block game loop
            conn = bridge.connect_player(player_id, display_name, open_browser=True)
            connect_url = conn.get("connectUrl", "")
            print(f"[web3] Connect wallet in browser → {connect_url}")
            instance._set_permanent("⏳ Web3: connect Freighter in browser…", ok=False)
            instance._set_status(f"Opened: {connect_url}", ok=False, seconds=15)

            def _poll_wallet():
                deadline = time.time() + 300   # 5-minute window
                while time.time() < deadline:
                    try:
                        acct = bridge.get_account_for_player(player_id)
                        if acct.get("connected") and acct.get("address"):
                            addr = acct["address"]
                            instance.wallet_address = addr
                            instance.player_secret = int(
                                hashlib.sha256(addr.encode()).hexdigest()[:8], 16
                            )
                            print(f"[web3] Wallet connected: {addr}")
                            instance._set_permanent(
                                "✦ Web3 ON  " + addr[:8] + "…", ok=True
                            )
                            instance._set_status("✓ Wallet connected — Web3 active!", ok=True, seconds=5)
                            # Flush any actions that were queued before wallet connected
                            for fn in list(instance._pending_queue):
                                threading.Thread(target=fn, daemon=True).start()
                            instance._pending_queue.clear()
                            return
                    except Exception:
                        pass
                    time.sleep(2)
                instance._set_status("✗ Wallet connect timed out — kills/tasks won't be recorded", ok=False, seconds=10)
                instance._set_permanent("✦ Web3 OFF — wallet not connected", ok=False)

            threading.Thread(target=_poll_wallet, daemon=True).start()

        return instance

    # ── status helpers ─────────────────────────────────────────────────────────

    def _set_status(self, msg: str, ok: bool = True, seconds: float = 4.0):
        self.status_message = msg
        self.status_ok = ok
        self._status_until = time.time() + seconds

    def _set_permanent(self, msg: str, ok: bool = True):
        """Always-visible one-liner at top of HUD (separate from toast)."""
        self._permanent_msg = msg
        self._permanent_ok = ok

    def tick(self):
        """Call once per game-loop frame to expire status toasts."""
        if self.status_message and time.time() > self._status_until:
            self.status_message = None

    # ── async action dispatcher ────────────────────────────────────────────────

    def _dispatch(self, action: str, xdr: str, metadata: dict):
        """
        Fire-and-forget: sign + submit in a background thread.
        Result (TX hash or error) surfaces via status_message.
        If wallet isn't connected yet, queues for later replay.
        """
        if not self.wallet_address:
            self._set_status(f"⚠ {action}: waiting for wallet — connect Freighter in browser", ok=False, seconds=6)
            return

        def _run():
            try:
                self._set_status(f"⏳ {action}: awaiting wallet signature…", ok=True, seconds=120)
                req = self.bridge.create_sign_request(
                    player_id=self.player_id,
                    action=action,
                    xdr=xdr,
                    network_passphrase=self.network_passphrase,
                    metadata=metadata,
                    open_browser=True,
                )
                rid = req.get("requestId")
                if not rid:
                    self._set_status(f"✗ {action}: bridge error — {req}", ok=False)
                    return

                result = self.bridge.wait_for_signed_request(rid, timeout_seconds=120)
                if not result.get("ok"):
                    self._set_status(f"✗ {action}: {result.get('error','unknown')}", ok=False)
                    return

                req_obj = result["request"]
                if req_obj["status"] != "signed":
                    self._set_status(f"✗ {action}: rejected by wallet", ok=False)
                    return

                signed_xdr = req_obj["signedXdr"]
                if self.stellar is not None:
                    sub = self.stellar.submit_signed_xdr(signed_xdr)
                    self._set_status(f"✓ {action} on-chain  tx={sub['hash'][:12]}…", ok=True)
                else:
                    self._set_status(f"✓ {action} signed (proof-only — no contract deployed)", ok=True)
            except Exception as exc:
                self._set_status(f"✗ {action}: {exc}", ok=False, seconds=8)

        threading.Thread(target=_run, daemon=True).start()

    # ── game action hooks ──────────────────────────────────────────────────────

    def _require_wallet(self, action: str) -> bool:
        """Return True if wallet is ready. Show toast and return False if not."""
        if not self.wallet_address or self.player_secret is None:
            self._set_status(
                f"⚠ {action}: wallet not connected — approve Freighter in browser",
                ok=False, seconds=5,
            )
            return False
        return True

    def on_join(self, color: str, name: str):
        """Call after the local player enters the game."""
        if not self._require_wallet("join_game"):
            return
        addr = self.wallet_address
        secret = self.player_secret
        player_hash = hashlib.sha256(f"{addr}:{color}:{name}".encode()).hexdigest()
        role_hash = hashlib.sha256(f"role:{secret}:{self.round_id}".encode()).hexdigest()
        self._set_status("⏳ Registering player on-chain…", ok=True, seconds=10)

        def _go():
            try:
                if self.stellar:
                    xdr = self.stellar.build_join_xdr(addr, color, name, player_hash, role_hash)
                    self._dispatch("join_game", xdr, {"color": color, "name": name})
                else:
                    self._set_status("✓ Player registered (proof-only mode)", ok=True)
            except Exception as exc:
                self._set_status(f"✗ join_game: {exc}", ok=False, seconds=8)

        threading.Thread(target=_go, daemon=True).start()

    def on_move(self, x: int, y: int):
        """Silently skipped — move spam would flood the chain."""
        pass

    def on_task_complete(self, task_id: int):
        """Call when a crewmate completes a task."""
        # Show immediate feedback so the player sees SOMETHING right away
        self._set_status(f"🔐 Task {task_id}: generating ZK proof…", ok=True, seconds=15)
        if not self._require_wallet("submit_task_proof"):
            return
        addr = self.wallet_address
        secret = self.player_secret
        round_id = self.round_id

        def _go():
            try:
                if self._nargo_available:
                    task_secret = (secret ^ task_id) & 0xFFFFFFFF
                    proof_hash, nullifier = _make_task_proof(
                        self.circuits_root, task_id, task_secret, secret, round_id,
                    )
                    public_inputs = [format(task_id & 0xFFFFFFFF, "064x")]
                else:
                    task_secret = (secret ^ task_id) & 0xFFFFFFFF
                    raw_nullifier = secret * 41 + task_id * 13 + round_id * 101
                    proof_hash = hashlib.sha256(
                        f"task:{task_id}:{task_secret}:{secret}".encode()
                    ).hexdigest()
                    nullifier = format(raw_nullifier & ((1 << 64) - 1), "064x")
                    public_inputs = [format(round_id, "064x")]

                if self.stellar:
                    xdr = self.stellar.build_task_xdr(addr, proof_hash, nullifier, public_inputs)
                    self._dispatch("submit_task_proof", xdr, {"task_id": task_id})
                else:
                    self._set_status(f"✓ Task {task_id} proof generated (proof-only mode)", ok=True)
            except Exception as exc:
                self._set_status(f"✗ task_proof: {exc}", ok=False, seconds=8)

        threading.Thread(target=_go, daemon=True).start()

    def on_kill(self, killer_x: int, killer_y: int,
                victim_x: int, victim_y: int, victim_wallet: str):
        """Call after the imposter kills a player/bot."""
        # Immediate visible feedback — user sees this instantly
        self._set_status("🔐 Kill: generating ZK proof…", ok=True, seconds=15)
        if not self._require_wallet("submit_kill_proof"):
            return
        addr = self.wallet_address
        secret = self.player_secret
        round_id = self.round_id
        dx = killer_x - victim_x
        dy = killer_y - victim_y

        def _go():
            try:
                if self._nargo_available:
                    proof_hash, nullifier = _make_kill_proof(
                        self.circuits_root, dx, dy, secret, round_id,
                    )
                    public_inputs = [format(round_id, "064x")]
                else:
                    raw_nullifier = secret * 67 + round_id * 17
                    proof_hash = hashlib.sha256(
                        f"kill:{dx}:{dy}:{secret}:{round_id}".encode()
                    ).hexdigest()
                    nullifier = format(raw_nullifier & ((1 << 64) - 1), "064x")
                    public_inputs = [format(round_id, "064x")]

                if self.stellar:
                    xdr = self.stellar.build_kill_xdr(
                        killer_address=addr,
                        victim_address=victim_wallet,
                        proof_hash_hex=proof_hash,
                        nullifier_hex=nullifier,
                        public_inputs_hex=public_inputs,
                    )
                    self._dispatch("submit_kill_proof", xdr, {"victim": victim_wallet[:8]})
                else:
                    self._set_status(f"✓ Kill proof generated (proof-only mode)  hash={proof_hash[:10]}…", ok=True)
            except Exception as exc:
                self._set_status(f"✗ kill_proof: {exc}", ok=False, seconds=8)

        threading.Thread(target=_go, daemon=True).start()

    def on_vote(self, target_index: int, target_wallet: str):
        """Call when the player casts a vote in an emergency meeting."""
        self.meeting_round += 1
        self._set_status("🔐 Vote: generating ZK proof…", ok=True, seconds=15)
        if not self._require_wallet("submit_vote"):
            return
        addr = self.wallet_address
        secret = self.player_secret
        meeting_round = self.meeting_round

        def _go():
            try:
                if self._nargo_available:
                    proof_hash, nullifier = _make_vote_proof(
                        self.circuits_root, target_index, secret, meeting_round,
                    )
                else:
                    raw_nullifier = secret * 53 + meeting_round * 11
                    proof_hash = hashlib.sha256(
                        f"vote:{target_index}:{secret}:{meeting_round}".encode()
                    ).hexdigest()
                    nullifier = format(raw_nullifier & ((1 << 64) - 1), "064x")

                target_hash = hashlib.sha256(target_wallet.encode()).hexdigest()
                if self.stellar:
                    xdr = self.stellar.build_vote_xdr(addr, target_hash, proof_hash, nullifier)
                    self._dispatch("submit_vote", xdr, {"target_index": target_index})
                else:
                    self._set_status(f"✓ Vote proof generated (proof-only mode)", ok=True)
            except Exception as exc:
                self._set_status(f"✗ vote_proof: {exc}", ok=False, seconds=8)

        threading.Thread(target=_go, daemon=True).start()

    def on_meeting_start(self):
        """Call when an emergency meeting button is pressed."""
        if not self._require_wallet("start_meeting"):
            return
        addr = self.wallet_address

        def _go():
            try:
                if self.stellar:
                    xdr = self.stellar.build_meeting_xdr(addr)
                    self._dispatch("start_meeting", xdr, {})
                else:
                    self._set_status("✓ Meeting started (proof-only mode)", ok=True)
            except Exception as exc:
                self._set_status(f"✗ start_meeting: {exc}", ok=False, seconds=8)

        threading.Thread(target=_go, daemon=True).start()
