/**
 * signer.js — Freighter wallet integration for the local signing bridge.
 *
 * Loaded as an ES module from signer.html.
 * Uses @stellar/freighter-api v6.x via esm.sh CDN.
 */

import {
  isConnected,
  requestAccess,
  signTransaction,
} from 'https://esm.sh/@stellar/freighter-api@6.0.1';

// ── helpers ──────────────────────────────────────────────────────────────────

const BRIDGE_ORIGIN = window.location.origin; // http://127.0.0.1:8787

const $ = (id) => document.getElementById(id);

function showStatus(msg, type = 'info') {
  const box = $('status-box');
  box.innerHTML = msg;
  box.className = `status-box show ${type}`;
}

function hideLoading() {
  $('loading').style.display = 'none';
}

/** Map Stellar network passphrase → Freighter network label */
function passphraseToNetwork(passphrase) {
  const map = {
    'Test SDF Network ; September 2015': 'TESTNET',
    'Public Global Stellar Network ; September 2015': 'PUBLIC',
    'Test SDF Future Network ; October 2022': 'FUTURENET',
  };
  return map[passphrase] ?? 'TESTNET';
}

async function bridgeFetch(path, opts = {}) {
  const r = await fetch(`${BRIDGE_ORIGIN}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  return r.json();
}

// ── connect-only mode ────────────────────────────────────────────────────────

async function runConnectMode(playerId) {
  hideLoading();
  $('panel-connect').style.display = 'block';

  $('btn-connect').addEventListener('click', async () => {
    $('btn-connect').disabled = true;
    showStatus('<span class="spinner"></span> Connecting to Freighter…', 'waiting');

    try {
      const connResult = await isConnected();
      if (!connResult.isConnected) {
        showStatus(
          'Freighter extension not detected. Please install it from ' +
          '<a href="https://www.freighter.app" target="_blank" style="color:#a5b4fc">freighter.app</a>.',
          'error'
        );
        $('btn-connect').disabled = false;
        return;
      }

      const accessResult = await requestAccess();
      if (accessResult.error) {
        showStatus(`Freighter error: ${accessResult.error}`, 'error');
        $('btn-connect').disabled = false;
        return;
      }

      const address = accessResult.address;

      // Tell bridge about the connected wallet
      await bridgeFetch('/wallet/session/update', {
        method: 'POST',
        body: JSON.stringify({ playerId, address, network: 'TESTNET' }),
      });

      showStatus(
        '✓ Wallet connected!<br><span class="address-chip">' + address + '</span><br>' +
        '<span style="color:#6b7280;font-size:12px;margin-top:8px;display:block">You can close this tab. Return to the game.</span>',
        'success'
      );
    } catch (err) {
      showStatus(`Unexpected error: ${err.message}`, 'error');
      $('btn-connect').disabled = false;
    }
  });
}

// ── sign-request mode ────────────────────────────────────────────────────────

async function runSignMode(requestId) {
  // Fetch the pending request from the bridge
  let data;
  try {
    data = await bridgeFetch(`/tx/request/${requestId}`);
  } catch (err) {
    hideLoading();
    showStatus(`Could not load request: ${err.message}`, 'error');
    return;
  }

  if (!data.ok) {
    hideLoading();
    showStatus(`Request not found (${requestId}). It may have expired.`, 'error');
    return;
  }

  const req = data.request;

  if (req.status !== 'pending') {
    hideLoading();
    const label = req.status === 'signed' ? '✓ Already signed.' :
                  req.status === 'rejected' ? '✗ Already rejected.' :
                  `Status: ${req.status}`;
    showStatus(label, req.status === 'signed' ? 'success' : 'error');
    return;
  }

  // Render details
  hideLoading();
  $('panel-sign').style.display = 'block';

  const network = passphraseToNetwork(req.networkPassphrase);
  const metaEntries = Object.entries(req.metadata || {});

  $('req-details').innerHTML = `
    <div class="info-row">
      <span class="info-label">Action</span>
      <span class="info-value" style="color:#7c85ff;font-weight:600">${req.action}</span>
    </div>
    <div class="info-row">
      <span class="info-label">Network</span>
      <span class="info-value">${network}</span>
    </div>
    <div class="info-row">
      <span class="info-label">Player</span>
      <span class="info-value">${req.playerId}</span>
    </div>
    ${metaEntries.map(([k, v]) => `
      <div class="info-row">
        <span class="info-label">${k}</span>
        <span class="info-value">${JSON.stringify(v)}</span>
      </div>
    `).join('')}
  `;

  $('xdr-preview').textContent = req.xdr;

  // Reject button
  $('btn-reject').addEventListener('click', async () => {
    $('btn-reject').disabled = true;
    $('btn-sign').disabled = true;
    try {
      await bridgeFetch(`/tx/request/${requestId}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'user_rejected' }),
      });
      showStatus('✗ Transaction rejected. You can close this tab.', 'error');
    } catch (err) {
      showStatus(`Error: ${err.message}`, 'error');
      $('btn-reject').disabled = false;
      $('btn-sign').disabled = false;
    }
  });

  // Sign button
  $('btn-sign').addEventListener('click', async () => {
    $('btn-sign').disabled = true;
    $('btn-reject').disabled = true;
    showStatus('<span class="spinner"></span> Waiting for Freighter confirmation…', 'waiting');

    try {
      // 1. Check extension present
      const connResult = await isConnected();
      if (!connResult.isConnected) {
        showStatus(
          'Freighter extension not detected. Install from ' +
          '<a href="https://www.freighter.app" target="_blank" style="color:#a5b4fc">freighter.app</a>.',
          'error'
        );
        $('btn-sign').disabled = false;
        $('btn-reject').disabled = false;
        return;
      }

      // 2. Get/confirm wallet address
      const accessResult = await requestAccess();
      if (accessResult.error) {
        showStatus(`Freighter access error: ${accessResult.error}`, 'error');
        $('btn-sign').disabled = false;
        $('btn-reject').disabled = false;
        return;
      }

      const walletAddress = accessResult.address;

      // 3. Sign the XDR
      const signResult = await signTransaction(req.xdr, {
        network,
        address: walletAddress,
      });

      if (signResult.error) {
        showStatus(`Signing error: ${signResult.error}`, 'error');
        $('btn-sign').disabled = false;
        $('btn-reject').disabled = false;
        return;
      }

      const signedXdr = signResult.signedTxXdr;

      // 4. Persist session
      await bridgeFetch('/wallet/session/update', {
        method: 'POST',
        body: JSON.stringify({ playerId: req.playerId, address: walletAddress, network }),
      });

      // 5. Mark request complete
      await bridgeFetch(`/tx/request/${requestId}/complete`, {
        method: 'POST',
        body: JSON.stringify({ signedXdr, walletAddress }),
      });

      showStatus(
        '✓ Transaction signed!<br>' +
        '<span class="address-chip">' + walletAddress + '</span><br>' +
        '<span style="color:#6b7280;font-size:12px;margin-top:8px;display:block">' +
        'Return to the game — it will continue automatically.</span>',
        'success'
      );
    } catch (err) {
      showStatus(`Unexpected error: ${err.message}`, 'error');
      $('btn-sign').disabled = false;
      $('btn-reject').disabled = false;
    }
  });
}

// ── entry point ──────────────────────────────────────────────────────────────

(async () => {
  const params = new URLSearchParams(window.location.search);
  const action = params.get('action');
  const requestId = params.get('requestId');
  const playerId = params.get('playerId') || '__default__';

  if (action === 'connect') {
    await runConnectMode(playerId);
  } else if (requestId) {
    await runSignMode(requestId);
  } else {
    hideLoading();
    showStatus(
      'This page is opened automatically by the game. ' +
      'No pending request found in the URL.',
      'info'
    );
  }
})();
