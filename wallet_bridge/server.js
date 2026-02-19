'use strict';

const express = require('express');
const cors = require('cors');
const { v4: uuidv4 } = require('uuid');
const path = require('path');
const fs = require('fs');

const PORT = 8789;
const HOST = '127.0.0.1';
const DB_PATH = path.join(__dirname, 'bridge-db.json');

// ---------- JSON-file DB helpers ----------

function readDb() {
  try {
    const raw = fs.readFileSync(DB_PATH, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return { sessions: {}, requests: {}, snapshots: {} };
  }
}

function writeDb(data) {
  fs.writeFileSync(DB_PATH, JSON.stringify(data, null, 2), 'utf-8');
}

function ensureDb() {
  if (!fs.existsSync(DB_PATH)) {
    writeDb({ sessions: {}, requests: {}, snapshots: {} });
    console.log('[bridge] Created fresh bridge-db.json');
  }
}

// ---------- Express app ----------

const app = express();

// Allow the browser signer page (same origin) and Python urllib/requests
app.use(cors({ origin: '*' }));
app.use(express.json());

// Serve signer.html + signer.js from ./public
app.use(express.static(path.join(__dirname, 'public')));

ensureDb();

// ----------------------------------------------------------------
// GET /health
// ----------------------------------------------------------------
app.get('/health', (_req, res) => {
  res.json({ ok: true, ts: Date.now() });
});

// ----------------------------------------------------------------
// GET /wallet/account?playerId=
// ----------------------------------------------------------------
app.get('/wallet/account', (req, res) => {
  const playerId = req.query.playerId || '__default__';
  const db = readDb();
  const session = db.sessions[playerId];
  if (session && session.address) {
    return res.json({
      ok: true,
      connected: true,
      address: session.address,
      network: session.network || null,
      playerId,
    });
  }
  res.json({ ok: true, connected: false, playerId });
});

// ----------------------------------------------------------------
// POST /wallet/connect   { playerId?, displayName? }
// Returns a connectUrl the Python client opens in the browser
// ----------------------------------------------------------------
app.post('/wallet/connect', (req, res) => {
  const { playerId, displayName } = req.body || {};
  const key = playerId || '__default__';

  const connectUrl =
    `http://${HOST}:${PORT}/signer.html` +
    `?action=connect` +
    `&playerId=${encodeURIComponent(key)}` +
    `&displayName=${encodeURIComponent(displayName || '')}`;

  const db = readDb();
  if (!db.sessions[key]) {
    db.sessions[key] = {
      playerId: key,
      displayName: displayName || null,
      address: null,
      network: null,
      connectedAt: null,
    };
    writeDb(db);
  }

  res.json({ ok: true, connectUrl, playerId: key });
});

// ----------------------------------------------------------------
// POST /wallet/session/update   { playerId, address, network }
// Called by the browser signer page after a wallet connects
// ----------------------------------------------------------------
app.post('/wallet/session/update', (req, res) => {
  const { playerId, address, network } = req.body || {};
  if (!address) return res.status(400).json({ ok: false, error: 'address_required' });

  const key = playerId || '__default__';
  const db = readDb();
  db.sessions[key] = {
    ...(db.sessions[key] || {}),
    playerId: key,
    address,
    network: network || null,
    connectedAt: Date.now(),
  };
  writeDb(db);

  console.log(`[bridge] Session updated — player=${key} address=${address}`);
  res.json({ ok: true });
});

// ----------------------------------------------------------------
// POST /tx/request   { playerId, action, xdr, networkPassphrase, metadata? }
// Creates a signing request + returns a signerUrl to open in browser
// ----------------------------------------------------------------
app.post('/tx/request', (req, res) => {
  const { playerId, action, xdr, networkPassphrase, metadata } = req.body || {};
  if (!xdr) return res.status(400).json({ ok: false, error: 'xdr_required' });

  const requestId = uuidv4();
  const signerUrl = `http://${HOST}:${PORT}/signer.html?requestId=${requestId}`;

  const db = readDb();
  db.requests[requestId] = {
    requestId,
    playerId: playerId || '__default__',
    action: action || 'unknown',
    xdr,
    networkPassphrase: networkPassphrase || 'Test SDF Network ; September 2015',
    metadata: metadata || {},
    status: 'pending',
    signedXdr: null,
    walletAddress: null,
    error: null,
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
  writeDb(db);

  console.log(`[bridge] Sign request created — id=${requestId} action=${action || 'unknown'}`);
  res.json({ ok: true, requestId, signerUrl });
});

// ----------------------------------------------------------------
// GET /tx/request/:id
// ----------------------------------------------------------------
app.get('/tx/request/:id', (req, res) => {
  const db = readDb();
  const request = db.requests[req.params.id];
  if (!request) return res.status(404).json({ ok: false, error: 'request_not_found' });
  res.json({ ok: true, request });
});

// ----------------------------------------------------------------
// POST /tx/request/:id/complete   { signedXdr, walletAddress }
// Called by the browser signer page after the user approves
// ----------------------------------------------------------------
app.post('/tx/request/:id/complete', (req, res) => {
  const { signedXdr, walletAddress } = req.body || {};
  if (!signedXdr) return res.status(400).json({ ok: false, error: 'signedXdr_required' });

  const db = readDb();
  const request = db.requests[req.params.id];
  if (!request) return res.status(404).json({ ok: false, error: 'request_not_found' });

  request.status = 'signed';
  request.signedXdr = signedXdr;
  request.walletAddress = walletAddress || null;
  request.updatedAt = Date.now();
  writeDb(db);

  console.log(`[bridge] Request signed — id=${req.params.id}`);
  res.json({ ok: true });
});

// ----------------------------------------------------------------
// POST /tx/request/:id/reject   { reason? }
// Called by the browser signer page on user rejection
// ----------------------------------------------------------------
app.post('/tx/request/:id/reject', (req, res) => {
  const { reason } = req.body || {};

  const db = readDb();
  const request = db.requests[req.params.id];
  if (!request) return res.status(404).json({ ok: false, error: 'request_not_found' });

  request.status = 'rejected';
  request.error = reason || 'user_rejected';
  request.updatedAt = Date.now();
  writeDb(db);

  console.log(`[bridge] Request rejected — id=${req.params.id}`);
  res.json({ ok: true });
});

// ----------------------------------------------------------------
// POST /game/snapshot   { playerId, snapshot }
// ----------------------------------------------------------------
app.post('/game/snapshot', (req, res) => {
  const { playerId, snapshot } = req.body || {};
  if (!playerId) return res.status(400).json({ ok: false, error: 'playerId_required' });

  const db = readDb();
  db.snapshots[playerId] = { playerId, snapshot, savedAt: Date.now() };
  writeDb(db);

  res.json({ ok: true });
});

// ----------------------------------------------------------------
// GET /game/snapshot/:playerId
// ----------------------------------------------------------------
app.get('/game/snapshot/:playerId', (req, res) => {
  const db = readDb();
  const snap = db.snapshots[req.params.playerId];
  if (!snap) return res.json({ ok: true, found: false, snapshot: null });
  res.json({ ok: true, found: true, ...snap });
});

// ----------------------------------------------------------------
// POST /wallet/sign   { xdr, networkPassphrase }
// Convenience: creates a sign request and returns the signerUrl.
// Python must open the url and poll tx/request/:id as usual.
// ----------------------------------------------------------------
app.post('/wallet/sign', (req, res) => {
  const { xdr, networkPassphrase } = req.body || {};
  if (!xdr) return res.status(400).json({ ok: false, error: 'xdr_required' });

  const requestId = uuidv4();
  const signerUrl = `http://${HOST}:${PORT}/signer.html?requestId=${requestId}`;

  const db = readDb();
  db.requests[requestId] = {
    requestId,
    playerId: '__direct__',
    action: 'sign',
    xdr,
    networkPassphrase: networkPassphrase || 'Test SDF Network ; September 2015',
    metadata: {},
    status: 'pending',
    signedXdr: null,
    walletAddress: null,
    error: null,
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
  writeDb(db);

  res.json({ ok: true, requestId, signerUrl });
});

// ----------------------------------------------------------------
// POST /wallet/sign-and-submit   { xdr, networkPassphrase, rpcUrl }
// Submits an already-signed XDR to the Soroban RPC node.
// ----------------------------------------------------------------
app.post('/wallet/sign-and-submit', async (req, res) => {
  const { xdr, networkPassphrase, rpcUrl } = req.body || {};
  if (!xdr || !rpcUrl) {
    return res.status(400).json({ ok: false, error: 'xdr_and_rpcUrl_required' });
  }

  try {
    const rpcBody = JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'sendTransaction',
      params: { transaction: xdr },
    });

    const response = await fetch(rpcUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: rpcBody,
    });

    const result = await response.json();
    console.log(`[bridge] Submitted to RPC — status=${result?.result?.status}`);
    res.json({ ok: true, result });
  } catch (err) {
    console.error(`[bridge] RPC submit error:`, err.message);
    res.status(500).json({ ok: false, error: err.message });
  }
});

// ----------------------------------------------------------------
app.listen(PORT, HOST, () => {
  console.log(`\n  Wallet bridge listening on http://${HOST}:${PORT}`);
  console.log(`  Signer UI  →  http://${HOST}:${PORT}/signer.html`);
  console.log(`  DB file    →  ${DB_PATH}\n`);
});
