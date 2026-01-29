#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cid=$(docker compose ps -q rtmp)
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
  if ! ss -ltn | grep -q ":1935"; then
    echo "Port 1935 is not listening on the host."
    exit 1
  fi
else
  echo "Warning: 'ss' not found; skipping host port check."
fi

echo "Waiting for HLS playlist to be available..."

ok=0
for _ in {1..30}; do
  if curl -sf http://127.0.0.1:8080/hls/stream.m3u8 >/dev/null; then
    ok=1
    break
  fi
  sleep 2
  echo "...still waiting"
done

if [[ "$ok" -eq 1 ]]; then
  echo "HLS playlist is available."
  exit 0
fi

echo "HLS playlist not found. Ensure ingest has started."
exit 1
