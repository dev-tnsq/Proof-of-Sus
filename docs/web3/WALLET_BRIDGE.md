# Wallet Connect for Pygame (Freighter via Local Bridge)

## Why a bridge is required

Freighter is a browser extension wallet. Pygame is a desktop Python app and cannot directly call browser extension APIs. The reliable architecture is:

- **Browser wallet context** signs,
- **local Node bridge** exposes simple HTTP endpoints,
- **Python game** calls the bridge.

## Bridge responsibilities

- Keep wallet session state (account, network, connection status).
- Return user account to Python client.
- Sign XDR payloads and return signed XDR.
- Optionally submit to RPC or return payload to Python submitter.

## Local API contract

### `GET /health`
- Returns `{ ok: true }`.

### `GET /wallet/account`
- Returns `{ connected: boolean, address?: string, network?: string }`.

### `POST /wallet/connect`
- Triggers wallet connection flow.
- Returns account metadata.

### `POST /wallet/session/update`
- Browser signer updates connected wallet address after successful connect.

### `POST /tx/request`
- Input: `{ playerId, action, xdr, networkPassphrase, metadata }`
- Returns `{ requestId, signerUrl }`.

### `GET /tx/request/:requestId`
- Poll pending request status (`pending`, `signed`, `rejected`).

### `POST /tx/request/:requestId/complete`
- Called by signer page after user approves in wallet.

### `POST /tx/request/:requestId/reject`
- Called by signer page on rejection.

### `POST /game/snapshot`
- Persists game snapshot for player.

### `GET /game/snapshot/:playerId`
- Restores last saved snapshot.

### `POST /wallet/sign`
- Input: `{ xdr: string, networkPassphrase: string }`
- Returns `{ signedXdr: string }`

### `POST /wallet/sign-and-submit` (optional)
- Input: `{ xdr: string, networkPassphrase: string, rpcUrl: string }`
- Returns tx hash and submission response.

## Python integration lifecycle

1. At Web3 mode startup, call `/health` and `/wallet/account`.
2. If disconnected, show modal in Pygame and call `/wallet/connect`.
3. For each on-chain action:
   - build tx XDR in Python,
   - request bridge signature,
   - submit via Stellar RPC,
   - map tx hash to pending local action.
4. Poll contract events and reconcile local predicted state.

## UX behavior in Pygame

- Connection state badge: `Disconnected / Connecting / Connected`.
- Blocking actions requiring signature should show “Awaiting wallet approval”.
- If signature rejected, revert local prediction and show toast.

## Security notes

- Bind bridge server to `127.0.0.1` only.
- Include CSRF token / nonce for POST endpoints.
- Never expose private keys through bridge API.

## Persistence

Bridge uses a local JSON database file:

- [wallet_bridge/bridge-db.json](wallet_bridge/bridge-db.json)

Stored objects include wallet session records, tx request queue, and game snapshots.
