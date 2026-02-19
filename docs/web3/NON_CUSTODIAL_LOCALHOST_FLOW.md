# Non-Custodial Localhost Flow (Pygame + Browser Wallet)

## Goal

Provide web-like wallet UX for desktop Pygame without custodial key handling.

## Final Signing Sequence

1. Pygame creates unsigned XDR for a Soroban action.
2. Pygame calls local bridge `POST /tx/request`.
3. Bridge stores request in local DB and returns `signerUrl`.
4. Pygame opens the browser signer page.
5. User connects Freighter and approves signature.
6. Browser posts signed XDR to bridge `POST /tx/request/:id/complete`.
7. Pygame polls `GET /tx/request/:id` until status is `signed`.
8. Pygame submits signed XDR to Stellar RPC.

## Why this is non-custodial

- Private key remains inside wallet extension.
- Bridge stores metadata and signed artifacts only.
- Pygame never sees seed phrase or private key.

## Local DB usage

Bridge stores:

- wallet sessions by player,
- pending/rejected/signed tx requests,
- game snapshots for resume/recovery UX.

Database file:

- [wallet_bridge/bridge-db.json](wallet_bridge/bridge-db.json)

## Security notes

- Bridge listens only on `127.0.0.1`.
- Never expose bridge port publicly.
- Add request nonce/auth token before production release.
