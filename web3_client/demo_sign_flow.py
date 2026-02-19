from web3_client.integration_flow import Web3GameplayBridge


def main():
    player_id = "demo-player"
    display_name = "Demo"
    bridge = Web3GameplayBridge(player_id=player_id, display_name=display_name)

    print("Checking wallet session...")
    account = bridge.ensure_wallet_connected()
    print("Session:", account)

    print("Creating sign request and opening signer in browser...")
    result = bridge.sign_action_xdr(
        action="join_game",
        xdr="AAAADEMOXDR",
        network_passphrase="Test SDF Network ; September 2015",
        metadata={"phase": "lobby"},
        timeout_seconds=180,
    )

    print("Sign result:", result)

    print("Saving game snapshot...")
    saved = bridge.save_local_progress({"phase": "lobby", "player": player_id})
    print("Snapshot save response:", saved)

    loaded = bridge.load_local_progress()
    print("Snapshot load response:", loaded)


if __name__ == "__main__":
    main()
