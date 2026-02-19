#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../wallet_bridge"
npm install
npm start
