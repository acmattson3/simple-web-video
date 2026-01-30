#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cid=$(docker compose ps -q mediamtx)
if [[ -z "${cid}" ]]; then
  echo "Container not found. Is it running?"
  exit 1
fi

running=$(docker inspect -f '{{.State.Running}}' "$cid")
if [[ "${running}" != "true" ]]; then
  echo "Container is not running."
  exit 1
fi

echo "Container is running."

if command -v ss >/dev/null 2>&1; then
  if ! ss -ltn | grep -q ":8554"; then
    echo "Port 8554 is not listening on the host."
    exit 1
  fi
  if ! ss -ltn | grep -q ":8889"; then
    echo "Port 8889 is not listening on the host."
    exit 1
  fi
  if ! ss -lun | grep -q ":8189"; then
    echo "UDP port 8189 is not listening on the host."
    exit 1
  fi
else
  echo "Warning: 'ss' not found; skipping host port check."
fi

echo "WebRTC endpoint is up. Stream availability depends on an active publisher."
